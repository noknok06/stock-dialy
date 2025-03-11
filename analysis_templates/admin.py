from django.contrib import admin
from .models import AnalysisTemplate, TemplateField, StockAnalysisData, FieldValue, TemplateGroup

@admin.register(AnalysisTemplate)
class AnalysisTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at', 'updated_at')

@admin.register(TemplateGroup)
class TemplateGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'template', 'order')
    list_filter = ('template',)

@admin.register(TemplateField)
class TemplateFieldAdmin(admin.ModelAdmin):
    list_display = ('label', 'template', 'field_type', 'is_required')
    search_fields = ('label', 'key')
    list_filter = ('template', 'field_type', 'is_required')

@admin.register(StockAnalysisData)
class StockAnalysisDataAdmin(admin.ModelAdmin):
    list_display = ('diary', 'template', 'created_at', 'updated_at')
    list_filter = ('template', 'created_at', 'updated_at')
    search_fields = ('diary__stock_name',)

@admin.register(FieldValue)
class FieldValueAdmin(admin.ModelAdmin):
    list_display = ('analysis_data', 'field', 'get_formatted_value')
    list_filter = ('field__field_type',)
    search_fields = ('field__label',)

    def get_formatted_value(self, obj):
        return obj.get_formatted_value()
    get_formatted_value.short_description = '値'