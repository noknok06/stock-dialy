# earnings_analysis/models.py
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import json

class CompanyEarnings(models.Model):
    """企業の決算情報マスタ"""
    edinet_code = models.CharField(max_length=6, unique=True, verbose_name='EDINETコード')
    company_code = models.CharField(max_length=6, db_index=True, verbose_name='証券コード')
    company_name = models.CharField(max_length=200, verbose_name='会社名')
    
    # 決算期情報
    fiscal_year_end_month = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        verbose_name='決算月'
    )
    
    # 最新分析情報
    latest_analysis_date = models.DateField(null=True, blank=True, verbose_name='最新分析日')
    latest_fiscal_year = models.CharField(max_length=10, blank=True, verbose_name='最新会計年度')
    latest_quarter = models.CharField(max_length=10, blank=True, verbose_name='最新四半期')
    
    # メタ情報
    is_active = models.BooleanField(default=True, verbose_name='分析対象')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'earnings_company_earnings'
        indexes = [
            models.Index(fields=['company_code']),
            models.Index(fields=['edinet_code']),
            models.Index(fields=['fiscal_year_end_month']),
        ]
    
    def __str__(self):
        return f"{self.company_name} ({self.company_code})"


class EarningsReport(models.Model):
    """決算報告書情報"""
    REPORT_TYPE_CHOICES = [
        ('quarterly', '四半期報告書'),
        ('annual', '有価証券報告書'),
        ('summary', '決算短信'),
    ]
    
    QUARTER_CHOICES = [
        ('Q1', '第1四半期'),
        ('Q2', '第2四半期'), 
        ('Q3', '第3四半期'),
        ('Q4', '第4四半期/通期'),
    ]
    
    company = models.ForeignKey(CompanyEarnings, on_delete=models.CASCADE, related_name='reports')
    
    # 報告書基本情報
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, verbose_name='報告書種別')
    fiscal_year = models.CharField(max_length=10, verbose_name='会計年度')
    quarter = models.CharField(max_length=5, choices=QUARTER_CHOICES, verbose_name='四半期')
    
    # EDINET情報
    document_id = models.CharField(max_length=50, unique=True, verbose_name='書類管理番号')
    submission_date = models.DateField(verbose_name='提出日')
    
    # 処理状況
    is_processed = models.BooleanField(default=False, verbose_name='処理済み')
    processing_error = models.TextField(blank=True, verbose_name='処理エラー')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'earnings_earnings_report'
        unique_together = ['company', 'fiscal_year', 'quarter', 'report_type']
        indexes = [
            models.Index(fields=['submission_date']),
            models.Index(fields=['is_processed']),
        ]
    
    def __str__(self):
        return f"{self.company.company_name} {self.fiscal_year} {self.quarter} {self.get_report_type_display()}"


class CashFlowAnalysis(models.Model):
    """キャッシュフロー分析結果"""
    CF_PATTERN_CHOICES = [
        ('ideal', '理想型（トヨタ型）'),
        ('growth', '成長型（テスラ型）'),
        ('danger', '危険型（破綻企業型）'),
        ('recovery', '回復型'),
        ('restructuring', 'リストラ型'),
        ('unknown', '判定不能'),
    ]
    
    HEALTH_SCORE_CHOICES = [
        ('excellent', '優秀'),
        ('good', '良好'),
        ('fair', '普通'),
        ('poor', '要注意'),
        ('critical', '危険'),
    ]
    
    report = models.OneToOneField(EarningsReport, on_delete=models.CASCADE, related_name='cashflow_analysis')
    
    # キャッシュフロー金額（百万円単位）
    operating_cf = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='営業CF')
    investing_cf = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='投資CF')
    financing_cf = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='財務CF')
    free_cf = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='フリーCF')
    
    # 分析結果
    cf_pattern = models.CharField(max_length=20, choices=CF_PATTERN_CHOICES, verbose_name='CFパターン')
    health_score = models.CharField(max_length=20, choices=HEALTH_SCORE_CHOICES, verbose_name='健全性スコア')
    
    # 前期比較
    operating_cf_change_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='営業CF変化率')
    free_cf_change_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='フリーCF変化率')
    
    # 分析コメント
    analysis_summary = models.TextField(blank=True, verbose_name='分析要約')
    risk_factors = models.TextField(blank=True, verbose_name='リスク要因')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'earnings_cashflow_analysis'
    
    def get_cf_pattern_description(self):
        """CFパターンの説明を取得"""
        descriptions = {
            'ideal': '営業CFでしっかり稼ぎ、将来投資を行い、借入金を返済している理想的な状態',
            'growth': '営業CFで稼ぎながら積極投資し、更なる成長のため資金調達も行っている',
            'danger': '本業で損失を出し、資産売却や借入で資金繰りを行っている危険な状態',
            'recovery': '営業CFは改善傾向だが、まだ投資余力が限定的な回復段階',
            'restructuring': '事業再構築のため一時的に特殊なCFパターンを示している',
            'unknown': 'データ不足または特殊要因により判定困難'
        }
        return descriptions.get(self.cf_pattern, '')


class SentimentAnalysis(models.Model):
    """感情分析・経営陣自信度分析結果"""
    CONFIDENCE_LEVEL_CHOICES = [
        ('very_high', '非常に高い'),
        ('high', '高い'),
        ('moderate', '普通'),
        ('low', '低い'),
        ('very_low', '非常に低い'),
    ]
    
    report = models.OneToOneField(EarningsReport, on_delete=models.CASCADE, related_name='sentiment_analysis')
    
    # 感情分析指標
    positive_expressions = models.PositiveIntegerField(default=0, verbose_name='ポジティブ表現数')
    negative_expressions = models.PositiveIntegerField(default=0, verbose_name='ネガティブ表現数')
    confidence_keywords = models.PositiveIntegerField(default=0, verbose_name='自信を示すキーワード数')
    uncertainty_keywords = models.PositiveIntegerField(default=0, verbose_name='不確実性キーワード数')
    risk_mentions = models.PositiveIntegerField(default=0, verbose_name='リスク言及数')
    
    # 計算指標
    sentiment_score = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='感情スコア')
    confidence_level = models.CharField(max_length=20, choices=CONFIDENCE_LEVEL_CHOICES, verbose_name='経営陣自信度')
    
    # 前期比較
    sentiment_change = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='感情スコア変化')
    confidence_change = models.CharField(max_length=50, blank=True, verbose_name='自信度変化')
    
    # 抽出されたキーワード（JSON形式で保存）
    extracted_keywords = models.TextField(blank=True, verbose_name='抽出キーワード')
    
    # 分析サマリー
    analysis_summary = models.TextField(blank=True, verbose_name='分析要約')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'earnings_sentiment_analysis'
    
    def get_extracted_keywords_dict(self):
        """抽出キーワードをdict形式で取得"""
        try:
            return json.loads(self.extracted_keywords) if self.extracted_keywords else {}
        except json.JSONDecodeError:
            return {}
    
    def set_extracted_keywords_dict(self, keywords_dict):
        """抽出キーワードをdict形式で設定"""
        self.extracted_keywords = json.dumps(keywords_dict, ensure_ascii=False)


class EarningsAlert(models.Model):
    """決算アラート設定"""
    ALERT_TYPE_CHOICES = [
        ('earnings_release', '決算発表'),
        ('report_submission', '報告書提出'),
        ('analysis_complete', '分析完了'),
        ('significant_change', '重要な変化'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    company = models.ForeignKey(CompanyEarnings, on_delete=models.CASCADE)
    
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPE_CHOICES, verbose_name='アラート種別')
    is_enabled = models.BooleanField(default=True, verbose_name='有効')
    
    # アラート条件
    days_before_earnings = models.PositiveIntegerField(default=7, verbose_name='決算何日前に通知')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'earnings_earnings_alert'
        unique_together = ['user', 'company', 'alert_type']
    
    def __str__(self):
        return f"{self.user.username} - {self.company.company_name} - {self.get_alert_type_display()}"


class AnalysisHistory(models.Model):
    """分析履歴（簡易ログ）"""
    company = models.ForeignKey(CompanyEarnings, on_delete=models.CASCADE, related_name='analysis_history')
    
    analysis_date = models.DateTimeField(auto_now_add=True)
    fiscal_year = models.CharField(max_length=10)
    quarter = models.CharField(max_length=5)
    
    # 分析結果サマリー（JSON形式）
    cashflow_summary = models.TextField(blank=True)
    sentiment_summary = models.TextField(blank=True)
    
    # 処理時間
    processing_time_seconds = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'earnings_analysis_history'
        indexes = [
            models.Index(fields=['analysis_date']),
            models.Index(fields=['company', 'fiscal_year', 'quarter']),
        ]
    
    def get_cashflow_summary_dict(self):
        try:
            return json.loads(self.cashflow_summary) if self.cashflow_summary else {}
        except json.JSONDecodeError:
            return {}
    
    def get_sentiment_summary_dict(self):
        try:
            return json.loads(self.sentiment_summary) if self.sentiment_summary else {}
        except json.JSONDecodeError:
            return {}