# ads/admin.py
from django.contrib import admin
from .models import AdPlacement, AdUnit, UserAdPreference

@admin.register(AdPlacement)
class AdPlacementAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'is_active')
    list_filter = ('is_active', 'position')
    search_fields = ('name', 'description')


@admin.register(AdUnit)
class AdUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'placement', 'ad_format', 'is_active')
    list_filter = ('is_active', 'placement', 'ad_format')
    search_fields = ('name', 'ad_client', 'ad_slot')
    autocomplete_fields = ('placement',)


@admin.register(UserAdPreference)
class UserAdPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'show_ads', 'is_premium', 'allow_personalized_ads')
    list_filter = ('show_ads', 'is_premium', 'allow_personalized_ads')
    search_fields = ('user__username', 'user__email')
    autocomplete_fields = ('user',)