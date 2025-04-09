# analysis_template/admin.py
from django.contrib import admin
from .models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from django.db.models import Count


class AnalysisItemInline(admin.TabularInline):
    model = AnalysisItem
    extra = 1
    fields = ('name', 'item_type', 'description', 'order', 'choices', 'value_label')

@admin.register(AnalysisTemplate)
class AnalysisTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'created_at', 'updated_at', 'item_count')
    list_filter = ('user', 'created_at')
    search_fields = ('name', 'description', 'user__username')
    date_hierarchy = 'created_at'
    inlines = [AnalysisItemInline]
    
    def get_queryset(self, request):
        # items の数をあらかじめ計算してクエリセットに追加
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(items_count=Count('items'))
        return queryset
    
    def item_count(self, obj):
        # annotate された値を使用
        return obj.items_count
    item_count.short_description = '項目数'
    item_count.admin_order_field = 'items_count'  # 項目数でのソートを可能に
    

@admin.register(AnalysisItem)
class AnalysisItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'template', 'item_type', 'order')
    list_filter = ('item_type', 'template__name')
    search_fields = ('name', 'description', 'template__name')
    list_select_related = ('template',)

@admin.register(DiaryAnalysisValue)
class DiaryAnalysisValueAdmin(admin.ModelAdmin):
    list_display = ('id', 'diary', 'analysis_item', 'get_item_type', 'get_display_value')
    list_filter = ('analysis_item__template', 'analysis_item__item_type')
    search_fields = ('diary__title', 'diary__stock_name', 'analysis_item__name')
    list_select_related = ('diary', 'analysis_item')
    
    def get_item_type(self, obj):
        return obj.analysis_item.get_item_type_display()
    get_item_type.short_description = '項目タイプ'
    
    def get_display_value(self, obj):
        if obj.analysis_item.item_type == 'number':
            return obj.number_value
        elif obj.analysis_item.item_type == 'boolean':
            return '✓' if obj.boolean_value else '✗'
        elif obj.analysis_item.item_type == 'boolean_with_value':
            boolean_status = '✓' if obj.boolean_value else '✗'
            if obj.number_value is not None:
                return f"{boolean_status} ({obj.number_value})"
            elif obj.text_value:
                return f"{boolean_status} ({obj.text_value})"
            return boolean_status
        else:
            return obj.text_value
    get_display_value.short_description = '値'