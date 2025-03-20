# subscriptions/admin.py
from django.contrib import admin
from .models import SubscriptionPlan, UserSubscription

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'max_tags', 'max_templates', 'max_snapshots', 'max_records', 'show_ads', 'price_monthly', 'price_yearly')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'is_active', 'start_date', 'end_date')
    list_filter = ('plan', 'is_active')
    search_fields = ('user__username', 'user__email')
    raw_id_fields = ('user',)