# earnings_analysis/models/document.py（書類種別表示名対応版・調整済み）
from django.db import models
from django.utils import timezone
from datetime import date, datetime, timedelta

class DocumentMetadata(models.Model):
    """書類メタデータ（表示名対応版）"""
    
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
            models.Index(fields=['edinet_code', '-submit_date_time']),
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
    
    # ========== 書類種別表示名マッピング（調整版） ==========

    # 分析適合度の高い書類種別コード
    HIGH_PRIORITY_DOC_TYPES = ['120', '160', '030']  # 有価証券報告書、半期報告書、有価証券届出書
    MEDIUM_PRIORITY_DOC_TYPES = ['130', '150', '135', '180', '040']  # 訂正有価証券報告書、訂正四半期報告書、確認書、臨時報告書、訂正有価証券届出書
    
    # 書類種別表示名マッピング（正確版）
    DOC_TYPE_DISPLAY_NAMES = {
        # 決算関連書類（高優先度）
        '120': '有価証券報告書',
        '030': '有価証券届出書',
        '040': '訂正有価証券届出書',
        '160': '半期報告書',
        
        # 決算関連書類（中優先度）
        '130': '訂正有価証券報告書',
        '150': '訂正四半期報告書',
        '135': '確認書',
        '170': '訂正半期報告書',
        '180': '臨時報告書',
        
        # 訂正・修正関連
        '190': '訂正臨時報告書',
        '236': '訂正内部統制報告書',
        
        # 公開買付関連
        '270': '公開買付報告書',
        '260': '公開買付撤回届出書',
        '210': '訂正親会社等状況報告書',
        '220': '自己株券買付状況報告書',
        '230': '訂正自己株券買付状況報告書',
        '240': '公開買付届出書',
        '250': '訂正公開買付届出書',
        
        # 大量保有・親会社関連
        '200': '親会社等状況報告書',
        '350': '変更報告書/大量保有報告書',
        '360': '訂正報告書（大量保有報告書・変更報告書）',
        
        # 内部統制関連
        '235': '内部統制報告書',
        
        # 発行登録関連
        '090': '訂正発行登録書',
        '091': '訂正発行登録書',
        '100': '発行登録追補書類',
        
        # 外国会社関連
        '181': '外国会社臨時報告書',
        
        # 投資信託・ファンド関連
        '280': '投資信託約款',
        '290': '意見表明報告書',
        '300': '訂正意見表明報告書',
        '301': '訂正意見表明報告書',
        '310': '対質問回答報告書',
        '311': '対質問回答報告書',
        
        # その他
        '201': '親会社等状況報告書（内国会社）',
        '999': 'その他',
        '000': '不明',
    }
    
    # 書類種別カテゴリ分類（更新版）
    DOC_TYPE_CATEGORIES = {
        'financial_main': {
            'name': '主要決算書類',
            'types': ['120', '160', '030'],  # 有価証券報告書、半期報告書、有価証券届出書
            'description': '投資判断に重要な決算関連書類',
            'priority': 1
        },
        'financial_sub': {
            'name': '補助決算書類',
            'types': ['130', '150', '135', '040', '170', '180', '190'],  # 訂正有価証券報告書、訂正四半期報告書、確認書等
            'description': '追加的な財務情報を含む書類',
            'priority': 2
        },
        'governance': {
            'name': 'ガバナンス関連',
            'types': ['235', '236'],  # 内部統制報告書
            'description': '内部統制や企業統治に関する書類',
            'priority': 3
        },
        'market_activity': {
            'name': '市場活動関連',
            'types': ['240', '250', '260', '270', '290'],  # 公開買付関連、意見表明報告書
            'description': '公開買付等の市場活動に関する書類',
            'priority': 4
        },
        'buyback_activity': {
            'name': '自己株券買付関連',
            'types': ['220', '230'],  # 自己株券買付状況報告書
            'description': '自己株券買付に関する書類',
            'priority': 5
        },
        'ownership': {
            'name': '株式保有・親会社関連',
            'types': ['200', '201', '210', '350', '360'],  # 親会社等状況報告書、大量保有関連
            'description': '大量保有報告書等の株式保有に関する書類',
            'priority': 6
        },
        'registration': {
            'name': '発行登録関連',
            'types': ['090', '091', '100'],  # 発行登録書等
            'description': '発行登録に関する書類',
            'priority': 7
        },
        'investment_trust': {
            'name': '投資信託関連',
            'types': ['280', '300', '301', '310', '311'],  # 投資信託約款、訂正意見表明報告書、対質問回答報告書
            'description': '投資信託に関する書類',
            'priority': 8
        },
        'foreign_company': {
            'name': '外国会社関連',
            'types': ['181'],  # 外国会社臨時報告書
            'description': '外国会社に関する書類',
            'priority': 9
        },
        'others': {
            'name': 'その他',
            'types': ['999', '000'],
            'description': 'その他の書類',
            'priority': 10
        }
    }
    
    @property
    def doc_type_display_name(self):
        """書類種別の日本語表示名"""
        return self.DOC_TYPE_DISPLAY_NAMES.get(self.doc_type_code, f'書類種別{self.doc_type_code}')
    
    @property
    def doc_type_category(self):
        """書類種別のカテゴリを取得"""
        for category_key, category_info in self.DOC_TYPE_CATEGORIES.items():
            if self.doc_type_code in category_info['types']:
                return {
                    'key': category_key,
                    'name': category_info['name'],
                    'description': category_info['description'],
                    'priority': category_info['priority']
                }
        return {
            'key': 'others',
            'name': 'その他',
            'description': 'その他の書類',
            'priority': 9
        }
    
    @classmethod
    def get_doc_type_choices_for_filter(cls):
        """フィルタ用の書類種別選択肢を取得（カテゴリ別）"""
        choices = []
        
        # カテゴリ別に整理
        for category_key, category_info in cls.DOC_TYPE_CATEGORIES.items():
            category_choices = []
            for doc_type_code in category_info['types']:
                display_name = cls.DOC_TYPE_DISPLAY_NAMES.get(doc_type_code, f'書類種別{doc_type_code}')
                category_choices.append({
                    'code': doc_type_code,
                    'name': display_name,
                    'full_name': f"{display_name} ({doc_type_code})"
                })
            
            if category_choices:
                choices.append({
                    'category': category_info['name'],
                    'priority': category_info['priority'],
                    'choices': category_choices
                })
        
        # 優先度順でソート
        choices.sort(key=lambda x: x['priority'])
        return choices
    
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
        financial_types = ['120', '160', '030', '130', '150', '135', '040', '180']  # 有価証券報告書、半期報告書、訂正有価証券報告書、訂正四半期報告書、確認書、臨時報告書等
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
            'doc_type_code',
            '-submit_date_time'
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
        try:
            if analysis_suitable_first:
                # 分析に適した書類（決算関連）を優先
                suitable_docs = cls.objects.filter(
                    edinet_code=edinet_code,
                    legal_status='1',
                    doc_type_code__in=cls.HIGH_PRIORITY_DOC_TYPES + cls.MEDIUM_PRIORITY_DOC_TYPES
                ).order_by('-submit_date_time')
                
                # その他の書類
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
                all_docs = cls.objects.filter(
                    edinet_code=edinet_code,
                    legal_status='1'
                ).order_by('-submit_date_time')
                
                return {
                    'suitable': [],
                    'others': list(all_docs)
                }
                
        except Exception as e:
            return {'suitable': [], 'others': []}
    
    def has_recent_analysis(self, hours=1):
        """最近分析が実行されたかチェック"""
        try:
            from .sentiment import SentimentAnalysisSession
            from .financial import FinancialAnalysisSession
            
            cutoff_time = timezone.now() - timedelta(hours=hours)
            
            recent_sentiment = SentimentAnalysisSession.objects.filter(
                document=self,
                processing_status='COMPLETED',
                created_at__gte=cutoff_time
            ).exists()
            
            recent_financial = FinancialAnalysisSession.objects.filter(
                document=self,
                processing_status='COMPLETED', 
                created_at__gte=cutoff_time
            ).exists()
            
            return recent_sentiment or recent_financial
            
        except Exception:
            return False
    
    @property
    def analysis_suitability_score(self):
        """分析適合度スコア（高いほど分析に適している）"""
        score = 0
        
        # XBRLがあると高スコア
        if self.xbrl_flag:
            score += 50
            
        # 決算関連書類は高スコア
        if self.is_financial_statement:
            score += 30
            
        # 新しい書類ほど高スコア
        if self.submit_date_time:
            days_old = (timezone.now() - self.submit_date_time).days
            if days_old < 30:
                score += 20
            elif days_old < 90:
                score += 10
                
        # PDFがあると少しプラス
        if self.pdf_flag:
            score += 5
            
        return score
    
    # URL関連プロパティ
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
        return reverse('earnings_analysis:financial-analysis', args=[self.doc_id])
    
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