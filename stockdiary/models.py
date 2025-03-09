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