# earnings_analysis/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.http import HttpResponse
import csv
from datetime import datetime

from .models import Company, DocumentMetadata, BatchExecution

# Admin Site の設定
admin.site.site_header = '決算書類管理システム'
admin.site.site_title = '決算書類管理'
admin.site.index_title = 'システム管理'

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = [
        'securities_code_display', 'company_name_link', 'edinet_code', 
        'document_count', 'is_active_badge', 'updated_at'
    ]
    list_filter = ['is_active', 'created_at', 'updated_at']
    search_fields = ['edinet_code', 'securities_code', 'company_name', 'company_name_kana']
    readonly_fields = ['created_at', 'updated_at', 'document_count_admin']
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
            'fields': ('document_count_admin',),
            'classes': ('collapse',),
            'description': '関連する書類の統計情報'
        }),
        ('管理情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'システム管理用タイムスタンプ'
        }),
    )
    
    actions = ['activate_companies', 'deactivate_companies', 'export_to_csv']
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            doc_count=Count('documentmetadata', filter=Q(documentmetadata__legal_status='1'))
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
    
    def document_count_admin(self, obj):
        """管理画面用の詳細な書類数"""
        total = DocumentMetadata.objects.filter(edinet_code=obj.edinet_code).count()
        active = DocumentMetadata.objects.filter(edinet_code=obj.edinet_code, legal_status='1').count()
        return format_html(
            '総数: {} 件<br>有効: {} 件',
            total, active
        )
    document_count_admin.short_description = '書類統計'
    
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
    
    def export_to_csv(self, request, queryset):
        """企業データをCSVエクスポート"""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="companies_{datetime.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['EDINETコード', '証券コード', '企業名', '企業名カナ', '法人番号', '有効フラグ', '作成日', '更新日'])
        
        for company in queryset:
            writer.writerow([
                company.edinet_code,
                company.securities_code or '',
                company.company_name,
                company.company_name_kana or '',
                company.jcn or '',
                '有効' if company.is_active else '無効',
                company.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                company.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            ])
        
        return response
    export_to_csv.short_description = "選択した企業をCSVエクスポート"


@admin.register(DocumentMetadata)
class DocumentMetadataAdmin(admin.ModelAdmin):
    list_display = [
        'doc_id_link', 'company_name_link', 'doc_type_code', 
        'submit_date_display', 'legal_status_badge', 'format_flags'
    ]
    list_filter = [
        'legal_status', 'doc_type_code', 'file_date', 
        'xbrl_flag', 'pdf_flag', 'created_at'
    ]
    search_fields = ['doc_id', 'company_name', 'securities_code', 'doc_description']
    readonly_fields = ['created_at', 'updated_at', 'download_links']
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
            'fields': ('xbrl_flag', 'pdf_flag', 'csv_flag', 'attach_doc_flag', 'english_doc_flag'),
            'description': 'ダウンロード可能なファイル形式'
        }),
        ('ステータス', {
            'fields': ('legal_status', 'withdrawal_status', 'doc_info_edit_status', 'disclosure_status'),
            'description': '書類の現在のステータス'
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
    
    actions = ['export_to_csv', 'mark_as_reviewed']
    
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
        """利用可能フォーマット表示"""
        flags = []
        if obj.pdf_flag:
            flags.append('<span class="badge badge-danger">PDF</span>')
        if obj.xbrl_flag:
            flags.append('<span class="badge badge-primary">XBRL</span>')
        if obj.csv_flag:
            flags.append('<span class="badge badge-success">CSV</span>')
        if obj.attach_doc_flag:
            flags.append('<span class="badge badge-warning">添付</span>')
        if obj.english_doc_flag:
            flags.append('<span class="badge badge-info">英文</span>')
        
        return format_html(' '.join(flags)) if flags else '—'
    format_flags.short_description = '利用可能フォーマット'
    
    def download_links(self, obj):
        """ダウンロードリンクの生成"""
        links = []
        base_url = reverse('earnings_analysis:document-download', args=[obj.doc_id])
        
        if obj.pdf_flag:
            links.append(f'<a href="{base_url}?type=pdf" target="_blank" class="button">PDFダウンロード</a>')
        if obj.xbrl_flag:
            links.append(f'<a href="{base_url}?type=xbrl" target="_blank" class="button">XBRLダウンロード</a>')
        if obj.csv_flag:
            links.append(f'<a href="{base_url}?type=csv" target="_blank" class="button">CSVダウンロード</a>')
        
        return format_html('<br>'.join(links)) if links else '利用可能なダウンロードなし'
    download_links.short_description = 'ダウンロード'
    
    def export_to_csv(self, request, queryset):
        """書類データをCSVエクスポート"""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="documents_{datetime.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            '書類管理番号', '企業名', '証券コード', 'EDINETコード', 
            '書類概要', '提出日時', '書類種別コード', '縦覧区分'
        ])
        
        for doc in queryset:
            writer.writerow([
                doc.doc_id,
                doc.company_name,
                doc.securities_code or '',
                doc.edinet_code,
                doc.doc_description,
                doc.submit_date_time.strftime('%Y-%m-%d %H:%M:%S'),
                doc.doc_type_code,
                doc.get_legal_status_display(),
            ])
        
        return response
    export_to_csv.short_description = "選択した書類をCSVエクスポート"
    
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
</style>
決算書類管理システム
''')