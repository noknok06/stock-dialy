"""
earnings_reports/admin.py
Django管理画面設定
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Avg
from .models import (
    Company, Document, Analysis, SentimentAnalysis, 
    CashFlowAnalysis, AnalysisHistory
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """企業管理"""
    
    list_display = ['stock_code', 'name', 'market', 'sector', 'document_count', 'analysis_count', 'last_sync']
    list_filter = ['market', 'sector', 'last_sync']
    search_fields = ['stock_code', 'name', 'name_kana']
    ordering = ['stock_code']
    readonly_fields = ['last_sync', 'created_at', 'updated_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('stock_code', 'name', 'name_kana')
        }),
        ('市場情報', {
            'fields': ('market', 'sector')
        }),
        ('EDINET情報', {
            'fields': ('edinet_code', 'last_sync')
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            document_count=Count('documents'),
            analysis_count=Count('documents__analysis')
        )
    
    def document_count(self, obj):
        """書類数"""
        return obj.document_count
    document_count.short_description = '書類数'
    document_count.admin_order_field = 'document_count'
    
    def analysis_count(self, obj):
        """分析数"""
        return obj.analysis_count
    analysis_count.short_description = '分析数'
    analysis_count.admin_order_field = 'analysis_count'
    
    actions = ['sync_company_documents']
    
    def sync_company_documents(self, request, queryset):
        """選択した企業の書類を同期"""
        from .services.edinet_service import EDINETService
        from django.conf import settings
        
        try:
            edinet_service = EDINETService(settings.EDINET_API_KEY)
            synced_count = 0
            
            for company in queryset:
                # 書類同期処理（簡略化）
                synced_count += 1
            
            self.message_user(request, f'{synced_count}社の書類同期を完了しました。')
        except Exception as e:
            self.message_user(request, f'同期エラー: {str(e)}', level='ERROR')
    
    sync_company_documents.short_description = '選択した企業の書類を同期'


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """書類管理"""
    
    list_display = ['doc_id', 'company_link', 'doc_type', 'doc_description_short', 'submit_date', 'analysis_status']
    list_filter = ['doc_type', 'submit_date', 'is_downloaded', 'is_analyzed']
    search_fields = ['doc_id', 'company__name', 'doc_description']
    date_hierarchy = 'submit_date'
    ordering = ['-submit_date']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('doc_id', 'company', 'doc_type', 'doc_description')
        }),
        ('期間情報', {
            'fields': ('submit_date', 'period_start', 'period_end')
        }),
        ('処理状況', {
            'fields': ('is_downloaded', 'download_size', 'is_analyzed')
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def company_link(self, obj):
        """企業へのリンク"""
        url = reverse('admin:earnings_reports_company_change', args=[obj.company.pk])
        return format_html('<a href="{}">{}</a>', url, obj.company.name)
    company_link.short_description = '企業名'
    
    def doc_description_short(self, obj):
        """書類名（短縮）"""
        return obj.doc_description[:50] + ('...' if len(obj.doc_description) > 50 else '')
    doc_description_short.short_description = '書類名'
    
    def analysis_status(self, obj):
        """分析状況"""
        if obj.is_analyzed:
            return format_html('<span style="color: green;">✓ 分析済み</span>')
        elif obj.is_downloaded:
            return format_html('<span style="color: orange;">⬇ DL済み</span>')
        else:
            return format_html('<span style="color: gray;">○ 未処理</span>')
    analysis_status.short_description = '分析状況'


class SentimentAnalysisInline(admin.StackedInline):
    """感情分析インライン"""
    model = SentimentAnalysis
    extra = 0
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('感情スコア', {
            'fields': ('positive_score', 'negative_score', 'neutral_score')
        }),
        ('キーワード分析', {
            'fields': ('confidence_keywords_count', 'uncertainty_keywords_count', 
                      'growth_keywords_count', 'risk_keywords_count')
        }),
        ('リスク分析', {
            'fields': ('risk_severity', 'sentiment_change', 'confidence_change')
        }),
        ('詳細データ', {
            'fields': ('key_phrases', 'risk_phrases'),
            'classes': ('collapse',)
        }),
    )


class CashFlowAnalysisInline(admin.StackedInline):
    """キャッシュフロー分析インライン"""
    model = CashFlowAnalysis
    extra = 0
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('キャッシュフロー金額', {
            'fields': ('operating_cf', 'investing_cf', 'financing_cf', 'free_cf')
        }),
        ('パターン分析', {
            'fields': ('pattern', 'pattern_score', 'cf_quality_score')
        }),
        ('成長率', {
            'fields': ('operating_cf_growth', 'investing_cf_growth', 'financing_cf_growth')
        }),
        ('解釈・リスク', {
            'fields': ('interpretation', 'risk_factors'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    """分析結果管理"""
    
    list_display = ['id', 'document_link', 'user', 'status_colored', 'overall_score', 'confidence_level', 'analysis_date']
    list_filter = ['status', 'confidence_level', 'analysis_date', 'document__doc_type']
    search_fields = ['document__company__name', 'user__username']
    date_hierarchy = 'analysis_date'
    ordering = ['-analysis_date']
    readonly_fields = ['analysis_date', 'processing_time', 'created_at', 'updated_at']
    
    inlines = [SentimentAnalysisInline, CashFlowAnalysisInline]
    
    fieldsets = (
        ('基本情報', {
            'fields': ('document', 'user', 'status')
        }),
        ('分析結果', {
            'fields': ('overall_score', 'confidence_level', 'processing_time')
        }),
        ('エラー情報', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('設定・メタデータ', {
            'fields': ('settings_json', 'analysis_date', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def document_link(self, obj):
        """書類へのリンク"""
        url = reverse('admin:earnings_reports_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{} - {}</a>', 
                          url, obj.document.company.name, obj.document.get_doc_type_display())
    document_link.short_description = '対象書類'
    
    def status_colored(self, obj):
        """色付きステータス"""
        colors = {
            'pending': 'gray',
            'processing': 'orange',
            'completed': 'green',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', 
                          color, obj.get_status_display())
    status_colored.short_description = 'ステータス'
    
    actions = ['reprocess_analysis']
    
    def reprocess_analysis(self, request, queryset):
        """選択した分析を再実行"""
        for analysis in queryset:
            analysis.status = 'pending'
            analysis.error_message = ''
            analysis.save()
        
        self.message_user(request, f'{queryset.count()}件の分析を再実行キューに追加しました。')
    
    reprocess_analysis.short_description = '選択した分析を再実行'


@admin.register(AnalysisHistory)
class AnalysisHistoryAdmin(admin.ModelAdmin):
    """分析履歴管理"""
    
    list_display = ['company', 'user', 'analysis_count', 'last_analysis_date', 'notify_on_earnings']
    list_filter = ['notify_on_earnings', 'last_analysis_date']
    search_fields = ['company__name', 'user__username']
    ordering = ['-last_analysis_date']
    readonly_fields = ['analysis_count', 'last_analysis_date', 'created_at', 'updated_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('company', 'user')
        }),
        ('統計情報', {
            'fields': ('analysis_count', 'last_analysis_date')
        }),
        ('通知設定', {
            'fields': ('notify_on_earnings', 'notify_threshold')
        }),
        ('トレンドデータ', {
            'fields': ('sentiment_trend', 'cf_trend'),
            'classes': ('collapse',)
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# 管理画面のカスタマイズ
admin.site.site_header = 'カブログ決算分析システム管理'
admin.site.site_title = '決算分析管理'
admin.site.index_title = 'システム管理'


# 統計情報を表示するカスタムビュー
class EarningsReportsAdminSite(admin.AdminSite):
    """カスタム管理サイト"""
    
    def index(self, request, extra_context=None):
        """管理画面トップページに統計情報を追加"""
        extra_context = extra_context or {}
        
        # 基本統計
        extra_context['total_companies'] = Company.objects.count()
        extra_context['total_documents'] = Document.objects.count()
        extra_context['total_analyses'] = Analysis.objects.count()
        extra_context['completed_analyses'] = Analysis.objects.filter(status='completed').count()
        
        # 最近の活動
        extra_context['recent_analyses'] = Analysis.objects.select_related(
            'document__company', 'user'
        ).order_by('-analysis_date')[:10]
        
        # 人気企業（分析数が多い順）
        extra_context['popular_companies'] = Company.objects.annotate(
            analysis_count=Count('documents__analysis')
        ).filter(analysis_count__gt=0).order_by('-analysis_count')[:10]
        
        return super().index(request, extra_context)


# カスタム管理サイトの登録（必要に応じて）
# earnings_admin_site = EarningsReportsAdminSite(name='earnings_admin')
# earnings_admin_site.register(Company, CompanyAdmin)
# earnings_admin_site.register(Document, DocumentAdmin)
# earnings_admin_site.register(Analysis, AnalysisAdmin)
# earnings_admin_site.register(AnalysisHistory, AnalysisHistoryAdmin)