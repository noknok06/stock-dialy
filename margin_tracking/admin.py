from decimal import Decimal, InvalidOperation

from django.contrib import admin, messages

from .models import MarginData, MarginFetchLog


def _recalc_ratio(rec):
    """1レコードの margin_ratio を long/short から再計算して返す。失敗時は None。"""
    try:
        if rec.short_balance and rec.short_balance > 0:
            return (
                Decimal(str(rec.long_balance)) / Decimal(str(rec.short_balance))
            ).quantize(Decimal('0.01'))
    except InvalidOperation:
        pass
    return None


@admin.action(description='選択したレコードの信用倍率を再計算する')
def recalc_selected(modeladmin, request, queryset):
    fixed = 0
    for rec in queryset:
        new_ratio = _recalc_ratio(rec)
        if new_ratio != rec.margin_ratio:
            MarginData.objects.filter(pk=rec.pk).update(margin_ratio=new_ratio)
            fixed += 1
    messages.success(request, f'{fixed} 件の信用倍率を更新しました（対象: {queryset.count()} 件）。')


@admin.register(MarginData)
class MarginDataAdmin(admin.ModelAdmin):
    list_display = ['stock_code', 'stock_name', 'record_date', 'short_balance', 'long_balance', 'margin_ratio', 'ratio_check']
    list_filter = ['record_date']
    search_fields = ['stock_code', 'stock_name']
    ordering = ['-record_date', 'stock_code']
    readonly_fields = ['margin_ratio', 'created_at', 'updated_at']
    actions = [recalc_selected, 'recalc_all']

    @admin.display(description='整合性')
    def ratio_check(self, obj):
        """保存値と実計算値が一致しているか確認用の列。"""
        correct = _recalc_ratio(obj)
        if correct is None:
            return '売り残=0'
        if obj.margin_ratio is None or abs(float(obj.margin_ratio) - float(correct)) > 0.01:
            return f'⚠ 正: {correct}'
        return '✓'

    @admin.action(description='【全件】信用倍率を再計算する')
    def recalc_all(self, request, queryset):
        all_records = MarginData.objects.all()
        fixed = 0
        for rec in all_records:
            new_ratio = _recalc_ratio(rec)
            if new_ratio != rec.margin_ratio:
                MarginData.objects.filter(pk=rec.pk).update(margin_ratio=new_ratio)
                fixed += 1
        messages.success(request, f'全件再計算完了: {fixed} 件を更新しました（総レコード数: {all_records.count()} 件）。')


@admin.register(MarginFetchLog)
class MarginFetchLogAdmin(admin.ModelAdmin):
    list_display = ['record_date', 'status', 'records_created', 'records_updated', 'total_records', 'started_at', 'completed_at']
    list_filter = ['status']
    ordering = ['-record_date']
    readonly_fields = ['started_at', 'completed_at']
