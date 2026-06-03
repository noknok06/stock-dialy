from django.contrib import admin

from .models import DiaryTemplate


@admin.register(DiaryTemplate)
class DiaryTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'updated_at', 'created_at')
    list_filter = ('user',)
    search_fields = ('title', 'body', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
