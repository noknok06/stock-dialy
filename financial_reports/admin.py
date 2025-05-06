# financial_reports/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .models import Company, FinancialReport, ReportView

class ReportInline(admin.TabularInline):
    """企業詳細ページにレポート一覧を表示するインライン"""
    model = FinancialReport
    extra = 0
    fields = ('fiscal_period', 'overall_rating', 'is_public', 'created_at', 'view_count_admin')
    readonly_fields = ('fiscal_period', 'overall_rating', 'created_at', 'view_count_admin')
    can_delete = False
    show_change_link = True
    
    def view_count_admin(self, obj):
        return obj.views.count()
    view_count_admin.short_description = '閲覧数'
    
    def has_add_permission(self, request, obj=None):
        return False

class ReportViewInline(admin.TabularInline):
    """レポート詳細ページに閲覧履歴を表示するインライン"""
    model = ReportView
    extra = 0
    fields = ('ip_address', 'user_agent', 'timestamp')
    readonly_fields = ('ip_address', 'user_agent', 'timestamp')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """企業情報の管理画面"""
    list_display = ('code', 'name', 'abbr', 'color_display', 'is_public', 'report_count', 'created_at')
    list_filter = ('is_public',)
    search_fields = ('name', 'code', 'abbr')
    ordering = ('code',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ReportInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'abbr', 'color', 'is_public')
        }),
        ('メタ情報', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    def color_display(self, obj):
        """色をビジュアル表示"""
        return format_html(
            '<span style="background-color:{}; width:20px; height:20px; display:inline-block; border-radius:3px;"></span> {}',
            obj.color, obj.color
        )
    color_display.short_description = 'ブランドカラー'
    
    def report_count(self, obj):
        """レポート数を表示"""
        count = obj.reports.count()
        return format_html(
            '<a href="{}?company__id__exact={}">{}</a>',
            reverse('admin:financial_reports_financialreport_changelist'),
            obj.id,
            count
        )
    report_count.short_description = 'レポート数'
    
    actions = ['make_public', 'make_private']
    
    def make_public(self, request, queryset):
        """選択した企業を公開に設定"""
        updated = queryset.update(is_public=True)
        self.message_user(request, f'{updated}件の企業を公開に設定しました。')
    make_public.short_description = '選択した企業を公開に設定'
    
    def make_private(self, request, queryset):
        """選択した企業を非公開に設定"""
        updated = queryset.update(is_public=False)
        self.message_user(request, f'{updated}件の企業を非公開に設定しました。')
    make_private.short_description = '選択した企業を非公開に設定'

@admin.register(FinancialReport)
class FinancialReportAdmin(admin.ModelAdmin):
    """決算レポートの管理画面"""
    list_display = ('id', 'company_link', 'fiscal_period', 'overall_rating_display', 'recommendation_display', 'is_public', 'view_count_admin', 'created_at')
    list_filter = ('is_public', 'created_at', 'company')
    search_fields = ('company__name', 'company__code', 'fiscal_period')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'data_pretty')
    inlines = [ReportViewInline]
    
    fieldsets = (
        (None, {
            'fields': ('company', 'fiscal_period', 'achievement_badge', 'overall_rating', 'is_public')
        }),
        ('レポートデータ', {
            'fields': ('data_pretty',),
        }),
        ('メタ情報', {
            'classes': ('collapse',),
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
        }),
    )
    
    def company_link(self, obj):
        """企業名をリンク表示"""
        return format_html(
            '<a href="{}">{} ({})</a>',
            reverse('admin:financial_reports_company_change', args=[obj.company.id]),
            obj.company.name,
            obj.company.code
        )
    company_link.short_description = '企業'
    
    def overall_rating_display(self, obj):
        """評価を色付きで表示"""
        rating = obj.overall_rating
        if rating >= 7:
            color = 'success'
            label = '高評価'
        elif rating >= 4:
            color = 'warning'
            label = '中評価'
        else:
            color = 'danger'
            label = '低評価'
        
        return format_html(
            '<span class="badge bg-{}">{} ({})</span>',
            color, rating, label
        )
    overall_rating_display.short_description = '総合評価'
    
    def recommendation_display(self, obj):
        """投資判断を表示"""
        recommendation = obj.data.get('recommendationText', '未設定')
        if '買い' in recommendation:
            color = 'success'
        elif '売り' in recommendation:
            color = 'danger'
        else:
            color = 'warning'
        
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, recommendation
        )
    recommendation_display.short_description = '投資判断'
    
    def view_count_admin(self, obj):
        """閲覧数を表示"""
        count = obj.views.count()
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:financial_reports_reportview_changelist') + f'?report__id__exact={obj.id}',
            count
        )
    view_count_admin.short_description = '閲覧数'
    
    def data_pretty(self, obj):
        """JSONデータを整形して表示"""
        import json
        from django.utils.safestring import mark_safe
        
        if not obj.data:
            return '-'
        
        json_formatted = json.dumps(obj.data, indent=2, ensure_ascii=False)
        return mark_safe(f'<pre style="max-height:400px;overflow-y:auto;">{json_formatted}</pre>')
    data_pretty.short_description = 'レポートデータ (JSON)'
    
    def save_model(self, request, obj, form, change):
        """管理者情報を自動保存"""
        if not change:  # 新規作成時
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['make_public', 'make_private']
    
    def make_public(self, request, queryset):
        """選択したレポートを公開に設定"""
        updated = queryset.update(is_public=True)
        self.message_user(request, f'{updated}件のレポートを公開に設定しました。')
    make_public.short_description = '選択したレポートを公開に設定'
    
    def make_private(self, request, queryset):
        """選択したレポートを非公開に設定"""
        updated = queryset.update(is_public=False)
        self.message_user(request, f'{updated}件のレポートを非公開に設定しました。')
    make_private.short_description = '選択したレポートを非公開に設定'

@admin.register(ReportView)
class ReportViewAdmin(admin.ModelAdmin):
    """閲覧履歴の管理画面"""
    list_display = ('id', 'report_link', 'company_name', 'ip_address', 'timestamp')
    list_filter = ('timestamp', 'report__company')
    search_fields = ('ip_address', 'user_agent', 'report__company__name')
    readonly_fields = ('report', 'ip_address', 'user_agent', 'timestamp')
    
    def report_link(self, obj):
        """レポートへのリンク"""
        return format_html(
            '<a href="{}">{} - {}</a>',
            reverse('admin:financial_reports_financialreport_change', args=[obj.report.id]),
            obj.report.company.code,
            obj.report.fiscal_period
        )
    report_link.short_description = 'レポート'
    
    def company_name(self, obj):
        """企業名"""
        return obj.report.company.name
    company_name.short_description = '企業名'
    
    def has_add_permission(self, request):
        """追加権限なし（自動記録のみ）"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """編集権限なし（閲覧のみ）"""
        return False