# stockdiary/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .models import StockDiary, Transaction, StockSplit, DiaryNote


class TransactionInline(admin.TabularInline):
    """取引のインライン編集"""
    model = Transaction
    extra = 0
    fields = (
        'transaction_date', 'transaction_type', 'price', 'quantity', 
        'amount_display', 'memo'
    )
    readonly_fields = ('amount_display',)
    ordering = ['-transaction_date', '-created_at']
    
    def amount_display(self, obj):
        """取引金額を表示"""
        if obj.price and obj.quantity:
            amount = obj.price * obj.quantity
            return f'¥{amount:,.0f}'
        return '-'
    amount_display.short_description = '金額'


class StockSplitInline(admin.TabularInline):
    """株式分割のインライン編集"""
    model = StockSplit
    extra = 0
    fields = ('split_date', 'split_ratio', 'is_applied', 'applied_at', 'memo')
    readonly_fields = ('applied_at',)
    ordering = ['-split_date']


class DiaryNoteInline(admin.StackedInline):
    """継続記録のインライン編集"""
    model = DiaryNote
    extra = 0
    fields = (
        'date', 'note_type', 'importance', 'content', 
        'current_price', 'image'
    )
    ordering = ['-date']


@admin.register(StockDiary)
class StockDiaryAdmin(admin.ModelAdmin):
    """株式日記の管理画面"""
    
    list_display = (
        'id', 'stock_name_link', 'stock_symbol', 'user', 'status_badge',
        'current_quantity_display', 'average_price_display', 
        'realized_profit_display', 'transaction_count', 
        'first_purchase_date', 'created_at'
    )
    
    list_filter = (
        'user', 'sector', 'created_at', 'first_purchase_date',
        ('current_quantity', admin.EmptyFieldListFilter),
    )
    
    search_fields = (
        'stock_name', 'stock_symbol', 'user__username', 
        'reason', 'memo', 'sector'
    )
    
    readonly_fields = (
        'current_quantity', 'average_purchase_price', 'total_cost',
        'realized_profit', 'total_bought_quantity', 'total_sold_quantity',
        'total_buy_amount', 'total_sell_amount', 'transaction_count',
        'first_purchase_date', 'last_transaction_date',
        'created_at', 'updated_at', 'image_preview'
    )
    
    fieldsets = (
        ('基本情報', {
            'fields': (
                'user', 'stock_symbol', 'stock_name', 'sector',
                'reason', 'memo', 'tags', 'checklist'
            )
        }),
        ('画像', {
            'fields': ('image', 'image_preview'),
            'classes': ('collapse',)
        }),
        ('集計情報（自動計算）', {
            'fields': (
                ('current_quantity', 'average_purchase_price'),
                ('total_cost', 'realized_profit'),
                ('total_bought_quantity', 'total_sold_quantity'),
                ('total_buy_amount', 'total_sell_amount'),
                'transaction_count',
            ),
            'classes': ('collapse',)
        }),
        ('日付情報', {
            'fields': (
                ('first_purchase_date', 'last_transaction_date'),
                ('created_at', 'updated_at')
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TransactionInline, StockSplitInline, DiaryNoteInline]
    
    date_hierarchy = 'created_at'
    
    actions = ['recalculate_aggregates', 'export_csv']
    
    def get_queryset(self, request):
        """関連オブジェクトを事前取得してパフォーマンスを改善"""
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('user').prefetch_related('tags')
        queryset = queryset.annotate(
            num_transactions=Count('transactions'),
            num_notes=Count('notes')
        )
        return queryset
    
    def stock_name_link(self, obj):
        """銘柄名をリンク付きで表示"""
        url = reverse('admin:stockdiary_stockdiary_change', args=[obj.id])
        return format_html('<a href="{}">{}</a>', url, obj.stock_name)
    stock_name_link.short_description = '銘柄名'
    stock_name_link.admin_order_field = 'stock_name'
    
    def status_badge(self, obj):
        """ステータスをバッジで表示"""
        if obj.is_memo:
            return format_html(
                '<span style="background-color: #6c757d; color: white; '
                'padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
                'メモ</span>'
            )
        elif obj.is_holding:
            return format_html(
                '<span style="background-color: #28a745; color: white; '
                'padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
                '保有中</span>'
            )
        elif obj.is_sold_out:
            return format_html(
                '<span style="background-color: #dc3545; color: white; '
                'padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
                '売却済</span>'
            )
        return '-'
    status_badge.short_description = 'ステータス'
    
    def current_quantity_display(self, obj):
        """現在保有数を表示"""
        if obj.current_quantity > 0:
            return f'{obj.current_quantity:,.2f}株'
        return '-'
    current_quantity_display.short_description = '保有数'
    current_quantity_display.admin_order_field = 'current_quantity'
    
    def average_price_display(self, obj):
        """平均取得単価を表示"""
        if obj.average_purchase_price:
            return f'¥{obj.average_purchase_price:,.2f}'
        return '-'
    average_price_display.short_description = '平均単価'
    average_price_display.admin_order_field = 'average_purchase_price'
    
    def realized_profit_display(self, obj):
        """実現損益を色付きで表示"""
        if obj.realized_profit == 0:
            return '¥0'
        
        color = '#28a745' if obj.realized_profit > 0 else '#dc3545'
        sign = '+' if obj.realized_profit > 0 else ''
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{:,.0f}円</span>',
            color, sign, obj.realized_profit
        )
    realized_profit_display.short_description = '実現損益'
    realized_profit_display.admin_order_field = 'realized_profit'
    
    def image_preview(self, obj):
        """画像のプレビューを表示"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px;"/>',
                obj.image.url
            )
        return 'なし'
    image_preview.short_description = '画像プレビュー'
    
    def recalculate_aggregates(self, request, queryset):
        """選択した日記の集計を再計算"""
        count = 0
        for diary in queryset:
            diary.update_aggregates()
            count += 1
        
        self.message_user(
            request,
            f'{count}件の日記の集計を再計算しました。'
        )
    recalculate_aggregates.short_description = '選択した日記の集計を再計算'
    
    def export_csv(self, request, queryset):
        """CSVエクスポート（簡易版）"""
        import csv
        from django.http import HttpResponse
        from datetime import datetime
        
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="stock_diary_{datetime.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'ユーザー', '銘柄コード', '銘柄名', '業種',
            '保有数', '平均単価', '総原価', '実現損益',
            '取引回数', '最初の購入日', '作成日'
        ])
        
        for obj in queryset:
            writer.writerow([
                obj.id,
                obj.user.username,
                obj.stock_symbol,
                obj.stock_name,
                obj.sector,
                obj.current_quantity,
                obj.average_purchase_price,
                obj.total_cost,
                obj.realized_profit,
                obj.transaction_count,
                obj.first_purchase_date,
                obj.created_at.strftime('%Y-%m-%d')
            ])
        
        return response
    export_csv.short_description = '選択した日記をCSV出力'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """取引の管理画面"""
    
    list_display = (
        'id', 'diary_link', 'transaction_type_badge', 'transaction_date',
        'price_display', 'quantity_display', 'amount_display',
        'quantity_after_display', 'created_at'
    )
    
    list_filter = (
        'transaction_type', 'transaction_date', 'diary__user'
    )
    
    search_fields = (
        'diary__stock_name', 'diary__stock_symbol', 
        'diary__user__username', 'memo'
    )
    
    readonly_fields = (
        'amount_display', 'quantity_after', 'average_price_after',
        'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('基本情報', {
            'fields': (
                'diary', 'transaction_type', 'transaction_date',
                'price', 'quantity', 'amount_display', 'memo'
            )
        }),
        ('取引後の状態', {
            'fields': (
                'quantity_after', 'average_price_after'
            ),
            'classes': ('collapse',)
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'transaction_date'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('diary', 'diary__user')
    
    def diary_link(self, obj):
        """日記へのリンク"""
        url = reverse('admin:stockdiary_stockdiary_change', args=[obj.diary.id])
        return format_html(
            '<a href="{}">{} ({})</a>',
            url, obj.diary.stock_name, obj.diary.stock_symbol
        )
    diary_link.short_description = '日記'
    
    def transaction_type_badge(self, obj):
        """取引種別をバッジで表示"""
        if obj.transaction_type == 'buy':
            color = '#007bff'
            label = '購入'
        else:
            color = '#dc3545'
            label = '売却'
        
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
            '{}</span>',
            color, label
        )
    transaction_type_badge.short_description = '種別'
    transaction_type_badge.admin_order_field = 'transaction_type'
    
    def price_display(self, obj):
        """単価を表示"""
        return f'¥{obj.price:,.2f}'
    price_display.short_description = '単価'
    price_display.admin_order_field = 'price'
    
    def quantity_display(self, obj):
        """数量を表示"""
        return f'{obj.quantity:,.2f}株'
    quantity_display.short_description = '数量'
    quantity_display.admin_order_field = 'quantity'
    
    def amount_display(self, obj):
        """金額を表示"""
        return f'¥{obj.amount:,.0f}'
    amount_display.short_description = '金額'
    
    def quantity_after_display(self, obj):
        """取引後保有数を表示"""
        if obj.quantity_after is not None:
            return f'{obj.quantity_after:,.2f}株'
        return '-'
    quantity_after_display.short_description = '取引後保有数'


@admin.register(StockSplit)
class StockSplitAdmin(admin.ModelAdmin):
    """株式分割の管理画面"""
    
    list_display = (
        'id', 'diary_link', 'split_date', 'split_ratio_display',
        'is_applied_badge', 'applied_at', 'created_at'
    )
    
    list_filter = ('is_applied', 'split_date', 'diary__user')
    
    search_fields = (
        'diary__stock_name', 'diary__stock_symbol',
        'diary__user__username', 'memo'
    )
    
    readonly_fields = ('applied_at', 'created_at')
    
    fieldsets = (
        ('基本情報', {
            'fields': (
                'diary', 'split_date', 'split_ratio', 'memo'
            )
        }),
        ('適用状態', {
            'fields': ('is_applied', 'applied_at')
        }),
        ('システム情報', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'split_date'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('diary', 'diary__user')
    
    def diary_link(self, obj):
        """日記へのリンク"""
        url = reverse('admin:stockdiary_stockdiary_change', args=[obj.diary.id])
        return format_html(
            '<a href="{}">{} ({})</a>',
            url, obj.diary.stock_name, obj.diary.stock_symbol
        )
    diary_link.short_description = '日記'
    
    def split_ratio_display(self, obj):
        """分割比率を表示"""
        return f'1 → {obj.split_ratio}倍'
    split_ratio_display.short_description = '分割比率'
    split_ratio_display.admin_order_field = 'split_ratio'
    
    def is_applied_badge(self, obj):
        """適用状態をバッジで表示"""
        if obj.is_applied:
            return format_html(
                '<span style="background-color: #28a745; color: white; '
                'padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
                '適用済み</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #6c757d; color: white; '
                'padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
                '未適用</span>'
            )
    is_applied_badge.short_description = '適用状態'
    is_applied_badge.admin_order_field = 'is_applied'


@admin.register(DiaryNote)
class DiaryNoteAdmin(admin.ModelAdmin):
    """継続記録の管理画面"""
    
    list_display = (
        'id', 'diary_link', 'date', 'note_type_badge',
        'importance_badge', 'content_preview', 'current_price_display',
        'created_at'
    )
    
    list_filter = (
        'note_type', 'importance', 'date', 'diary__user'
    )
    
    search_fields = (
        'diary__stock_name', 'diary__stock_symbol',
        'diary__user__username', 'content'
    )
    
    readonly_fields = ('created_at', 'updated_at', 'image_preview')
    
    fieldsets = (
        ('基本情報', {
            'fields': (
                'diary', 'date', 'note_type', 'importance',
                'content', 'current_price'
            )
        }),
        ('画像', {
            'fields': ('image', 'image_preview'),
            'classes': ('collapse',)
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'date'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('diary', 'diary__user')
    
    def diary_link(self, obj):
        """日記へのリンク"""
        url = reverse('admin:stockdiary_stockdiary_change', args=[obj.diary.id])
        return format_html(
            '<a href="{}">{} ({})</a>',
            url, obj.diary.stock_name, obj.diary.stock_symbol
        )
    diary_link.short_description = '日記'
    
    def note_type_badge(self, obj):
        """記録タイプをバッジで表示"""
        colors = {
            'analysis': '#007bff',
            'news': '#17a2b8',
            'earnings': '#28a745',
            'insight': '#ffc107',
            'risk': '#dc3545',
            'other': '#6c757d'
        }
        
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
            '{}</span>',
            colors.get(obj.note_type, '#6c757d'),
            obj.get_note_type_display()
        )
    note_type_badge.short_description = 'タイプ'
    note_type_badge.admin_order_field = 'note_type'
    
    def importance_badge(self, obj):
        """重要度をバッジで表示"""
        colors = {
            'high': '#dc3545',
            'medium': '#ffc107',
            'low': '#28a745'
        }
        
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
            '{}</span>',
            colors.get(obj.importance, '#6c757d'),
            obj.get_importance_display()
        )
    importance_badge.short_description = '重要度'
    importance_badge.admin_order_field = 'importance'
    
    def content_preview(self, obj):
        """内容のプレビュー"""
        if len(obj.content) > 50:
            return f'{obj.content[:50]}...'
        return obj.content
    content_preview.short_description = '内容'
    
    def current_price_display(self, obj):
        """記録時価格を表示"""
        if obj.current_price:
            return f'¥{obj.current_price:,.2f}'
        return '-'
    current_price_display.short_description = '記録時価格'
    current_price_display.admin_order_field = 'current_price'
    
    def image_preview(self, obj):
        """画像のプレビューを表示"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px;"/>',
                obj.image.url
            )
        return 'なし'
    image_preview.short_description = '画像プレビュー'