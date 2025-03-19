# stockdiary/admin.py
from django.contrib import admin
from .models import StockDiary, DiaryNote

class DiaryNoteInline(admin.TabularInline):
    model = DiaryNote
    extra = 1
    fields = ('date', 'note_type', 'importance', 'current_price', 'content')

@admin.register(StockDiary)
class StockDiaryAdmin(admin.ModelAdmin):
    list_display = ('id', 'stock_name', 'stock_symbol', 'user', 'purchase_date', 'purchase_price', 'purchase_quantity', 'get_total_value', 'sell_date')
    list_filter = ('user', 'purchase_date', 'sell_date', 'tags')
    search_fields = ('stock_name', 'stock_symbol', 'user__username', 'memo')
    filter_horizontal = ('tags', 'checklist')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'purchase_date'
    inlines = [DiaryNoteInline]
    
    fieldsets = (
        ('基本情報', {
            'fields': ('user', 'stock_name', 'stock_symbol')
        }),
        ('取引情報', {
            'fields': ('purchase_date', 'purchase_price', 'purchase_quantity', 'sell_date', 'sell_price')
        }),
        ('詳細情報', {
            'fields': ('reason', 'memo', 'tags', 'sector')
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_total_value(self, obj):
        """購入時の合計金額を表示（Null値のチェックを追加）"""
        if obj.purchase_price is not None and obj.purchase_quantity is not None:
            return obj.purchase_price * obj.purchase_quantity
        return None
    get_total_value.short_description = '購入金額（合計）'

@admin.register(DiaryNote)
class DiaryNoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'diary', 'date', 'note_type', 'importance', 'current_price', 'get_price_change_percent')
    list_filter = ('note_type', 'importance', 'date')
    search_fields = ('diary__stock_name', 'diary__stock_symbol', 'content')
    date_hierarchy = 'date'
    
    fieldsets = (
        ('関連情報', {
            'fields': ('diary', 'date')
        }),
        ('ノート情報', {
            'fields': ('note_type', 'importance', 'current_price', 'content')
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def get_price_change_percent(self, obj):
        """価格変動率を表示"""
        change = obj.get_price_change()
        if change is not None:
            return f"{change:.2f}%"
        return "-"
    get_price_change_percent.short_description = '変動率'