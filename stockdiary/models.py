# stockdiary/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.urls import reverse
from django.db.models import Sum, F, Q, Count
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
import os
import uuid
from PIL import Image
import io
from tags.models import Tag


def get_diary_image_path(instance, filename):
    """日記画像のアップロードパスを生成"""
    ext = filename.split('.')[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    return f"diary_images/{instance.user.id}/{filename}"


def get_note_image_path(instance, filename):
    """継続記録画像のアップロードパスを生成"""
    ext = filename.split('.')[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    return f"note_images/{instance.diary.user.id}/{filename}"


class StockDiary(models.Model):
    """株式投資日記（基本情報のみ）"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stock_symbol = models.CharField(max_length=50, blank=True, db_index=True, verbose_name='銘柄コード')
    stock_name = models.CharField(max_length=100, verbose_name='銘柄名')
    reason = models.TextField(verbose_name='投資理由', blank=True, max_length=5000)
    tags = models.ManyToManyField(Tag, blank=True)
    memo = models.TextField(blank=True, max_length=1000, verbose_name='メモ')
    sector = models.CharField(max_length=50, blank=True, verbose_name='業種')
    image = models.ImageField(upload_to=get_diary_image_path, null=True, blank=True, help_text="日記に関連する画像")
    
    # 集計フィールド（自動計算）
    current_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='現在保有数')
    average_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='平均取得単価')
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='総取得原価')
    realized_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='実現損益')
    
    # 取引統計
    total_bought_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='累計購入数')
    total_sold_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='累計売却数')
    total_buy_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='累計購入額')
    total_sell_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='累計売却額')
    transaction_count = models.IntegerField(default=0, verbose_name='取引回数')
    
    # 日付情報
    first_purchase_date = models.DateField(null=True, blank=True, db_index=True, verbose_name='最初の購入日')
    last_transaction_date = models.DateField(null=True, blank=True, verbose_name='最後の取引日')
    
    # システム情報
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'first_purchase_date']),
            models.Index(fields=['user', 'stock_symbol']),
            models.Index(fields=['user', 'current_quantity']),
        ]
        verbose_name = '株式日記'
        verbose_name_plural = '株式日記'
    
    def __str__(self):
        return f"{self.stock_name} ({self.stock_symbol})"

    @property
    def is_memo(self):
        """メモ記録かどうか（取引がない場合）"""
        return self.transaction_count == 0

    @property
    def is_holding(self):
        """保有中かどうか（プラス保有）"""
        return self.current_quantity > 0

    @property
    def is_sold_out(self):
        """売却済みかどうか（取引はあるが保有数ゼロ）"""
        return self.transaction_count > 0 and self.current_quantity == 0

    # ✅ 追加: 信用売り（ショート）かどうか
    @property
    def is_short(self):
        """信用売り（ショートポジション）かどうか"""
        return self.current_quantity < 0

    def update_aggregates(self):
        """集計フィールドを再計算"""
        transactions = self.transactions.all().order_by('transaction_date', 'created_at')
        
        # 初期化
        self.current_quantity = Decimal('0')
        self.total_cost = Decimal('0')
        self.realized_profit = Decimal('0')
        self.total_bought_quantity = Decimal('0')
        self.total_sold_quantity = Decimal('0')
        self.total_buy_amount = Decimal('0')
        self.total_sell_amount = Decimal('0')
        self.transaction_count = 0
        self.first_purchase_date = None
        self.last_transaction_date = None
        self.average_purchase_price = None
        
        # デバッグ用のログ
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"\n{'='*60}")
        logger.info(f"集計開始: {self.stock_name} ({self.stock_symbol})")
        logger.info(f"取引数: {transactions.count()}")
        
        for idx, transaction in enumerate(transactions, 1):
            # 分割調整を適用
            adjusted_quantity = transaction.quantity
            adjusted_price = transaction.price
            
            # 処理前の状態をログ
            before_qty = self.current_quantity
            
            if transaction.transaction_type == 'buy':
                # 購入処理
                buy_amount = adjusted_price * adjusted_quantity
                
                # ✅ マイナス保有（信用売り）からの返済買いの場合
                if self.current_quantity < 0:
                    # 信用売りの返済買い
                    returned_quantity = min(adjusted_quantity, abs(self.current_quantity))
                    
                    # 返済分の損益計算（売却時の単価で計算）
                    if self.total_cost < 0:
                        avg_sell_price = abs(self.total_cost) / abs(self.current_quantity)
                        returned_cost = avg_sell_price * returned_quantity
                        buy_cost = adjusted_price * returned_quantity
                        profit = returned_cost - buy_cost
                        self.realized_profit += profit
                        
                        logger.info(
                            f"{idx}. {transaction.transaction_date} 返済買い "
                            f"{returned_quantity}株 @ {adjusted_price}円 "
                            f"(平均売却単価: {avg_sell_price:.2f}円) "
                            f"損益: {profit:+,.2f}円"
                        )
                    
                    # 保有数を戻す
                    self.current_quantity += returned_quantity
                    self.total_cost += avg_sell_price * returned_quantity if self.total_cost < 0 else 0
                    
                    # 残りの購入分（通常の購入）
                    remaining_quantity = adjusted_quantity - returned_quantity
                    if remaining_quantity > 0:
                        remaining_amount = adjusted_price * remaining_quantity
                        self.total_cost += remaining_amount
                        self.current_quantity += remaining_quantity
                else:
                    # 通常の購入
                    self.total_cost += buy_amount
                    self.current_quantity += adjusted_quantity
                
                self.total_bought_quantity += adjusted_quantity
                self.total_buy_amount += buy_amount
                
                logger.info(
                    f"{idx}. {transaction.transaction_date} 購入 "
                    f"{adjusted_quantity}株 @ {adjusted_price}円 "
                    f"→ 保有: {before_qty} → {self.current_quantity}"
                )
                
                # 最初の購入日を記録
                if self.first_purchase_date is None:
                    self.first_purchase_date = transaction.transaction_date
                
            elif transaction.transaction_type == 'sell':
                # 売却処理
                sell_amount = adjusted_price * adjusted_quantity
                
                # ✅ プラス保有（現物・信用買い）の売却
                if self.current_quantity > 0:
                    # 平均取得単価を計算
                    avg_price = self.total_cost / self.current_quantity
                    
                    # 売却する数量（保有数を超えないように）
                    sold_quantity = min(adjusted_quantity, self.current_quantity)
                    
                    # 売却原価と売却代金
                    sell_cost = avg_price * sold_quantity
                    actual_sell_amount = adjusted_price * sold_quantity
                    
                    # 実現損益を計算
                    profit = actual_sell_amount - sell_cost
                    self.realized_profit += profit
                    
                    # 総原価と保有数を減少
                    self.total_cost -= sell_cost
                    self.current_quantity -= sold_quantity
                    
                    logger.info(
                        f"{idx}. {transaction.transaction_date} 売却 "
                        f"{sold_quantity}株 @ {adjusted_price}円 "
                        f"(平均単価: {avg_price:.2f}円) "
                        f"→ 保有: {before_qty} → {self.current_quantity} "
                        f"損益: {profit:+,.2f}円"
                    )
                    
                    # 残りの売却分（信用売り）
                    remaining_quantity = adjusted_quantity - sold_quantity
                    if remaining_quantity > 0:
                        # 信用売り（ショート）
                        self.current_quantity -= remaining_quantity
                        self.total_cost -= adjusted_price * remaining_quantity
                        
                        logger.info(
                            f"    ↳ 信用売り {remaining_quantity}株 "
                            f"→ 保有: {self.current_quantity}"
                        )
                
                # ✅ ゼロまたはマイナス保有からの売却（信用売り）
                else:
                    # 信用売り（空売り）
                    self.current_quantity -= adjusted_quantity
                    self.total_cost -= sell_amount
                    
                    logger.info(
                        f"{idx}. {transaction.transaction_date} 信用売り "
                        f"{adjusted_quantity}株 @ {adjusted_price}円 "
                        f"→ 保有: {before_qty} → {self.current_quantity}"
                    )
                
                self.total_sold_quantity += adjusted_quantity
                self.total_sell_amount += sell_amount
            
            self.transaction_count += 1
            self.last_transaction_date = transaction.transaction_date
        
        # 平均取得単価を計算
        if self.current_quantity > 0 and self.total_cost > 0:
            self.average_purchase_price = (self.total_cost / self.current_quantity).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        elif self.current_quantity < 0 and self.total_cost < 0:
            # マイナス保有（信用売り）の場合の平均売却単価
            self.average_purchase_price = (abs(self.total_cost) / abs(self.current_quantity)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        
        # 数値の丸め処理
        self.current_quantity = self.current_quantity.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.total_cost = self.total_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.realized_profit = self.realized_profit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        logger.info(f"集計完了: 保有数={self.current_quantity}, "
                    f"購入計={self.total_bought_quantity}, "
                    f"売却計={self.total_sold_quantity}, "
                    f"実現損益={self.realized_profit}")
        logger.info(f"{'='*60}\n")
        
        self.save()    
    def process_and_save_image(self, image_file):
        """画像を圧縮・処理して保存"""
        try:
            if self.image:
                self.delete_image()
            
            img = Image.open(image_file)
            
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            max_width, max_height = 800, 600
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            
            try:
                img.save(output, format='WebP', quality=85, optimize=True)
                format_used = 'webp'
            except Exception:
                img.save(output, format='JPEG', quality=85, optimize=True)
                format_used = 'jpg'
            
            filename = f"{uuid.uuid4().hex}.{format_used}"
            content_file = ContentFile(output.getvalue())
            
            self.image.save(filename, content_file, save=False)
            self.save(update_fields=['image'])
            
            return True
            
        except Exception as e:
            print(f"Image processing failed: {str(e)}")
            return False

    def delete_image(self):
        """画像を削除"""
        try:
            if self.image:
                self.image.delete(save=False)
                self.image = None
                self.save(update_fields=['image'])
                return True
        except Exception as e:
            print(f"Image deletion failed: {str(e)}")
        return False

    def get_image_url(self):
        """画像URLを取得"""
        if self.image:
            return reverse('stockdiary:serve_image', kwargs={
                'diary_id': self.id,
                'image_type': 'diary'
            })
        return None

    def calculate_cash_only_stats(self):
        """現物取引（is_margin=False）のみの統計を計算"""
        from decimal import Decimal, ROUND_HALF_UP
        
        cash_transactions = self.transactions.filter(is_margin=False).order_by('transaction_date', 'created_at')
        
        cash_quantity = Decimal('0')
        cash_cost = Decimal('0')
        cash_realized_profit = Decimal('0')
        cash_bought_quantity = Decimal('0')
        cash_sold_quantity = Decimal('0')
        cash_buy_amount = Decimal('0')
        cash_sell_amount = Decimal('0')
        
        for transaction in cash_transactions:
            # 分割調整を適用
            adjusted_quantity = transaction.quantity
            adjusted_price = transaction.price
                        
            if transaction.transaction_type == 'buy':
                # 購入処理
                buy_amount = adjusted_price * adjusted_quantity
                cash_cost += buy_amount
                cash_quantity += adjusted_quantity
                cash_bought_quantity += adjusted_quantity
                cash_buy_amount += buy_amount
                
            elif transaction.transaction_type == 'sell':
                # 売却処理
                if cash_quantity > 0:
                    avg_price = cash_cost / cash_quantity
                    sell_quantity = min(adjusted_quantity, cash_quantity)
                    sell_cost = avg_price * sell_quantity
                    actual_sell_amount = adjusted_price * sell_quantity
                    profit = actual_sell_amount - sell_cost
                    cash_realized_profit += profit
                    cash_cost -= sell_cost
                    cash_quantity -= sell_quantity
                    cash_sold_quantity += adjusted_quantity
                    cash_sell_amount += adjusted_price * adjusted_quantity
        
        # 平均取得単価を計算
        cash_avg_price = None
        if cash_quantity > 0:
            cash_avg_price = (cash_cost / cash_quantity).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        
        # 数値の丸め処理
        cash_quantity = cash_quantity.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        cash_cost = cash_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        cash_realized_profit = cash_realized_profit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return {
            'current_quantity': cash_quantity,
            'average_purchase_price': cash_avg_price,
            'total_cost': cash_cost,
            'realized_profit': cash_realized_profit,
            'total_bought_quantity': cash_bought_quantity,
            'total_sold_quantity': cash_sold_quantity,
            'total_buy_amount': cash_buy_amount,
            'total_sell_amount': cash_sell_amount,
        }
        
    @property
    def image_url(self):
        return self.get_image_url()


class Transaction(models.Model):
    """取引記録"""
    TRANSACTION_TYPES = [
        ('buy', '購入'),
        ('sell', '売却'),
    ]
    
    diary = models.ForeignKey(StockDiary, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, verbose_name='取引種別')
    transaction_date = models.DateField(verbose_name='取引日', db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='単価')
    quantity = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='数量')
    memo = models.TextField(blank=True, max_length=500, verbose_name='メモ')
    is_margin = models.BooleanField(default=False, verbose_name='信用取引')
    
    # 取引時点の状態（参照用）
    quantity_after = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='取引後保有数')
    average_price_after = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='取引後平均単価')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['diary', 'transaction_date']),
        ]
        verbose_name = '取引'
        verbose_name_plural = '取引'

    def __str__(self):
        type_display = self.get_transaction_type_display()
        return f"{self.diary.stock_name} - {type_display} {self.quantity}株 @ {self.price}円"

    def clean(self):
        """バリデーション"""
        super().clean()
        
        # 価格と数量は正の数
        if self.price is not None and self.price <= 0:
            raise ValidationError({'price': '価格は正の数を入力してください'})
        
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({'quantity': '数量は正の数を入力してください'})

    def save(self, *args, **kwargs):
        # フルクリーンはスキップ（views.py で呼び出す）
        super().save(*args, **kwargs)
        # 保存後に日記の集計を更新
        if self.diary_id:
            self.diary.update_aggregates()

    def delete(self, *args, **kwargs):
        diary = self.diary
        super().delete(*args, **kwargs)
        # 削除後に日記の集計を更新
        diary.update_aggregates()

    @property
    def amount(self):
        """取引金額"""
        return self.price * self.quantity
        

class StockSplit(models.Model):
    """株式分割記録"""
    diary = models.ForeignKey(StockDiary, on_delete=models.CASCADE, related_name='stock_splits')
    split_date = models.DateField(verbose_name='分割実行日', db_index=True)
    split_ratio = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='分割比率')
    memo = models.TextField(blank=True, max_length=500, verbose_name='メモ')
    is_applied = models.BooleanField(default=False, verbose_name='適用済み')
    applied_at = models.DateTimeField(null=True, blank=True, verbose_name='適用日時')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-split_date']
        indexes = [
            models.Index(fields=['diary', 'split_date']),
        ]
        verbose_name = '株式分割'
        verbose_name_plural = '株式分割'

    def __str__(self):
        return f"{self.diary.stock_name} - {self.split_date} ({self.split_ratio}倍)"

    def clean(self):
        """バリデーション"""
        super().clean()
        
        if self.split_ratio <= 0:
            raise ValidationError({'split_ratio': '分割比率は正の数を入力してください'})
        
        # 適用済みの場合は削除・編集不可
        if self.is_applied and self.pk:
            old_split = StockSplit.objects.get(pk=self.pk)
            if old_split.is_applied:
                raise ValidationError('適用済みの分割情報は編集できません')

    def apply_split(self):
        # 対象取引（分割日より前）
        transactions = self.diary.transactions.filter(
            transaction_date__lt=self.split_date
        )

        for tx in transactions:
            tx.quantity = tx.quantity * self.split_ratio
            tx.price = tx.price / self.split_ratio
            tx.save(update_fields=["quantity", "price"])

        # フラグ更新
        self.is_applied = True
        self.applied_at = timezone.now()
        self.save(update_fields=["is_applied", "applied_at"])

        # 再集計
        self.diary.update_aggregates()


class DiaryNote(models.Model):
    """日記への継続的な追記"""
    diary = models.ForeignKey(StockDiary, on_delete=models.CASCADE, related_name='notes')
    date = models.DateField()
    content = models.TextField(verbose_name='記録内容', blank=True, max_length=1000)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                       verbose_name='記録時点の価格')
    
    image = models.ImageField(upload_to=get_note_image_path, null=True, blank=True, help_text="継続記録に関連する画像")
    
    TYPE_CHOICES = [
        ('analysis', '分析更新'),
        ('news', 'ニュース'),
        ('earnings', '決算情報'),
        ('insight', '新たな気づき'),
        ('risk', 'リスク要因'),
        ('other', 'その他')
    ]
    note_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='analysis')
    
    IMPORTANCE_CHOICES = [
        ('high', '高'),
        ('medium', '中'),
        ('low', '低')
    ]
    importance = models.CharField(max_length=10, choices=IMPORTANCE_CHOICES, default='medium')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = '継続記録'
        verbose_name_plural = '継続記録'
    
    def __str__(self):
        return f"{self.diary.stock_name} - {self.date}"
    
    def clean(self):
        super().clean()
        if self.content and len(self.content) > 1000:
            raise ValidationError({'content': '記録内容は1000文字以内で入力してください'})
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
        # 親日記のupdated_atを更新
        self.diary.updated_at = timezone.now()
        self.diary.save(update_fields=['updated_at'])

    def process_and_save_image(self, image_file):
        """画像を圧縮・処理して保存"""
        try:
            if self.image:
                self.delete_image()
            
            img = Image.open(image_file)
            
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            max_width, max_height = 600, 400
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            
            try:
                img.save(output, format='WebP', quality=80, optimize=True)
                format_used = 'webp'
            except Exception:
                img.save(output, format='JPEG', quality=80, optimize=True)
                format_used = 'jpg'
            
            filename = f"{uuid.uuid4().hex}.{format_used}"
            content_file = ContentFile(output.getvalue())
            
            self.image.save(filename, content_file, save=False)
            self.save(update_fields=['image'])
            
            return True
            
        except Exception as e:
            print(f"Note image processing failed: {str(e)}")
            return False

    def delete_image(self):
        """画像を削除"""
        try:
            if self.image:
                self.image.delete(save=False)
                self.image = None
                self.save(update_fields=['image'])
                return True
        except Exception as e:
            print(f"Note image deletion failed: {str(e)}")
        return False

    def get_image_url(self):
        """画像URLを取得"""
        if self.image:
            return reverse('stockdiary:serve_image', kwargs={
                'diary_id': self.diary.id,
                'image_type': 'note',
                'note_id': self.id
            })
        return None

    @property
    def image_url(self):
        return self.get_image_url()
    
    def get_price_change(self):
        """購入価格からの変動率を計算"""
        if self.current_price and self.diary.average_purchase_price:
            change = ((self.current_price - self.diary.average_purchase_price) / self.diary.average_purchase_price) * 100
            return change
        return None

class PushSubscription(models.Model):
    """PWAのプッシュ通知サブスクリプション"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='push_subscriptions'
    )
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    device_name = models.CharField(max_length=100, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'プッシュ通知サブスクリプション'
        verbose_name_plural = 'プッシュ通知サブスクリプション'
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.device_name or "Unknown Device"}'


class DiaryNotification(models.Model):
    """日記の通知設定（リマインダーのみ）"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    diary = models.ForeignKey(
        'StockDiary',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    remind_at = models.DateTimeField(verbose_name='通知日時')
    message = models.TextField(max_length=200, blank=True, verbose_name='メッセージ')
    is_active = models.BooleanField(default=True, verbose_name='有効')
    last_sent = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = '日記通知設定'
        verbose_name_plural = '日記通知設定'
        indexes = [
            models.Index(fields=['diary', 'is_active']),
        ]


class NotificationLog(models.Model):
    """通知送信履歴"""
    notification = models.ForeignKey(
        'DiaryNotification',
        on_delete=models.CASCADE,
        related_name='logs',
        null=True, blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_logs'
    )
    title = models.CharField(max_length=100)
    message = models.TextField(max_length=500)
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    is_clicked = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = '通知履歴'
        verbose_name_plural = '通知履歴'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-sent_at']),
        ]        