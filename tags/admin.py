from django.contrib import admin

from .models import MasterTag


@admin.register(MasterTag)
class MasterTagAdmin(admin.ModelAdmin):
    """標準タグ（全ユーザー共有の補完候補）の管理。

    ここで追加・編集・無効化した内容はデプロイなしで即時反映される
    （tag_axis_config.get_master_axis_map() のキャッシュは保存時にクリアされる）。
    """
    list_display = ('name', 'axis', 'is_active', 'sort_order', 'updated_at')
    list_editable = ('axis', 'is_active', 'sort_order')
    list_filter = ('axis', 'is_active')
    search_fields = ('name',)
    ordering = ('sort_order', 'axis', 'name')
    actions = ('activate', 'deactivate')

    @admin.action(description='選択した標準タグを有効化')
    def activate(self, request, queryset):
        queryset.update(is_active=True)
        from django.core.cache import cache
        cache.delete(MasterTag.CACHE_KEY)

    @admin.action(description='選択した標準タグを無効化')
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)
        from django.core.cache import cache
        cache.delete(MasterTag.CACHE_KEY)
