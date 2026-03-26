from django.contrib import admin
from django.contrib import messages
from .models import MarginData, MarginFetchLog


@admin.register(MarginData)
class MarginDataAdmin(admin.ModelAdmin):
    list_display = ['stock_code', 'stock_name', 'record_date', 'short_balance', 'long_balance', 'margin_ratio']
    list_filter = ['record_date']
    search_fields = ['stock_code', 'stock_name']
    ordering = ['-record_date', 'stock_code']
    readonly_fields = ['margin_ratio', 'created_at', 'updated_at']
    actions = ['recalculate_margin_ratio']

    def recalculate_margin_ratio(self, request, queryset):
        """選択したレコードの信用倍率を再計算してDBに保存する。"""
        from .services.jpx_margin_service import JPXMarginService
        count = 0
        for obj in queryset:
            ratio = JPXMarginService._compute_margin_ratio(obj.short_balance, obj.long_balance)
            obj.margin_ratio = ratio
            obj.save(update_fields=['margin_ratio', 'updated_at'])
            count += 1
        self.message_user(request, f'{count} 件の信用倍率を再計算しました。', messages.SUCCESS)
    recalculate_margin_ratio.short_description = '選択した銘柄の信用倍率を再計算'


@admin.register(MarginFetchLog)
class MarginFetchLogAdmin(admin.ModelAdmin):
    list_display = ['record_date', 'status', 'records_created', 'records_updated', 'total_records', 'started_at', 'completed_at']
    list_filter = ['status']
    ordering = ['-record_date']
    readonly_fields = ['started_at', 'completed_at']
