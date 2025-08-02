# contact/admin.py に追加・更新
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.contrib import messages
from .models import ContactMessage

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name_with_flags', 'email', 'subject_short', 'verification_status', 'spam_score_display', 'created_at', 'is_read')
    list_filter = ('is_read', 'is_spam', 'is_verified', 'created_at', 'spam_score')
    search_fields = ('name', 'email', 'subject', 'message', 'ip_address')
    readonly_fields = ('created_at', 'spam_score', 'ip_address', 'verification_token', 'verified_at', 'verification_expires_at')
    ordering = ['-is_verified', '-is_spam', '-spam_score', '-created_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'email', 'subject', 'created_at', 'is_read')
        }),
        ('内容', {
            'fields': ('message',)
        }),
        ('メール認証情報', {
            'fields': ('is_verified', 'verified_at', 'verification_token', 'verification_expires_at'),
            'classes': ('collapse',)
        }),
        ('スパム検出情報', {
            'fields': ('spam_score', 'is_spam', 'ip_address'),
            'classes': ('collapse',)
        }),
    )
    
    def name_with_flags(self, obj):
        """名前にスパム・認証フラグを追加"""
        flags = []
        name = obj.name
        
        # 認証状態
        if not obj.is_verified:
            if obj.is_verification_expired():
                flags.append('<span style="color: #dc3545;">🕐 期限切れ</span>')
            else:
                flags.append('<span style="color: #fd7e14;">📧 未認証</span>')
        else:
            flags.append('<span style="color: #198754;">✅ 認証済</span>')
        
        # スパム状態
        if obj.is_spam:
            flags.append('<span style="color: #dc3545; font-weight: bold;">🚫 スパム</span>')
        elif obj.spam_score > 2:
            flags.append('<span style="color: #fd7e14;">⚠️ 要注意</span>')
        
        flag_str = ' '.join(flags) if flags else ''
        
        return format_html(
            '{}<br><small>{}</small>',
            name,
            flag_str
        )
    name_with_flags.short_description = 'お名前'
    name_with_flags.admin_order_field = 'name'
    
    def subject_short(self, obj):
        """件名を短縮表示"""
        if len(obj.subject) > 30:
            return obj.subject[:30] + '...'
        return obj.subject
    subject_short.short_description = '件名'
    subject_short.admin_order_field = 'subject'
    
    def verification_status(self, obj):
        """認証状態を表示"""
        if obj.is_verified:
            return format_html(
                '<span style="color: #198754; font-weight: bold;">✅ 認証済み</span><br>'
                '<small>{}</small>',
                obj.verified_at.strftime('%m/%d %H:%M') if obj.verified_at else ''
            )
        elif obj.is_verification_expired():
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">🕐 期限切れ</span><br>'
                '<small>期限: {}</small>',
                obj.verification_expires_at.strftime('%m/%d %H:%M') if obj.verification_expires_at else ''
            )
        else:
            remaining_time = obj.verification_expires_at - timezone.now() if obj.verification_expires_at else None
            if remaining_time:
                hours = int(remaining_time.total_seconds() // 3600)
                return format_html(
                    '<span style="color: #fd7e14; font-weight: bold;">📧 未認証</span><br>'
                    '<small>残り: {}時間</small>',
                    hours
                )
            else:
                return format_html('<span style="color: #fd7e14; font-weight: bold;">📧 未認証</span>')
    
    verification_status.short_description = '認証状態'
    verification_status.admin_order_field = 'is_verified'
    
    def spam_score_display(self, obj):
        """スパムスコアをカラー表示"""
        if obj.spam_score >= 5:
            color = '#dc3545'
            icon = '🚫'
        elif obj.spam_score >= 3:
            color = '#fd7e14'
            icon = '⚠️'
        elif obj.spam_score >= 1:
            color = '#6c757d'
            icon = '❓'
        else:
            color = '#198754'
            icon = '✅'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.spam_score
        )
    spam_score_display.short_description = 'スパムスコア'
    spam_score_display.admin_order_field = 'spam_score'
    
    def mark_as_read(self, request, queryset):
        """選択された項目を既読にする"""
        verified_queryset = queryset.filter(is_verified=True)
        updated = verified_queryset.update(is_read=True)
        self.message_user(request, f'{updated}件の認証済みメッセージを既読にしました。')
    mark_as_read.short_description = "認証済みメッセージを既読にする"
    
    def mark_as_spam(self, request, queryset):
        """選択された項目をスパムとしてマーク"""
        updated = queryset.update(is_spam=True)
        self.message_user(request, f'{updated}件のメッセージをスパムとしてマークしました。')
    mark_as_spam.short_description = "選択された項目をスパムとしてマーク"
    
    def block_ip_addresses(self, request, queryset):
        """選択されたメッセージのIPアドレスをブロック"""
        from security.models import BlockedIP
        
        blocked_count = 0
        for message in queryset:
            if message.ip_address:
                blocked_ip, created = BlockedIP.objects.get_or_create(
                    ip_address=message.ip_address,
                    defaults={
                        'reason': 'spam',
                        'description': f'問い合わせスパムによる自動ブロック: {message.name} ({message.email})',
                        'created_by': request.user,
                    }
                )
                if created:
                    blocked_count += 1
        
        self.message_user(
            request, 
            f'{blocked_count}件のIPアドレスをブロックリストに追加しました。',
            messages.SUCCESS
        )
    block_ip_addresses.short_description = "IPアドレスをブロックリストに追加"
    
    def block_email_addresses(self, request, queryset):
        """選択されたメッセージのメールアドレスをブロック"""
        from security.models import BlockedEmail
        
        blocked_count = 0
        for message in queryset:
            if message.email:
                blocked_email, created = BlockedEmail.objects.get_or_create(
                    email_pattern=message.email.lower(),
                    defaults={
                        'block_type': 'exact',
                        'reason': 'spam',
                        'description': f'問い合わせスパムによる自動ブロック: {message.name}',
                        'created_by': request.user,
                    }
                )
                if created:
                    blocked_count += 1
        
        self.message_user(
            request, 
            f'{blocked_count}件のメールアドレスをブロックリストに追加しました。',
            messages.SUCCESS
        )
    block_email_addresses.short_description = "メールアドレスをブロックリストに追加"
    
    def block_email_domains(self, request, queryset):
        """選択されたメッセージのメールドメインをブロック"""
        from security.models import BlockedEmail
        
        blocked_count = 0
        domains_added = set()
        
        for message in queryset:
            if message.email and '@' in message.email:
                domain = '@' + message.email.split('@')[1].lower()
                
                if domain not in domains_added:
                    blocked_email, created = BlockedEmail.objects.get_or_create(
                        email_pattern=domain,
                        defaults={
                            'block_type': 'domain',
                            'reason': 'spam',
                            'description': f'問い合わせスパムによる自動ブロック (ドメイン): {message.email}',
                            'created_by': request.user,
                        }
                    )
                    if created:
                        blocked_count += 1
                        domains_added.add(domain)
        
        self.message_user(
            request, 
            f'{blocked_count}件のメールドメインをブロックリストに追加しました。',
            messages.SUCCESS
        )
    block_email_domains.short_description = "メールドメインをブロックリストに追加"
    
    def delete_unverified_expired(self, request, queryset):
        """期限切れの未認証メッセージを削除"""
        expired_unverified = queryset.filter(
            is_verified=False,
            verification_expires_at__lt=timezone.now()
        )
        count = expired_unverified.count()
        expired_unverified.delete()
        self.message_user(request, f'{count}件の期限切れ未認証メッセージを削除しました。')
    delete_unverified_expired.short_description = "期限切れ未認証メッセージを削除"
    
    def delete_spam(self, request, queryset):
        """スパムメッセージを削除"""
        spam_messages = queryset.filter(is_spam=True)
        count = spam_messages.count()
        spam_messages.delete()
        self.message_user(request, f'{count}件のスパムメッセージを削除しました。')
    delete_spam.short_description = "スパムメッセージを削除"
    
    actions = [
        'mark_as_read', 
        'mark_as_spam', 
        'block_ip_addresses',
        'block_email_addresses', 
        'block_email_domains',
        'delete_unverified_expired',
        'delete_spam'
    ]
    
    def get_queryset(self, request):
        """クエリセットをカスタマイズ"""
        qs = super().get_queryset(request)
        return qs.extra(
            select={
                'priority': """
                    CASE 
                        WHEN is_verified = true AND is_spam = false THEN 1
                        WHEN is_verified = false AND is_spam = false THEN 2
                        ELSE 3
                    END
                """
            }
        ).order_by('priority', '-created_at')