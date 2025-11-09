# analysis_template/admin.py
from django.contrib import admin
from .models import (
    AnalysisTemplate, TemplateCompany, MetricDefinition,
    TemplateMetrics, IndustryBenchmark, CompanyScore
)


class TemplateCompanyInline(admin.TabularInline):
    model = TemplateCompany
    extra = 1
    autocomplete_fields = ['company']


class TemplateMetricsInline(admin.TabularInline):
    model = TemplateMetrics
    extra = 0
    autocomplete_fields = ['company', 'metric_definition']


@admin.register(AnalysisTemplate)
class AnalysisTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'get_company_count', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name', 'description', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [TemplateCompanyInline]
    
    def get_company_count(self, obj):
        return obj.get_company_count()
    get_company_count.short_description = '企業数'


@admin.register(MetricDefinition)
class MetricDefinitionAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'metric_type', 'metric_group', 
                    'is_active', 'display_order']
    list_filter = ['metric_type', 'metric_group', 'is_active']
    search_fields = ['name', 'display_name', 'description']
    list_editable = ['display_order', 'is_active']
    ordering = ['display_order', 'name']


@admin.register(TemplateMetrics)
class TemplateMetricsAdmin(admin.ModelAdmin):
    list_display = ['template', 'company', 'metric_definition', 'value', 
                    'fiscal_year', 'updated_at']
    list_filter = ['template', 'fiscal_year', 'updated_at']
    search_fields = ['company__name', 'metric_definition__display_name']
    autocomplete_fields = ['template', 'company', 'metric_definition']


@admin.register(IndustryBenchmark)
class IndustryBenchmarkAdmin(admin.ModelAdmin):
    list_display = ['industry_name', 'metric_definition', 'average_value', 
                    'fiscal_year', 'updated_at']
    list_filter = ['industry_code', 'fiscal_year', 'updated_at']
    search_fields = ['industry_name', 'metric_definition__display_name']
    autocomplete_fields = ['metric_definition']


@admin.register(CompanyScore)
class CompanyScoreAdmin(admin.ModelAdmin):
    list_display = ['company', 'template', 'total_score', 'rank', 
                    'calculated_at']
    list_filter = ['template', 'calculated_at']
    search_fields = ['company__name', 'template__name']
    readonly_fields = ['calculated_at']
    ordering = ['-total_score']