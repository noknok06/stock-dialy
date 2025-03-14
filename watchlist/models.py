# watchlist/models.py
from django.db import models
from django.conf import settings
from ckeditor_uploader.fields import RichTextUploadingField
from tags.models import Tag

class WatchlistEntry(models.Model):
    """銘柄ウォッチリストのエントリー"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stock_symbol = models.CharField(max_length=10)
    stock_name = models.CharField(max_length=100)
    
    # 分析情報
    discovery_date = models.DateField()
    analysis = RichTextUploadingField(verbose_name='分析内容')
    interest_reason = models.TextField(verbose_name='注目理由', blank=True)
    potential_entry_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                              verbose_name='想定購入価格')
    
    # タグとステータス
    tags = models.ManyToManyField(Tag, blank=True)
    STATUS_CHOICES = [
        ('active', '監視中'),
        ('bought', '購入済み'),
        ('rejected', '見送り'),
        ('archived', 'アーカイブ')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # 優先度
    PRIORITY_CHOICES = [
        ('high', '高'),
        ('medium', '中'),
        ('low', '低')
    ]
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # メタデータ
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.stock_name} ({self.stock_symbol})"
    
class WatchlistNote(models.Model):
    """ウォッチリストエントリーへの追加メモ/更新"""
    entry = models.ForeignKey(WatchlistEntry, on_delete=models.CASCADE, related_name='notes')
    date = models.DateField()
    content = RichTextUploadingField(verbose_name='メモ内容')
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # アクション
    ACTION_CHOICES = [
        ('none', '様子見'),
        ('research', '追加調査'),
        ('buy_soon', '購入検討'),
        ('remove', 'ウォッチリストから除外'),
    ]
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='none')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.entry.stock_name} - {self.date}"