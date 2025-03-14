# stockdiary/models.py
from django.db import models
from django.contrib.auth import get_user_model
# from checklist.models import Checklist  # この行をコメントアウト
from tags.models import Tag
from django.conf import settings
from ckeditor_uploader.fields import RichTextUploadingField


class StockDiary(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stock_symbol = models.CharField(max_length=10)
    stock_name = models.CharField(max_length=100)
    purchase_date = models.DateField()
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_quantity = models.IntegerField()
    reason = RichTextUploadingField(verbose_name='購入理由') 
    # 文字列参照を使用して循環参照を避ける
    checklist = models.ManyToManyField('checklist.Checklist', blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    sell_date = models.DateField(null=True, blank=True)
    sell_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    memo = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.stock_name} ({self.stock_symbol})"

    # 日記にチェックリストを追加するメソッドを追加
    def add_checklist(self, checklist):
        """チェックリストを日記に追加し、関連するアイテムの状態を初期化する"""
        from checklist.models import DiaryChecklistItem
        
        # チェックリストを追加
        self.checklist.add(checklist)
        
        # 関連するアイテムごとにDiaryChecklistItemを作成
        for item in checklist.items.all():
            DiaryChecklistItem.objects.get_or_create(
                diary=self,
                checklist_item=item,
                defaults={'status': False}
            )

    # チェックリストアイテムの状態を取得するメソッド
    def get_checklist_item_status(self, checklist_item):
        """特定のチェックリストアイテムの状態を取得"""
        from checklist.models import DiaryChecklistItem
        
        try:
            item_status = DiaryChecklistItem.objects.get(
                diary=self,
                checklist_item=checklist_item
            )
            return item_status.status
        except DiaryChecklistItem.DoesNotExist:
            return False            

# stockdiary/models.py に追加

class DiaryNote(models.Model):
    """日記エントリーへの継続的な追記"""
    diary = models.ForeignKey(StockDiary, on_delete=models.CASCADE, related_name='notes')
    date = models.DateField()
    content = RichTextUploadingField(verbose_name='記録内容')
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                       verbose_name='記録時点の価格')
    
    # メモタイプ
    TYPE_CHOICES = [
        ('analysis', '分析更新'),
        ('news', 'ニュース'),
        ('earnings', '決算情報'),
        ('insight', '新たな気づき'),
        ('risk', 'リスク要因'),
        ('other', 'その他')
    ]
    note_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='analysis')
    
    # メモの重要度
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
    
    def __str__(self):
        return f"{self.diary.stock_name} - {self.date}"
    
    def get_price_change(self):
        """購入価格からの変動率を計算"""
        if self.current_price and self.diary.purchase_price:
            change = ((self.current_price - self.diary.purchase_price) / self.diary.purchase_price) * 100
            return change
        return None            