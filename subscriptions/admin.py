# subscriptions/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import SubscriptionPlan, UserSubscription, StripeCustomer, SubscriptionEvent
from django.urls import reverse
from django.utils import timezone
from django.contrib.admin import SimpleListFilter

class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'price_monthly', 'price_yearly', 'max_tags', 'max_templates', 'show_ads', 'display_order')
    list_editable = ('price_monthly', 'price_yearly', 'display_order')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('show_ads',)
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'slug', 'display_order')
        }),
        ('料金設定', {
            'fields': ('price_monthly', 'price_yearly', 'stripe_price_id')
        }),
        ('機能制限', {
            'fields': ('max_tags', 'max_templates', 'max_records')
        }),
        ('機能フラグ', {
            'fields': ('show_ads', 'export_enabled', 'advanced_analytics')
        }),
    )

class CanceledFilter(SimpleListFilter):
    title = 'キャンセル状態'
    parameter_name = 'canceled'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'キャンセル済み'),
            ('no', '有効'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(canceled_at__isnull=False)
        if self.value() == 'no':
            return queryset.filter(canceled_at__isnull=True)
        return queryset

class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'plan', 'is_active', 'formatted_start_date', 
        'current_period_end_formatted', 'has_scheduled_downgrade', 
        'stripe_subscription_id_short', 'stripe_customer_id_short',
        'action_buttons'
    )
    list_filter = ('is_active', 'plan', CanceledFilter)
    search_fields = ('user__username', 'user__email', 'stripe_subscription_id', 'stripe_customer_id')
    raw_id_fields = ('user', 'plan', 'scheduled_downgrade_to')
    readonly_fields = ('created_at', 'updated_at', 'current_period_start', 'current_period_end')
    
    fieldsets = (
        ('ユーザー情報', {
            'fields': ('user', 'plan', 'is_active')
        }),
        ('期間情報', {
            'fields': ('start_date', 'end_date', 'current_period_start', 'current_period_end')
        }),
        ('ダウングレード情報', {
            'fields': ('scheduled_downgrade_to', 'canceled_at')
        }),
        ('Stripe情報', {
            'fields': ('stripe_subscription_id', 'stripe_customer_id')
        }),
        ('メタデータ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def formatted_start_date(self, obj):
        return timezone.localtime(obj.start_date).strftime('%Y-%m-%d %H:%M')
    formatted_start_date.short_description = '開始日'
    
    def current_period_end_formatted(self, obj):
        if obj.current_period_end:
            return timezone.localtime(obj.current_period_end).strftime('%Y-%m-%d %H:%M')
        return '-'
    current_period_end_formatted.short_description = '次の請求日'
    
    def has_scheduled_downgrade(self, obj):
        if obj.scheduled_downgrade_to:
            return format_html(
                '<span style="color: #e53e3e;"><i class="fas fa-arrow-down"></i> {} へ</span>',
                obj.scheduled_downgrade_to.name
            )
        return '-'
    has_scheduled_downgrade.short_description = 'ダウングレード予定'
    
    def stripe_subscription_id_short(self, obj):
        if obj.stripe_subscription_id:
            return f"{obj.stripe_subscription_id[:8]}..."
        return '-'
    stripe_subscription_id_short.short_description = 'サブスクリプションID'
    
    def stripe_customer_id_short(self, obj):
        if obj.stripe_customer_id:
            return f"{obj.stripe_customer_id[:8]}..."
        return '-'
    stripe_customer_id_short.short_description = '顧客ID'
    
    def action_buttons(self, obj):
        if not obj.is_active:
            activate_url = reverse('admin:activate_subscription', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}">有効化</a>',
                activate_url
            )
        
        buttons = []
        
        # キャンセル関連ボタン
        if obj.scheduled_downgrade_to:
            cancel_downgrade_url = reverse('admin:cancel_downgrade', args=[obj.pk])
            buttons.append(
                f'<a class="button" href="{cancel_downgrade_url}">ダウングレードをキャンセル</a>'
            )
        elif obj.stripe_subscription_id and not obj.canceled_at:
            cancel_url = reverse('admin:cancel_subscription', args=[obj.pk])
            buttons.append(
                f'<a class="button" style="background-color: #e53e3e; color: white;" href="{cancel_url}">キャンセル</a>'
            )
        
        # プラン変更ボタン
        change_plan_url = reverse('admin:change_plan', args=[obj.pk])
        buttons.append(
            f'<a class="button" href="{change_plan_url}">プラン変更</a>'
        )
        
        # Stripe同期ボタン
        if obj.stripe_subscription_id:
            sync_url = reverse('admin:sync_subscription', args=[obj.pk])
            buttons.append(
                f'<a class="button" href="{sync_url}">Stripeと同期</a>'
            )
        
        return format_html(
            '<div style="display: flex; gap: 5px;">{}</div>',
            format_html(''.join(buttons))
        )
    action_buttons.short_description = 'アクション'


class StripeCustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'stripe_id', 'created_at')
    search_fields = ('user__username', 'user__email', 'stripe_id')
    raw_id_fields = ('user',)


class SubscriptionEventAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'from_plan_name', 'to_plan_name', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('user__username', 'user__email', 'stripe_event_id')
    raw_id_fields = ('user', 'subscription', 'from_plan', 'to_plan')
    readonly_fields = ('created_at', 'details_pretty')
    
    def from_plan_name(self, obj):
        return obj.from_plan.name if obj.from_plan else '-'
    from_plan_name.short_description = '変更前プラン'
    
    def to_plan_name(self, obj):
        return obj.to_plan.name if obj.to_plan else '-'
    to_plan_name.short_description = '変更後プラン'
    
    def details_pretty(self, obj):
        if not obj.details:
            return '-'
        
        import json
        try:
            formatted = json.dumps(obj.details, indent=2, ensure_ascii=False)
            return format_html('<pre>{}</pre>', formatted)
        except Exception:
            return str(obj.details)
    details_pretty.short_description = '詳細情報'


# 修正後の実装:
def get_admin_urls(urls):
    def get_urls(self):
        from django.urls import path
        from . import views
        
        custom_urls = [
            path('subscription/<uuid:id>/cancel/', 
                 views.admin_cancel_subscription, 
                 name='cancel_subscription'),
            path('subscription/<uuid:id>/activate/', 
                 views.admin_activate_subscription, 
                 name='activate_subscription'),
            path('subscription/<uuid:id>/change-plan/', 
                 views.admin_change_plan, 
                 name='change_plan'),
            path('subscription/<uuid:id>/cancel-downgrade/', 
                 views.admin_cancel_downgrade, 
                 name='cancel_downgrade'),
            path('subscription/<uuid:id>/sync/', 
                 views.admin_sync_subscription, 
                 name='sync_subscription'),
        ]
        return custom_urls + urls(self)
    return get_urls

# 管理アクションの適用
UserSubscriptionAdmin.get_urls = get_admin_urls(UserSubscriptionAdmin.get_urls)

# モデルの登録
admin.site.register(SubscriptionPlan, SubscriptionPlanAdmin)
admin.site.register(UserSubscription, UserSubscriptionAdmin)
admin.site.register(StripeCustomer, StripeCustomerAdmin)
admin.site.register(SubscriptionEvent, SubscriptionEventAdmin)