from django.contrib import admin
from django.utils.html import format_html

from .models import MasterTag, Tag


def _clear_master_cache():
    from django.core.cache import cache
    cache.delete(MasterTag.CACHE_KEY)


_AXIS_BADGE_COLORS = {
    'theme':          ('#7c3aed', 'テーマ'),
    'macro':          ('#d97706', 'マクロ感応'),
    'capital_policy': ('#16a34a', '資本政策'),
    'business_model': ('#0891b2', 'ビジネスモデル'),
    'risk':           ('#dc2626', 'リスク'),
    'event':          ('#6b7280', 'イベント'),
    'custom':         ('#9333ea', 'ラベル'),
}


@admin.register(MasterTag)
class MasterTagAdmin(admin.ModelAdmin):
    """標準タグ（全ユーザー共有の補完候補）の管理。

    保存・削除・一括操作すると get_master_axis_map() のキャッシュが即時クリアされ、
    次のリクエストから全ユーザーの補完候補・軸決定に反映される。
    """

    list_display = ('name', 'axis_badge', 'is_active', 'sort_order', 'updated_at')
    list_editable = ('is_active', 'sort_order')
    list_filter = ('axis', 'is_active')
    search_fields = ('name',)
    ordering = ('sort_order', 'axis', 'name')
    actions = ('activate', 'deactivate', 'set_axis_theme', 'set_axis_macro',
               'set_axis_capital_policy', 'set_axis_business_model',
               'set_axis_risk', 'set_axis_event', 'set_axis_custom')

    fieldsets = (
        (None, {
            'fields': ('name', 'axis', 'is_active', 'sort_order'),
            'description': (
                '<p style="color:#555;">追加・変更を保存するとキャッシュが自動クリアされ、'
                '全ユーザーの補完候補に即時反映されます（デプロイ不要）。</p>'
            ),
        }),
    )

    @admin.display(description='軸')
    def axis_badge(self, obj):
        color, label = _AXIS_BADGE_COLORS.get(obj.axis, ('#6b7280', obj.axis))
        return format_html(
            '<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
            'background:{};color:#fff;font-size:0.8em;font-weight:600;">{}</span>',
            color, label,
        )

    # ---- アクション: 有効 / 無効 ----

    @admin.action(description='✅ 選択した標準タグを有効化')
    def activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        _clear_master_cache()
        self.message_user(request, f'{updated} 件を有効化しました。')

    @admin.action(description='⛔ 選択した標準タグを無効化')
    def deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        _clear_master_cache()
        self.message_user(request, f'{updated} 件を無効化しました。')

    # ---- アクション: 軸を一括変更 ----

    def _set_axis(self, request, queryset, axis, label):
        updated = queryset.update(axis=axis)
        _clear_master_cache()
        self.message_user(request, f'{updated} 件の軸を「{label}」に変更しました。')

    @admin.action(description='軸を「テーマ」に変更')
    def set_axis_theme(self, request, queryset):
        self._set_axis(request, queryset, Tag.AXIS_THEME, 'テーマ')

    @admin.action(description='軸を「マクロ感応」に変更')
    def set_axis_macro(self, request, queryset):
        self._set_axis(request, queryset, Tag.AXIS_MACRO, 'マクロ感応')

    @admin.action(description='軸を「資本政策」に変更')
    def set_axis_capital_policy(self, request, queryset):
        self._set_axis(request, queryset, Tag.AXIS_CAPITAL_POLICY, '資本政策')

    @admin.action(description='軸を「ビジネスモデル」に変更')
    def set_axis_business_model(self, request, queryset):
        self._set_axis(request, queryset, Tag.AXIS_BUSINESS_MODEL, 'ビジネスモデル')

    @admin.action(description='軸を「リスク」に変更')
    def set_axis_risk(self, request, queryset):
        self._set_axis(request, queryset, Tag.AXIS_RISK, 'リスク')

    @admin.action(description='軸を「イベント」に変更')
    def set_axis_event(self, request, queryset):
        self._set_axis(request, queryset, Tag.AXIS_EVENT, 'イベント')

    @admin.action(description='軸を「ラベル（custom）」に変更')
    def set_axis_custom(self, request, queryset):
        self._set_axis(request, queryset, Tag.AXIS_CUSTOM, 'ラベル')
