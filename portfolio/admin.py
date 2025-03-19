from django.contrib import admin
from .models import PortfolioSnapshot, HoldingRecord, SectorAllocation

class HoldingRecordInline(admin.TabularInline):
    model = HoldingRecord
    extra = 0
    fields = ('stock_symbol', 'stock_name', 'quantity', 'price', 'total_value', 'sector', 'percentage')
    readonly_fields = ('total_value', 'percentage')

class SectorAllocationInline(admin.TabularInline):
    model = SectorAllocation
    extra = 0
    fields = ('sector_name', 'percentage')

@admin.register(PortfolioSnapshot)
class PortfolioSnapshotAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at', 'total_value', 'get_holdings_count')
    list_filter = ('created_at', 'user')
    search_fields = ('name', 'description', 'user__username')
    readonly_fields = ('created_at', 'total_value')
    inlines = [HoldingRecordInline, SectorAllocationInline]
    
    fieldsets = (
        ('基本情報', {
            'fields': ('user', 'name', 'created_at')
        }),
        ('ポートフォリオ情報', {
            'fields': ('total_value', 'description')
        }),
    )
    
    def get_holdings_count(self, obj):
        """保有銘柄数を表示"""
        return obj.holdings.count()
    get_holdings_count.short_description = '保有銘柄数'

@admin.register(HoldingRecord)
class HoldingRecordAdmin(admin.ModelAdmin):
    list_display = ('stock_name', 'stock_symbol', 'snapshot', 'quantity', 'price', 'total_value', 'percentage', 'sector')
    list_filter = ('snapshot', 'sector')
    search_fields = ('stock_name', 'stock_symbol', 'snapshot__name')
    readonly_fields = ('total_value', 'percentage')
    
    fieldsets = (
        ('関連情報', {
            'fields': ('snapshot',)
        }),
        ('銘柄情報', {
            'fields': ('stock_symbol', 'stock_name', 'sector')
        }),
        ('保有情報', {
            'fields': ('quantity', 'price', 'total_value', 'percentage')
        }),
    )

@admin.register(SectorAllocation)
class SectorAllocationAdmin(admin.ModelAdmin):
    list_display = ('sector_name', 'snapshot', 'percentage')
    list_filter = ('snapshot', 'sector_name')
    search_fields = ('sector_name', 'snapshot__name')