# earnings_analysis/models/financial.py（新規作成）
from django.db import models
from django.utils import timezone
from django.db.models import JSONField
from decimal import Decimal
import uuid

class FinancialAnalysisSession(models.Model):
    """財務分析セッション"""
    
    STATUS_CHOICES = [
        ('PENDING', '待機中'),
        ('PROCESSING', '処理中'),
        ('COMPLETED', '完了'),
        ('FAILED', '失敗'),
    ]
    
    RISK_LEVEL_CHOICES = [
        ('low', '低リスク'),
        ('medium', '中リスク'),
        ('high', '高リスク'),
    ]
    
    INVESTMENT_STANCE_CHOICES = [
        ('aggressive', '積極的投資推奨'),
        ('conditional', '条件付き投資推奨'),
        ('cautious', '慎重な検討が必要'),
        ('avoid', '投資非推奨'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    session_id = models.CharField('セッションID', max_length=64, unique=True, default=uuid.uuid4)
    document = models.ForeignKey('DocumentMetadata', on_delete=models.CASCADE, verbose_name='対象書類')
    
    # 財務分析結果
    overall_health_score = models.FloatField('総合健全性スコア', null=True, blank=True, help_text='0-100')
    risk_level = models.CharField('リスクレベル', max_length=20, choices=RISK_LEVEL_CHOICES, null=True, blank=True)
    investment_stance = models.CharField('投資スタンス', max_length=20, choices=INVESTMENT_STANCE_CHOICES, null=True, blank=True)
    
    # キャッシュフロー分析
    cashflow_pattern = models.CharField('CFパターン', max_length=50, null=True, blank=True)
    operating_cf = models.DecimalField('営業CF', max_digits=20, decimal_places=0, null=True, blank=True)
    investing_cf = models.DecimalField('投資CF', max_digits=20, decimal_places=0, null=True, blank=True)
    financing_cf = models.DecimalField('財務CF', max_digits=20, decimal_places=0, null=True, blank=True)
    
    # 経営陣自信度
    management_confidence_score = models.FloatField('経営陣自信度', null=True, blank=True, help_text='0-100')
    
    # ステータス
    processing_status = models.CharField('処理ステータス', max_length=20, choices=STATUS_CHOICES, default='PENDING')
    error_message = models.TextField('エラーメッセージ', blank=True)
    
    # 分析結果詳細（JSON）
    analysis_result = JSONField('分析結果詳細', null=True, blank=True)
    financial_data = JSONField('財務データ', null=True, blank=True)
    
    # タイムスタンプ
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    expires_at = models.DateTimeField('有効期限')
    
    class Meta:
        db_table = 'earnings_analysis_financial_session'
        verbose_name = '財務分析セッション'
        verbose_name_plural = '財務分析セッション一覧'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['processing_status']),
            models.Index(fields=['document', 'created_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=48)  # 48時間有効
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"財務分析 {self.session_id[:8]}... - {self.document.company_name}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def progress_percentage(self):
        """進行率計算"""
        if self.processing_status == 'PENDING':
            return 0
        elif self.processing_status == 'PROCESSING':
            return 50
        elif self.processing_status in ['COMPLETED', 'FAILED']:
            return 100
        return 0


class FinancialAnalysisHistory(models.Model):
    """財務分析履歴（統計用）"""
    
    RISK_LEVEL_CHOICES = [
        ('low', '低リスク'),
        ('medium', '中リスク'),
        ('high', '高リスク'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    document = models.ForeignKey('DocumentMetadata', on_delete=models.CASCADE, verbose_name='対象書類')
    
    # 分析結果サマリー
    overall_health_score = models.FloatField('総合健全性スコア', help_text='0-100')
    risk_level = models.CharField('リスクレベル', max_length=20, choices=RISK_LEVEL_CHOICES)
    cashflow_pattern = models.CharField('CFパターン', max_length=50, null=True, blank=True)
    management_confidence_score = models.FloatField('経営陣自信度', null=True, blank=True)
    
    # メタデータ
    analysis_date = models.DateTimeField('分析実行日時', auto_now_add=True)
    user_ip = models.GenericIPAddressField('実行ユーザーIP', null=True, blank=True)
    analysis_duration = models.FloatField('分析処理時間（秒）', null=True, blank=True)
    data_quality = models.CharField('データ品質', max_length=20, null=True, blank=True)
    
    class Meta:
        db_table = 'earnings_analysis_financial_history'
        verbose_name = '財務分析履歴'
        verbose_name_plural = '財務分析履歴一覧'
        ordering = ['-analysis_date']
        indexes = [
            models.Index(fields=['document', 'analysis_date']),
            models.Index(fields=['risk_level']),
            models.Index(fields=['analysis_date']),
            models.Index(fields=['cashflow_pattern']),
        ]
    
    def __str__(self):
        return f"{self.document.company_name} - {self.get_risk_level_display()} ({self.overall_health_score:.1f})"


class CompanyFinancialData(models.Model):
    """企業の財務データ（期間別）"""
    
    PERIOD_TYPE_CHOICES = [
        ('annual', '年次'),
        ('quarterly', '四半期'),
        ('semi_annual', '半期'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    document = models.ForeignKey('DocumentMetadata', on_delete=models.CASCADE, verbose_name='出典書類')
    company = models.ForeignKey('Company', on_delete=models.CASCADE, verbose_name='企業', null=True, blank=True)
    
    # 期間情報
    period_type = models.CharField('期間種別', max_length=20, choices=PERIOD_TYPE_CHOICES)
    period_start = models.DateField('期間開始日', null=True, blank=True)
    period_end = models.DateField('期間終了日', null=True, blank=True)
    fiscal_year = models.IntegerField('会計年度', null=True, blank=True)
    
    # 損益計算書データ
    net_sales = models.DecimalField('売上高', max_digits=20, decimal_places=0, null=True, blank=True)
    operating_income = models.DecimalField('営業利益', max_digits=20, decimal_places=0, null=True, blank=True)
    ordinary_income = models.DecimalField('経常利益', max_digits=20, decimal_places=0, null=True, blank=True)
    net_income = models.DecimalField('当期純利益', max_digits=20, decimal_places=0, null=True, blank=True)
    
    # 貸借対照表データ
    total_assets = models.DecimalField('総資産', max_digits=20, decimal_places=0, null=True, blank=True)
    total_liabilities = models.DecimalField('総負債', max_digits=20, decimal_places=0, null=True, blank=True)
    net_assets = models.DecimalField('純資産', max_digits=20, decimal_places=0, null=True, blank=True)
    
    # キャッシュフロー計算書データ
    operating_cf = models.DecimalField('営業CF', max_digits=20, decimal_places=0, null=True, blank=True)
    investing_cf = models.DecimalField('投資CF', max_digits=20, decimal_places=0, null=True, blank=True)
    financing_cf = models.DecimalField('財務CF', max_digits=20, decimal_places=0, null=True, blank=True)
    
    # 計算済み指標
    operating_margin = models.DecimalField('営業利益率(%)', max_digits=8, decimal_places=2, null=True, blank=True)
    net_margin = models.DecimalField('当期純利益率(%)', max_digits=8, decimal_places=2, null=True, blank=True)
    roa = models.DecimalField('ROA(%)', max_digits=8, decimal_places=2, null=True, blank=True)
    equity_ratio = models.DecimalField('自己資本比率(%)', max_digits=8, decimal_places=2, null=True, blank=True)
    
    # データ品質情報
    data_completeness = models.FloatField('データ完全性', null=True, blank=True, help_text='0-1.0')
    extraction_confidence = models.FloatField('抽出信頼度', null=True, blank=True, help_text='0-1.0')
    
    # タイムスタンプ
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    
    class Meta:
        db_table = 'earnings_analysis_company_financial_data'
        verbose_name = '企業財務データ'
        verbose_name_plural = '企業財務データ一覧'
        ordering = ['-period_end', '-created_at']
        unique_together = ['document', 'period_type', 'period_start', 'period_end']
        indexes = [
            models.Index(fields=['company', 'period_end']),
            models.Index(fields=['period_type', 'fiscal_year']),
            models.Index(fields=['document']),
        ]
    
    def __str__(self):
        company_name = self.company.company_name if self.company else self.document.company_name
        period_str = f"{self.period_start} - {self.period_end}" if self.period_start and self.period_end else "期間不明"
        return f"{company_name} ({period_str})"
    
    def save(self, *args, **kwargs):
        # 財務比率の自動計算
        self._calculate_ratios()
        super().save(*args, **kwargs)
    
    def _calculate_ratios(self):
        """財務比率の自動計算"""
        try:
            # 営業利益率
            if self.net_sales and self.operating_income and self.net_sales > 0:
                self.operating_margin = (self.operating_income / self.net_sales * 100).quantize(Decimal('0.01'))
            
            # 当期純利益率
            if self.net_sales and self.net_income and self.net_sales > 0:
                self.net_margin = (self.net_income / self.net_sales * 100).quantize(Decimal('0.01'))
            
            # ROA
            if self.total_assets and self.net_income and self.total_assets > 0:
                self.roa = (self.net_income / self.total_assets * 100).quantize(Decimal('0.01'))
            
            # 自己資本比率
            if self.total_assets and self.net_assets and self.total_assets > 0:
                self.equity_ratio = (self.net_assets / self.total_assets * 100).quantize(Decimal('0.01'))
                
        except (TypeError, ZeroDivisionError, AttributeError):
            # 計算エラーは無視（nullのまま）
            pass
    
    @property
    def has_complete_pl_data(self):
        """損益計算書データが完全か"""
        return all([
            self.net_sales is not None,
            self.operating_income is not None,
            self.net_income is not None
        ])
    
    @property
    def has_complete_bs_data(self):
        """貸借対照表データが完全か"""
        return all([
            self.total_assets is not None,
            self.total_liabilities is not None,
            self.net_assets is not None
        ])
    
    @property
    def has_complete_cf_data(self):
        """キャッシュフロー計算書データが完全か"""
        return all([
            self.operating_cf is not None,
            self.investing_cf is not None,
            self.financing_cf is not None
        ])
    
    @property
    def overall_data_completeness(self):
        """全体的なデータ完全性"""
        total_fields = 9  # 主要な財務データフィールド数
        complete_fields = sum([
            1 if self.net_sales is not None else 0,
            1 if self.operating_income is not None else 0,
            1 if self.net_income is not None else 0,
            1 if self.total_assets is not None else 0,
            1 if self.total_liabilities is not None else 0,
            1 if self.net_assets is not None else 0,
            1 if self.operating_cf is not None else 0,
            1 if self.investing_cf is not None else 0,
            1 if self.financing_cf is not None else 0,
        ])
        return complete_fields / total_fields


class FinancialBenchmark(models.Model):
    """業界ベンチマークデータ"""
    
    id = models.BigAutoField(primary_key=True)
    
    # 業界分類
    industry_category = models.CharField('業界カテゴリ', max_length=100)
    industry_subcategory = models.CharField('業界サブカテゴリ', max_length=100, blank=True)
    
    # ベンチマーク指標
    operating_margin_median = models.DecimalField('営業利益率中央値(%)', max_digits=8, decimal_places=2, null=True, blank=True)
    operating_margin_top25 = models.DecimalField('営業利益率上位25%(%)', max_digits=8, decimal_places=2, null=True, blank=True)
    
    roa_median = models.DecimalField('ROA中央値(%)', max_digits=8, decimal_places=2, null=True, blank=True)
    roa_top25 = models.DecimalField('ROA上位25%(%)', max_digits=8, decimal_places=2, null=True, blank=True)
    
    equity_ratio_median = models.DecimalField('自己資本比率中央値(%)', max_digits=8, decimal_places=2, null=True, blank=True)
    equity_ratio_top25 = models.DecimalField('自己資本比率上位25%(%)', max_digits=8, decimal_places=2, null=True, blank=True)
    
    # メタデータ
    sample_size = models.IntegerField('サンプル数', null=True, blank=True)
    reference_period = models.CharField('参照期間', max_length=50, blank=True)
    data_source = models.CharField('データソース', max_length=100, blank=True)
    
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    
    class Meta:
        db_table = 'earnings_analysis_financial_benchmark'
        verbose_name = '財務ベンチマーク'
        verbose_name_plural = '財務ベンチマーク一覧'
        unique_together = ['industry_category', 'industry_subcategory', 'reference_period']
        indexes = [
            models.Index(fields=['industry_category']),
            models.Index(fields=['industry_category', 'industry_subcategory']),
        ]
    
    def __str__(self):
        subcategory_part = f" > {self.industry_subcategory}" if self.industry_subcategory else ""
        return f"{self.industry_category}{subcategory_part} ({self.reference_period})"