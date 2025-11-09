# analysis_template/admin.py
from django.contrib import admin
from .models import (
    AnalysisTemplate, TemplateCompany, MetricDefinition, TemplateMetrics,
    IndustryBenchmark
)


class TemplateCompanyInline(admin.TabularInline):
    model = TemplateCompany
    extra = 1
    autocomplete_fields = ['company']


class TemplateMetricsInline(admin.TabularInline):
    model = TemplateMetrics
    extra = 1
    autocomplete_fields = ['company', 'metric_definition']


@admin.register(AnalysisTemplate)
class AnalysisTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'user', 'get_company_count', 'created_at', 'updated_at'
    ]
    list_filter = ['created_at', 'updated_at', 'user']
    search_fields = ['name', 'description', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [TemplateCompanyInline, TemplateMetricsInline]
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'description', 'user')
        }),
        ('タイムスタンプ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_company_count(self, obj):
        return obj.get_company_count()
    get_company_count.short_description = '企業数'


@admin.register(TemplateCompany)
class TemplateCompanyAdmin(admin.ModelAdmin):
    list_display = ['template', 'company', 'display_order', 'added_at']
    list_filter = ['added_at', 'template']
    search_fields = ['template__name', 'company__name', 'company__code']
    autocomplete_fields = ['template', 'company']
    ordering = ['template', 'display_order']


@admin.register(MetricDefinition)
class MetricDefinitionAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 'name', 'metric_type', 'metric_group', 'unit',
        'chart_suitable', 'is_active', 'display_order'
    ]
    list_filter = ['metric_type', 'metric_group', 'chart_suitable', 'is_active']
    search_fields = ['name', 'display_name', 'description']
    list_editable = ['chart_suitable', 'is_active', 'display_order']
    ordering = ['metric_group', 'display_order', 'name']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'display_name', 'metric_type', 'metric_group', 'description')
        }),
        ('値の設定', {
            'fields': ('unit', 'min_value', 'max_value')
        }),
        ('表示設定', {
            'fields': ('chart_suitable', 'is_active', 'display_order')
        }),
    )


@admin.register(TemplateMetrics)
class TemplateMetricsAdmin(admin.ModelAdmin):
    list_display = [
        'template', 'company', 'metric_definition', 'value',
        'fiscal_year', 'updated_at'
    ]
    list_filter = ['fiscal_year', 'updated_at', 'metric_definition']
    search_fields = [
        'template__name', 'company__name', 'company__code',
        'metric_definition__display_name'
    ]
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['template', 'company', 'metric_definition']
    
    fieldsets = (
        ('関連情報', {
            'fields': ('template', 'company', 'metric_definition')
        }),
        ('指標値', {
            'fields': ('value', 'fiscal_year', 'notes')
        }),
        ('タイムスタンプ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(IndustryBenchmark)
class IndustryBenchmarkAdmin(admin.ModelAdmin):
    list_display = [
        'industry_name', 'metric_definition', 'average_value',
        'excellent_threshold', 'poor_threshold', 'fiscal_year'
    ]
    list_filter = ['fiscal_year', 'industry_code', 'metric_definition']
    search_fields = ['industry_name', 'industry_code', 'metric_definition__display_name']
    autocomplete_fields = ['metric_definition']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('industry_code', 'industry_name', 'metric_definition', 'fiscal_year')
        }),
        ('統計値', {
            'fields': ('average_value', 'median_value', 'lower_quartile', 'upper_quartile')
        }),
        ('評価基準', {
            'fields': ('excellent_threshold', 'poor_threshold', 'notes')
        }),
        ('タイムスタンプ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )