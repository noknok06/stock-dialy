from django.contrib import admin
from django.utils.html import format_html
from .models import Company, DocumentMetadata, BatchExecution

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['edinet_code', 'securities_code', 'company_name', 'is_active', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['edinet_code', 'securities_code', 'company_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('edinet_code', 'securities_code', 'company_name', 'company_name_kana')
        }),
        ('詳細情報', {
            'fields': ('jcn', 'is_active')
        }),
        ('管理情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(DocumentMetadata)
class DocumentMetadataAdmin(admin.ModelAdmin):
    list_display = [
        'doc_id', 'company_name', 'doc_type_code', 
        'submit_date_time', 'legal_status', 'format_flags'
    ]
    list_filter = [
        'legal_status', 'doc_type_code', 'file_date', 
        'xbrl_flag', 'pdf_flag', 'created_at'
    ]
    search_fields = ['doc_id', 'company_name', 'securities_code', 'doc_description']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'submit_date_time'
    
    fieldsets = (
        ('基本情報', {
            'fields': ('doc_id', 'company_name', 'securities_code', 'edinet_code')
        }),
        ('書類分類', {
            'fields': ('doc_type_code', 'ordinance_code', 'form_code', 'fund_code')
        }),
        ('期間・日時', {
            'fields': ('period_start', 'period_end', 'submit_date_time', 'file_date')
        }),
        ('書類内容', {
            'fields': ('doc_description',)
        }),
        ('利用可能フォーマット', {
            'fields': ('xbrl_flag', 'pdf_flag', 'csv_flag', 'attach_doc_flag', 'english_doc_flag')
        }),
        ('ステータス', {
            'fields': ('legal_status', 'withdrawal_status', 'doc_info_edit_status', 'disclosure_status')
        }),
        ('管理情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def format_flags(self, obj):
        """利用可能フォーマット表示"""
        flags = []
        if obj.pdf_flag:
            flags.append('<span style="color: green;">PDF</span>')
        if obj.xbrl_flag:
            flags.append('<span style="color: blue;">XBRL</span>')
        if obj.csv_flag:
            flags.append('<span style="color: orange;">CSV</span>')
        if obj.attach_doc_flag:
            flags.append('<span style="color: purple;">添付</span>')
        if obj.english_doc_flag:
            flags.append('<span style="color: red;">英文</span>')
        
        return format_html(' | '.join(flags)) if flags else '-'
    
    format_flags.short_description = '利用可能フォーマット'

@admin.register(BatchExecution)
class BatchExecutionAdmin(admin.ModelAdmin):
    list_display = ['batch_date', 'status', 'processed_count', 'started_at', 'completed_at', 'duration']
    list_filter = ['status', 'batch_date']
    readonly_fields = ['duration', 'created_at']
    
    def duration(self, obj):
        """実行時間計算"""
        if obj.started_at and obj.completed_at:
            duration = obj.completed_at - obj.started_at
            return str(duration).split('.')[0]  # ミリ秒除去
        return '-'
    
    duration.short_description = '実行時間'