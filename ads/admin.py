# ads/admin.py
from django.contrib import admin
from .models import AdPlacement, AdUnit, UserAdPreference
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.conf import settings

@admin.register(AdPlacement)
class AdPlacementAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'is_active')
    list_filter = ('is_active', 'position')
    search_fields = ('name', 'description')


# ads/admin.py の AdUnitAdmin クラスを拡張

@admin.register(AdUnit)
class AdUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'placement', 'template_type', 'ad_format', 'is_fluid', 'is_active', 'preview_link')
    list_filter = ('is_active', 'placement', 'ad_format', 'is_fluid')
    search_fields = ('name', 'ad_client', 'ad_slot', 'template_type')
    autocomplete_fields = ('placement',)
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'placement', 'is_active')
        }),
        ('AdSense設定', {
            'fields': ('ad_client', 'ad_slot', 'ad_format')
        }),
        ('詳細設定', {
            'fields': ('template_type', 'width', 'height', 'is_fluid', 'ad_layout', 'ad_layout_key')
        }),
        ('カスタマイズ', {
            'fields': ('custom_style', 'custom_js')
        }),
    )
    
    # 変更フォームのテンプレートをカスタマイズ
    change_form_template = 'admin/ads/adunit/change_form.html'
    
    # リストビューにプレビューリンクを追加
    def preview_link(self, obj):
        return format_html('<a href="#" onclick="openAdPreview({0}); return false;">プレビュー</a>', obj.id)
    preview_link.short_description = 'プレビュー'
    
    class Media:
        js = ('js/ad_preview.js',)


@admin.register(UserAdPreference)
class UserAdPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'show_ads', 'is_premium', 'allow_personalized_ads')
    list_filter = ('show_ads', 'is_premium', 'allow_personalized_ads')
    search_fields = ('user__username', 'user__email')
    autocomplete_fields = ('user',)