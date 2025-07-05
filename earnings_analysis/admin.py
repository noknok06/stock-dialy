# earnings_analysis/admin.py（CSV削除版 + 財務分析モデル追加）
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.http import HttpResponse
from datetime import datetime

from .models import (
    Company, DocumentMetadata, BatchExecution,
    FinancialAnalysisSession, FinancialAnalysisHistory, 
    CompanyFinancialData, FinancialBenchmark
)

# Admin Site の設定
admin.site.site_header = '決算書類管理システム'
admin.site.site_title = '決算書類管理'
admin.site.index_title = 'システム管理'

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = [
        'securities_code_display', 'company_name_link', 'edinet_code', 
        'document_count', 'financial_data_count', 'is_active_badge', 'updated_at'
    ]
    list_filter = ['is_active', 'created_at', 'updated_at']
    search_fields = ['edinet_code', 'securities_code', 'company_name', 'company_name_kana']
    readonly_fields = ['created_at', 'updated_at', 'document_count_admin', 'financial_summary']
    list_per_page = 50
    
    fieldsets = (
        ('基本情報', {
            'fields': ('edinet_code', 'securities_code', 'company_name', 'company_name_kana'),
            'description': '企業の基本的な識別情報'
        }),
        ('詳細情報', {
            'fields': ('jcn', 'is_active'),
            'description': '法人番号と有効性フラグ'
        }),
        ('統計情報', {
            'fields': ('document_count_admin', 'financial_summary'),
            'classes': ('collapse',),
            'description': '関連する書類と財務データの統計情報'
        }),
        ('管理情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'システム管理用タイムスタンプ'
        }),
    )
    
    actions = ['activate_companies', 'deactivate_companies']
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            doc_count=Count('documentmetadata', filter=Q(documentmetadata__legal_status='1')),
            financial_count=Count('companyfinancialdata')
        )
    
    def securities_code_display(self, obj):
        """証券コード表示の改善"""
        if obj.securities_code:
            return format_html(
                '<span class="badge badge-primary">{}</span>',
                obj.securities_code
            )
        return format_html('<span class="text-muted">—</span>')
    securities_code_display.short_description = '証券コード'
    securities_code_display.admin_order_field = 'securities_code'
    
    def company_name_link(self, obj):
        """企業名にリンクを追加"""
        url = reverse('admin:earnings_analysis_documentmetadata_changelist')
        return format_html(
            '<a href="{}?edinet_code={}" title="この企業の書類を表示">{}</a>',
            url, obj.edinet_code, obj.company_name
        )
    company_name_link.short_description = '企業名'
    company_name_link.admin_order_field = 'company_name'
    
    def document_count(self, obj):
        """書類数表示"""
        count = getattr(obj, 'doc_count', 0)
        if count > 0:
            return format_html(
                '<span class="badge badge-success">{} 件</span>',
                count
            )
        return format_html('<span class="text-muted">0 件</span>')
    document_count.short_description = '書類数'
    document_count.admin_order_field = 'doc_count'
    
    def financial_data_count(self, obj):
        """財務データ数表示"""
        count = getattr(obj, 'financial_count', 0)
        if count > 0:
            return format_html(
                '<span class="badge badge-info">{} 件</span>',
                count
            )
        return format_html('<span class="text-muted">0 件</span>')
    financial_data_count.short_description = '財務データ数'
    financial_data_count.admin_order_field = 'financial_count'
    
    def document_count_admin(self, obj):
        """管理画面用の詳細な書類数"""
        total = DocumentMetadata.objects.filter(edinet_code=obj.edinet_code).count()
        active = DocumentMetadata.objects.filter(edinet_code=obj.edinet_code, legal_status='1').count()
        return format_html(
            '総数: {} 件<br>有効: {} 件',
            total, active
        )
    document_count_admin.short_description = '書類統計'
    
    def financial_summary(self, obj):
        """財務データサマリー"""
        financial_data = CompanyFinancialData.objects.filter(company=obj).order_by('-period_end')[:3]
        if financial_data:
            summary = []
            for data in financial_data:
                summary.append(f"{data.period_end}: 健全性 {data.overall_data_completeness:.1%}")
            return format_html('<br>'.join(summary))
        return '財務データなし'
    financial_summary.short_description = '財務データサマリー'
    
    def is_active_badge(self, obj):
        """アクティブ状態のバッジ表示"""
        if obj.is_active:
            return format_html('<span class="badge badge-success">有効</span>')
        return format_html('<span class="badge badge-secondary">無効</span>')
    is_active_badge.short_description = '状態'
    is_active_badge.admin_order_field = 'is_active'
    
    def activate_companies(self, request, queryset):
        """企業を有効化"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} 社を有効化しました。')
    activate_companies.short_description = "選択した企業を有効化"
    
    def deactivate_companies(self, request, queryset):
        """企業を無効化"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} 社を無効化しました。')
    deactivate_companies.short_description = "選択した企業を無効化"


@admin.register(DocumentMetadata)
class DocumentMetadataAdmin(admin.ModelAdmin):
    list_display = [
        'doc_id_link', 'company_name_link', 'doc_type_code', 
        'submit_date_display', 'legal_status_badge', 'format_flags', 'analysis_status'
    ]
    list_filter = [
        'legal_status', 'doc_type_code', 'file_date', 
        'xbrl_flag', 'pdf_flag', 'created_at'
    ]
    search_fields = ['doc_id', 'company_name', 'securities_code', 'doc_description']
    readonly_fields = ['created_at', 'updated_at', 'download_links', 'analysis_summary']
    date_hierarchy = 'submit_date_time'
    list_per_page = 100
    
    fieldsets = (
        ('基本情報', {
            'fields': ('doc_id', 'company_name', 'securities_code', 'edinet_code'),
            'description': '書類とそれに関連する企業の基本情報'
        }),
        ('書類分類', {
            'fields': ('doc_type_code', 'ordinance_code', 'form_code', 'fund_code'),
            'description': '書類の種別と分類コード'
        }),
        ('期間・日時', {
            'fields': ('period_start', 'period_end', 'submit_date_time', 'file_date'),
            'description': '書類の対象期間と提出日時'
        }),
        ('書類内容', {
            'fields': ('doc_description',),
            'description': '書類の詳細説明'
        }),
        ('利用可能フォーマット', {
            'fields': ('xbrl_flag', 'pdf_flag', 'attach_doc_flag', 'english_doc_flag'),
            'description': 'ダウンロード可能なファイル形式'
        }),
        ('ステータス', {
            'fields': ('legal_status', 'withdrawal_status', 'doc_info_edit_status', 'disclosure_status'),
            'description': '書類の現在のステータス'
        }),
        ('分析情報', {
            'fields': ('analysis_summary',),
            'classes': ('collapse',),
            'description': '感情分析・財務分析の実行状況'
        }),
        ('ダウンロード', {
            'fields': ('download_links',),
            'classes': ('collapse',),
            'description': '書類ダウンロードリンク'
        }),
        ('管理情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'システム管理用タイムスタンプ'
        }),
    )
    
    actions = ['mark_as_reviewed']
    
    def doc_id_link(self, obj):
        """書類IDにダウンロードリンクを追加"""
        if obj.pdf_flag:
            download_url = reverse('earnings_analysis:document-download', args=[obj.doc_id])
            return format_html(
                '<a href="{}" target="_blank" title="PDFダウンロード">{}</a>',
                f"{download_url}?type=pdf", obj.doc_id
            )
        return obj.doc_id
    doc_id_link.short_description = '書類管理番号'
    doc_id_link.admin_order_field = 'doc_id'
    
    def company_name_link(self, obj):
        """企業名に企業詳細へのリンクを追加"""
        try:
            company = Company.objects.get(edinet_code=obj.edinet_code)
            url = reverse('admin:earnings_analysis_company_change', args=[company.pk])
            return format_html(
                '<a href="{}" title="企業詳細を表示">{}</a>',
                url, obj.company_name
            )
        except Company.DoesNotExist:
            return obj.company_name
    company_name_link.short_description = '企業名'
    company_name_link.admin_order_field = 'company_name'
    
    def submit_date_display(self, obj):
        """提出日時の表示改善"""
        return format_html(
            '<span title="{}">{}</span>',
            obj.submit_date_time.strftime('%Y-%m-%d %H:%M:%S'),
            obj.submit_date_time.strftime('%m/%d %H:%M')
        )
    submit_date_display.short_description = '提出日時'
    submit_date_display.admin_order_field = 'submit_date_time'
    
    def legal_status_badge(self, obj):
        """法的ステータスのバッジ表示"""
        status_map = {
            '0': ('閲覧期間満了', 'badge-warning'),
            '1': ('縦覧中', 'badge-success'),
            '2': ('延長期間中', 'badge-info'),
        }
        status_text, badge_class = status_map.get(obj.legal_status, ('不明', 'badge-secondary'))
        return format_html('<span class="{}">{}</span>', badge_class, status_text)
    legal_status_badge.short_description = '縦覧区分'
    legal_status_badge.admin_order_field = 'legal_status'
    
    def format_flags(self, obj):
        """利用可能フォーマット表示（CSV削除）"""
        flags = []
        if obj.pdf_flag:
            flags.append('<span class="badge badge-danger">PDF</span>')
        if obj.xbrl_flag:
            flags.append('<span class="badge badge-primary">XBRL</span>')
        if obj.attach_doc_flag:
            flags.append('<span class="badge badge-warning">添付</span>')
        if obj.english_doc_flag:
            flags.append('<span class="badge badge-info">英文</span>')
        
        return format_html(' '.join(flags)) if flags else '—'
    format_flags.short_description = '利用可能フォーマット'
    
    def analysis_status(self, obj):
        """分析実行状況"""
        from .models import SentimentAnalysisSession, FinancialAnalysisSession
        
        sentiment_count = SentimentAnalysisSession.objects.filter(
            document=obj, processing_status='COMPLETED'
        ).count()
        
        financial_count = FinancialAnalysisSession.objects.filter(
            document=obj, processing_status='COMPLETED'
        ).count()
        
        badges = []
        if sentiment_count > 0:
            badges.append(f'<span class="badge badge-purple">感情×{sentiment_count}</span>')
        if financial_count > 0:
            badges.append(f'<span class="badge badge-blue">財務×{financial_count}</span>')
            
        return format_html(' '.join(badges)) if badges else '—'
    analysis_status.short_description = '分析実行状況'
    
    def analysis_summary(self, obj):
        """分析サマリー（管理画面用）"""
        from .models import SentimentAnalysisSession, FinancialAnalysisSession
        
        sentiment_sessions = SentimentAnalysisSession.objects.filter(document=obj).order_by('-created_at')[:3]
        financial_sessions = FinancialAnalysisSession.objects.filter(document=obj).order_by('-created_at')[:3]
        
        summary = []
        
        if sentiment_sessions:
            summary.append('<strong>感情分析:</strong>')
            for session in sentiment_sessions:
                summary.append(f"- {session.created_at.strftime('%m/%d')}: {session.get_processing_status_display()}")
        
        if financial_sessions:
            summary.append('<strong>財務分析:</strong>')
            for session in financial_sessions:
                summary.append(f"- {session.created_at.strftime('%m/%d')}: {session.get_processing_status_display()}")
        
        return format_html('<br>'.join(summary)) if summary else '分析履歴なし'
    analysis_summary.short_description = '分析サマリー'
    
    def download_links(self, obj):
        """ダウンロードリンクの生成（CSV削除）"""
        links = []
        base_url = reverse('earnings_analysis:document-download', args=[obj.doc_id])
        
        if obj.pdf_flag:
            links.append(f'<a href="{base_url}?type=pdf" target="_blank" class="button">PDFダウンロード</a>')
        if obj.xbrl_flag:
            links.append(f'<a href="{base_url}?type=xbrl" target="_blank" class="button">XBRLダウンロード</a>')
        
        return format_html('<br>'.join(links)) if links else '利用可能なダウンロードなし'
    download_links.short_description = 'ダウンロード'
    
    def mark_as_reviewed(self, request, queryset):
        """レビュー済みとしてマーク（将来の拡張用）"""
        count = queryset.count()
        self.message_user(request, f'{count} 件の書類をレビュー済みとしました。')
    mark_as_reviewed.short_description = "選択した書類をレビュー済みにする"


@admin.register(BatchExecution)
class BatchExecutionAdmin(admin.ModelAdmin):
    list_display = [
        'batch_date', 'status_badge', 'processed_count_display', 
        'duration_display', 'started_at', 'error_summary'
    ]
    list_filter = ['status', 'batch_date', 'started_at']
    readonly_fields = ['duration_display', 'created_at', 'error_details']
    date_hierarchy = 'batch_date'
    ordering = ['-batch_date']
    
    fieldsets = (
        ('実行情報', {
            'fields': ('batch_date', 'status', 'started_at', 'completed_at', 'duration_display'),
            'description': 'バッチ処理の実行状況'
        }),
        ('処理結果', {
            'fields': ('processed_count',),
            'description': '処理された書類数'
        }),
        ('エラー情報', {
            'fields': ('error_message', 'error_details'),
            'classes': ('collapse',),
            'description': 'エラーが発生した場合の詳細情報'
        }),
        ('管理情報', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    
    def status_badge(self, obj):
        """ステータスのバッジ表示"""
        status_map = {
            'RUNNING': ('実行中', 'badge-warning'),
            'SUCCESS': ('成功', 'badge-success'),
            'FAILED': ('失敗', 'badge-danger'),
        }
        status_text, badge_class = status_map.get(obj.status, ('不明', 'badge-secondary'))
        return format_html('<span class="{}">{}</span>', badge_class, status_text)
    status_badge.short_description = 'ステータス'
    status_badge.admin_order_field = 'status'
    
    def processed_count_display(self, obj):
        """処理件数の表示改善"""
        if obj.processed_count > 0:
            return format_html('<strong>{}</strong> 件', obj.processed_count)
        return '0 件'
    processed_count_display.short_description = '処理件数'
    processed_count_display.admin_order_field = 'processed_count'
    
    def duration_display(self, obj):
        """実行時間計算"""
        if obj.started_at and obj.completed_at:
            duration = obj.completed_at - obj.started_at
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f'{hours}時間{minutes}分{seconds}秒'
            elif minutes > 0:
                return f'{minutes}分{seconds}秒'
            else:
                return f'{seconds}秒'
        return '—'
    duration_display.short_description = '実行時間'
    
    def error_summary(self, obj):
        """エラーの概要表示"""
        if obj.error_message:
            summary = obj.error_message[:50]
            return format_html(
                '<span class="text-danger" title="{}">{}</span>',
                obj.error_message, f'{summary}...' if len(obj.error_message) > 50 else summary
            )
        return '—'
    error_summary.short_description = 'エラー概要'
    
    def error_details(self, obj):
        """エラーの詳細表示"""
        if obj.error_message:
            return format_html('<pre>{}</pre>', obj.error_message)
        return 'エラーなし'
    error_details.short_description = 'エラー詳細'


@admin.register(FinancialAnalysisSession)
class FinancialAnalysisSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_id_short', 'document_link', 'overall_health_score_display',
        'risk_level_badge', 'investment_stance_badge', 'processing_status_badge', 'created_at'
    ]
    list_filter = ['processing_status', 'risk_level', 'investment_stance', 'created_at']
    search_fields = ['session_id', 'document__company_name', 'document__doc_id']
    readonly_fields = ['session_id', 'created_at', 'updated_at', 'analysis_summary_admin']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('セッション情報', {
            'fields': ('session_id', 'document', 'processing_status', 'created_at', 'updated_at', 'expires_at'),
        }),
        ('分析結果', {
            'fields': ('overall_health_score', 'risk_level', 'investment_stance', 'cashflow_pattern', 'management_confidence_score'),
        }),
        ('財務データ', {
            'fields': ('operating_cf', 'investing_cf', 'financing_cf'),
            'classes': ('collapse',),
        }),
        ('詳細結果', {
            'fields': ('analysis_summary_admin',),
            'classes': ('collapse',),
        }),
        ('エラー情報', {
            'fields': ('error_message',),
            'classes': ('collapse',),
        }),
    )
    
    def session_id_short(self, obj):
        return f"{obj.session_id[:8]}..."
    session_id_short.short_description = 'セッションID'
    
    def document_link(self, obj):
        url = reverse('admin:earnings_analysis_documentmetadata_change', args=[obj.document.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, f"{obj.document.company_name} ({obj.document.doc_id})"
        )
    document_link.short_description = '対象書類'
    
    def overall_health_score_display(self, obj):
        if obj.overall_health_score is not None:
            if obj.overall_health_score >= 80:
                color = 'text-success'
            elif obj.overall_health_score >= 60:
                color = 'text-info'
            elif obj.overall_health_score >= 40:
                color = 'text-warning'
            else:
                color = 'text-danger'
            return format_html('<span class="{}">{}</span>', color, f"{obj.overall_health_score:.1f}")
        return '—'
    overall_health_score_display.short_description = '健全性スコア'
    
    def risk_level_badge(self, obj):
        if obj.risk_level:
            color_map = {'low': 'badge-success', 'medium': 'badge-warning', 'high': 'badge-danger'}
            color = color_map.get(obj.risk_level, 'badge-secondary')
            return format_html('<span class="{}">{}</span>', color, obj.get_risk_level_display())
        return '—'
    risk_level_badge.short_description = 'リスクレベル'
    
    def investment_stance_badge(self, obj):
        if obj.investment_stance:
            color_map = {
                'aggressive': 'badge-success', 
                'conditional': 'badge-info', 
                'cautious': 'badge-warning', 
                'avoid': 'badge-danger'
            }
            color = color_map.get(obj.investment_stance, 'badge-secondary')
            return format_html('<span class="{}">{}</span>', color, obj.get_investment_stance_display())
        return '—'
    investment_stance_badge.short_description = '投資スタンス'
    
    def processing_status_badge(self, obj):
        color_map = {
            'PENDING': 'badge-secondary',
            'PROCESSING': 'badge-warning', 
            'COMPLETED': 'badge-success', 
            'FAILED': 'badge-danger'
        }
        color = color_map.get(obj.processing_status, 'badge-secondary')
        return format_html('<span class="{}">{}</span>', color, obj.get_processing_status_display())
    processing_status_badge.short_description = 'ステータス'
    
    def analysis_summary_admin(self, obj):
        if obj.analysis_result:
            integrated = obj.analysis_result.get('integrated_analysis', {})
            key_findings = integrated.get('key_findings', {})
            
            summary = []
            if integrated.get('overall_score'):
                summary.append(f"統合スコア: {integrated['overall_score']}")
            
            strengths = key_findings.get('strengths', [])
            if strengths:
                summary.append(f"強み: {', '.join(strengths[:2])}")
            
            concerns = key_findings.get('concerns', [])
            if concerns:
                summary.append(f"懸念: {', '.join(concerns[:2])}")
            
            return format_html('<br>'.join(summary)) if summary else '詳細なし'
        return '分析結果なし'
    analysis_summary_admin.short_description = '分析サマリー'


@admin.register(FinancialAnalysisHistory)
class FinancialAnalysisHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'document_link', 'overall_health_score_display', 'risk_level_badge',
        'cashflow_pattern', 'analysis_date', 'data_quality'
    ]
    list_filter = ['risk_level', 'cashflow_pattern', 'analysis_date', 'data_quality']
    search_fields = ['document__company_name', 'document__doc_id']
    date_hierarchy = 'analysis_date'
    
    def document_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            reverse('admin:earnings_analysis_documentmetadata_change', args=[obj.document.pk]),
            f"{obj.document.company_name} ({obj.document.doc_id})"
        )
    document_link.short_description = '対象書類'
    
    def overall_health_score_display(self, obj):
        if obj.overall_health_score >= 80:
            color = 'text-success'
        elif obj.overall_health_score >= 60:
            color = 'text-info'
        elif obj.overall_health_score >= 40:
            color = 'text-warning'
        else:
            color = 'text-danger'
        return format_html('<span class="{}">{}</span>', color, f"{obj.overall_health_score:.1f}")
    overall_health_score_display.short_description = '健全性スコア'
    
    def risk_level_badge(self, obj):
        color_map = {'low': 'badge-success', 'medium': 'badge-warning', 'high': 'badge-danger'}
        color = color_map.get(obj.risk_level, 'badge-secondary')
        return format_html('<span class="{}">{}</span>', color, obj.get_risk_level_display())
    risk_level_badge.short_description = 'リスクレベル'


@admin.register(CompanyFinancialData)
class CompanyFinancialDataAdmin(admin.ModelAdmin):
    list_display = [
        'company_name_display', 'period_display', 'period_type', 
        'key_metrics', 'data_completeness_display', 'created_at'
    ]
    list_filter = ['period_type', 'fiscal_year', 'data_completeness', 'created_at']
    search_fields = ['company__company_name', 'document__company_name', 'document__doc_id']
    readonly_fields = ['created_at', 'updated_at', 'calculated_ratios']
    date_hierarchy = 'period_end'
    
    fieldsets = (
        ('基本情報', {
            'fields': ('document', 'company', 'period_type', 'period_start', 'period_end', 'fiscal_year'),
        }),
        ('損益計算書', {
            'fields': ('net_sales', 'operating_income', 'ordinary_income', 'net_income'),
        }),
        ('貸借対照表', {
            'fields': ('total_assets', 'total_liabilities', 'net_assets'),
        }),
        ('キャッシュフロー計算書', {
            'fields': ('operating_cf', 'investing_cf', 'financing_cf'),
        }),
        ('計算済み指標', {
            'fields': ('calculated_ratios',),
            'classes': ('collapse',),
        }),
        ('データ品質', {
            'fields': ('data_completeness', 'extraction_confidence'),
        }),
        ('管理情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def company_name_display(self, obj):
        name = obj.company.company_name if obj.company else obj.document.company_name
        securities_code = obj.company.securities_code if obj.company else obj.document.securities_code
        if securities_code:
            return f"{name} ({securities_code})"
        return name
    company_name_display.short_description = '企業名'
    
    def period_display(self, obj):
        if obj.period_start and obj.period_end:
            return f"{obj.period_start.strftime('%Y/%m/%d')} - {obj.period_end.strftime('%Y/%m/%d')}"
        return '期間不明'
    period_display.short_description = '対象期間'
    
    def key_metrics(self, obj):
        metrics = []
        if obj.operating_margin:
            metrics.append(f"営業利益率: {obj.operating_margin}%")
        if obj.roa:
            metrics.append(f"ROA: {obj.roa}%")
        if obj.equity_ratio:
            metrics.append(f"自己資本比率: {obj.equity_ratio}%")
        return format_html('<br>'.join(metrics)) if metrics else '—'
    key_metrics.short_description = '主要指標'
    
    def data_completeness_display(self, obj):
        if obj.data_completeness:
            percentage = obj.data_completeness * 100
            if percentage >= 80:
                color = 'text-success'
            elif percentage >= 60:
                color = 'text-warning'
            else:
                color = 'text-danger'
            return format_html('<span class="{}">{:.1f}%</span>', color, percentage)
        return '—'
    data_completeness_display.short_description = 'データ完全性'
    
    def calculated_ratios(self, obj):
        ratios = []
        if obj.operating_margin is not None:
            ratios.append(f"営業利益率: {obj.operating_margin}%")
        if obj.net_margin is not None:
            ratios.append(f"当期純利益率: {obj.net_margin}%")
        if obj.roa is not None:
            ratios.append(f"ROA: {obj.roa}%")
        if obj.equity_ratio is not None:
            ratios.append(f"自己資本比率: {obj.equity_ratio}%")
        return format_html('<br>'.join(ratios)) if ratios else '計算済み指標なし'
    calculated_ratios.short_description = '計算済み財務指標'


@admin.register(FinancialBenchmark)
class FinancialBenchmarkAdmin(admin.ModelAdmin):
    list_display = [
        'industry_category', 'industry_subcategory', 'reference_period',
        'sample_size', 'operating_margin_median', 'roa_median', 'equity_ratio_median'
    ]
    list_filter = ['industry_category', 'reference_period']
    search_fields = ['industry_category', 'industry_subcategory']


# 管理画面のカスタムCSS（拡張版）
admin.site.site_header = mark_safe('''
<style>
.badge { 
    display: inline-block; 
    padding: 0.25em 0.4em; 
    font-size: 75%; 
    font-weight: 700; 
    line-height: 1; 
    text-align: center; 
    white-space: nowrap; 
    vertical-align: baseline; 
    border-radius: 0.25rem; 
}
.badge-primary { color: #fff; background-color: #007bff; }
.badge-success { color: #fff; background-color: #28a745; }
.badge-danger { color: #fff; background-color: #dc3545; }
.badge-warning { color: #212529; background-color: #ffc107; }
.badge-info { color: #fff; background-color: #17a2b8; }
.badge-secondary { color: #fff; background-color: #6c757d; }
.badge-purple { color: #fff; background-color: #8b5cf6; }
.badge-blue { color: #fff; background-color: #3b82f6; }
.text-success { color: #28a745 !important; }
.text-danger { color: #dc3545 !important; }
.text-warning { color: #856404 !important; }
.text-info { color: #17a2b8 !important; }
</style>
決算書類管理システム
''')