# models.py
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

class MarketIssue(models.Model):
    """銘柄マスタ"""
    code = models.CharField(max_length=10, unique=True, verbose_name="証券コード")
    jp_code = models.CharField(max_length=12, unique=True, verbose_name="JPコード")
    name = models.CharField(max_length=100, verbose_name="銘柄名")
    category = models.CharField(max_length=10, verbose_name="市場区分", default="B")
    
    class Meta:
        db_table = 'market_issue'
        verbose_name = '銘柄'
        verbose_name_plural = '銘柄'
    
    def __str__(self):
        return f"{self.code} - {self.name}"

class MarginTradingData(models.Model):
    """信用取引データ"""
    issue = models.ForeignKey(MarketIssue, on_delete=models.CASCADE, verbose_name="銘柄")
    date = models.DateField(verbose_name="データ日付")
    
    # 売残高関連
    outstanding_sales = models.BigIntegerField(verbose_name="売残高", default=0)
    outstanding_sales_change = models.BigIntegerField(verbose_name="売残高前週比", default=0)
    
    # 買残高関連  
    outstanding_purchases = models.BigIntegerField(verbose_name="買残高", default=0)
    outstanding_purchases_change = models.BigIntegerField(verbose_name="買残高前週比", default=0)
    
    # 一般信用関連
    negotiable_credit = models.BigIntegerField(verbose_name="一般信用", default=0)
    negotiable_credit_change = models.BigIntegerField(verbose_name="一般信用前週比", default=0)
    
    # 制度信用関連
    standardized_credit = models.BigIntegerField(verbose_name="制度信用", default=0)
    standardized_credit_change = models.BigIntegerField(verbose_name="制度信用前週比", default=0)
    
    # 追加のデータフィールド（サンプルデータで見つけた項目）
    additional_data_1 = models.BigIntegerField(verbose_name="追加データ1", null=True, blank=True)
    additional_data_2 = models.BigIntegerField(verbose_name="追加データ2", null=True, blank=True)
    additional_data_3 = models.BigIntegerField(verbose_name="追加データ3", null=True, blank=True)
    additional_data_4 = models.BigIntegerField(verbose_name="追加データ4", null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        db_table = 'margin_trading_data'
        verbose_name = '信用取引データ'
        verbose_name_plural = '信用取引データ'
        unique_together = ('issue', 'date')
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['issue', 'date']),
        ]
    
    def __str__(self):
        return f"{self.issue.name} - {self.date}"

class DataImportLog(models.Model):
    """データ取得ログ"""
    STATUS_CHOICES = [
        ('SUCCESS', '成功'),
        ('FAILED', '失敗'),
        ('SKIPPED', 'スキップ'),
        ('PROCESSING', '処理中'),
    ]
    
    date = models.DateField(verbose_name="対象日付")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, verbose_name="ステータス")
    message = models.TextField(verbose_name="メッセージ", blank=True)
    records_count = models.IntegerField(verbose_name="取得件数", default=0)
    pdf_url = models.URLField(verbose_name="PDF URL", blank=True)
    executed_at = models.DateTimeField(auto_now_add=True, verbose_name="実行日時")
    
    class Meta:
        db_table = 'data_import_log'
        verbose_name = 'データ取得ログ'
        verbose_name_plural = 'データ取得ログ'
        ordering = ['-executed_at']
    
    def __str__(self):
        return f"{self.date} - {self.get_status_display()}"