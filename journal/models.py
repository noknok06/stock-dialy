# journal/models.py
from django.db import models
from django.conf import settings
from ckeditor_uploader.fields import RichTextUploadingField
from stockdiary.models import StockDiary
from tags.models import Tag
from checklist.models import Checklist, DiaryChecklistItem

class Stock(models.Model):
    """銘柄情報モデル"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=10, verbose_name="証券コード")
    name = models.CharField(max_length=100, verbose_name="銘柄名")
    industry = models.CharField(max_length=100, blank=True, verbose_name="業種")
    sector = models.CharField(max_length=100, blank=True, verbose_name="セクター")
    
    # 現在のステータス
    STATUS_CHOICES = [
        ('watching', 'ウォッチ中'),
        ('holding', '保有中'),
        ('sold', '売却済み'),
    ]
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='watching',
        verbose_name="ステータス"
    )
    
    # 基本情報
    first_watch_date = models.DateField(null=True, blank=True, verbose_name="初回ウォッチ日")
    purchase_date = models.DateField(null=True, blank=True, verbose_name="購入日")
    purchase_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="購入価格"
    )
    purchase_quantity = models.IntegerField(null=True, blank=True, verbose_name="購入数量")
    sell_date = models.DateField(null=True, blank=True, verbose_name="売却日")
    sell_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="売却価格"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.symbol})"
    
    class Meta:
        unique_together = ['user', 'symbol']
        ordering = ['symbol']
        verbose_name = "銘柄"
        verbose_name_plural = "銘柄"

class JournalEntry(models.Model):
    """投資判断記録モデル"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stock = models.ForeignKey(
        Stock, 
        on_delete=models.CASCADE, 
        related_name='journal_entries',
        verbose_name="銘柄"
    )
    
    # 日記タイプ
    ENTRY_TYPE_CHOICES = [
        ('watch', 'ウォッチリスト'),  # 新銘柄発見時の初期評価
        ('research', '投資検討'),     # 売買判断前の調査・思考プロセス
        ('trade', '売買実行'),        # 実際の売買記録
        ('holding', '保有分析'),      # 保有中の評価見直し
        ('market', '市場観測'),       # 市場全体に関する分析
    ]
    entry_type = models.CharField(
        max_length=20, 
        choices=ENTRY_TYPE_CHOICES,
        default='research',
        verbose_name="記録タイプ"
    )
    
    entry_date = models.DateField(verbose_name="記録日")
    title = models.CharField(max_length=200, verbose_name="タイトル")
    content = RichTextUploadingField(verbose_name="記録内容")
    
    # 前回の記録からの変化追跡
    # previous_entry = models.ForeignKey(
    #     'self', 
    #     null=True, 
    #     blank=True, 
    #     related_name='next_entries',
    #     verbose_name="前回の記録"
    # )
    thesis_change = models.TextField(
        blank=True, 
        verbose_name="投資判断の変化",
        help_text="前回からの投資判断の変化点があれば記入してください"
    )
    
    # ウォッチリスト固有フィールド
    price_at_entry = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="現在株価"
    )
    watch_reason = models.TextField(
        blank=True, 
        verbose_name="注目理由",
        help_text="この銘柄に注目した理由を簡潔に記入してください"
    )
    
    # 投資検討固有フィールド
    target_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="目標株価"
    )
    stop_loss = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="損切価格"
    )
    expected_return = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="期待リターン(%)"
    )
    
    # 売買実行固有フィールド
    TRADE_TYPE_CHOICES = [
        ('buy', '購入'),
        ('sell', '売却'),
    ]
    trade_type = models.CharField(
        max_length=10, 
        choices=TRADE_TYPE_CHOICES,
        null=True, 
        blank=True,
        verbose_name="取引タイプ"
    )
    trade_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="取引価格"
    )
    trade_quantity = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="数量"
    )
    trade_costs = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="取引コスト"
    )
    
    # 関連項目
    checklist = models.ManyToManyField(
        Checklist, 
        blank=True,
        verbose_name="チェックリスト"
    )
    tags = models.ManyToManyField(
        Tag, 
        blank=True,
        verbose_name="タグ"
    )
    analysis_template = models.ForeignKey(
        'analysis_template.AnalysisTemplate', 
        null=True, 
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="分析テンプレート"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-entry_date', '-created_at']
        verbose_name = "投資判断記録"
        verbose_name_plural = "投資判断記録"
    
    def __str__(self):
        return f"{self.get_entry_type_display()} - {self.stock.name} ({self.entry_date})"
    
    def save(self, *args, **kwargs):
        # 銘柄ステータスの自動更新
        stock_updated = False
        
        # ウォッチリスト記録の場合、初回ウォッチ日を設定
        if self.entry_type == 'watch' and not self.stock.first_watch_date:
            self.stock.first_watch_date = self.entry_date
            self.stock.status = 'watching'
            stock_updated = True
        
        # 売買実行記録の場合
        if self.entry_type == 'trade':
            if self.trade_type == 'buy':
                # 購入情報を更新
                self.stock.purchase_date = self.entry_date
                self.stock.purchase_price = self.trade_price
                self.stock.purchase_quantity = self.trade_quantity
                self.stock.status = 'holding'
                stock_updated = True
                
            elif self.trade_type == 'sell':
                # 売却情報を更新
                self.stock.sell_date = self.entry_date
                self.stock.sell_price = self.trade_price
                self.stock.status = 'sold'
                stock_updated = True
        
        # 変更があれば銘柄情報を保存
        if stock_updated:
            self.stock.save()
        
        super().save(*args, **kwargs)

class DiaryJournalChecklistItem(models.Model):
    """日記のチェックリスト項目ステータス"""
    journal_entry = models.ForeignKey(
        JournalEntry, 
        on_delete=models.CASCADE,
        related_name='checklist_items'
    )
    checklist_item = models.ForeignKey(
        'checklist.ChecklistItem', 
        on_delete=models.CASCADE
    )
    status = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('journal_entry', 'checklist_item')
        verbose_name = "チェックリスト項目ステータス"
        verbose_name_plural = "チェックリスト項目ステータス"
    
    def __str__(self):
        return f"{self.journal_entry} - {self.checklist_item} ({self.status})"

class ThesisChangeTracker(models.Model):
    """投資判断変化追跡モデル"""
    stock = models.ForeignKey(
        Stock, 
        on_delete=models.CASCADE, 
        related_name='thesis_changes'
    )
    from_entry = models.ForeignKey(
        JournalEntry, 
        on_delete=models.CASCADE, 
        related_name='thesis_changes_from'
    )
    to_entry = models.ForeignKey(
        JournalEntry, 
        on_delete=models.CASCADE, 
        related_name='thesis_changes_to'
    )
    
    CHANGE_TYPE_CHOICES = [
        ('bullish_to_bearish', '強気→弱気'),
        ('bearish_to_bullish', '弱気→強気'),
        ('price_target_increase', '目標株価引き上げ'),
        ('price_target_decrease', '目標株価引き下げ'),
        ('thesis_confirmation', '投資判断の確認'),
        ('thesis_adjustment', '投資判断の調整'),
        ('risk_assessment_change', 'リスク評価の変更'),
        ('catalyst_update', '催化剤の更新'),
        ('other', 'その他'),
    ]
    
    change_type = models.CharField(
        max_length=50,
        choices=CHANGE_TYPE_CHOICES,
        verbose_name="変化タイプ"
    )
    change_summary = models.CharField(
        max_length=200,
        verbose_name="変化の要約"
    )
    change_detail = models.TextField(verbose_name="変化の詳細")
    
    impact_level = models.IntegerField(
        choices=[(1, '小'), (2, '中'), (3, '大')],
        verbose_name="影響レベル"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "投資判断変化"
        verbose_name_plural = "投資判断変化"
    
    def __str__(self):
        return f"{self.stock.name} - {self.get_change_type_display()} ({self.created_at.date()})"