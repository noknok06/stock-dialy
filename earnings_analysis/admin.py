# earnings_analysis/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    CompanyEarnings, EarningsReport, CashFlowAnalysis, 
    SentimentAnalysis, EarningsAlert, AnalysisHistory
)


@admin.register(CompanyEarnings)
class CompanyEarningsAdmin(admin.ModelAdmin):
    list_display = [
        'company_code', 'company_name', 'edinet_code', 
        'fiscal_year_end_month', 'latest_analysis_date', 
        'is_active', 'reports_count'
    ]
    list_filter = ['is_active', 'fiscal_year_end_month', 'latest_analysis_date']
    search_fields = ['company_code', 'company_name', 'edinet_code']
    list_editable = ['is_active']
    ordering = ['company_code']
    
    def reports_count(self, obj):
        count = obj.reports.count()
        if count > 0:
            url = reverse('admin:earnings_analysis_earningsreport_changelist')
            return format_html('<a href="{}?company__id={}">{} 件</a>', url, obj.id, count)
        return '0 件'
    
    reports_count.short_description = '報告書数'
    
    actions = ['activate_companies', 'deactivate_companies']
    
    def activate_companies(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} 社を分析対象に設定しました。')
    activate_companies.short_description = '選択した企業を分析対象にする'
    
    def deactivate_companies(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} 社を分析対象外に設定しました。')
    deactivate_companies.short_description = '選択した企業を分析対象外にする'


class CashFlowAnalysisInline(admin.StackedInline):
    model = CashFlowAnalysis
    extra = 0
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('キャッシュフロー金額', {
            'fields': ('operating_cf', 'investing_cf', 'financing_cf', 'free_cf')
        }),
        ('分析結果', {
            'fields': ('cf_pattern', 'health_score', 'analysis_summary')
        }),
        ('前期比較', {
            'fields': ('operating_cf_change_rate', 'free_cf_change_rate')
        }),
        ('リスク要因', {
            'fields': ('risk_factors',)
        }),
    )


class SentimentAnalysisInline(admin.StackedInline):
    model = SentimentAnalysis
    extra = 0
    readonly_fields = ['created_at', 'extracted_keywords']
    
    fieldsets = (
        ('感情分析指標', {
            'fields': ('positive_expressions', 'negative_expressions', 
                      'confidence_keywords', 'uncertainty_keywords', 'risk_mentions')
        }),
        ('計算結果', {
            'fields': ('sentiment_score', 'confidence_level')
        }),
        ('前期比較', {
            'fields': ('sentiment_change', 'confidence_change')
        }),
        ('分析要約', {
            'fields': ('analysis_summary',)
        }),
    )


@admin.register(EarningsReport)
class EarningsReportAdmin(admin.ModelAdmin):
    list_display = [
        'company_name', 'fiscal_year', 'quarter', 'report_type', 
        'submission_date', 'is_processed', 'has_cashflow_analysis', 
        'has_sentiment_analysis'
    ]
    list_filter = [
        'report_type', 'quarter', 'is_processed', 'submission_date', 
        'company__fiscal_year_end_month'
    ]
    search_fields = ['company__company_name', 'company__company_code', 'document_id']
    readonly_fields = ['document_id', 'created_at', 'updated_at']
    date_hierarchy = 'submission_date'
    
    inlines = [CashFlowAnalysisInline, SentimentAnalysisInline]
    
    fieldsets = (
        ('基本情報', {
            'fields': ('company', 'report_type', 'fiscal_year', 'quarter')
        }),
        ('EDINET情報', {
            'fields': ('document_id', 'submission_date')
        }),
        ('処理状況', {
            'fields': ('is_processed', 'processing_error')
        }),
        ('メタ情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def company_name(self, obj):
        return f"{obj.company.company_name} ({obj.company.company_code})"
    company_name.short_description = '企業名'
    
    def has_cashflow_analysis(self, obj):
        return hasattr(obj, 'cashflow_analysis')
    has_cashflow_analysis.boolean = True
    has_cashflow_analysis.short_description = 'CF分析'
    
    def has_sentiment_analysis(self, obj):
        return hasattr(obj, 'sentiment_analysis')
    has_sentiment_analysis.boolean = True
    has_sentiment_analysis.short_description = '感情分析'
    
    actions = ['reprocess_reports']
    
    def reprocess_reports(self, request, queryset):
        # 再処理フラグをリセット
        updated = queryset.update(is_processed=False, processing_error='')
        self.message_user(request, f'{updated} 件の報告書を再処理対象に設定しました。')
    reprocess_reports.short_description = '選択した報告書を再処理する'


@admin.register(CashFlowAnalysis)
class CashFlowAnalysisAdmin(admin.ModelAdmin):
    list_display = [
        'company_name', 'fiscal_year_quarter', 'cf_pattern', 'health_score',
        'operating_cf_formatted', 'free_cf_formatted', 'created_at'
    ]
    list_filter = ['cf_pattern', 'health_score', 'created_at']
    search_fields = ['report__company__company_name', 'report__company__company_code']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def company_name(self, obj):
        return obj.report.company.company_name
    company_name.short_description = '企業名'
    
    def fiscal_year_quarter(self, obj):
        return f"{obj.report.fiscal_year} {obj.report.quarter}"
    fiscal_year_quarter.short_description = '決算期'
    
    def operating_cf_formatted(self, obj):
        if obj.operating_cf:
            value = float(obj.operating_cf)
            color = 'green' if value > 0 else 'red'
            return format_html('<span style="color: {}">{:,.0f}百万円</span>', color, value)
        return '-'
    operating_cf_formatted.short_description = '営業CF'
    
    def free_cf_formatted(self, obj):
        if obj.free_cf:
            value = float(obj.free_cf)
            color = 'green' if value > 0 else 'red'
            return format_html('<span style="color: {}">{:,.0f}百万円</span>', color, value)
        return '-'
    free_cf_formatted.short_description = 'フリーCF'


@admin.register(SentimentAnalysis)
class SentimentAnalysisAdmin(admin.ModelAdmin):
    list_display = [
        'company_name', 'fiscal_year_quarter', 'sentiment_score_formatted',
        'confidence_level', 'risk_mentions', 'created_at'
    ]
    list_filter = ['confidence_level', 'created_at']
    search_fields = ['report__company__company_name', 'report__company__company_code']
    readonly_fields = ['created_at', 'extracted_keywords_display']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('基本情報', {
            'fields': ('report',)
        }),
        ('感情分析結果', {
            'fields': ('sentiment_score', 'confidence_level', 'analysis_summary')
        }),
        ('詳細指標', {
            'fields': ('positive_expressions', 'negative_expressions', 
                      'confidence_keywords', 'uncertainty_keywords', 'risk_mentions')
        }),
        ('前期比較', {
            'fields': ('sentiment_change', 'confidence_change')
        }),
        ('抽出キーワード', {
            'fields': ('extracted_keywords_display',),
            'classes': ('collapse',)
        }),
    )
    
    def company_name(self, obj):
        return obj.report.company.company_name
    company_name.short_description = '企業名'
    
    def fiscal_year_quarter(self, obj):
        return f"{obj.report.fiscal_year} {obj.report.quarter}"
    fiscal_year_quarter.short_description = '決算期'
    
    def sentiment_score_formatted(self, obj):
        score = float(obj.sentiment_score)
        if score > 20:
            color = 'green'
        elif score < -20:
            color = 'red'
        else:
            color = 'orange'
        return format_html('<span style="color: {}">{:.1f}</span>', color, score)
    sentiment_score_formatted.short_description = '感情スコア'
    
    def extracted_keywords_display(self, obj):
        keywords = obj.get_extracted_keywords_dict()
        if not keywords:
            return '抽出されたキーワードはありません'
        
        html = ''
        for category, word_list in keywords.items():
            if word_list:
                html += f'<h4>{category.title()}</h4><ul>'
                for item in word_list[:5]:  # 最初の5件のみ表示
                    if isinstance(item, dict):
                        keyword = item.get('keyword', '')
                        context = item.get('context', '')[:50] + '...'
                        html += f'<li><strong>{keyword}</strong>: {context}</li>'
                    else:
                        html += f'<li>{item}</li>'
                html += '</ul>'
        
        return mark_safe(html)
    extracted_keywords_display.short_description = '抽出キーワード'


@admin.register(EarningsAlert)
class EarningsAlertAdmin(admin.ModelAdmin):
    list_display = [
        'user_name', 'company_name', 'alert_type', 'is_enabled', 
        'days_before_earnings', 'created_at'
    ]
    list_filter = ['alert_type', 'is_enabled', 'created_at']
    search_fields = ['user__username', 'company__company_name', 'company__company_code']
    
    def user_name(self, obj):
        return obj.user.username
    user_name.short_description = 'ユーザー'
    
    def company_name(self, obj):
        return f"{obj.company.company_name} ({obj.company.company_code})"
    company_name.short_description = '企業名'


@admin.register(AnalysisHistory)
class AnalysisHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'company_name', 'fiscal_year', 'quarter', 'analysis_date', 
        'processing_time_seconds', 'has_cashflow', 'has_sentiment'
    ]
    list_filter = ['analysis_date', 'quarter']
    search_fields = ['company__company_name', 'company__company_code']
    readonly_fields = ['analysis_date', 'processing_time_seconds']
    date_hierarchy = 'analysis_date'
    
    def company_name(self, obj):
        return obj.company.company_name
    company_name.short_description = '企業名'
    
    def has_cashflow(self, obj):
        return bool(obj.cashflow_summary)
    has_cashflow.boolean = True
    has_cashflow.short_description = 'CF分析'
    
    def has_sentiment(self, obj):
        return bool(obj.sentiment_summary)
    has_sentiment.boolean = True
    has_sentiment.short_description = '感情分析'


# カスタム管理画面のタイトル設定
admin.site.site_header = 'カブログ 決算分析システム'
admin.site.site_title = 'カブログ 決算分析'
admin.site.index_title = '決算分析管理'