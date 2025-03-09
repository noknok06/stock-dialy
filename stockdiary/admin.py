# stockdiary/admin.py
from django.contrib import admin
from .models import StockDiary
from checklist.models import Checklist
from tags.models import Tag

class StockDiaryAdmin(admin.ModelAdmin):
    list_display = ('stock_symbol', 'stock_name', 'purchase_date', 'purchase_price', 'purchase_quantity', 'reason', 'sell_date', 'sell_price', 'created_at', 'updated_at')
    search_fields = ('stock_symbol', 'stock_name', 'reason')
    list_filter = ('purchase_date', 'sell_date', 'tags', 'checklist')
    ordering = ('-created_at',)

    # チェックリストとタグの表示
    filter_horizontal = ('checklist', 'tags')

    # 詳細表示時に表示するフィールド
    fieldsets = (
        (None, {
            'fields': ('user', 'stock_symbol', 'stock_name', 'purchase_date', 'purchase_price', 'purchase_quantity', 'reason')
        }),
        ('売却情報', {
            'fields': ('sell_date', 'sell_price', 'memo')
        }),
        ('関連情報', {
            'fields': ('checklist', 'tags')
        }),
        ('日時情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# モデルをDjango adminに登録
admin.site.register(StockDiary, StockDiaryAdmin)

# 既に登録されているチェックリストとタグも管理画面に表示される
admin.site.register(Checklist)
admin.site.register(Tag)
