# investment_review/admin.py
from django.contrib import admin
from .models import InvestmentReview, ReviewInsight


@admin.register(InvestmentReview)
class InvestmentReviewAdmin(admin.ModelAdmin):
    list_display = [
        'title', 
        'user', 
        'review_type', 
        'start_date', 
        'end_date', 
        'status',
        'total_entries',
        'created_at'
    ]
    list_filter = [
        'status', 
        'review_type', 
        'created_at',
        'start_date'
    ]
    search_fields = [
        'title', 
        'user__username', 
        'professional_insights'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    readonly_fields = [
        'analysis_data', 
        'analysis_completed_at',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('基本情報', {
            'fields': ('user', 'title', 'review_type', 'start_date', 'end_date')
        }),
        ('分析状況', {
            'fields': ('status', 'analysis_completed_at')
        }),
        ('統計情報', {
            'fields': ('total_entries', 'active_holdings', 'completed_trades', 'memo_entries')
        }),
        ('分析結果', {
            'fields': ('professional_insights', 'analysis_data'),
            'classes': ('collapse',)
        }),
        ('メタデータ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(ReviewInsight)
class ReviewInsightAdmin(admin.ModelAdmin):
    list_display = [
        'review', 
        'insight_type', 
        'title', 
        'priority',
        'created_at'
    ]
    list_filter = [
        'insight_type', 
        'priority',
        'created_at'
    ]
    search_fields = [
        'title', 
        'content',
        'review__title',
        'review__user__username'
    ]
    ordering = ['-created_at', '-priority']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('review', 'insight_type', 'title', 'priority')
        }),
        ('内容', {
            'fields': ('content',)
        }),
        ('根拠データ', {
            'fields': ('supporting_data',),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('review', 'review__user')