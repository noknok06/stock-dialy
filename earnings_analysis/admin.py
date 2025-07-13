# earnings_analysis/admin.py（改良版・バッチ実行機能付き）
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.db.models import Count, Q, Avg, Max, Min
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib import messages
from django.shortcuts import render
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import logging

from .models import (
    Company, DocumentMetadata, BatchExecution,
    SentimentAnalysisSession, SentimentAnalysisHistory,
    FinancialAnalysisSession, FinancialAnalysisHistory, 
    CompanyFinancialData, FinancialBenchmark
)

logger = logging.getLogger(__name__)

# Admin Site の設定
admin.site.site_header = 'コーポマインドリーダー'
admin.site.site_title = 'CMR Admin'
admin.site.index_title = 'システム管理ダッシュボード'

# カスタムフィルター
class DocumentCountFilter(admin.SimpleListFilter):
    title = '書類保有状況'
    parameter_name = 'doc_count'

    def lookups(self, request, model_admin):
        return (
            ('high', '10件以上'),
            ('medium', '5-9件'),
            ('low', '1-4件'),
            ('none', '0件'),
        )

    def queryset(self, request, queryset):
        if self.value():
            company_ids = []
            for company in queryset:
                doc_count = DocumentMetadata.objects.filter(
                    edinet_code=company.edinet_code,
                    legal_status='1'
                ).count()
                
                if self.value() == 'high' and doc_count >= 10:
                    company_ids.append(company.id)
                elif self.value() == 'medium' and 5 <= doc_count < 10:
                    company_ids.append(company.id)
                elif self.value() == 'low' and 1 <= doc_count < 5:
                    company_ids.append(company.id)
                elif self.value() == 'none' and doc_count == 0:
                    company_ids.append(company.id)
            
            return queryset.filter(id__in=company_ids)
        return queryset


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = [
        'securities_code_display', 'company_name_link', 'edinet_code', 
        'document_count', 'financial_data_count', 'analysis_summary',
        'is_active_badge', 'updated_at'
    ]
    list_filter = ['is_active', DocumentCountFilter, 'created_at', 'updated_at']
    search_fields = ['edinet_code', 'securities_code', 'company_name', 'company_name_kana', 'jcn']
    readonly_fields = ['created_at', 'updated_at', 'document_count_admin', 'financial_summary', 'analysis_overview']
    list_per_page = 50
    list_select_related = True
    
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
            'fields': ('document_count_admin', 'financial_summary', 'analysis_overview'),
            'classes': ('collapse',),
            'description': '関連する書類と財務データの統計情報'
        }),
        ('管理情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'システム管理用タイムスタンプ'
        }),
    )
    
    actions = ['activate_companies', 'deactivate_companies', 'export_company_csv', 'analyze_companies']
    
    def get_queryset(self, request):
        # 外部キー関係がないため、手動で集計を行う
        return super().get_queryset(request)
    
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
        count = DocumentMetadata.objects.filter(
            edinet_code=obj.edinet_code, 
            legal_status='1'
        ).count()
        
        if count > 0:
            color = 'success' if count >= 10 else 'info' if count >= 5 else 'warning'
            return format_html(
                '<span class="badge badge-{}">{} 件</span>',
                color, count
            )
        return format_html('<span class="text-muted">0 件</span>')
    document_count.short_description = '書類数'
    
    def financial_data_count(self, obj):
        """財務データ数表示"""
        count = CompanyFinancialData.objects.filter(
            Q(company=obj) | Q(document__edinet_code=obj.edinet_code)
        ).count()
        
        if count > 0:
            return format_html(
                '<span class="badge badge-info">{} 件</span>',
                count
            )
        return format_html('<span class="text-muted">0 件</span>')
    financial_data_count.short_description = '財務データ数'
    
    def analysis_summary(self, obj):
        """分析実行サマリー"""
        # 感情分析セッション数
        sentiment_count = SentimentAnalysisSession.objects.filter(
            document__edinet_code=obj.edinet_code
        ).count()
        
        # 財務分析セッション数
        financial_count = FinancialAnalysisSession.objects.filter(
            document__edinet_code=obj.edinet_code
        ).count()
        
        badges = []
        if sentiment_count > 0:
            badges.append('<span class="badge badge-purple">感情×{}</span>'.format(sentiment_count))
        if financial_count > 0:
            badges.append('<span class="badge badge-blue">財務×{}</span>'.format(financial_count))
            
        return format_html(' '.join(badges)) if badges else '—'
    analysis_summary.short_description = '分析実行状況'
    
    def document_count_admin(self, obj):
        """管理画面用の詳細な書類数"""
        total = DocumentMetadata.objects.filter(edinet_code=obj.edinet_code).count()
        active = DocumentMetadata.objects.filter(edinet_code=obj.edinet_code, legal_status='1').count()
        financial = DocumentMetadata.objects.filter(
            edinet_code=obj.edinet_code, 
            legal_status='1',
            doc_type_code__in=['120', '160', '030']
        ).count()
        return format_html(
            '総数: {} 件<br>有効: {} 件<br>決算書類: {} 件',
            total, active, financial
        )
    document_count_admin.short_description = '書類統計'
    
    def financial_summary(self, obj):
        """財務データサマリー"""
        financial_data = CompanyFinancialData.objects.filter(company=obj).order_by('-period_end')[:3]
        if financial_data:
            summary = []
            for data in financial_data:
                try:
                    completeness = float(data.overall_data_completeness) * 100
                    summary.append("{}: 健全性 {:.1f}%".format(data.period_end, completeness))
                except (ValueError, TypeError, AttributeError):
                    summary.append("{}: 健全性 計算不可".format(data.period_end))
            return format_html('<br>'.join(summary))
        return '財務データなし'
    financial_summary.short_description = '財務データサマリー'
    
    def analysis_overview(self, obj):
        """分析概要"""
        # 最新の分析結果
        latest_sentiment = SentimentAnalysisSession.objects.filter(
            document__edinet_code=obj.edinet_code,
            processing_status='COMPLETED'
        ).order_by('-created_at').first()
        
        latest_financial = FinancialAnalysisSession.objects.filter(
            document__edinet_code=obj.edinet_code,
            processing_status='COMPLETED'
        ).order_by('-created_at').first()
        
        summary = []
        if latest_sentiment:
            summary.append("最新感情分析: {}".format(latest_sentiment.created_at.strftime('%m/%d')))
        if latest_financial:
            summary.append("最新財務分析: {}".format(latest_financial.created_at.strftime('%m/%d')))
        
        return format_html('<br>'.join(summary)) if summary else '分析実行なし'
    analysis_overview.short_description = '分析概要'
    
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
        self.message_user(request, '{} 社を有効化しました。'.format(updated))
    activate_companies.short_description = "選択した企業を有効化"
    
    def deactivate_companies(self, request, queryset):
        """企業を無効化"""
        updated = queryset.update(is_active=False)
        self.message_user(request, '{} 社を無効化しました。'.format(updated))
    deactivate_companies.short_description = "選択した企業を無効化"
    
    def export_company_csv(self, request, queryset):
        """企業データをCSVエクスポート"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="companies.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['EDINETコード', '証券コード', '企業名', '企業名カナ', '書類数', '有効フラグ'])
        
        for company in queryset:
            doc_count = DocumentMetadata.objects.filter(
                edinet_code=company.edinet_code, 
                legal_status='1'
            ).count()
            
            writer.writerow([
                company.edinet_code,
                company.securities_code or '',
                company.company_name,
                company.company_name_kana or '',
                doc_count,
                '有効' if company.is_active else '無効'
            ])
        
        return response
    export_company_csv.short_description = "選択した企業をCSVエクスポート"
    
    def analyze_companies(self, request, queryset):
        """選択した企業の分析を実行"""
        count = 0
        for company in queryset:
            # 最新の決算書類を取得
            latest_doc = DocumentMetadata.objects.filter(
                edinet_code=company.edinet_code,
                legal_status='1',
                doc_type_code__in=['120', '160', '030']
            ).order_by('-submit_date_time').first()
            
            if latest_doc:
                count += 1
        
        self.message_user(
            request, 
            '{} 社の最新決算書類が分析対象として確認されました。'.format(count)
        )
    analyze_companies.short_description = "選択した企業の分析可能性チェック"


@admin.register(DocumentMetadata)
class DocumentMetadataAdmin(admin.ModelAdmin):
    list_display = [
        'doc_id_link', 'company_name_link', 'doc_type_display', 
        'submit_date_display', 'legal_status_badge', 'format_flags', 
        'analysis_status', 'priority_badge'
    ]
    list_filter = [
        'legal_status', 'doc_type_code', 'file_date', 
        'xbrl_flag', 'pdf_flag', 'created_at'
    ]
    search_fields = ['doc_id', 'company_name', 'securities_code', 'doc_description', 'edinet_code']
    readonly_fields = ['created_at', 'updated_at', 'download_links', 'analysis_summary', 'priority_info']
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
            'fields': ('analysis_summary', 'priority_info'),
            'classes': ('collapse',),
            'description': '感情分析・財務分析の実行状況と優先度'
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
    
    actions = ['mark_as_reviewed', 'export_documents_csv', 'check_analysis_readiness']
    
    def doc_type_display(self, obj):
        """書類種別の表示名"""
        return obj.doc_type_display_name
    doc_type_display.short_description = '書類種別'
    doc_type_display.admin_order_field = 'doc_type_code'
    
    def priority_badge(self, obj):
        """分析優先度バッジ"""
        priority = obj.analysis_priority
        badge_classes = {
            'high': 'badge-success',
            'medium': 'badge-info',
            'low': 'badge-secondary'
        }
        display_names = {
            'high': '分析推奨',
            'medium': '分析可能',
            'low': '分析困難'
        }
        
        badge_class = badge_classes.get(priority, 'badge-secondary')
        display_name = display_names.get(priority, '不明')
        
        return format_html(
            '<span class="{}">{}</span>',
            badge_class, display_name
        )
    priority_badge.short_description = '分析優先度'
    
    def priority_info(self, obj):
        """分析優先度詳細情報"""
        info = [
            f"優先度: {obj.analysis_priority_display}",
            f"適合度スコア: {obj.analysis_suitability_score}",
            f"決算書類: {'はい' if obj.is_financial_statement else 'いいえ'}",
        ]
        
        if obj.xbrl_flag:
            info.append("XBRL利用可能")
        if obj.pdf_flag:
            info.append("PDF利用可能")
            
        return format_html('<br>'.join(info))
    priority_info.short_description = '分析優先度詳細'
    
    def doc_id_link(self, obj):
        """書類IDにダウンロードリンクを追加"""
        if obj.pdf_flag:
            download_url = reverse('earnings_analysis:document-download', args=[obj.doc_id])
            return format_html(
                '<a href="{}" target="_blank" title="PDFダウンロード">{}</a>',
                "{}?type=pdf".format(download_url), obj.doc_id
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
        """利用可能フォーマット表示"""
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
        sentiment_count = SentimentAnalysisSession.objects.filter(
            document=obj, processing_status='COMPLETED'
        ).count()
        
        financial_count = FinancialAnalysisSession.objects.filter(
            document=obj, processing_status='COMPLETED'
        ).count()
        
        badges = []
        if sentiment_count > 0:
            badges.append('<span class="badge badge-purple">感情×{}</span>'.format(sentiment_count))
        if financial_count > 0:
            badges.append('<span class="badge badge-blue">財務×{}</span>'.format(financial_count))
            
        return format_html(' '.join(badges)) if badges else '—'
    analysis_status.short_description = '分析実行状況'
    
    def analysis_summary(self, obj):
        """分析サマリー（管理画面用）"""
        sentiment_sessions = SentimentAnalysisSession.objects.filter(document=obj).order_by('-created_at')[:3]
        financial_sessions = FinancialAnalysisSession.objects.filter(document=obj).order_by('-created_at')[:3]
        
        summary = []
        
        if sentiment_sessions:
            summary.append('<strong>感情分析:</strong>')
            for session in sentiment_sessions:
                status_display = session.get_processing_status_display()
                score_text = ""
                if session.overall_score is not None:
                    try:
                        score = float(session.overall_score)
                        score_text = " ({:.2f})".format(score)
                    except (ValueError, TypeError):
                        score_text = " (形式エラー)"
                summary.append("- {}: {}{}".format(
                    session.created_at.strftime('%m/%d'), 
                    status_display, 
                    score_text
                ))
        
        if financial_sessions:
            summary.append('<strong>財務分析:</strong>')
            for session in financial_sessions:
                status_display = session.get_processing_status_display()
                score_text = ""
                if session.overall_health_score is not None:
                    try:
                        score = float(session.overall_health_score)
                        score_text = " ({:.1f})".format(score)
                    except (ValueError, TypeError):
                        score_text = " (形式エラー)"
                summary.append("- {}: {}{}".format(
                    session.created_at.strftime('%m/%d'), 
                    status_display, 
                    score_text
                ))
        
        return format_html('<br>'.join(summary)) if summary else '分析履歴なし'
    analysis_summary.short_description = '分析サマリー'
    
    def download_links(self, obj):
        """ダウンロードリンクの生成"""
        links = []
        base_url = reverse('earnings_analysis:document-download', args=[obj.doc_id])
        
        if obj.pdf_flag:
            links.append('<a href="{}?type=pdf" target="_blank" class="button">PDFダウンロード</a>'.format(base_url))
        if obj.xbrl_flag:
            links.append('<a href="{}?type=xbrl" target="_blank" class="button">XBRLダウンロード</a>'.format(base_url))
        
        return format_html('<br>'.join(links)) if links else '利用可能なダウンロードなし'
    download_links.short_description = 'ダウンロード'
    
    def mark_as_reviewed(self, request, queryset):
        """レビュー済みとしてマーク"""
        count = queryset.count()
        self.message_user(request, '{} 件の書類をレビュー済みとしました。'.format(count))
    mark_as_reviewed.short_description = "選択した書類をレビュー済みにする"
    
    def export_documents_csv(self, request, queryset):
        """書類データをCSVエクスポート"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="documents.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            '書類管理番号', '企業名', '証券コード', 'EDINETコード', 
            '書類種別', '提出日時', '法的ステータス', 'PDF', 'XBRL'
        ])
        
        for doc in queryset:
            writer.writerow([
                doc.doc_id,
                doc.company_name,
                doc.securities_code or '',
                doc.edinet_code,
                doc.doc_type_display_name,
                doc.submit_date_time.strftime('%Y-%m-%d %H:%M'),
                doc.get_legal_status_display(),
                'あり' if doc.pdf_flag else 'なし',
                'あり' if doc.xbrl_flag else 'なし'
            ])
        
        return response
    export_documents_csv.short_description = "選択した書類をCSVエクスポート"
    
    def check_analysis_readiness(self, request, queryset):
        """分析準備状況チェック"""
        ready_count = 0
        for doc in queryset:
            if doc.analysis_suitable and doc.xbrl_flag:
                ready_count += 1
        
        self.message_user(
            request, 
            '選択した {} 件中 {} 件が分析実行可能です。'.format(queryset.count(), ready_count)
        )
    check_analysis_readiness.short_description = "分析実行可能性チェック"


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
    
    # カスタムURLとビューを追加
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('execute-batch/', self.admin_site.admin_view(self.execute_batch_view), name='execute_batch'),
        ]
        return custom_urls + urls
    
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
    
    actions = ['rerun_batch', 'mark_as_reviewed']
    
    def execute_batch_view(self, request):
        """バッチ実行ビュー"""
        if request.method == 'POST':
            batch_date = request.POST.get('batch_date')
            if batch_date:
                try:
                    # バッチ実行ロジック（実際のバッチ処理を呼び出し）
                    from .services.batch_service import BatchService
                    
                    service = BatchService()
                    result = service.execute_daily_batch(batch_date)
                    
                    if result['success']:
                        messages.success(request, f"バッチ処理が正常に実行されました。処理件数: {result['processed_count']}")
                    else:
                        messages.error(request, f"バッチ処理でエラーが発生しました: {result['error']}")
                        
                except Exception as e:
                    logger.error(f"バッチ実行エラー: {e}")
                    messages.error(request, f"バッチ実行中にエラーが発生しました: {str(e)}")
                
                return HttpResponseRedirect('../')
        
        # バッチ実行フォームを表示
        context = {
            'title': 'バッチ実行',
            'has_permission': True,
            'opts': self.model._meta,
            'today': timezone.now().date(),
        }
        
        return render(request, 'admin/earnings_analysis/batch_execution/execute_batch.html', context)
    
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
        try:
            count = int(obj.processed_count)
            if count > 0:
                return format_html('<strong>{}</strong> 件', count)
            return '0 件'
        except (ValueError, TypeError):
            return '計算エラー'
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
                return '{}時間{}分{}秒'.format(hours, minutes, seconds)
            elif minutes > 0:
                return '{}分{}秒'.format(minutes, seconds)
            else:
                return '{}秒'.format(seconds)
        return '—'
    duration_display.short_description = '実行時間'
    
    def error_summary(self, obj):
        """エラーの概要表示"""
        if obj.error_message:
            summary = obj.error_message[:50]
            display_text = '{}...'.format(summary) if len(obj.error_message) > 50 else summary
            return format_html(
                '<span class="text-danger" title="{}">{}</span>',
                obj.error_message, display_text
            )
        return '—'
    error_summary.short_description = 'エラー概要'
    
    def error_details(self, obj):
        """エラーの詳細表示"""
        if obj.error_message:
            return format_html('<pre>{}</pre>', obj.error_message)
        return 'エラーなし'
    error_details.short_description = 'エラー詳細'
    
    def rerun_batch(self, request, queryset):
        """バッチを再実行"""
        for batch in queryset:
            if batch.status == 'FAILED':
                try:
                    from .services.batch_service import BatchService
                    service = BatchService()
                    service.execute_daily_batch(batch.batch_date.strftime('%Y-%m-%d'))
                    
                except Exception as e:
                    logger.error("バッチ再実行エラー: {}".format(e))
        
        self.message_user(request, '{} 件のバッチ再実行を開始しました。'.format(queryset.count()))
    rerun_batch.short_description = "失敗したバッチを再実行"
    
    def mark_as_reviewed(self, request, queryset):
        """確認済みとしてマーク"""
        count = queryset.count()
        self.message_user(request, '{} 件のバッチ実行を確認済みとしました。'.format(count))
    mark_as_reviewed.short_description = "選択したバッチを確認済みにする"


@admin.register(SentimentAnalysisSession)
class SentimentAnalysisSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_id_short', 'document_link', 'overall_score_display',
        'sentiment_label_badge', 'processing_status_badge', 'created_at'
    ]
    list_filter = ['processing_status', 'sentiment_label', 'created_at']
    search_fields = ['session_id', 'document__company_name', 'document__doc_id']
    readonly_fields = ['session_id', 'created_at', 'updated_at', 'analysis_summary_admin']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('セッション情報', {
            'fields': ('session_id', 'document', 'processing_status', 'created_at', 'updated_at', 'expires_at'),
        }),
        ('分析結果', {
            'fields': ('overall_score', 'sentiment_label'),
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
        return "{}...".format(obj.session_id[:8])
    session_id_short.short_description = 'セッションID'
    
    def document_link(self, obj):
        url = reverse('admin:earnings_analysis_documentmetadata_change', args=[obj.document.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, f"{obj.document.company_name} ({obj.document.doc_id})"
        )
    document_link.short_description = '対象書類'
    
    def overall_score_display(self, obj):
        if obj.overall_score is not None:
            try:
                score = float(obj.overall_score)
                if score >= 0.3:
                    color = 'text-success'
                elif score >= -0.3:
                    color = 'text-info'
                else:
                    color = 'text-danger'
                return format_html('<span class="{}">{:.2f}</span>', color, score)
            except (ValueError, TypeError):
                return format_html('<span class="text-muted">形式エラー</span>')
        return '—'
    overall_score_display.short_description = '感情スコア'
    
    def sentiment_label_badge(self, obj):
        if obj.sentiment_label:
            color_map = {'positive': 'badge-success', 'neutral': 'badge-info', 'negative': 'badge-danger'}
            color = color_map.get(obj.sentiment_label, 'badge-secondary')
            return format_html('<span class="{}">{}</span>', color, obj.get_sentiment_label_display())
        return '—'
    sentiment_label_badge.short_description = '感情ラベル'
    
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
            try:
                statistics = obj.analysis_result.get('statistics', {})
                
                summary = []
                if statistics.get('total_words_analyzed'):
                    summary.append("分析語数: {}".format(statistics['total_words_analyzed']))
                if statistics.get('sentences_analyzed'):
                    summary.append("分析文数: {}".format(statistics['sentences_analyzed']))
                if statistics.get('positive_words_count'):
                    summary.append("ポジティブ語: {}".format(statistics['positive_words_count']))
                if statistics.get('negative_words_count'):
                    summary.append("ネガティブ語: {}".format(statistics['negative_words_count']))
                
                if summary:
                    return format_html('<br>'.join(summary))
                else:
                    return '詳細なし'
            except (AttributeError, TypeError):
                return '分析結果解析エラー'
        return '分析結果なし'
    analysis_summary_admin.short_description = '分析サマリー'


@admin.register(SentimentAnalysisHistory)
class SentimentAnalysisHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'document_link', 'overall_score_display', 'sentiment_label_badge',
        'analysis_date', 'analysis_duration'
    ]
    list_filter = ['sentiment_label', 'analysis_date']
    search_fields = ['document__company_name', 'document__doc_id']
    date_hierarchy = 'analysis_date'
    
    def document_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            reverse('admin:earnings_analysis_documentmetadata_change', args=[obj.document.pk]),
            f"{obj.document.company_name} ({obj.document.doc_id})"
        )
    document_link.short_description = '対象書類'
    
    def overall_score_display(self, obj):
        try:
            score = float(obj.overall_score)
            if score >= 0.3:
                color = 'text-success'
            elif score >= -0.3:
                color = 'text-info'
            else:
                color = 'text-danger'
            return format_html('<span class="{}">{:.2f}</span>', color, score)
        except (ValueError, TypeError):
            return format_html('<span class="text-muted">形式エラー</span>')
    overall_score_display.short_description = '感情スコア'
    
    def sentiment_label_badge(self, obj):
        color_map = {'positive': 'badge-success', 'neutral': 'badge-info', 'negative': 'badge-danger'}
        color = color_map.get(obj.sentiment_label, 'badge-secondary')
        return format_html('<span class="{}">{}</span>', color, obj.get_sentiment_label_display())
    sentiment_label_badge.short_description = '感情ラベル'


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
        return "{}...".format(obj.session_id[:8])
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
            try:
                score = float(obj.overall_health_score)
                if score >= 80:
                    color = 'text-success'
                elif score >= 60:
                    color = 'text-info'
                elif score >= 40:
                    color = 'text-warning'
                else:
                    color = 'text-danger'
                return format_html('<span class="{}">{:.1f}</span>', color, score)
            except (ValueError, TypeError):
                return format_html('<span class="text-muted">形式エラー</span>')
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
            try:
                integrated = obj.analysis_result.get('integrated_analysis', {})
                key_findings = integrated.get('key_findings', {})
                
                summary = []
                if integrated.get('overall_score'):
                    summary.append("統合スコア: {}".format(integrated['overall_score']))
                
                strengths = key_findings.get('strengths', [])
                if strengths:
                    summary.append("強み: {}".format(', '.join(strengths[:2])))
                
                concerns = key_findings.get('concerns', [])
                if concerns:
                    summary.append("懸念: {}".format(', '.join(concerns[:2])))
                
                if summary:
                    return format_html('<br>'.join(summary))
                else:
                    return '詳細なし'
            except (AttributeError, TypeError):
                return '分析結果解析エラー'
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
        try:
            score = float(obj.overall_health_score)
            if score >= 80:
                color = 'text-success'
            elif score >= 60:
                color = 'text-info'
            elif score >= 40:
                color = 'text-warning'
            else:
                color = 'text-danger'
            return format_html('<span class="{}">{:.1f}</span>', color, score)
        except (ValueError, TypeError):
            return format_html('<span class="text-muted">形式エラー</span>')
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
    
    actions = ['recalculate_ratios', 'export_financial_csv']
    
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
        try:
            if obj.operating_margin:
                metrics.append("営業利益率: {}%".format(obj.operating_margin))
            if obj.roa:
                metrics.append("ROA: {}%".format(obj.roa))
            if obj.equity_ratio:
                metrics.append("自己資本比率: {}%".format(obj.equity_ratio))
        except (ValueError, TypeError):
            return '計算エラー'
        
        return format_html('<br>'.join(metrics)) if metrics else '—'
    key_metrics.short_description = '主要指標'
    
    def data_completeness_display(self, obj):
        if obj.data_completeness:
            try:
                percentage = float(obj.data_completeness) * 100
                if percentage >= 80:
                    color = 'text-success'
                elif percentage >= 60:
                    color = 'text-warning'
                else:
                    color = 'text-danger'
                return format_html('<span class="{}">{:.1f}%</span>', color, percentage)
            except (ValueError, TypeError):
                return format_html('<span class="text-muted">形式エラー</span>')
        return '—'
    data_completeness_display.short_description = 'データ完全性'
    
    def calculated_ratios(self, obj):
        ratios = []
        try:
            if obj.operating_margin is not None:
                ratios.append("営業利益率: {}%".format(obj.operating_margin))
            if obj.net_margin is not None:
                ratios.append("当期純利益率: {}%".format(obj.net_margin))
            if obj.roa is not None:
                ratios.append("ROA: {}%".format(obj.roa))
            if obj.equity_ratio is not None:
                ratios.append("自己資本比率: {}%".format(obj.equity_ratio))
        except (ValueError, TypeError):
            return '計算エラー'
        
        return format_html('<br>'.join(ratios)) if ratios else '計算済み指標なし'
    calculated_ratios.short_description = '計算済み財務指標'
    
    def recalculate_ratios(self, request, queryset):
        """財務比率を再計算"""
        for financial_data in queryset:
            financial_data.save()  # saveメソッドで比率が再計算される
        
        self.message_user(request, '{} 件の財務比率を再計算しました。'.format(queryset.count()))
    recalculate_ratios.short_description = "選択した財務データの比率を再計算"
    
    def export_financial_csv(self, request, queryset):
        """財務データをCSVエクスポート"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="financial_data.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            '企業名', '証券コード', '期間種別', '期間開始', '期間終了',
            '売上高', '営業利益', '当期純利益', '総資産', '純資産',
            '営業利益率', 'ROA', '自己資本比率'
        ])
        
        for data in queryset:
            company_name = data.company.company_name if data.company else data.document.company_name
            securities_code = data.company.securities_code if data.company else data.document.securities_code
            
            writer.writerow([
                company_name,
                securities_code or '',
                data.get_period_type_display(),
                data.period_start,
                data.period_end,
                data.net_sales or 0,
                data.operating_income or 0,
                data.net_income or 0,
                data.total_assets or 0,
                data.net_assets or 0,
                data.operating_margin or 0,
                data.roa or 0,
                data.equity_ratio or 0,
            ])
        
        return response
    export_financial_csv.short_description = "選択した財務データをCSVエクスポート"


@admin.register(FinancialBenchmark)
class FinancialBenchmarkAdmin(admin.ModelAdmin):
    list_display = [
        'industry_category', 'industry_subcategory', 'reference_period',
        'sample_size', 'operating_margin_median', 'roa_median', 'equity_ratio_median'
    ]
    list_filter = ['industry_category', 'reference_period']
    search_fields = ['industry_category', 'industry_subcategory']


# 管理画面のカスタムCSS
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

/* バッチ実行ボタンのスタイル */
.batch-execute-btn {
    background-color: #007bff;
    color: white;
    padding: 10px 20px;
    text-decoration: none;
    border-radius: 4px;
    display: inline-block;
    margin: 10px 0;
}

.batch-execute-btn:hover {
    background-color: #0056b3;
    color: white;
    text-decoration: none;
}

/* 統計情報のスタイル */
.admin-stats {
    background: #f8f9fa;
    padding: 15px;
    border-radius: 5px;
    margin: 10px 0;
}

.admin-stats h4 {
    color: #495057;
    margin-bottom: 10px;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
}

.stat-item {
    text-align: center;
    padding: 10px;
    background: white;
    border-radius: 3px;
    border: 1px solid #dee2e6;
}

.stat-value {
    font-size: 24px;
    font-weight: bold;
    color: #007bff;
}

.stat-label {
    font-size: 12px;
    color: #6c757d;
    text-transform: uppercase;
}
</style>
コーポマインドリーダー
''')