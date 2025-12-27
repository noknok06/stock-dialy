# earnings_analysis/models/tdnet.py

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
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
        """PDFが利用可能か"""
        return bool(self.pdf_url)
    
    @property
    def display_type(self):
        """開示種別の表示名"""
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
    
    # 基本情報
    report_id = models.CharField(
        'レポートID',
        max_length=100,
        unique=True,
        db_index=True,
        help_text='レポートの一意識別子'
    )
    disclosure = models.ForeignKey(
        TDNETDisclosure,
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name='元開示情報',
        help_text='このレポートの元となる開示情報'
    )
    
    # レポート情報
    title = models.CharField(
        'レポートタイトル',
        max_length=500,
        help_text='レポートのタイトル'
    )
    report_type = models.CharField(
        'レポート種別',
        max_length=50,
        choices=REPORT_TYPE_CHOICES,
        db_index=True,
        default='other'
    )
    
    # 内容
    summary = models.TextField(
        '要約',
        help_text='レポートの要約（3-5文）'
    )
    key_points = models.JSONField(
        '重要ポイント',
        default=list,
        help_text='重要なポイントのリスト'
    )
    analysis = models.TextField(
        '分析',
        blank=True,
        help_text='詳細な分析内容'
    )
    
    # ステータス
    status = models.CharField(
        'ステータス',
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True,
        help_text='公開状態'
    )
    
    # 生成情報
    generated_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_tdnet_reports',
        verbose_name='生成者',
        help_text='レポートを生成した管理者'
    )
    generation_model = models.CharField(
        '生成モデル',
        max_length=100,
        default='gemini-pro',
        help_text='使用したAIモデル'
    )
    generation_prompt = models.TextField(
        '生成プロンプト',
        blank=True,
        help_text='AIに送信したプロンプト'
    )
    generation_token_count = models.IntegerField(
        '生成トークン数',
        default=0,
        validators=[MinValueValidator(0)],
        help_text='生成に使用したトークン数'
    )
    
    # 統計
    view_count = models.IntegerField(
        '閲覧数',
        default=0,
        validators=[MinValueValidator(0)],
        help_text='レポートの閲覧回数'
    )
    
    # 既存システム連携
    related_stock_diaries = models.ManyToManyField(
        'stockdiary.StockDiary',
        blank=True,
        related_name='related_tdnet_reports',
        verbose_name='関連投資記録',
        help_text='このレポートに関連する投資記録'
    )
    
    # メタ情報
    published_at = models.DateTimeField(
        '公開日時',
        null=True,
        blank=True,
        db_index=True,
        help_text='レポートが公開された日時'
    )
    created_at = models.DateTimeField(
        '作成日時',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        '更新日時',
        auto_now=True
    )
    
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
        """公開されているか"""
        return self.status == 'published'
    
    @property
    def display_type(self):
        """レポート種別の表示名"""
        return dict(self.REPORT_TYPE_CHOICES).get(self.report_type, self.report_type)
    
    def publish(self):
        """レポートを公開"""
        if self.status != 'published':
            self.status = 'published'
            self.published_at = timezone.now()
            self.save(update_fields=['status', 'published_at', 'updated_at'])
    
    def unpublish(self):
        """レポートを非公開に"""
        if self.status == 'published':
            self.status = 'draft'
            self.published_at = None
            self.save(update_fields=['status', 'published_at', 'updated_at'])
    
    def increment_view_count(self):
        """閲覧数をインクリメント"""
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
    title = models.CharField(
        'セクションタイトル',
        max_length=255
    )
    content = models.TextField(
        '内容',
        help_text='セクションの本文'
    )
    order = models.IntegerField(
        '表示順',
        default=0,
        validators=[MinValueValidator(0)],
        help_text='セクションの表示順序'
    )
    
    # データ
    data = models.JSONField(
        '構造化データ',
        default=dict,
        blank=True,
        null=True,  # ← これがあるか確認
        help_text='セクション固有の構造化データ'
    )
    
    created_at = models.DateTimeField(
        '作成日時',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        '更新日時',
        auto_now=True
    )
    
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
        """セクション種別の表示名"""
        return dict(self.SECTION_TYPE_CHOICES).get(self.section_type, self.section_type)
