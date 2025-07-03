from django.db import models

class DocumentMetadata(models.Model):
    """書類メタデータ"""
    
    # ステータス選択肢
    LEGAL_STATUS_CHOICES = [
        ('0', '閲覧期間満了'),
        ('1', '縦覧中'),
        ('2', '延長期間中'),
    ]
    
    WITHDRAWAL_STATUS_CHOICES = [
        ('0', '通常'),
        ('1', '取下書'),
        ('2', '取下げられた書類'),
    ]
    
    # 基本情報
    doc_id = models.CharField('書類管理番号', max_length=8, unique=True, db_index=True)
    edinet_code = models.CharField('EDINETコード', max_length=6, db_index=True)
    securities_code = models.CharField('証券コード', max_length=5, blank=True, db_index=True)
    company_name = models.CharField('企業名', max_length=255, db_index=True)
    
    # 書類分類
    fund_code = models.CharField('ファンドコード', max_length=6, blank=True)
    ordinance_code = models.CharField('府令コード', max_length=3)
    form_code = models.CharField('様式コード', max_length=6)
    doc_type_code = models.CharField('書類種別コード', max_length=3, db_index=True)
    
    # 期間情報
    period_start = models.DateField('期間開始日', blank=True, null=True)
    period_end = models.DateField('期間終了日', blank=True, null=True)
    submit_date_time = models.DateTimeField('提出日時', db_index=True)
    file_date = models.DateField('ファイル日付', db_index=True)
    
    # 書類情報
    doc_description = models.TextField('書類概要')
    
    # 利用可能フォーマット
    xbrl_flag = models.BooleanField('XBRL有無', default=False)
    pdf_flag = models.BooleanField('PDF有無', default=False)
    attach_doc_flag = models.BooleanField('添付文書有無', default=False)
    english_doc_flag = models.BooleanField('英文ファイル有無', default=False)
    csv_flag = models.BooleanField('CSV有無', default=False)
    
    # ステータス
    legal_status = models.CharField('縦覧区分', max_length=1, choices=LEGAL_STATUS_CHOICES, default='1', db_index=True)
    withdrawal_status = models.CharField('取下区分', max_length=1, choices=WITHDRAWAL_STATUS_CHOICES, default='0')
    doc_info_edit_status = models.CharField('書類情報修正区分', max_length=1, default='0')
    disclosure_status = models.CharField('開示不開示区分', max_length=1, default='0')
    
    # 管理情報
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'earnings_analysis_document_metadata'
        verbose_name = '書類メタデータ'
        verbose_name_plural = '書類メタデータ一覧'
        ordering = ['-submit_date_time']
        indexes = [
            models.Index(fields=['securities_code', 'file_date']),
            models.Index(fields=['doc_type_code', 'legal_status']),
            models.Index(fields=['company_name', 'submit_date_time']),
        ]

    def __str__(self):
        return f"{self.doc_id}: {self.company_name} - {self.doc_description[:50]}"
    
    @property
    def available_formats(self):
        """利用可能フォーマット一覧"""
        return {
            'pdf': self.pdf_flag,
            'xbrl': self.xbrl_flag,
            'csv': self.csv_flag,
            'attach': self.attach_doc_flag,
            'english': self.english_doc_flag,
        }