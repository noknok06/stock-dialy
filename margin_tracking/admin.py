from django.contrib import admin
from .models import MarginData, MarginFetchLog


@admin.register(MarginData)
class MarginDataAdmin(admin.ModelAdmin):
    list_display = ['stock_code', 'stock_name', 'record_date', 'short_balance', 'long_balance', 'margin_ratio']
    list_filter = ['record_date']
    search_fields = ['stock_code', 'stock_name']
    ordering = ['-record_date', 'stock_code']
    readonly_fields = ['margin_ratio', 'created_at', 'updated_at']


@admin.register(MarginFetchLog)
class MarginFetchLogAdmin(admin.ModelAdmin):
    list_display = ['record_date', 'status', 'records_created', 'records_updated', 'total_records', 'started_at', 'completed_at']
    list_filter = ['status']
    ordering = ['-record_date']
    readonly_fields = ['started_at', 'completed_at']
