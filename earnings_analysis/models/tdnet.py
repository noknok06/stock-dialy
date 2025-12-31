# earnings_analysis/models/tdnet.py

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class TDNETDisclosure(models.Model):
    """TDNET開示情報マスタ"""
    
    DISCLOSURE_TYPE_CHOICES = [
        ('earnings', '決算短信'),
        ('forecast', '業績予想修正'),
        ('dividend', '配当予想修正'),
        ('buyback', '自己株式取得'),
        ('merger', '合併・買収'),
        ('offering', '募集・発行'),
        ('governance', 'ガバナンス'),
        ('other', 'その他'),
    ]
    
    # 基本情報
    disclosure_id = models.CharField(
        '開示ID',
        max_length=50,
        unique=True,
        db_index=True,
        help_text='TDNET開示ID'
    )
    company_code = models.CharField(
        '証券コード',
        max_length=10,
        db_index=True,
        help_text='証券コード（4桁）'
    )
    company_name = models.CharField(
        '企業名',
        max_length=255,
        db_index=True
    )
    
    # 開示情報
    disclosure_date = models.DateTimeField(
        '開示日時',
        db_index=True,
        help_text='適時開示された日時'
    )
    disclosure_type = models.CharField(
        '開示種別',
        max_length=50,
        choices=DISCLOSURE_TYPE_CHOICES,
        db_index=True,
        default='other'
    )
    disclosure_category = models.CharField(
        '開示区分',
        max_length=100,
        blank=True,
        help_text='詳細な開示区分'
    )
    title = models.CharField(
        'タイトル',
        max_length=500
    )
    summary = models.TextField(
        '概要',
        blank=True,
        help_text='開示内容の概要'
    )
    
    # データ
    raw_data = models.JSONField(
        '元データ',
        default=dict,
        help_text='TDNET APIから取得した生データ'
    )
    pdf_url = models.URLField(
        'PDF URL',
        max_length=500,
        blank=True,
        help_text='PDFファイルのURL'
    )
    pdf_cached = models.BooleanField(
        'PDF取得済み',
        default=False,
        help_text='PDFファイルがローカルに保存済みか'
    )
    pdf_file_path = models.CharField(
        'PDFパス',
        max_length=500,
        blank=True,
        help_text='ローカルに保存されたPDFのパス'
    )
    
    # 既存システム連携
    company_master = models.ForeignKey(
        'company_master.CompanyMaster',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tdnet_disclosures',
        verbose_name='企業マスタ',
        help_text='company_masterテーブルへの参照'
    )
    
    # ステータス
    is_processed = models.BooleanField(
        '処理済み',
        default=False,
        help_text='データ処理が完了したか'
    )
    report_generated = models.BooleanField(
        'レポート生成済み',
        default=False,
        help_text='AIレポートが生成済みか'
    )
    
    # メタ情報
    created_at = models.DateTimeField(
        '作成日時',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        '更新日時',
        auto_now=True
    )
    
    class Meta:
        db_table = 'earnings_tdnet_disclosure'
        verbose_name = 'TDNET開示情報'
        verbose_name_plural = 'TDNET開示情報一覧'
        ordering = ['-disclosure_date']
        indexes = [
            models.Index(fields=['company_code', '-disclosure_date'], name='idx_tdnet_disc_co_date'),
            models.Index(fields=['disclosure_type', '-disclosure_date'], name='idx_tdnet_disc_type_date'),
            models.Index(fields=['is_processed', 'report_generated'], name='idx_tdnet_disc_status'),
        ]
    
    def __str__(self):
        return f"{self.disclosure_id}: {self.company_name} - {self.title[:50]}"
    
    @property
    def has_pdf(self):
        return bool(self.pdf_url)
    
    @property
    def display_type(self):
        return dict(self.DISCLOSURE_TYPE_CHOICES).get(self.disclosure_type, self.disclosure_type)


class TDNETReport(models.Model):
    """TDNETレポート（AI生成）"""
    
    STATUS_CHOICES = [
        ('draft', '下書き'),
        ('published', '公開'),
        ('archived', 'アーカイブ'),
    ]
    
    REPORT_TYPE_CHOICES = [
        ('earnings', '決算短信'),
        ('forecast', '業績予想'),
        ('dividend', '配当'),
        ('merger', '合併・買収'),
        ('offering', '募集・発行'),
        ('governance', 'ガバナンス'),
        ('other', 'その他'),
    ]
    
    SIGNAL_CHOICES = [
        ('strong_positive', '強気'),
        ('positive', 'やや強気'),
        ('neutral', '中立'),
        ('negative', 'やや弱気'),
        ('strong_negative', '弱気'),
    ]
    
    # 基本情報
    report_id = models.CharField(
        'レポートID',
        max_length=100,
        unique=True,
        db_index=True
    )
    disclosure = models.ForeignKey(
        TDNETDisclosure,
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name='元開示情報'
    )
    
    # レポート情報
    title = models.CharField('レポートタイトル', max_length=500)
    report_type = models.CharField(
        'レポート種別',
        max_length=50,
        choices=REPORT_TYPE_CHOICES,
        db_index=True,
        default='other'
    )
    
    # 採点・評価（新規追加）
    overall_score = models.IntegerField(
        '総合スコア',
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='0-100の総合評価スコア'
    )
    signal = models.CharField(
        '投資シグナル',
        max_length=20,
        choices=SIGNAL_CHOICES,
        default='neutral',
        help_text='投資判断シグナル'
    )
    one_line_summary = models.CharField(
        '一言サマリー',
        max_length=100,
        blank=True,
        help_text='スマホ画面で最初に表示する一言'
    )
    
    # 内容
    summary = models.TextField('要約', help_text='レポートの要約（3-5文）')
    key_points = models.JSONField('重要ポイント', default=list)
    analysis = models.TextField('分析', blank=True)
    
    # 採点詳細（新規追加）
    score_details = models.JSONField(
        '採点詳細',
        default=dict,
        help_text='各項目の採点詳細'
    )
    
    # ステータス
    status = models.CharField(
        'ステータス',
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True
    )
    
    # 生成情報
    generated_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_tdnet_reports',
        verbose_name='生成者'
    )
    generation_model = models.CharField('生成モデル', max_length=100, default='gemini-pro')
    generation_prompt = models.TextField('生成プロンプト', blank=True)
    generation_token_count = models.IntegerField(
        '生成トークン数',
        default=0,
        validators=[MinValueValidator(0)]
    )
    
    # 統計
    view_count = models.IntegerField(
        '閲覧数',
        default=0,
        validators=[MinValueValidator(0)]
    )
    
    # 既存システム連携
    related_stock_diaries = models.ManyToManyField(
        'stockdiary.StockDiary',
        blank=True,
        related_name='related_tdnet_reports',
        verbose_name='関連投資記録'
    )
    
    # メタ情報
    published_at = models.DateTimeField('公開日時', null=True, blank=True, db_index=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    
    class Meta:
        db_table = 'earnings_tdnet_report'
        verbose_name = 'TDNETレポート'
        verbose_name_plural = 'TDNETレポート一覧'
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', '-published_at'], name='idx_tdnet_rep_status_pub'),
            models.Index(fields=['report_type', '-published_at'], name='idx_tdnet_rep_type_pub'),
            models.Index(fields=['disclosure', '-created_at'], name='idx_tdnet_rep_disc_date'),
        ]
    
    def __str__(self):
        return f"{self.report_id}: {self.title[:50]}"
    
    @property
    def is_published(self):
        return self.status == 'published'
    
    @property
    def display_type(self):
        return dict(self.REPORT_TYPE_CHOICES).get(self.report_type, self.report_type)
    
    @property
    def signal_display(self):
        return dict(self.SIGNAL_CHOICES).get(self.signal, self.signal)
    
    @property
    def signal_color(self):
        """シグナルに応じた色を返す"""
        colors = {
            'strong_positive': '#22c55e',
            'positive': '#84cc16',
            'neutral': '#6b7280',
            'negative': '#f97316',
            'strong_negative': '#ef4444',
        }
        return colors.get(self.signal, '#6b7280')
    
    @property
    def score_grade(self):
        """スコアに応じたグレードを返す"""
        if self.overall_score >= 80:
            return 'A'
        elif self.overall_score >= 60:
            return 'B'
        elif self.overall_score >= 40:
            return 'C'
        elif self.overall_score >= 20:
            return 'D'
        return 'E'
    
    def publish(self):
        if self.status != 'published':
            self.status = 'published'
            self.published_at = timezone.now()
            self.save(update_fields=['status', 'published_at', 'updated_at'])
    
    def unpublish(self):
        if self.status == 'published':
            self.status = 'draft'
            self.published_at = None
            self.save(update_fields=['status', 'published_at', 'updated_at'])
    
    def increment_view_count(self):
        self.view_count = models.F('view_count') + 1
        self.save(update_fields=['view_count'])


class TDNETReportSection(models.Model):
    """TDNETレポートセクション（構造化）"""
    
    SECTION_TYPE_CHOICES = [
        ('overview', '概要'),
        ('financial', '財務情報'),
        ('forecast', '業績予想'),
        ('analysis', '分析'),
        ('risk', 'リスク'),
        ('opportunity', '機会'),
        ('conclusion', '結論'),
        ('other', 'その他'),
    ]
    
    report = models.ForeignKey(
        TDNETReport,
        on_delete=models.CASCADE,
        related_name='sections',
        verbose_name='レポート'
    )
    
    section_type = models.CharField(
        'セクション種別',
        max_length=50,
        choices=SECTION_TYPE_CHOICES,
        default='other'
    )
    title = models.CharField('セクションタイトル', max_length=255)
    content = models.TextField('内容')
    order = models.IntegerField('表示順', default=0, validators=[MinValueValidator(0)])
    
    data = models.JSONField('構造化データ', default=dict, blank=True, null=True)
    
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    
    class Meta:
        db_table = 'earnings_tdnet_report_section'
        verbose_name = 'TDNETレポートセクション'
        verbose_name_plural = 'TDNETレポートセクション一覧'
        ordering = ['report', 'order']
        unique_together = [['report', 'order']]
        indexes = [
            models.Index(fields=['report', 'order'], name='idx_tdnet_sec_rep_order'),
        ]
    
    def __str__(self):
        return f"{self.report.report_id} - {self.title}"
    
    @property
    def display_type(self):
        return dict(self.SECTION_TYPE_CHOICES).get(self.section_type, self.section_type)