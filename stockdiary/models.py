# stockdiary/models.py
from django.db import models
from django.contrib.auth import get_user_model
# from checklist.models import Checklist  # この行をコメントアウト
from tags.models import Tag
from django.conf import settings


class StockDiary(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stock_symbol = models.CharField(max_length=50, blank=True)
    stock_name = models.CharField(max_length=100)
    purchase_date = models.DateField()
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    purchase_quantity = models.IntegerField(null=True, blank=True)
    reason = models.TextField(verbose_name='購入理由', blank=True)
    # 文字列参照を使用して循環参照を避ける
    checklist = models.ManyToManyField('checklist.Checklist', blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    sell_date = models.DateField(null=True, blank=True)
    sell_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    memo = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_memo = models.BooleanField(default=False, verbose_name='メモ記録')
    sector = models.CharField(max_length=50, blank=True, verbose_name='業種')

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

    def can_be_sold(self):
        """この株式が売却可能かどうかを確認"""
        return self.purchase_price is not None and self.purchase_quantity is not None and not self.is_memo
        
    def save(self, *args, **kwargs):
        # 売却情報が設定されている場合は購入情報もチェック
        if self.sell_date is not None and not self.can_be_sold():
            raise ValueError("購入価格と株数が設定されていない株式は売却できません")
        
        # 価格や数量が入力されているかを確認してメモフラグを設定
        if self.purchase_price is None or self.purchase_quantity is None:
            self.is_memo = True
        else:
            # 価格と数量が両方入力されている場合はメモフラグをFalseに設定
            self.is_memo = False
            
        super().save(*args, **kwargs)
# stockdiary/models.py に追加

class DiaryNote(models.Model):
    """日記エントリーへの継続的な追記"""
    diary = models.ForeignKey(StockDiary, on_delete=models.CASCADE, related_name='notes')
    date = models.DateField()
    content = models.TextField(verbose_name='記録内容', blank=True)
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