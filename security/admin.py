# security/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import BlockedIP, BlockedEmail, BlockLog

@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'cidr_notation', 'reason_display', 'is_active_display', 'created_at', 'expires_at', 'created_by')
    list_filter = ('is_active', 'reason', 'created_at', 'expires_at')
    search_fields = ('ip_address', 'cidr_notation', 'description')
    readonly_fields = ('created_at', 'created_by')
    ordering = ['-created_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('ip_address', 'cidr_notation', 'is_active')
        }),
        ('ブロック設定', {
            'fields': ('reason', 'description', 'expires_at')
        }),
        ('作成情報', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def reason_display(self, obj):
        colors = {
            'spam': '#dc3545',
            'abuse': '#fd7e14',
            'security': '#dc3545',
            'manual': '#6c757d',
            'automated': '#0d6efd',
        }
        color = colors.get(obj.reason, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_reason_display()
        )
    reason_display.short_description = 'ブロック理由'
    reason_display.admin_order_field = 'reason'
    
    def is_active_display(self, obj):
        if not obj.is_active:
            return format_html('<span style="color: #6c757d;">❌ 無効</span>')
        elif obj.is_expired():
            return format_html('<span style="color: #fd7e14;">⏰ 期限切れ</span>')
        else:
            return format_html('<span style="color: #198754;">✅ 有効</span>')
    is_active_display.short_description = '状態'
    is_active_display.admin_order_field = 'is_active'
    
    def save_model(self, request, obj, form, change):
        if not change:  # 新規作成時
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def deactivate_blocks(self, request, queryset):
        """選択されたブロックを無効化"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated}件のIPブロックを無効化しました。')
    deactivate_blocks.short_description = "選択されたIPブロックを無効化"
    
    def activate_blocks(self, request, queryset):
        """選択されたブロックを有効化"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated}件のIPブロックを有効化しました。')
    activate_blocks.short_description = "選択されたIPブロックを有効化"
    
    actions = ['deactivate_blocks', 'activate_blocks']


@admin.register(BlockedEmail)
class BlockedEmailAdmin(admin.ModelAdmin):
    list_display = ('email_pattern', 'block_type', 'reason_display', 'is_active_display', 'created_at', 'expires_at', 'created_by')
    list_filter = ('is_active', 'block_type', 'reason', 'created_at', 'expires_at')
    search_fields = ('email_pattern', 'description')
    readonly_fields = ('created_at', 'created_by')
    ordering = ['-created_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('email_pattern', 'block_type', 'is_active')
        }),
        ('ブロック設定', {
            'fields': ('reason', 'description', 'expires_at')
        }),
        ('作成情報', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def reason_display(self, obj):
        colors = {
            'spam': '#dc3545',
            'abuse': '#fd7e14',
            'fake': '#dc3545',
            'manual': '#6c757d',
            'automated': '#0d6efd',
        }
        color = colors.get(obj.reason, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_reason_display()
        )
    reason_display.short_description = 'ブロック理由'
    reason_display.admin_order_field = 'reason'
    
    def is_active_display(self, obj):
        if not obj.is_active:
            return format_html('<span style="color: #6c757d;">❌ 無効</span>')
        elif obj.is_expired():
            return format_html('<span style="color: #fd7e14;">⏰ 期限切れ</span>')
        else:
            return format_html('<span style="color: #198754;">✅ 有効</span>')
    is_active_display.short_description = '状態'
    is_active_display.admin_order_field = 'is_active'
    
    def save_model(self, request, obj, form, change):
        if not change:  # 新規作成時
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def deactivate_blocks(self, request, queryset):
        """選択されたブロックを無効化"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated}件のメールブロックを無効化しました。')
    deactivate_blocks.short_description = "選択されたメールブロックを無効化"
    
    def activate_blocks(self, request, queryset):
        """選択されたブロックを有効化"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated}件のメールブロックを有効化しました。')
    activate_blocks.short_description = "選択されたメールブロックを有効化"
    
    actions = ['deactivate_blocks', 'activate_blocks']


@admin.register(BlockLog)
class BlockLogAdmin(admin.ModelAdmin):
    list_display = ('block_type', 'blocked_value', 'ip_address', 'request_path', 'blocked_at')
    list_filter = ('block_type', 'blocked_at')
    search_fields = ('blocked_value', 'ip_address', 'request_path')
    readonly_fields = ('block_type', 'blocked_value', 'ip_address', 'user_agent', 'request_path', 'blocked_at')
    ordering = ['-blocked_at']
    
    def has_add_permission(self, request):
        return False  # ログは手動で追加させない
    
    def has_change_permission(self, request, obj=None):
        return False  # ログは変更させない