# stockdiary/models.py
from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.urls import reverse
from decimal import Decimal
import os
import uuid
from PIL import Image
import io


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
    """株式日記エントリー（親エントリー）"""
    # 基本情報
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stock_symbol = models.CharField(max_length=50, blank=True, db_index=True)
    stock_name = models.CharField(max_length=100)
    sector = models.CharField(max_length=50, blank=True, verbose_name='業種')
    reason = models.TextField(verbose_name='投資理由', blank=True, max_length=1000)
    memo = models.TextField(blank=True, max_length=1000)
    
    # 画像関連
    image = models.ImageField(
        upload_to=get_diary_image_path,
        null=True, 
        blank=True,
        help_text="日記に関連する画像"
    )
    
    # タグ・チェックリスト
    tags = models.ManyToManyField('tags.Tag', blank=True)
    checklist = models.ManyToManyField('checklist.Checklist', blank=True)
    
    # 集計フィールド（自動計算）
    current_quantity = models.IntegerField(default=0, verbose_name='現在保有数')
    average_purchase_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name='平均取得単価'
    )
    total_cost = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name='総取得原価'
    )
    realized_profit = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name='実現損益'
    )
    
    # 累計統計
    total_bought_quantity = models.IntegerField(default=0, verbose_name='累計購入数')
    total_sold_quantity = models.IntegerField(default=0, verbose_name='累計売却数')
    total_buy_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name='累計購入額'
    )
    total_sell_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name='累計売却額'
    )
    transaction_count = models.IntegerField(default=0, verbose_name='取引回数')
    
    # 日付情報
    first_purchase_date = models.DateField(null=True, blank=True, verbose_name='最初の購入日')
    last_transaction_date = models.DateField(null=True, blank=True, verbose_name='最後の取引日')
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'stock_symbol']),
            models.Index(fields=['user', 'current_quantity']),
            models.Index(fields=['user', 'first_purchase_date']),
            models.Index(fields=['user', 'last_transaction_date']),
        ]
        ordering = ['-last_transaction_date', '-updated_at']

    def __str__(self):
        return f"{self.stock_name} ({self.stock_symbol})"

    def recalculate_summary(self):
        """トランザクションから集計値を再計算"""
        transactions = self.transactions.order_by('date', 'id')
        
        if not transactions.exists():
            self._reset_summary()
            return
        
        # 初期化
        holding_quantity = 0
        total_cost = Decimal('0')
        realized_profit = Decimal('0')
        
        total_bought_qty = 0
        total_sold_qty = 0
        total_buy_amount = Decimal('0')
        total_sell_amount = Decimal('0')
        
        # 各取引を処理
        for t in transactions:
            if t.transaction_type == 'buy':
                # 購入処理
                buy_cost = t.price * t.quantity
                holding_quantity += t.quantity
                total_cost += buy_cost
                total_bought_qty += t.quantity
                total_buy_amount += buy_cost
                
            elif t.transaction_type == 'sell':
                # 売却処理
                if holding_quantity > 0:
                    avg_cost_per_share = total_cost / holding_quantity
                    sell_cost = avg_cost_per_share * t.quantity
                    sell_proceeds = t.price * t.quantity
                    
                    profit = sell_proceeds - sell_cost
                    realized_profit += profit
                    
                    holding_quantity -= t.quantity
                    total_cost -= sell_cost
                    total_sold_qty += t.quantity
                    total_sell_amount += sell_proceeds
        
        # 集計フィールドを更新
        self.current_quantity = holding_quantity
        self.average_purchase_price = (
            total_cost / holding_quantity if holding_quantity > 0 else Decimal('0')
        )
        self.total_cost = total_cost
        self.realized_profit = realized_profit
        self.total_bought_quantity = total_bought_qty
        self.total_sold_quantity = total_sold_qty
        self.total_buy_amount = total_buy_amount
        self.total_sell_amount = total_sell_amount
        self.transaction_count = transactions.count()
        
        # 日付情報
        first_buy = transactions.filter(transaction_type='buy').first()
        self.first_purchase_date = first_buy.date if first_buy else None
        
        last_transaction = transactions.last()
        self.last_transaction_date = last_transaction.date if last_transaction else None
        
        self.save(update_fields=[
            'current_quantity', 'average_purchase_price', 'total_cost',
            'realized_profit', 'total_bought_quantity', 'total_sold_quantity',
            'total_buy_amount', 'total_sell_amount', 'transaction_count',
            'first_purchase_date', 'last_transaction_date', 'updated_at'
        ])

    def _reset_summary(self):
        """集計値をリセット"""
        self.current_quantity = 0
        self.average_purchase_price = Decimal('0')
        self.total_cost = Decimal('0')
        self.realized_profit = Decimal('0')
        self.total_bought_quantity = 0
        self.total_sold_quantity = 0
        self.total_buy_amount = Decimal('0')
        self.total_sell_amount = Decimal('0')
        self.transaction_count = 0
        self.first_purchase_date = None
        self.last_transaction_date = None
        self.save(update_fields=[
            'current_quantity', 'average_purchase_price', 'total_cost',
            'realized_profit', 'total_bought_quantity', 'total_sold_quantity',
            'total_buy_amount', 'total_sell_amount', 'transaction_count',
            'first_purchase_date', 'last_transaction_date', 'updated_at'
        ])

    def get_quick_summary(self):
        """高速サマリー（一覧表示用）"""
        return {
            'current_quantity': self.current_quantity,
            'average_purchase_price': self.average_purchase_price,
            'realized_profit': self.realized_profit,
            'has_active_position': self.has_active_position,
            'is_fully_sold': self.is_fully_sold,
        }

    def get_position_summary(self):
        """詳細サマリー（詳細表示用）"""
        return {
            'current_quantity': self.current_quantity,
            'average_purchase_price': self.average_purchase_price,
            'total_cost': self.total_cost,
            'realized_profit': self.realized_profit,
            'total_bought_quantity': self.total_bought_quantity,
            'total_sold_quantity': self.total_sold_quantity,
            'total_buy_amount': self.total_buy_amount,
            'total_sell_amount': self.total_sell_amount,
            'transaction_count': self.transaction_count,
            'first_purchase_date': self.first_purchase_date,
            'last_transaction_date': self.last_transaction_date,
        }

    def get_transaction_history_with_details(self):
        """取引履歴（各時点の保有数・平均単価付き）"""
        transactions = self.transactions.order_by('date', 'id')
        splits = self.stock_splits.order_by('split_date')
        
        history = []
        holding_quantity = 0
        total_cost = Decimal('0')
        
        all_events = []
        for t in transactions:
            all_events.append(('transaction', t.date, t))
        for s in splits:
            all_events.append(('split', s.split_date, s))
        
        all_events.sort(key=lambda x: x[1])
        
        for event_type, event_date, event_obj in all_events:
            if event_type == 'transaction':
                t = event_obj
                trade_profit = Decimal('0')
                
                if t.transaction_type == 'buy':
                    buy_cost = t.price * t.quantity
                    holding_quantity += t.quantity
                    total_cost += buy_cost
                    
                elif t.transaction_type == 'sell':
                    if holding_quantity > 0:
                        avg_cost_per_share = total_cost / holding_quantity
                        sell_cost = avg_cost_per_share * t.quantity
                        sell_proceeds = t.price * t.quantity
                        trade_profit = sell_proceeds - sell_cost
                        
                        holding_quantity -= t.quantity
                        total_cost -= sell_cost
                
                history.append({
                    'event_type': 'transaction',
                    'transaction': t,
                    'holding_quantity': holding_quantity,
                    'average_price': total_cost / holding_quantity if holding_quantity > 0 else Decimal('0'),
                    'trade_profit': trade_profit,
                })
                
            elif event_type == 'split':
                s = event_obj
                if s.is_applied:
                    holding_quantity = int(holding_quantity * s.split_ratio)
                    if holding_quantity > 0:
                        total_cost = total_cost
                    
                    history.append({
                        'event_type': 'split',
                        'split': s,
                        'holding_quantity': holding_quantity,
                        'average_price': total_cost / holding_quantity if holding_quantity > 0 else Decimal('0'),
                    })
        
        return history

    @property
    def has_active_position(self):
        """保有中かどうか"""
        return self.current_quantity > 0

    @property
    def is_fully_sold(self):
        """完全売却済みかどうか"""
        return self.transaction_count > 0 and self.current_quantity == 0

    # 画像関連メソッド（既存のまま維持）
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

    def get_thumbnail_url(self, width=300, height=200):
        """サムネイル用の画像URLを取得"""
        if self.image:
            return reverse('stockdiary:serve_image', kwargs={
                'diary_id': self.id,
                'image_type': 'diary'
            }) + f'?thumbnail=1&w={width}&h={height}'
        return None

    @property
    def image_url(self):
        return self.get_image_url()

    # チェックリスト関連（既存のまま維持）
    def add_checklist(self, checklist):
        from checklist.models import DiaryChecklistItem
        self.checklist.add(checklist)
        for item in checklist.items.all():
            DiaryChecklistItem.objects.get_or_create(
                diary=self,
                checklist_item=item,
                defaults={'status': False}
            )

    def get_checklist_item_status(self, checklist_item):
        from checklist.models import DiaryChecklistItem
        try:
            item_status = DiaryChecklistItem.objects.get(
                diary=self,
                checklist_item=checklist_item
            )
            return item_status.status
        except DiaryChecklistItem.DoesNotExist:
            return False


class StockTransaction(models.Model):
    """売買トランザクション"""
    TRANSACTION_TYPES = [
        ('buy', '購入'),
        ('sell', '売却'),
    ]
    
    diary = models.ForeignKey(
        StockDiary, 
        on_delete=models.CASCADE, 
        related_name='transactions'
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    date = models.DateField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'id']
        indexes = [
            models.Index(fields=['diary', 'date']),
            models.Index(fields=['diary', 'transaction_type']),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} {self.quantity}株 @ {self.price}円 ({self.date})"

    @property
    def total_amount(self):
        """取引総額"""
        return self.price * self.quantity

    def save(self, *args, **kwargs):
        """保存時に親日記の集計を更新"""
        super().save(*args, **kwargs)
        self.diary.recalculate_summary()

    def delete(self, *args, **kwargs):
        """削除時に親日記の集計を更新"""
        diary = self.diary
        result = super().delete(*args, **kwargs)
        diary.recalculate_summary()
        return result

    def get_deletion_impact(self):
        """削除時の影響分析"""
        transactions = self.diary.transactions.order_by('date', 'id')
        is_latest = transactions.last() == self
        
        affected_count = 0
        if not is_latest:
            later_transactions = transactions.filter(
                models.Q(date__gt=self.date) | 
                models.Q(date=self.date, id__gt=self.id)
            )
            affected_count = later_transactions.count()
        
        return {
            'is_latest': is_latest,
            'affected_transaction_count': affected_count,
            'will_recalculate': affected_count > 0,
        }


class StockSplit(models.Model):
    """株式分割"""
    diary = models.ForeignKey(
        StockDiary, 
        on_delete=models.CASCADE, 
        related_name='stock_splits'
    )
    split_date = models.DateField(verbose_name='分割実行日')
    split_ratio = models.DecimalField(
        max_digits=10, decimal_places=4, 
        verbose_name='分割比率',
        help_text='例: 2.0 = 1→2株'
    )
    note = models.CharField(max_length=200, blank=True)
    is_applied = models.BooleanField(default=False, verbose_name='適用済みフラグ')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['split_date']

    def __str__(self):
        return f"{self.diary.stock_name} 株式分割 {self.split_ratio}倍 ({self.split_date})"

    def apply_split(self):
        """
        分割日以前の取引を調整
        - 数量 = 元の数量 × 分割比率
        - 単価 = 元の単価 ÷ 分割比率
        """
        if self.is_applied:
            return
        
        with transaction.atomic():
            transactions = self.diary.transactions.filter(
                date__lt=self.split_date
            )
            
            for t in transactions:
                t.quantity = int(t.quantity * self.split_ratio)
                t.price = t.price / self.split_ratio
                t.save(update_fields=['quantity', 'price'])
            
            self.is_applied = True
            self.save(update_fields=['is_applied'])
            
            self.diary.recalculate_summary()


class DiaryNote(models.Model):
    """日記エントリーへの継続的な追記"""
    diary = models.ForeignKey(StockDiary, on_delete=models.CASCADE, related_name='notes')
    date = models.DateField()
    content = models.TextField(verbose_name='記録内容', blank=True, max_length=1000)
    current_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, 
        verbose_name='記録時点の価格'
    )
    
    image = models.ImageField(
        upload_to=get_note_image_path,
        null=True, 
        blank=True,
        help_text="継続記録に関連する画像"
    )
    
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
    
    def clean(self):
        super().clean()
        if self.content and len(self.content) > 1000:
            raise ValidationError({
                'content': '記録内容は1000文字以内で入力してください。'
            })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
        from django.utils import timezone
        self.diary.updated_at = timezone.now()
        self.diary.save(update_fields=['updated_at'])

    def __str__(self):
        return f"{self.diary.stock_name} - {self.date}"
    
    def get_price_change(self):
        """購入価格からの変動率を計算"""
        if self.current_price and self.diary.average_purchase_price:
            change = ((self.current_price - self.diary.average_purchase_price) / 
                     self.diary.average_purchase_price) * 100
            return change
        return None

    # 画像関連メソッド（StockDiaryと同様）
    def process_and_save_image(self, image_file):
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
        if self.image:
            return reverse('stockdiary:serve_image', kwargs={
                'diary_id': self.diary.id,
                'image_type': 'note',
                'note_id': self.id
            })
        return None

    def get_thumbnail_url(self, width=200, height=150):
        if self.image:
            return reverse('stockdiary:serve_image', kwargs={
                'diary_id': self.diary.id,
                'image_type': 'note',
                'note_id': self.id
            }) + f'?thumbnail=1&w={width}&h={height}'
        return None

    @property
    def image_url(self):
        return self.get_image_url()