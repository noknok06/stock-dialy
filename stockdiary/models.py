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
    reason = models.TextField(verbose_name='投資理由', blank=True, max_length=1000)
    checklist = models.ManyToManyField('checklist.Checklist', blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    memo = models.TextField(blank=True, max_length=1000, verbose_name='メモ')
    sector = models.CharField(max_length=50, blank=True, verbose_name='業種')
    image = models.ImageField(upload_to=get_diary_image_path, null=True, blank=True)
    
    # 🔧 現物取引の集計フィールド
    current_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='現物保有数')
    average_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='現物平均単価')
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='現物総原価')
    realized_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='現物実現損益')
    
    # 🆕 信用取引の集計フィールド
    margin_current_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='信用保有数')
    margin_average_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='信用平均単価')
    margin_total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='信用総原価')
    margin_realized_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='信用実現損益')
    
    # 取引統計（現物+信用の合計）
    total_bought_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='累計購入数')
    total_sold_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='累計売却数')
    total_buy_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='累計購入額')
    total_sell_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='累計売却額')
    transaction_count = models.IntegerField(default=0, verbose_name='取引回数')
    
    # 🆕 取引区分別の統計
    cash_transaction_count = models.IntegerField(default=0, verbose_name='現物取引回数')
    margin_transaction_count = models.IntegerField(default=0, verbose_name='信用取引回数')
    
    # 日付情報
    first_purchase_date = models.DateField(null=True, blank=True, db_index=True, verbose_name='最初の購入日')
    last_transaction_date = models.DateField(null=True, blank=True, verbose_name='最後の取引日')
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'first_purchase_date']),
            models.Index(fields=['user', 'stock_symbol']),
            models.Index(fields=['user', 'current_quantity']),
            models.Index(fields=['user', 'margin_current_quantity']),  # 🆕
        ]
        verbose_name = '株式日記'
        verbose_name_plural = '株式日記'

    # 🆕 合計保有数（現物+信用）
    @property
    def total_quantity(self):
        """現物と信用の合計保有数"""
        return self.current_quantity + self.margin_current_quantity

    # 🆕 合計実現損益（現物+信用）
    @property
    def total_realized_profit(self):
        """現物と信用の合計実現損益"""
        return self.realized_profit + self.margin_realized_profit

    # 🔧 保有中かどうかの判定を修正
    @property
    def is_holding(self):
        """保有中かどうか（現物または信用でプラス保有）"""
        return self.current_quantity > 0 or self.margin_current_quantity > 0

    # 🔧 売却済みかどうかの判定を修正
    @property
    def is_sold_out(self):
        """売却済みかどうか（取引はあるが現物・信用ともに保有数ゼロ）"""
        return (self.transaction_count > 0 and 
                self.current_quantity == 0 and 
                self.margin_current_quantity == 0)

    def update_aggregates(self):
        """集計フィールドを再計算（現物・信用を分けて処理）"""
        transactions = self.transactions.all().order_by('transaction_date', 'created_at')
        
        # 初期化
        self.current_quantity = Decimal('0')
        self.total_cost = Decimal('0')
        self.realized_profit = Decimal('0')
        
        self.margin_current_quantity = Decimal('0')
        self.margin_total_cost = Decimal('0')
        self.margin_realized_profit = Decimal('0')
        
        self.total_bought_quantity = Decimal('0')
        self.total_sold_quantity = Decimal('0')
        self.total_buy_amount = Decimal('0')
        self.total_sell_amount = Decimal('0')
        self.transaction_count = 0
        self.cash_transaction_count = 0
        self.margin_transaction_count = 0
        
        self.first_purchase_date = None
        self.last_transaction_date = None
        self.average_purchase_price = None
        self.margin_average_price = None
        
        # 株式分割の適用
        splits = self.stock_splits.filter(is_applied=True).order_by('split_date')
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"\n{'='*60}")
        logger.info(f"集計開始: {self.stock_name} ({self.stock_symbol})")
        
        for idx, transaction in enumerate(transactions, 1):
            # 分割調整を適用
            adjusted_quantity = transaction.quantity
            adjusted_price = transaction.price
            
            for split in splits:
                if transaction.transaction_date < split.split_date:
                    adjusted_quantity = adjusted_quantity * split.split_ratio
                    adjusted_price = adjusted_price / split.split_ratio
            
            # 🆕 現物・信用で処理を分岐
            is_cash = transaction.trade_type == Transaction.TradeType.CASH
            
            if is_cash:
                # 現物取引の処理
                if transaction.transaction_type == 'buy':
                    buy_amount = adjusted_price * adjusted_quantity
                    self.total_cost += buy_amount
                    self.current_quantity += adjusted_quantity
                    self.total_bought_quantity += adjusted_quantity
                    self.total_buy_amount += buy_amount
                    
                    if self.first_purchase_date is None:
                        self.first_purchase_date = transaction.transaction_date
                    
                    logger.info(f"{idx}. [現物] 購入 {adjusted_quantity}株 @ {adjusted_price}円")
                
                elif transaction.transaction_type == 'sell':
                    if self.current_quantity > 0:
                        avg_price = self.total_cost / self.current_quantity
                        sold_quantity = min(adjusted_quantity, self.current_quantity)
                        sell_cost = avg_price * sold_quantity
                        actual_sell_amount = adjusted_price * sold_quantity
                        profit = actual_sell_amount - sell_cost
                        
                        self.realized_profit += profit
                        self.total_cost -= sell_cost
                        self.current_quantity -= sold_quantity
                        
                        logger.info(f"{idx}. [現物] 売却 {sold_quantity}株 損益: {profit:+,.2f}円")
                    
                    self.total_sold_quantity += adjusted_quantity
                    self.total_sell_amount += adjusted_price * adjusted_quantity
                
                self.cash_transaction_count += 1
            
            else:
                # 信用取引の処理
                if transaction.transaction_type == 'buy':
                    buy_amount = adjusted_price * adjusted_quantity
                    
                    # 信用売りの返済買いかどうか
                    if self.margin_current_quantity < 0:
                        returned_quantity = min(adjusted_quantity, abs(self.margin_current_quantity))
                        
                        if self.margin_total_cost < 0:
                            avg_sell_price = abs(self.margin_total_cost) / abs(self.margin_current_quantity)
                            returned_cost = avg_sell_price * returned_quantity
                            buy_cost = adjusted_price * returned_quantity
                            profit = returned_cost - buy_cost
                            self.margin_realized_profit += profit
                            
                            logger.info(f"{idx}. [信用] 返済買い {returned_quantity}株 損益: {profit:+,.2f}円")
                        
                        self.margin_current_quantity += returned_quantity
                        
                        # 残りの購入分
                        remaining_quantity = adjusted_quantity - returned_quantity
                        if remaining_quantity > 0:
                            remaining_amount = adjusted_price * remaining_quantity
                            self.margin_total_cost += remaining_amount
                            self.margin_current_quantity += remaining_quantity
                    else:
                        # 通常の信用買い
                        self.margin_total_cost += buy_amount
                        self.margin_current_quantity += adjusted_quantity
                    
                    self.total_bought_quantity += adjusted_quantity
                    self.total_buy_amount += buy_amount
                    logger.info(f"{idx}. [信用] 購入 {adjusted_quantity}株 @ {adjusted_price}円")
                
                elif transaction.transaction_type == 'sell':
                    sell_amount = adjusted_price * adjusted_quantity
                    
                    # 信用買いの売却かどうか
                    if self.margin_current_quantity > 0:
                        avg_price = self.margin_total_cost / self.margin_current_quantity
                        sold_quantity = min(adjusted_quantity, self.margin_current_quantity)
                        sell_cost = avg_price * sold_quantity
                        actual_sell_amount = adjusted_price * sold_quantity
                        profit = actual_sell_amount - sell_cost
                        
                        self.margin_realized_profit += profit
                        self.margin_total_cost -= sell_cost
                        self.margin_current_quantity -= sold_quantity
                        
                        logger.info(f"{idx}. [信用] 売却 {sold_quantity}株 損益: {profit:+,.2f}円")
                        
                        # 残りの売却分（信用売り）
                        remaining_quantity = adjusted_quantity - sold_quantity
                        if remaining_quantity > 0:
                            self.margin_current_quantity -= remaining_quantity
                            self.margin_total_cost -= adjusted_price * remaining_quantity
                    else:
                        # 信用売り（空売り）
                        self.margin_current_quantity -= adjusted_quantity
                        self.margin_total_cost -= sell_amount
                        logger.info(f"{idx}. [信用] 空売り {adjusted_quantity}株 @ {adjusted_price}円")
                    
                    self.total_sold_quantity += adjusted_quantity
                    self.total_sell_amount += sell_amount
                
                self.margin_transaction_count += 1
            
            self.transaction_count += 1
            self.last_transaction_date = transaction.transaction_date
        
        # 平均取得単価を計算
        if self.current_quantity > 0 and self.total_cost > 0:
            self.average_purchase_price = (self.total_cost / self.current_quantity).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        
        if self.margin_current_quantity > 0 and self.margin_total_cost > 0:
            self.margin_average_price = (self.margin_total_cost / self.margin_current_quantity).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        elif self.margin_current_quantity < 0 and self.margin_total_cost < 0:
            self.margin_average_price = (abs(self.margin_total_cost) / abs(self.margin_current_quantity)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        
        # 数値の丸め処理
        self.current_quantity = self.current_quantity.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.margin_current_quantity = self.margin_current_quantity.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.total_cost = self.total_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.margin_total_cost = self.margin_total_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.realized_profit = self.realized_profit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.margin_realized_profit = self.margin_realized_profit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        logger.info(f"現物: 保有数={self.current_quantity}, 実現損益={self.realized_profit}")
        logger.info(f"信用: 保有数={self.margin_current_quantity}, 実現損益={self.margin_realized_profit}")
        logger.info(f"{'='*60}\n")
        
        self.save()


class Transaction(models.Model):
    """取引記録"""
    TRANSACTION_TYPES = [
        ('buy', '購入'),
        ('sell', '売却'),
    ]
    
    # 🆕 現物・信用の区別
    class TradeType(models.TextChoices):
        CASH = "cash", "現物"
        MARGIN = "margin", "信用"
    
    diary = models.ForeignKey(StockDiary, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, verbose_name='取引種別')
    
    # 🆕 現物/信用の区別（デフォルトは現物）
    trade_type = models.CharField(
        max_length=10, 
        choices=TradeType.choices, 
        default=TradeType.CASH,
        verbose_name='取引区分'
    )
    
    transaction_date = models.DateField(verbose_name='取引日', db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='単価')
    quantity = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='数量')
    memo = models.TextField(blank=True, max_length=500, verbose_name='メモ')
    
    # 取引時点の状態（参照用）
    quantity_after = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='取引後保有数')
    average_price_after = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='取引後平均単価')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['diary', 'transaction_date']),
            models.Index(fields=['diary', 'trade_type']),  # 🆕 信用取引検索用
        ]
        verbose_name = '取引'
        verbose_name_plural = '取引'

    def __str__(self):
        type_display = self.get_transaction_type_display()
        trade_type_display = self.get_trade_type_display()
        return f"{self.diary.stock_name} - [{trade_type_display}] {type_display} {self.quantity}株 @ {self.price}円"

    # 🆕 現物取引かどうかを判定
    @property
    def is_cash_trade(self):
        return self.trade_type == self.TradeType.CASH

    # 🆕 信用取引かどうかを判定
    @property
    def is_margin_trade(self):
        return self.trade_type == self.TradeType.MARGIN

        

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
        # フラグだけ設定
        self.is_applied = True
        self.applied_at = timezone.now()
        self.save()
        
        # update_aggregatesで調整処理を一括実行
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
    """日記の通知設定"""
    NOTIFICATION_TYPES = [
        ('price_alert', '価格アラート'),
        ('reminder', 'リマインダー'),
        ('periodic', '定期通知'),
    ]
    
    FREQUENCY_CHOICES = [
        ('daily', '毎日'),
        ('weekly', '毎週'),
        ('monthly', '毎月'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    diary = models.ForeignKey(
        'StockDiary',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default='reminder'
    )
    target_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True, verbose_name='目標価格'
    )
    alert_above = models.BooleanField(default=True, verbose_name='上回ったら通知')
    remind_at = models.DateTimeField(null=True, blank=True, verbose_name='通知日時')
    frequency = models.CharField(
        max_length=20, choices=FREQUENCY_CHOICES,
        null=True, blank=True, verbose_name='通知頻度'
    )
    notify_time = models.TimeField(null=True, blank=True, verbose_name='通知時刻')
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
            models.Index(fields=['notification_type', 'is_active']),
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