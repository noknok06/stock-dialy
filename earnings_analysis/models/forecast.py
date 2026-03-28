# earnings_analysis/models/forecast.py
"""
予想達成率・予想信頼性スコア モデル

会社が発表した業績予想と実績を記録し、
複数年にわたる予想達成の信頼性を数値化する。
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class EarningsForecast(models.Model):
    """
    業績予想 vs 実績レコード

    1社 × 1期 の予想値と実績値を保持する。
    決算短信や業績予想修正開示から登録される。
    """

    PERIOD_TYPE_CHOICES = [
        ('annual', '通期'),
        ('q1', '第1四半期'),
        ('q2', '第2四半期'),
        ('q3', '第3四半期'),
        ('half', '上半期'),
    ]

    SOURCE_CHOICES = [
        ('tdnet', 'TDNET開示'),
        ('edinet', 'EDINET'),
        ('manual', '手動入力'),
    ]

    # 企業識別
    company_code = models.CharField(
        '証券コード',
        max_length=10,
        db_index=True,
        help_text='4桁証券コード'
    )
    company_name = models.CharField(
        '企業名',
        max_length=255,
        blank=True
    )

    # 期間情報
    fiscal_year = models.IntegerField(
        '会計年度',
        help_text='例: 2024（2024年3月期 = 2024）',
        db_index=True
    )
    period_type = models.CharField(
        '期間種別',
        max_length=10,
        choices=PERIOD_TYPE_CHOICES,
        default='annual'
    )

    # 予想値（期初または修正後）
    forecast_net_sales = models.DecimalField(
        '予想売上高',
        max_digits=20, decimal_places=0,
        null=True, blank=True,
        help_text='単位: 百万円'
    )
    forecast_operating_income = models.DecimalField(
        '予想営業利益',
        max_digits=20, decimal_places=0,
        null=True, blank=True
    )
    forecast_ordinary_income = models.DecimalField(
        '予想経常利益',
        max_digits=20, decimal_places=0,
        null=True, blank=True
    )
    forecast_net_income = models.DecimalField(
        '予想当期純利益',
        max_digits=20, decimal_places=0,
        null=True, blank=True
    )
    forecast_eps = models.DecimalField(
        '予想EPS',
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text='1株当たり当期純利益（円）'
    )

    # 予想修正情報
    forecast_revision_count = models.SmallIntegerField(
        '予想修正回数',
        default=0,
        help_text='当期中に何回業績予想を修正したか'
    )
    forecast_announced_date = models.DateField(
        '予想発表日',
        null=True, blank=True
    )

    # 実績値（確定後に更新）
    actual_net_sales = models.DecimalField(
        '実績売上高',
        max_digits=20, decimal_places=0,
        null=True, blank=True
    )
    actual_operating_income = models.DecimalField(
        '実績営業利益',
        max_digits=20, decimal_places=0,
        null=True, blank=True
    )
    actual_ordinary_income = models.DecimalField(
        '実績経常利益',
        max_digits=20, decimal_places=0,
        null=True, blank=True
    )
    actual_net_income = models.DecimalField(
        '実績当期純利益',
        max_digits=20, decimal_places=0,
        null=True, blank=True
    )
    actual_eps = models.DecimalField(
        '実績EPS',
        max_digits=12, decimal_places=2,
        null=True, blank=True
    )
    actual_announced_date = models.DateField(
        '実績発表日',
        null=True, blank=True
    )

    # 達成率（自動計算）
    achievement_rate_net_sales = models.DecimalField(
        '売上高達成率(%)',
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        help_text='実績 / 予想 × 100'
    )
    achievement_rate_operating_income = models.DecimalField(
        '営業利益達成率(%)',
        max_digits=8, decimal_places=2,
        null=True, blank=True
    )
    achievement_rate_ordinary_income = models.DecimalField(
        '経常利益達成率(%)',
        max_digits=8, decimal_places=2,
        null=True, blank=True
    )
    achievement_rate_net_income = models.DecimalField(
        '当期純利益達成率(%)',
        max_digits=8, decimal_places=2,
        null=True, blank=True
    )

    # データソース
    source = models.CharField(
        'データソース',
        max_length=20,
        choices=SOURCE_CHOICES,
        default='tdnet'
    )
    disclosure = models.ForeignKey(
        'TDNETDisclosure',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='earnings_forecasts',
        verbose_name='元開示情報'
    )

    # フラグ
    has_actual = models.BooleanField(
        '実績確定済み',
        default=False,
        help_text='実績値が登録されているか'
    )

    # タイムスタンプ
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'earnings_forecast_record'
        verbose_name = '業績予想実績レコード'
        verbose_name_plural = '業績予想実績一覧'
        ordering = ['-fiscal_year', 'company_code']
        unique_together = [['company_code', 'fiscal_year', 'period_type']]
        indexes = [
            models.Index(fields=['company_code', '-fiscal_year'], name='idx_forecast_co_year'),
            models.Index(fields=['has_actual'], name='idx_forecast_has_actual'),
        ]

    def __str__(self):
        return f"{self.company_code} {self.fiscal_year}年度 {self.get_period_type_display()}"

    def calculate_achievement_rates(self):
        """実績値から達成率を計算してフィールドに反映する"""

        def _rate(actual, forecast):
            if actual is None or forecast is None:
                return None
            if forecast == 0:
                return None
            return (Decimal(str(actual)) / Decimal(str(forecast)) * 100).quantize(Decimal('0.01'))

        self.achievement_rate_net_sales = _rate(self.actual_net_sales, self.forecast_net_sales)
        self.achievement_rate_operating_income = _rate(
            self.actual_operating_income, self.forecast_operating_income
        )
        self.achievement_rate_ordinary_income = _rate(
            self.actual_ordinary_income, self.forecast_ordinary_income
        )
        self.achievement_rate_net_income = _rate(self.actual_net_income, self.forecast_net_income)

    def save(self, *args, **kwargs):
        if self.actual_net_sales is not None or self.actual_net_income is not None:
            self.has_actual = True
            self.calculate_achievement_rates()
        super().save(*args, **kwargs)

    @property
    def composite_achievement_rate(self):
        """
        代表的な達成率（営業利益 > 純利益 > 売上高の優先順位）
        投資判断で最も重要な指標を返す
        """
        if self.achievement_rate_operating_income is not None:
            return float(self.achievement_rate_operating_income)
        if self.achievement_rate_net_income is not None:
            return float(self.achievement_rate_net_income)
        if self.achievement_rate_net_sales is not None:
            return float(self.achievement_rate_net_sales)
        return None

    @property
    def achievement_label(self):
        """達成率に応じたラベル"""
        rate = self.composite_achievement_rate
        if rate is None:
            return 'unknown', '未確定'
        if rate >= 120:
            return 'exceeded', '大幅超過'
        if rate >= 105:
            return 'beat', '超過達成'
        if rate >= 95:
            return 'met', 'ほぼ達成'
        if rate >= 80:
            return 'miss', '未達'
        return 'big_miss', '大幅未達'


class ForecastReliabilityScore(models.Model):
    """
    予想信頼性スコア（企業別・集計値）

    複数年分の EarningsForecast を集計し、
    その企業の予想がどれだけ信頼できるかを数値化する。
    """

    TENDENCY_CHOICES = [
        ('very_conservative', '超保守的（大幅超過が常態）'),
        ('conservative', '保守的（継続的に超過）'),
        ('accurate', '精度高（±5%以内）'),
        ('optimistic', '楽観的（未達傾向）'),
        ('very_optimistic', '過度に楽観的（大幅未達が常態）'),
        ('unknown', '判断不可'),
    ]

    GRADE_CHOICES = [
        ('S', 'S（最高信頼性）'),
        ('A', 'A（高信頼性）'),
        ('B', 'B（標準）'),
        ('C', 'C（やや不安）'),
        ('D', 'D（要注意）'),
        ('N', 'N（データ不足）'),
    ]

    # 企業識別
    company_code = models.CharField(
        '証券コード',
        max_length=10,
        unique=True,
        db_index=True
    )
    company_name = models.CharField(
        '企業名',
        max_length=255,
        blank=True
    )

    # 集計基本情報
    years_tracked = models.SmallIntegerField(
        '追跡年数',
        default=0,
        help_text='実績データが揃っている年数'
    )
    earliest_fiscal_year = models.IntegerField(
        '最古会計年度',
        null=True, blank=True
    )
    latest_fiscal_year = models.IntegerField(
        '最新会計年度',
        null=True, blank=True
    )

    # 達成率統計
    avg_achievement_rate = models.DecimalField(
        '平均達成率(%)',
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        help_text='全期間の代表達成率の平均'
    )
    std_achievement_rate = models.DecimalField(
        '達成率標準偏差',
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        help_text='低いほど予想が安定している'
    )
    min_achievement_rate = models.DecimalField(
        '最低達成率(%)',
        max_digits=8, decimal_places=2,
        null=True, blank=True
    )
    max_achievement_rate = models.DecimalField(
        '最高達成率(%)',
        max_digits=8, decimal_places=2,
        null=True, blank=True
    )

    # 達成カウント
    beat_count = models.SmallIntegerField('超過達成回数（≥105%）', default=0)
    met_count = models.SmallIntegerField('達成回数（95-105%）', default=0)
    miss_count = models.SmallIntegerField('未達回数（<95%）', default=0)

    # 予想傾向
    forecast_tendency = models.CharField(
        '予想傾向',
        max_length=20,
        choices=TENDENCY_CHOICES,
        default='unknown'
    )

    # 信頼性スコア（0-100）
    reliability_score = models.IntegerField(
        '信頼性スコア',
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='予想の信頼性。高いほど予想通りに動く（保守的傾向も加点）'
    )
    grade = models.CharField(
        'グレード',
        max_length=2,
        choices=GRADE_CHOICES,
        default='N'
    )

    # 投資判断への影響
    investment_signal = models.CharField(
        '投資シグナル',
        max_length=20,
        choices=[
            ('strong_positive', '強い買い（超保守×高信頼）'),
            ('positive', '買い（保守×信頼）'),
            ('neutral', '中立'),
            ('caution', '注意（楽観傾向）'),
            ('warning', '警戒（大幅未達常態）'),
            ('insufficient_data', 'データ不足'),
        ],
        default='insufficient_data'
    )
    investment_signal_reason = models.TextField(
        '判断理由',
        blank=True
    )

    # 直近傾向（改善/悪化）
    recent_trend = models.CharField(
        '直近傾向',
        max_length=20,
        choices=[
            ('improving', '改善中'),
            ('stable', '安定'),
            ('declining', '悪化中'),
            ('unknown', '不明'),
        ],
        default='unknown'
    )

    # メタ
    last_calculated = models.DateTimeField('最終計算日時', auto_now=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)

    class Meta:
        db_table = 'earnings_forecast_reliability'
        verbose_name = '予想信頼性スコア'
        verbose_name_plural = '予想信頼性スコア一覧'
        ordering = ['-reliability_score']
        indexes = [
            models.Index(fields=['-reliability_score'], name='idx_reliability_score'),
            models.Index(fields=['investment_signal'], name='idx_reliability_signal'),
            models.Index(fields=['grade'], name='idx_reliability_grade'),
        ]

    def __str__(self):
        return f"{self.company_code} {self.grade}({self.reliability_score}) {self.get_forecast_tendency_display()}"

    @property
    def beat_rate(self):
        """超過達成率（%）"""
        total = self.beat_count + self.met_count + self.miss_count
        if total == 0:
            return 0
        return round(self.beat_count / total * 100, 1)

    @property
    def miss_rate(self):
        """未達率（%）"""
        total = self.beat_count + self.met_count + self.miss_count
        if total == 0:
            return 0
        return round(self.miss_count / total * 100, 1)

    @property
    def signal_color(self):
        colors = {
            'strong_positive': '#22c55e',
            'positive': '#84cc16',
            'neutral': '#6b7280',
            'caution': '#f97316',
            'warning': '#ef4444',
            'insufficient_data': '#475569',
        }
        return colors.get(self.investment_signal, '#6b7280')

    @property
    def grade_color(self):
        colors = {
            'S': '#f59e0b',
            'A': '#22c55e',
            'B': '#3b82f6',
            'C': '#f97316',
            'D': '#ef4444',
            'N': '#475569',
        }
        return colors.get(self.grade, '#475569')
