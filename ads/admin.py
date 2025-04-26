# ads/admin.py
from django.contrib import admin
from .models import AdPlacement, AdUnit, UserAdPreference

@admin.register(AdPlacement)
class AdPlacementAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'is_active')
    list_filter = ('is_active', 'position')
    search_fields = ('name', 'description')


# ads/admin.py の AdUnitAdmin クラスを拡張

@admin.register(AdUnit)
class AdUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'placement', 'template_type', 'ad_format', 'is_fluid', 'is_active')
    list_filter = ('is_active', 'placement', 'ad_format', 'template_type', 'is_fluid')
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
            'classes': ('collapse',),
            'fields': ('custom_style', 'custom_js')
        }),
    )


@admin.register(UserAdPreference)
class UserAdPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'show_ads', 'is_premium', 'allow_personalized_ads')
    list_filter = ('show_ads', 'is_premium', 'allow_personalized_ads')
    search_fields = ('user__username', 'user__email')
    autocomplete_fields = ('user',)