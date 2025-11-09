# analysis_template/models.py
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from company_master.models import CompanyMaster


class AnalysisTemplate(models.Model):
    """分析テンプレートモデル"""
    name = models.CharField(
        max_length=200,
        verbose_name="テンプレート名"
    )
    description = models.TextField(
        blank=True,
        verbose_name="説明"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='analysis_templates',
        verbose_name="作成者"
    )
    companies = models.ManyToManyField(
        CompanyMaster,
        through='TemplateCompany',
        related_name='analysis_templates',
        verbose_name="対象企業"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        verbose_name = "分析テンプレート"
        verbose_name_plural = "分析テンプレート"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"
    
    def get_company_count(self):
        """登録企業数を取得"""
        return self.companies.count()
    
    def get_metrics_summary(self):
        """指標の集計情報を取得"""
        metrics = TemplateMetrics.objects.filter(template=self)
        return {
            'total': metrics.count(),
            'companies': metrics.values('company').distinct().count()
        }


class TemplateCompany(models.Model):
    """テンプレートと企業の中間テーブル"""
    template = models.ForeignKey(
        AnalysisTemplate,
        on_delete=models.CASCADE,
        verbose_name="テンプレート"
    )
    company = models.ForeignKey(
        CompanyMaster,
        on_delete=models.CASCADE,
        verbose_name="企業"
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name="表示順"
    )
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="追加日時")
    
    class Meta:
        verbose_name = "テンプレート企業"
        verbose_name_plural = "テンプレート企業"
        ordering = ['display_order', 'added_at']
        unique_together = [['template', 'company']]
    
    def __str__(self):
        return f"{self.template.name} - {self.company.name}"


class MetricDefinition(models.Model):
    """指標定義マスター"""
    METRIC_TYPES = [
        ('percentage', 'パーセント(%)'),
        ('ratio', '倍率'),
        ('amount', '金額(億円)'),
        ('number', '数値'),
        ('rate', '率'),
    ]
    
    METRIC_GROUPS = [
        ('profitability', '収益性'),
        ('growth', '成長性'),
        ('valuation', 'バリュエーション'),
        ('dividend', '配当'),
        ('financial_health', '財務健全性'),
        ('efficiency', '効率性'),
        ('scale', '規模・実績'),
    ]
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="指標名"
    )
    display_name = models.CharField(
        max_length=100,
        verbose_name="表示名"
    )
    metric_type = models.CharField(
        max_length=20,
        choices=METRIC_TYPES,
        default='number',
        verbose_name="指標タイプ"
    )
    metric_group = models.CharField(
        max_length=30,
        choices=METRIC_GROUPS,
        default='profitability',
        verbose_name="指標グループ"
    )
    description = models.TextField(
        blank=True,
        verbose_name="説明"
    )
    unit = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="単位"
    )
    min_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="最小値"
    )
    max_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="最大値"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="有効"
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name="表示順"
    )
    chart_suitable = models.BooleanField(
        default=True,
        verbose_name="チャート表示に適している"
    )
    
    class Meta:
        verbose_name = "指標定義"
        verbose_name_plural = "指標定義"
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.display_name
    
    def get_formatted_unit(self):
        """フォーマット済みの単位を取得"""
        if self.unit:
            return self.unit
        
        unit_map = {
            'percentage': '%',
            'ratio': '倍',
            'amount': '億円',
            'rate': '%',
        }
        return unit_map.get(self.metric_type, '')


class TemplateMetrics(models.Model):
    """テンプレート指標値"""
    template = models.ForeignKey(
        AnalysisTemplate,
        on_delete=models.CASCADE,
        related_name='metrics',
        verbose_name="テンプレート"
    )
    company = models.ForeignKey(
        CompanyMaster,
        on_delete=models.CASCADE,
        related_name='template_metrics',
        verbose_name="企業"
    )
    metric_definition = models.ForeignKey(
        MetricDefinition,
        on_delete=models.CASCADE,
        related_name='template_metrics',
        verbose_name="指標定義"
    )
    value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="値"
    )
    fiscal_year = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="会計年度"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="備考"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        verbose_name = "テンプレート指標"
        verbose_name_plural = "テンプレート指標"
        ordering = ['company', 'metric_definition__display_order']
        unique_together = [['template', 'company', 'metric_definition', 'fiscal_year']]
        indexes = [
            models.Index(fields=['template', 'company']),
            models.Index(fields=['metric_definition']),
        ]
    
    def __str__(self):
        return f"{self.company.name} - {self.metric_definition.display_name}: {self.value}"
    
    def get_formatted_value(self):
        """フォーマット済みの値を取得"""
        unit = self.metric_definition.get_formatted_unit()
        if self.metric_definition.metric_type in ['percentage', 'rate']:
            return f"{self.value}{unit}"
        elif self.metric_definition.metric_type == 'amount':
            return f"{self.value:,.0f}{unit}"
        elif self.metric_definition.metric_type == 'ratio':
            return f"{self.value}{unit}"
        else:
            return f"{self.value}"


class IndustryBenchmark(models.Model):
    """業種別ベンチマーク"""
    industry_code = models.CharField(
        max_length=10,
        verbose_name="業種コード"
    )
    industry_name = models.CharField(
        max_length=100,
        verbose_name="業種名"
    )
    metric_definition = models.ForeignKey(
        MetricDefinition,
        on_delete=models.CASCADE,
        related_name='industry_benchmarks',
        verbose_name="指標定義"
    )
    average_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="業種平均値"
    )
    median_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="業種中央値"
    )
    lower_quartile = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="下位25%値"
    )
    upper_quartile = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="上位25%値"
    )
    excellent_threshold = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="優良基準値"
    )
    poor_threshold = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="要注意基準値"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="備考"
    )
    fiscal_year = models.CharField(
        max_length=10,
        verbose_name="会計年度"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        verbose_name = "業種別ベンチマーク"
        verbose_name_plural = "業種別ベンチマーク"
        ordering = ['industry_code', 'metric_definition__display_order']
        unique_together = [['industry_code', 'metric_definition', 'fiscal_year']]
        indexes = [
            models.Index(fields=['industry_code', 'metric_definition']),
        ]
    
    def __str__(self):
        return f"{self.industry_name} - {self.metric_definition.display_name}: {self.average_value}"
    
    def get_evaluation(self, value):
        """値の評価を返す"""
        if not value:
            return 'unknown', '不明'
        
        value = float(value)
        
        if self.excellent_threshold and value >= float(self.excellent_threshold):
            return 'excellent', '優良'
        elif self.poor_threshold and value <= float(self.poor_threshold):
            return 'poor', '要注意'
        elif self.upper_quartile and value >= float(self.upper_quartile):
            return 'good', '良好'
        elif self.lower_quartile and value <= float(self.lower_quartile):
            return 'below_average', '平均以下'
        else:
            return 'average', '平均的'
    
    def normalize_value(self, value):
        """値を0-100のスケールに正規化（業種平均=50）"""
        if not value or not self.average_value:
            return None
        
        value = float(value)
        avg = float(self.average_value)
        
        if avg == 0:
            return 50
        
        # 業種平均を50として正規化
        normalized = (value / avg) * 50
        
        # 0-100の範囲に制限
        return max(0, min(100, normalized))


class CompanyScore(models.Model):
    """企業の総合スコア"""
    template = models.ForeignKey(
        'AnalysisTemplate',
        on_delete=models.CASCADE,
        related_name='company_scores',
        verbose_name="テンプレート"
    )
    company = models.ForeignKey(
        CompanyMaster,
        on_delete=models.CASCADE,
        related_name='analysis_scores',
        verbose_name="企業"
    )
    total_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="総合スコア"
    )
    profitability_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="収益性スコア"
    )
    growth_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="成長性スコア"
    )
    valuation_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="バリュエーションスコア"
    )
    financial_health_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="財務健全性スコア"
    )
    data_completeness = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="データ完全性"
    )
    rank = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="順位"
    )
    calculated_at = models.DateTimeField(auto_now=True, verbose_name="計算日時")
    
    class Meta:
        verbose_name = "企業スコア"
        verbose_name_plural = "企業スコア"
        ordering = ['-total_score']
        unique_together = [['template', 'company']]
        indexes = [
            models.Index(fields=['template', '-total_score']),
        ]
    
    def __str__(self):
        return f"{self.company.name} - 総合スコア: {self.total_score}"
    
    def get_grade(self):
        """スコアに基づく評価グレードを返す"""
        score = float(self.total_score)
        if score >= 80:
            return 'S', '秀'
        elif score >= 70:
            return 'A', '優'
        elif score >= 60:
            return 'B', '良'
        elif score >= 50:
            return 'C', '可'
        else:
            return 'D', '要改善'