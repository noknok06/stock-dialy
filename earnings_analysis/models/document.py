# earnings_analysis/models/document.py（拡張版）
from django.db import models

class DocumentMetadata(models.Model):
    """書類メタデータ（分析優先度機能付き）"""
    
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
            models.Index(fields=['edinet_code', '-submit_date_time']),  # 企業詳細用
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
    
    # ========== 新規追加: 分析優先度機能 ==========
    
    # 分析適合度の高い書類種別コード
    HIGH_PRIORITY_DOC_TYPES = ['120', '130', '140']  # 決算短信、四半期報告書、有価証券報告書
    MEDIUM_PRIORITY_DOC_TYPES = ['150', '160']  # 半期報告書、その他四半期報告書
    
    # 書類種別表示名マッピング
    DOC_TYPE_DISPLAY_NAMES = {
        '120': '決算短信',
        '130': '四半期報告書',
        '140': '有価証券報告書',
        '150': '半期報告書',
        '160': 'その他四半期報告書',
        '110': '臨時報告書',
        '170': '確認書',
        '180': '内部統制報告書',
        '200': '公開買付届出書',
        '210': '意見表明報告書',
        '220': '対質問回答報告書',
        '230': '公開買付撤回届出書',
        '240': '公開買付報告書',
        '250': '株券等大量保有報告書',
        '260': '変更報告書',
        '270': '大量保有変更報告書',
        '999': 'その他',
    }
    
    @property
    def analysis_priority(self):
        """分析適合度を返す (high/medium/low)"""
        if self.doc_type_code in self.HIGH_PRIORITY_DOC_TYPES:
            return 'high'
        elif self.doc_type_code in self.MEDIUM_PRIORITY_DOC_TYPES:
            return 'medium'
        else:
            return 'low'
    
    @property
    def analysis_suitable(self):
        """分析に適しているか (True/False)"""
        return self.analysis_priority in ['high', 'medium']
    
    @property
    def doc_type_display_name(self):
        """書類種別の日本語表示名"""
        return self.DOC_TYPE_DISPLAY_NAMES.get(self.doc_type_code, f'書類種別{self.doc_type_code}')
    
    @property
    def analysis_priority_badge_class(self):
        """優先度に応じたBootstrapバッジクラス"""
        priority_classes = {
            'high': 'bg-success',
            'medium': 'bg-info', 
            'low': 'bg-secondary'
        }
        return priority_classes.get(self.analysis_priority, 'bg-secondary')
    
    @property
    def analysis_priority_display(self):
        """優先度の日本語表示"""
        priority_display = {
            'high': '分析推奨',
            'medium': '分析可能',
            'low': '分析困難'
        }
        return priority_display.get(self.analysis_priority, '分析困難')
    
    @property
    def is_financial_statement(self):
        """決算関連書類かどうか"""
        financial_types = ['120', '130', '140', '150', '160']
        return self.doc_type_code in financial_types
    
    @property
    def period_display(self):
        """期間の表示用文字列"""
        if self.period_start and self.period_end:
            if self.period_start.year == self.period_end.year:
                return f"{self.period_end.year}年{self.period_end.month}月期"
            else:
                return f"{self.period_start.year}/{self.period_start.month}-{self.period_end.year}/{self.period_end.month}"
        return "期間不明"
    
    @classmethod
    def get_recommended_for_analysis(cls, edinet_code, limit=3):
        """分析推奨書類を優先度順で返す"""
        return cls.objects.filter(
            edinet_code=edinet_code,
            legal_status='1',
            doc_type_code__in=cls.HIGH_PRIORITY_DOC_TYPES + cls.MEDIUM_PRIORITY_DOC_TYPES
        ).order_by(
            'doc_type_code',  # 書類種別順
            '-submit_date_time'  # 新しい順
        )[:limit]
    
    @classmethod
    def get_latest_financial_document(cls, edinet_code):
        """最新の決算関連書類を取得"""
        return cls.objects.filter(
            edinet_code=edinet_code,
            legal_status='1',
            doc_type_code__in=cls.HIGH_PRIORITY_DOC_TYPES
        ).order_by('-submit_date_time').first()
    
    @classmethod
    def get_documents_by_company(cls, edinet_code, analysis_suitable_first=True):
        """企業の書類を分析適合性順で取得"""
        if analysis_suitable_first:
            # 分析適合書類を先に表示
            suitable_docs = cls.objects.filter(
                edinet_code=edinet_code,
                legal_status='1',
                doc_type_code__in=cls.HIGH_PRIORITY_DOC_TYPES + cls.MEDIUM_PRIORITY_DOC_TYPES
            ).order_by('-submit_date_time')
            
            other_docs = cls.objects.filter(
                edinet_code=edinet_code,
                legal_status='1'
            ).exclude(
                doc_type_code__in=cls.HIGH_PRIORITY_DOC_TYPES + cls.MEDIUM_PRIORITY_DOC_TYPES
            ).order_by('-submit_date_time')
            
            return {
                'suitable': list(suitable_docs),
                'others': list(other_docs)
            }
        else:
            return cls.objects.filter(
                edinet_code=edinet_code,
                legal_status='1'
            ).order_by('-submit_date_time')
    
    @property
    def financial_analysis_url(self):
        """財務分析URL"""
        from django.urls import reverse
        return reverse('earnings_analysis:financial-analysis', args=[self.doc_id])
    
    @property
    def sentiment_analysis_url(self):
        """感情分析URL"""
        from django.urls import reverse
        return reverse('earnings_analysis:sentiment-analysis', args=[self.doc_id])
    
    @property
    def comprehensive_analysis_url(self):
        """包括分析URL"""
        from django.urls import reverse
        return reverse('earnings_analysis:financial-analysis', args=[self.doc_id])  # 暫定的に財務分析を使用
    
    @property
    def detail_url(self):
        """書類詳細URL"""
        from django.urls import reverse
        return reverse('earnings_analysis:document-detail-ui', args=[self.doc_id])
    
    def get_analysis_url(self, analysis_type='comprehensive'):
        """分析URLを取得（後方互換性のため残す）"""
        if analysis_type == 'comprehensive':
            return self.comprehensive_analysis_url
        elif analysis_type == 'sentiment':
            return self.sentiment_analysis_url
        elif analysis_type == 'financial':
            return self.financial_analysis_url
        else:
            return self.detail_url
    
    def has_recent_analysis(self, hours=24):
        """最近の分析実行があるかチェック"""
        from django.utils import timezone
        from datetime import timedelta
        
        recent_time = timezone.now() - timedelta(hours=hours)
        
        # 感情分析履歴をチェック
        from .sentiment import SentimentAnalysisHistory
        has_sentiment = SentimentAnalysisHistory.objects.filter(
            document=self,
            analysis_date__gte=recent_time
        ).exists()
        
        # 財務分析履歴をチェック
        from .financial import FinancialAnalysisHistory
        has_financial = FinancialAnalysisHistory.objects.filter(
            document=self,
            analysis_date__gte=recent_time
        ).exists()
        
        return has_sentiment or has_financial