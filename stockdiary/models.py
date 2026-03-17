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
import logging
from tags.models import Tag

logger = logging.getLogger(__name__)


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

    # 現物取引のみの集計フィールド（is_margin=False）
    cash_only_current_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='現物保有数')
    cash_only_average_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='現物平均取得単価')
    cash_only_total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='現物総原価')
    cash_only_realized_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='現物実現損益')
    cash_only_total_bought_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='現物累計購入数')
    cash_only_total_sold_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='現物累計売却数')
    cash_only_total_buy_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='現物累計購入額')
    cash_only_total_sell_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='現物累計売却額')
    
    # 日付情報
    first_purchase_date = models.DateField(null=True, blank=True, db_index=True, verbose_name='最初の購入日')
    last_transaction_date = models.DateField(null=True, blank=True, verbose_name='最後の取引日')
    
    # 関連日記（非対称M2M：対称性はアプリ層で管理）
    linked_diaries = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='linked_from', verbose_name='関連日記')

    # 開示書類情報（EDINETから定期更新）
    latest_disclosure_date = models.DateField(
        null=True, blank=True, verbose_name='最新開示日'
    )
    latest_disclosure_doc_type_name = models.CharField(
        max_length=50, blank=True, verbose_name='最新開示種別'
    )

    # システム情報
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'first_purchase_date']),
            models.Index(fields=['user', 'stock_symbol']),
            models.Index(fields=['user', 'current_quantity']),
            models.Index(fields=['user', '-updated_at']),
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

    @property
    def recent_disclosure_status(self):
        """開示書類の直近度: 'new'(7日以内), 'recent'(30日以内), None"""
        if not self.latest_disclosure_date:
            return None
        from datetime import date
        days = (date.today() - self.latest_disclosure_date).days
        if days <= 7:
            return 'new'
        elif days <= 30:
            return 'recent'
        return None

    def update_aggregates(self):
        """集計フィールドを再計算して save() する。"""
        from .services.aggregate_service import AggregateService
        AggregateService.recalculate(self)

    def process_and_save_image(self, image_file):
        """画像を非同期で圧縮・保存する。元画像をまず保存してからdjango-qでリサイズする。"""
        from .services.image_service import ImageService
        try:
            if self.image:
                self.image.delete(save=False)

            filename = f"{uuid.uuid4().hex}{os.path.splitext(image_file.name)[1]}"
            self.image.save(filename, image_file, save=True)

            from django_q.tasks import async_task
            async_task('stockdiary.tasks.compress_diary_image', self.id)
            return True

        except Exception as e:
            logger.error("Image upload failed for StockDiary(id=%s): %s", self.id, e, exc_info=True)
            # フォールバック: 同期圧縮
            try:
                image_file.seek(0)
                return ImageService.compress_and_save(self, image_file, max_size=(800, 600), quality=85)
            except Exception:
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
            logger.error(f"Image deletion failed for StockDiary: {str(e)}", exc_info=True)
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
        """現物取引（is_margin=False）のみの統計を返す（キャッシュ済みフィールドを使用）"""
        return {
            'current_quantity': self.cash_only_current_quantity,
            'average_purchase_price': self.cash_only_average_purchase_price,
            'total_cost': self.cash_only_total_cost,
            'realized_profit': self.cash_only_realized_profit,
            'total_bought_quantity': self.cash_only_total_bought_quantity,
            'total_sold_quantity': self.cash_only_total_sold_quantity,
            'total_buy_amount': self.cash_only_total_buy_amount,
            'total_sell_amount': self.cash_only_total_sell_amount,
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
    content = models.TextField(verbose_name='記録内容', blank=True, max_length=3000)
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

    source_doc_id = models.CharField('参照書類ID', max_length=8, null=True, blank=True,
                                     help_text='関連するEDINET書類のdoc_id')

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
        if self.content and len(self.content) > 3000:
            raise ValidationError({'content': '記録内容は3000文字以内で入力してください'})
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
        # 親日記のupdated_atを更新
        self.diary.updated_at = timezone.now()
        self.diary.save(update_fields=['updated_at'])

    def process_and_save_image(self, image_file):
        """画像を非同期で圧縮・保存する。元画像をまず保存してからdjango-qでリサイズする。"""
        from .services.image_service import ImageService
        try:
            if self.image:
                self.image.delete(save=False)

            filename = f"{uuid.uuid4().hex}{os.path.splitext(image_file.name)[1]}"
            self.image.save(filename, image_file, save=True)

            from django_q.tasks import async_task
            async_task('stockdiary.tasks.compress_note_image', self.id)
            return True

        except Exception as e:
            logger.error("Image upload failed for DiaryNote(id=%s): %s", self.id, e, exc_info=True)
            # フォールバック: 同期圧縮
            try:
                image_file.seek(0)
                return ImageService.compress_and_save(self, image_file, max_size=(600, 400), quality=80)
            except Exception:
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
            logger.error(f"Note image deletion failed for DiaryNote: {str(e)}", exc_info=True)
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
