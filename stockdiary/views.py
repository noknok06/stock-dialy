from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.urls import reverse_lazy
from django.db.models import Q, Count, Avg, F, Sum, Min, Max, Case, When, Value, IntegerField
from django.db.models.functions import TruncMonth, ExtractWeekDay, Length
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.template.defaultfilters import truncatechars_html
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse, Http404
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.conf import settings
from django.urls import reverse

from utils.mixins import ObjectNotFoundRedirectMixin
from .utils import process_analysis_values, calculate_analysis_completion_rate
from .models import StockDiary, DiaryNote
from .models import Transaction, StockSplit
from .forms import TransactionForm, StockSplitForm
from .forms import StockDiaryForm, DiaryNoteForm
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from company_master.models import CompanyMaster
from tags.models import Tag

from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import calendar
import mimetypes
import os
import io
import traceback
import html
import json
import re
import statistics

from PIL import Image

# margin_trading アプリのインポート（オプション）
try:
    from margin_trading.models import MarginTradingData, MarketIssue
    MARGIN_TRADING_AVAILABLE = True
except ImportError:
    MARGIN_TRADING_AVAILABLE = False
    import logging
    logging.getLogger(__name__).warning(
        "margin_trading アプリが見つかりません。信用倍率機能は無効になります。"
    )


# ==========================================
# ユーティリティ関数
# ==========================================

def get_market_issue(stock_symbol):
    """証券コードから銘柄を取得する共通関数"""
    if not MARGIN_TRADING_AVAILABLE or not stock_symbol:
        return None
    
    search_code = str(stock_symbol).rstrip('0') + '0'
    market_issue = MarketIssue.objects.filter(code=search_code).first()
    if not market_issue:
        market_issue = MarketIssue.objects.filter(code=str(stock_symbol)).first()
    return market_issue


def calculate_margin_ratio(outstanding_purchases, outstanding_sales):
    """信用倍率を計算する共通関数"""
    if outstanding_sales > 0:
        return round(outstanding_purchases / outstanding_sales, 2)
    return 0


def get_margin_data(stock_symbol, limit=20):
    """銘柄の信用倍率データを取得する共通関数"""
    if not MARGIN_TRADING_AVAILABLE:
        return None, None
    
    try:
        market_issue = get_market_issue(stock_symbol)
        if not market_issue:
            return None, None
        
        margin_queryset = MarginTradingData.objects.filter(
            issue=market_issue
        ).order_by('-date')[:limit]
        
        latest_margin_data = margin_queryset.first() if margin_queryset else None
        margin_data = list(margin_queryset)
        
        return margin_data, latest_margin_data
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"信用倍率データ取得エラー (symbol: {stock_symbol}): {e}")
        return None, None


def render_error_html(icon, title, message, show_retry=False):
    """エラーメッセージHTMLを生成する共通関数"""
    retry_button = '''
        <button class="btn btn-sm btn-outline-primary" onclick="window.location.reload()">
            <i class="bi bi-arrow-clockwise me-1"></i>再試行
        </button>
    ''' if show_retry else ''
    
    return f'''
    <div class="text-center py-4">
        <div class="text-muted">
            <i class="bi bi-{icon}" style="font-size: 2rem;"></i>
            <h6 class="mt-3">{title}</h6>
            <p class="mb-0 small">{message}</p>
            {retry_button}
        </div>
    </div>
    '''


def get_note_badge_class(note_type):
    """ノートタイプに応じたバッジクラスを取得"""
    badge_classes = {
        'analysis': 'bg-primary',
        'news': 'bg-info',
        'earnings': 'bg-success',
        'insight': 'bg-warning',
        'risk': 'bg-danger'
    }
    return badge_classes.get(note_type, 'bg-secondary')


def get_note_type_display(note_type):
    """ノートタイプの表示名を取得"""
    type_displays = {
        'analysis': '分析更新',
        'news': 'ニュース',
        'earnings': '決算情報',
        'insight': '新たな気づき',
        'risk': 'リスク要因'
    }
    return type_displays.get(note_type, 'その他')


# ==========================================
# ビュークラス
# ==========================================

class StockDiaryListView(LoginRequiredMixin, ListView):
    model = StockDiary
    template_name = 'stockdiary/home.html'
    context_object_name = 'diaries'
    paginate_by = 4
    
    def get_queryset(self):
        queryset = StockDiary.objects.filter(user=self.request.user).order_by('-updated_at')
        queryset = queryset.select_related('user').prefetch_related('tags', 'notes')
        
        # 検索フィルター
        query = self.request.GET.get('query', '')
        tag_id = self.request.GET.get('tag', '')
        status = self.request.GET.get('status', '')
        
        if query:
            queryset = queryset.filter(
                Q(stock_name__icontains=query) | 
                Q(stock_symbol__icontains=query) |
                Q(reason__icontains=query) |
                Q(memo__icontains=query)
            )

        # 日付範囲フィルター
        date_range = self.request.GET.get('date_range', '')
        if date_range:
            today = timezone.now().date()
            
            range_mapping = {
                '1w': 7,
                '1m': 30,
                '3m': 90,
                '6m': 180,
                '1y': 365
            }
            
            if date_range in range_mapping:
                start_date = today - timedelta(days=range_mapping[date_range])
                queryset = queryset.filter(first_purchase_date__gte=start_date)
                        
        if tag_id:
            queryset = queryset.filter(tags__id=tag_id)
        
        # ステータスフィルター
        if status == 'active':
            queryset = queryset.filter(current_quantity__gt=0)
        elif status == 'sold':
            queryset = queryset.filter(current_quantity=0, transaction_count__gt=0)
        elif status == 'memo':
            queryset = queryset.filter(transaction_count=0)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tags'] = Tag.objects.filter(user=self.request.user)
        
        # カレンダー表示用にすべての日記データを追加
        diaries_query = StockDiary.objects.filter(user=self.request.user)
        context['all_diaries'] = diaries_query.defer(
            'reason', 'memo', 'created_at', 'updated_at',
        )
        
        # 統計情報を計算
        all_diaries = StockDiary.objects.filter(user=self.request.user)
        
        # 保有中の銘柄数
        active_holdings = all_diaries.filter(current_quantity__gt=0)
        context['active_holdings_count'] = active_holdings.count()
        
        # 実現損益の合計
        realized_profit = all_diaries.aggregate(
            total_profit=Sum('realized_profit')
        )['total_profit'] or Decimal('0')
        context['realized_profit'] = realized_profit
        
        context['current_query'] = self.request.GET.urlencode()
    
        # フォーム用のスピードダイアルアクション
        context['form_actions'] = [
            {
                'type': 'add',
                'url': reverse_lazy('stockdiary:create'),
                'icon': 'bi-plus-lg',
                'label': '詳細作成',
                'aria_label': '詳細作成' 
            },
            {
                'type': 'template',
                'url': reverse_lazy('analysis_template:list'),
                'icon': 'bi-clipboard-data',
                'label': 'テンプレート',
                'aria_label': 'テンプレート',
            },
            {
                'type': 'tag',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-tags',
                'label': 'タグ管理',
                'aria_label': 'タグ管理' 
            }
        ]
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                self.object_list = self.get_queryset()
                page_size = self.get_paginate_by(self.object_list)
                
                if page_size:
                    paginator = self.get_paginator(self.object_list, page_size)
                    page_number = request.GET.get('page', 1)
                    try:
                        page_obj = paginator.get_page(page_number)
                    except (EmptyPage, PageNotAnInteger):
                        page_obj = paginator.get_page(1)
                    
                    data = []
                    for diary in page_obj:
                        try:
                            diary_html = render_to_string('stockdiary/partials/diary_card.html', {
                                'diary': diary,
                                'request': request,
                                'forloop': {'counter': 1}
                            })
                            data.append(diary_html)
                        except Exception as e:
                            print(f"Error rendering diary {diary.id}: {e}")
                            continue
                    
                    return JsonResponse({
                        'html': data,
                        'has_next': page_obj.has_next(),
                        'next_page': page_obj.next_page_number() if page_obj.has_next() else None
                    })
            except Exception as e:
                print(f"AJAX request error: {e}")
                print(traceback.format_exc())
                return JsonResponse({
                    'error': str(e),
                    'message': 'データの読み込み中にエラーが発生しました。'
                }, status=500)
        
        return super().get(request, *args, **kwargs)


class StockDiaryDetailView(ObjectNotFoundRedirectMixin, LoginRequiredMixin, DetailView):
    model = StockDiary
    template_name = 'stockdiary/detail.html'
    context_object_name = 'diary'
    redirect_url = 'stockdiary:home'
    not_found_message = "日記エントリーが見つかりません。削除された可能性があります。"
    
    def get_queryset(self):
        return StockDiary.objects.filter(user=self.request.user).select_related('user').prefetch_related(
            'notes', 'tags', 'checklist', 'analysis_values__analysis_item',
            'transactions', 'stock_splits'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 取引履歴を取得
        transactions = self.object.transactions.all().order_by('-transaction_date', '-created_at')
        context['transactions'] = transactions
        
        # 株式分割履歴を取得
        stock_splits = self.object.stock_splits.all().order_by('-split_date')
        context['stock_splits'] = stock_splits
        
        # 取引と分割を時系列で統合
        combined = []
        for transaction in transactions:
            combined.append({
                'type': 'transaction',
                'date': transaction.transaction_date,
                'data': transaction
            })
        
        for split in stock_splits:
            combined.append({
                'type': 'split',
                'date': split.split_date,
                'data': split
            })
        
        # 日付でソート（降順）
        combined.sort(key=lambda x: x['date'], reverse=True)
        context['combined_history'] = combined
        
        # 継続記録
        context['note_form'] = DiaryNoteForm(initial={'date': timezone.now().date()})
        context['notes'] = self.object.notes.all().order_by('-date')
        
        # 分析テンプレート情報
        context['analysis_templates_info'] = self._get_analysis_templates_info()
        
        # 信用倍率データ
        if MARGIN_TRADING_AVAILABLE:
            from .views import get_margin_data
            margin_data, latest_margin_data = get_margin_data(self.object.stock_symbol, limit=10)
            context['margin_data'] = margin_data
            context['latest_margin_data'] = latest_margin_data
        
        # 関連日記
        all_related_diaries = StockDiary.objects.filter(
            user=self.request.user,
            stock_symbol=self.object.stock_symbol
        ).order_by('first_purchase_date', 'created_at')
        
        context['related_diaries'] = all_related_diaries.exclude(id=self.object.id)
        context['timeline_diaries'] = all_related_diaries
        
        # スピードダイアルアクション
        context['diary_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'edit',
                'url': reverse_lazy('stockdiary:update', kwargs={'pk': self.object.id}),
                'icon': 'bi-pencil',
                'label': '編集'
            },
            {
                'type': 'delete',
                'url': reverse_lazy('stockdiary:delete', kwargs={'pk': self.object.id}),
                'icon': 'bi-trash',
                'label': '削除'
            }
        ]
        
        return context
    
    def _get_analysis_templates_info(self):
        """分析テンプレート情報を取得"""
        from collections import defaultdict
        from analysis_template.models import DiaryAnalysisValue
        
        diary = self.object
        analysis_values = DiaryAnalysisValue.objects.filter(
            diary=diary
        ).select_related('analysis_item__template').order_by('analysis_item__order')
        
        if not analysis_values.exists():
            return []
        
        templates_data = defaultdict(lambda: {
            'template': None,
            'total_items': 0,
            'completed_items': 0,
            'completion_rate': 0,
            'values': [],
            'items_with_values': []
        })
        
        for value in analysis_values:
            template = value.analysis_item.template
            template_id = template.id
            
            if templates_data[template_id]['template'] is None:
                templates_data[template_id]['template'] = template
                templates_data[template_id]['total_items'] = template.items.count()
            
            templates_data[template_id]['values'].append(value)
            
            item_with_value = {
                'item': value.analysis_item,
                'value': value,
                'display_value': self._get_analysis_display_value(value),
                'is_completed': self._is_analysis_item_completed(value)
            }
            templates_data[template_id]['items_with_values'].append(item_with_value)
            
            if item_with_value['is_completed']:
                templates_data[template_id]['completed_items'] += 1
        
        result = []
        for template_data in templates_data.values():
            if template_data['total_items'] > 0:
                completion_rate = (template_data['completed_items'] / template_data['total_items']) * 100
                template_data['completion_rate'] = round(completion_rate, 1)
            result.append(template_data)
        
        result.sort(key=lambda x: x['template'].name)
        return result
    
    def _get_analysis_display_value(self, analysis_value):
        """分析値の表示用テキストを取得"""
        item = analysis_value.analysis_item
        
        if item.item_type == 'boolean':
            return "はい" if analysis_value.boolean_value else "いいえ"
        elif item.item_type == 'boolean_with_value':
            result = "✓" if analysis_value.boolean_value else "✗"
            if analysis_value.boolean_value:
                if analysis_value.number_value is not None:
                    result += f" {analysis_value.number_value}"
                    if analysis_value.analysis_item.value_label:
                        result += f" {analysis_value.analysis_item.value_label}"
                elif analysis_value.text_value:
                    result += f" {analysis_value.text_value}"
            return result
        elif item.item_type == 'number':
            return f"{analysis_value.number_value}" if analysis_value.number_value is not None else "-"
        elif item.item_type == 'select':
            return analysis_value.text_value if analysis_value.text_value else "-"
        elif item.item_type == 'text':
            return analysis_value.text_value if analysis_value.text_value else "-"
        
        return "-"
    
    def _is_analysis_item_completed(self, analysis_value):
        """分析項目が完了しているかを判定"""
        item = analysis_value.analysis_item
        
        if item.item_type == 'boolean':
            return analysis_value.boolean_value is True
        elif item.item_type == 'boolean_with_value':
            return analysis_value.boolean_value is True
        elif item.item_type == 'number':
            return analysis_value.number_value is not None
        elif item.item_type in ['text', 'select']:
            return bool(analysis_value.text_value and analysis_value.text_value.strip())
        
        return False

class StockDiaryCreateView(LoginRequiredMixin, CreateView):
    model = StockDiary
    form_class = StockDiaryForm
    template_name = 'stockdiary/diary_form.html'
    success_url = reverse_lazy('stockdiary:home')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        
        # 画像ファイルの処理
        image_file = form.cleaned_data.get('image')
        if image_file:
            success = self.object.process_and_save_image(image_file)
            if not success:
                messages.warning(self.request, '日記は作成されましたが、画像の処理に失敗しました。')
        
        # 分析テンプレートの処理
        analysis_template_id = self.request.POST.get('analysis_template')
        if analysis_template_id:
            from .utils import process_analysis_values
            process_analysis_values(self.request, self.object, analysis_template_id)
        
        # 初回購入情報の処理
        if form.cleaned_data.get('add_initial_purchase'):
            try:
                initial_transaction = Transaction(
                    diary=self.object,
                    transaction_type='buy',
                    transaction_date=form.cleaned_data['initial_purchase_date'],
                    price=form.cleaned_data['initial_purchase_price'],
                    quantity=form.cleaned_data['initial_purchase_quantity'],
                    memo='初回購入'
                )
                initial_transaction.save()
                
                # 取引後の状態を記録
                initial_transaction.quantity_after = self.object.current_quantity
                initial_transaction.average_price_after = self.object.average_purchase_price
                initial_transaction.save(update_fields=['quantity_after', 'average_price_after'])
                
                messages.success(self.request, '日記を作成し、初回購入取引を記録しました')
            except Exception as e:
                messages.warning(
                    self.request,
                    f'日記は作成されましたが、初回購入取引の記録に失敗しました: {str(e)}'
                )
        else:
            messages.success(self.request, '日記を作成しました')
        
        return response


class StockDiaryUpdateView(ObjectNotFoundRedirectMixin, LoginRequiredMixin, UpdateView):
    model = StockDiary
    form_class = StockDiaryForm
    template_name = 'stockdiary/diary_form.html'
    redirect_url = 'stockdiary:home'
    not_found_message = "日記エントリーが見つかりません。削除された可能性があります。"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:detail', kwargs={'pk': self.object.pk}),
                'icon': 'bi-arrow-left',
                'label': '戻る',
                'aria_label': '戻る' 
            },
            {
                'type': 'template',
                'url': reverse_lazy('analysis_template:list'),
                'icon': 'bi-clipboard-data',
                'label': 'テンプレート',
                'aria_label': 'テンプレート' 
            },
            {
                'type': 'tag',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-tags',
                'label': 'タグ管理',
                'aria_label': 'タグ管理' 
            }
        ]
        return context

    def get_queryset(self):
        return StockDiary.objects.filter(user=self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        if request.POST.get('clear_image'):
            success = self.object.delete_image()
            if not success:
                messages.warning(request, '画像の削除に失敗しました。')
        
        return super().post(request, *args, **kwargs)
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        image_file = form.cleaned_data.get('image')
        if image_file:
            success = self.object.process_and_save_image(image_file)
            if not success:
                messages.warning(self.request, '日記は更新されましたが、画像の処理に失敗しました。')
        
        analysis_template_id = self.request.POST.get('analysis_template')
        if analysis_template_id:
            DiaryAnalysisValue.objects.filter(diary_id=self.object.id).delete()
            process_analysis_values(self.request, self.object, analysis_template_id)
        
        return response
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        diary = self.get_object()
        diary_analysis_values = DiaryAnalysisValue.objects.filter(diary=diary).select_related('analysis_item__template')
        
        used_templates = set()
        for value in diary_analysis_values:
            used_templates.add(value.analysis_item.template_id)
        
        if used_templates:
            template_id = list(used_templates)[0]
            form.fields['analysis_template'].initial = template_id
        
        return form
    
    def get_success_url(self):
        return reverse_lazy('stockdiary:detail', kwargs={'pk': self.object.pk})


class StockDiaryDeleteView(LoginRequiredMixin, DeleteView):
    model = StockDiary
    template_name = 'stockdiary/diary_confirm_delete.html'
    success_url = reverse_lazy('stockdiary:home')
    
    def get_queryset(self):
        return StockDiary.objects.filter(user=self.request.user)


class AddDiaryNoteView(LoginRequiredMixin, CreateView):
    """日記エントリーへの継続記録追加"""
    model = DiaryNote
    form_class = DiaryNoteForm
    http_method_names = ['post']
    
    def form_valid(self, form):
        diary_id = self.kwargs.get('pk')
        diary = get_object_or_404(StockDiary, id=diary_id, user=self.request.user)
        form.instance.diary = diary
        
        response = super().form_valid(form)
        
        image_file = self.request.FILES.get('image')
        if image_file:
            if image_file.size > 10 * 1024 * 1024:
                messages.error(self.request, '画像ファイルのサイズは10MB以下にしてください')
                return self.form_invalid(form)
            
            valid_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(image_file, 'content_type') and image_file.content_type not in valid_formats:
                messages.error(self.request, 'JPEG、PNG、GIF、WebP形式の画像ファイルのみアップロード可能です')
                return self.form_invalid(form)
            
            success = self.object.process_and_save_image(image_file)
            if not success:
                messages.warning(self.request, '継続記録は追加されましたが、画像の処理に失敗しました。')
        
        messages.success(self.request, "継続記録を追加しました")
        return response
    
    def get_success_url(self):
        return reverse_lazy('stockdiary:detail', kwargs={'pk': self.kwargs.get('pk')})
    
    def form_invalid(self, form):
        diary_id = self.kwargs.get('pk')
        return redirect('stockdiary:detail', pk=diary_id)


class CancelSellView(LoginRequiredMixin, View):
    """売却情報を取り消すビュー"""
    
    def get(self, request, *args, **kwargs):
        diary_id = kwargs.get('pk')
        try:
            diary = StockDiary.objects.get(id=diary_id, user=request.user)
            diary.sell_date = None
            diary.sell_price = None
            diary.save()
            messages.success(request, f'{diary.stock_name}の売却情報を取り消しました')
        except StockDiary.DoesNotExist:
            messages.error(request, '指定された日記が見つかりません')
        
        return redirect('stockdiary:detail', pk=diary_id)


class DeleteDiaryNoteView(LoginRequiredMixin, DeleteView):
    """継続記録を削除するビュー"""
    model = DiaryNote
    template_name = 'stockdiary/note_confirm_delete.html'
    
    def get_queryset(self):
        return DiaryNote.objects.filter(diary__user=self.request.user)
    
    def get_success_url(self):
        diary_pk = self.kwargs.get('diary_pk')
        return reverse_lazy('stockdiary:detail', kwargs={'pk': diary_pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['diary_pk'] = self.kwargs.get('diary_pk')
        return context


class DiaryTabContentView(LoginRequiredMixin, View):
    def get(self, request, diary_id, tab_type):
        try:
            diary = StockDiary.objects.get(id=diary_id, user=request.user)
            
            context = {
                'diary': diary,
                'diary_id': diary.id,
            }
            
            if tab_type == 'notes':
                html = self._render_notes_tab(diary)
            elif tab_type == 'analysis':
                html = self._render_analysis_tab(diary)
            elif tab_type == 'details':
                html = self._render_details_tab(context)
            elif tab_type == 'margin':
                html = self._render_margin_tab(diary)
            else:
                return JsonResponse({'error': '無効なタブタイプです'}, status=400)
            
            return JsonResponse({'html': html})
            
        except StockDiary.DoesNotExist:
            return JsonResponse({'error': '日記が見つかりません'}, status=404)
        except Exception as e:
            error_details = traceback.format_exc()
            print(f"Tab content error: {error_details}")
            return JsonResponse({
                'error': str(e),
                'details': error_details
            }, status=500)

    def _render_margin_tab(self, diary):
        """信用倍率タブのHTMLをテンプレートレンダリングで生成"""
        if not MARGIN_TRADING_AVAILABLE:
            return render_error_html('exclamation-triangle', '信用倍率機能は利用できません', 
                                   'margin_trading アプリが設定されていません')
        
        if not diary.stock_symbol:
            return render_error_html('info-circle', '証券コードが設定されていません', 
                                   '信用倍率データを取得するには証券コードが必要です')
        
        try:
            margin_data, latest_margin_data = get_margin_data(diary.stock_symbol, limit=20)
            
            if margin_data is None:
                return render_error_html('search', '銘柄が見つかりません', 
                                       f'証券コード: {diary.stock_symbol}')
            
            if not margin_data:
                return render_error_html('database-x', '信用取引データがありません', 
                                       f'証券コード: {diary.stock_symbol}')
            
            context = {
                'diary': diary,
                'margin_data': margin_data,
                'latest_margin_data': latest_margin_data,
                'request': self.request,
            }
            
            try:
                return render_to_string('stockdiary/partials/tab_margin.html', context)
            except Exception as template_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Margin tab template error: {template_error}", exc_info=True)
                return render_error_html('exclamation-triangle text-warning', 'テンプレートエラー', 
                                       '信用倍率タブの表示中にエラーが発生しました', show_retry=True)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Margin tab rendering error (diary_id: {diary.id}): {e}", exc_info=True)
            return render_error_html('exclamation-triangle text-warning', 'データ取得エラー', 
                                   '信用倍率データの取得中にエラーが発生しました', show_retry=True)
        
    def _render_notes_tab(self, diary):
        """継続記録タブのHTMLを直接生成"""
        notes = diary.notes.all().order_by('-date')[:3]
        html = '<div class="px-1 py-2"><div class="notes-timeline">'
        
        if notes.exists():
            for note in notes:
                date_str = note.date.strftime('%Y年%m月%d日')
                badge_class = get_note_badge_class(note.note_type)
                badge_text = get_note_type_display(note.note_type)
                
                html += f'''
                <div class="note-item mb-3" data-importance="{note.importance}">
                  <div class="d-flex justify-content-between align-items-start mb-1">
                    <div class="note-date">
                      <i class="bi bi-calendar-date text-muted"></i>
                      <span class="text-muted small">{date_str}</span>
                    </div>
                    <span class="badge {badge_class} small">{badge_text}</span>
                  </div>
                '''

                                
                formatted_content = note.content.replace('\n', '<br>')
                html += f'''
                <div class="note-content bg-light p-2 rounded">
                    {formatted_content}
                </div>
                </div>
                '''
            
            notes_count = diary.notes.count()
            if notes_count > 3:
                html += f'''
                <div class="text-end mt-2">
                  <a href="/stockdiary/{diary.id}/" class="text-primary text-decoration-none small">
                    すべての記録を見る ({notes_count}件) <i class="bi bi-arrow-right"></i>
                  </a>
                </div>
                '''
        else:
            html += '<p class="text-muted">継続記録はまだありません</p>'
        
        html += '</div></div>'
        return html
            
    def _render_analysis_tab(self, diary):
        """分析タブのHTMLを直接生成"""
        html = '<div class="px-1 py-2">'
        
        analysis_values = DiaryAnalysisValue.objects.filter(diary=diary).select_related('analysis_item__template')
        
        if analysis_values.exists():
            templates = defaultdict(list)
            
            for value in analysis_values:
                template = value.analysis_item.template
                templates[template.id].append(value)
            
            for template_id, values in templates.items():
                if not values:
                    continue
                    
                template = values[0].analysis_item.template
                
                html += f'''
                <div class="analysis-template-summary mb-3" data-template-id="{template.id}">
                  <h6 class="mb-2">
                    <i class="bi bi-clipboard-check"></i> {template.name}
                  </h6>
                  <div class="progress mb-2" style="height: 6px;">
                '''
                
                items_count = template.items.count()
                filled_count = len(values)
                completion = int((filled_count / items_count) * 100) if items_count > 0 else 0
                
                html += f'<div class="progress-bar bg-primary" style="width: {completion}%"></div></div>'
                html += '<div class="analysis-item-preview">'
                
                for value in values[:5]:
                    item_name = value.analysis_item.name
                    item = value.analysis_item
                    
                    if item.item_type == 'boolean_with_value':
                        display_value = "✓" if value.boolean_value else ""
                        if value.boolean_value:
                            if value.number_value is not None:
                                display_value += f" {value.number_value:.2f}"
                            elif value.text_value:
                                display_value += f" {value.text_value}"
                    elif item.item_type == 'number':
                        display_value = f"{float(value.number_value):.2f}" if value.number_value is not None else "-"
                    elif item.item_type == 'boolean':
                        display_value = "はい" if value.boolean_value else "いいえ"
                    elif item.item_type == 'select':
                        display_value = value.text_value or "-"
                    else:
                        display_value = value.text_value or "-"
                    
                    html += f'''
                    <div class="analysis-preview-item">
                      <span class="key">{item_name}:</span>
                      <span class="value">{display_value}</span>
                    </div>
                    '''
                
                if len(values) > 5:
                    html += f'''
                    <div class="text-end mt-2">
                      <a href="/stockdiary/{diary.id}/" class="text-primary text-decoration-none small">
                        すべて表示 <i class="bi bi-arrow-right"></i>
                      </a>
                    </div>
                    '''
                
                html += '</div></div>'
        else:
            html += '<p class="text-muted">分析データはありません</p>'
        
        html += '</div>'
        return html

class StockListView(LoginRequiredMixin, TemplateView):
    """登録株式一覧を表示するビュー"""
    template_name = 'stockdiary/stock_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        search_query = self.request.GET.get('q', '').strip()
        sort_by = self.request.GET.get('sort', 'symbol')
        sector_filter = self.request.GET.get('sector', '')
        
        diary_stocks = StockDiary.objects.filter(user=user).values(
            'stock_symbol', 'stock_name', 'sector'
        ).distinct().order_by('stock_symbol')
        
        stock_list = []
        
        for stock in diary_stocks:
            if not stock['stock_symbol']:
                continue
                
            stock_info = {
                'symbol': stock['stock_symbol'],
                'name': stock['stock_name'],
                'sector': stock['sector'] or '未分類',
                'current_ratio': 0,
                'previous_ratio': 0,
                'ratio_change': 0,
                'latest_date': None,
                'diary_count': 0,
                'has_active_holdings': False,
                'has_completed_sales': False,
                'margin_data_available': False
            }
            
            stock_info['diary_count'] = StockDiary.objects.filter(
                user=user, 
                stock_symbol=stock['stock_symbol']
            ).count()
            
            if not stock_info['sector'] or stock_info['sector'] == '未分類':
                try:
                    company = CompanyMaster.objects.filter(code=stock['stock_symbol']).first()
                    if company:
                        stock_info['sector'] = company.industry_name_33 or company.industry_name_17 or '未分類'
                except:
                    pass
            
            if MARGIN_TRADING_AVAILABLE:
                try:
                    market_issue = get_market_issue(stock['stock_symbol'])
                    
                    if market_issue:
                        margin_data = MarginTradingData.objects.filter(
                            issue=market_issue
                        ).order_by('-date')[:2]
                        
                        if margin_data.exists():
                            stock_info['margin_data_available'] = True
                            latest_data = margin_data[0]
                            stock_info['latest_date'] = latest_data.date
                            stock_info['current_ratio'] = calculate_margin_ratio(
                                latest_data.outstanding_purchases, 
                                latest_data.outstanding_sales
                            )
                            
                            if len(margin_data) > 1:
                                previous_data = margin_data[1]
                                stock_info['previous_ratio'] = calculate_margin_ratio(
                                    previous_data.outstanding_purchases,
                                    previous_data.outstanding_sales
                                )
                                stock_info['ratio_change'] = round(
                                    stock_info['current_ratio'] - stock_info['previous_ratio'], 2
                                )
                
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"信用倍率データ取得エラー ({stock['stock_symbol']}): {e}")
            
            stock_list.append(stock_info)
        
        if search_query:
            stock_list = [
                stock for stock in stock_list
                if search_query.lower() in stock['name'].lower() or 
                   search_query.lower() in stock['symbol'].lower() or
                   search_query.lower() in stock['sector'].lower()
            ]
        
        if sector_filter:
            stock_list = [stock for stock in stock_list if stock['sector'] == sector_filter]
        
        sort_mapping = {
            'name': lambda x: x['name'],
            'sector': lambda x: x['sector'],
            'current_ratio_desc': lambda x: x['current_ratio'],
            'current_ratio_asc': lambda x: x['current_ratio'],
            'ratio_change_desc': lambda x: x['ratio_change'],
            'ratio_change_asc': lambda x: x['ratio_change'],
            'diary_count_desc': lambda x: x['diary_count'],
        }
        
        if sort_by in sort_mapping:
            reverse = sort_by.endswith('_desc')
            stock_list.sort(key=sort_mapping[sort_by], reverse=reverse)
        else:
            stock_list.sort(key=lambda x: x['symbol'])
        
        sectors = sorted(list(set([stock['sector'] for stock in stock_list])))
        
        stats = {
            'total_stocks': len(stock_list),
            'active_holdings': len([s for s in stock_list if s['has_active_holdings']]),
            'margin_data_available': len([s for s in stock_list if s['margin_data_available']]),
            'sectors_count': len(sectors)
        }
        
        context['page_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'add',
                'url': reverse_lazy('stockdiary:create'),
                'icon': 'bi-plus-lg',
                'label': '新規作成'
            }
        ]
        
        context.update({
            'stock_list': stock_list,
            'sectors': sectors,
            'stats': stats,
            'search_query': search_query,
            'sort_by': sort_by,
            'sector_filter': sector_filter,
            'margin_trading_available': MARGIN_TRADING_AVAILABLE,
        })
        
        return context


class ServeImageView(LoginRequiredMixin, View):
    """ユーザー認証付きの画像配信ビュー"""
    
    def get(self, request, diary_id, image_type, note_id=None):
        try:
            diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
            
            if image_type == 'diary':
                if not diary.image:
                    raise Http404("画像が見つかりません")
                image_field = diary.image
                
            elif image_type == 'note':
                if not note_id:
                    raise Http404("ノートIDが指定されていません")
                note = get_object_or_404(DiaryNote, id=note_id, diary=diary)
                if not note.image:
                    raise Http404("画像が見つかりません")
                image_field = note.image
            else:
                raise Http404("無効な画像タイプです")
            
            is_thumbnail = request.GET.get('thumbnail') == '1'
            if is_thumbnail:
                return self._serve_thumbnail(image_field, request)
            
            return self._serve_image(image_field)
            
        except Exception as e:
            print(f"Image serving error: {str(e)}")
            raise Http404("画像の配信中にエラーが発生しました")
    
    def _serve_image(self, image_field):
        """通常の画像を配信"""
        try:
            image_file = image_field.open('rb')
            file_path = image_field.name
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = 'image/jpeg'
            
            response = HttpResponse(image_file.read(), content_type=content_type)
            response['Cache-Control'] = 'private, max-age=3600'
            
            filename = os.path.basename(file_path)
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            
            image_file.close()
            return response
            
        except Exception as e:
            print(f"Error serving image: {str(e)}")
            raise Http404("画像ファイルが見つかりません")
    
    def _serve_thumbnail(self, image_field, request):
        """サムネイル画像を生成して配信"""
        try:
            width = int(request.GET.get('w', 300))
            height = int(request.GET.get('h', 200))
            
            width = min(max(width, 50), 800)
            height = min(max(height, 50), 600)
            
            image_file = image_field.open('rb')
            img = Image.open(image_file)
            
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            img_ratio = img.width / img.height
            thumb_ratio = width / height
            
            if img_ratio > thumb_ratio:
                new_height = height
                new_width = int(height * img_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                left = (new_width - width) // 2
                img = img.crop((left, 0, left + width, height))
            else:
                new_width = width
                new_height = int(width / img_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                top = (new_height - height) // 2
                img = img.crop((0, top, width, top + height))
            
            output = io.BytesIO()
            
            try:
                img.save(output, format='WebP', quality=80, optimize=True)
                content_type = 'image/webp'
            except Exception:
                img.save(output, format='JPEG', quality=80, optimize=True)
                content_type = 'image/jpeg'
            
            output.seek(0)
            
            response = HttpResponse(output.getvalue(), content_type=content_type)
            response['Cache-Control'] = 'private, max-age=7200'
            
            image_file.close()
            return response
            
        except Exception as e:
            print(f"Error creating thumbnail: {str(e)}")
            return self._serve_image(image_field)


# ==========================================
# ファンクションベースビュー
# ==========================================

def diary_list(request):
    """日記リストを表示するビュー"""
    is_htmx = request.headers.get('HX-Request') == 'true' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if not is_htmx:
        return redirect(f'/stockdiary/?{request.GET.urlencode()}')
    
    try:
        queryset = StockDiary.objects.filter(user=request.user).order_by('-updated_at')
        queryset = queryset.select_related('user').prefetch_related('tags', 'notes')
        
        query = request.GET.get('query', '')
        tag_id = request.GET.get('tag', '')
        sector = request.GET.get('sector', '')
        status = request.GET.get('status', '')
                
        current_params = request.GET.copy()
        current_params.pop('page', None)

        if query:
            queryset = queryset.filter(
                Q(stock_name__icontains=query) | 
                Q(stock_symbol__icontains=query) |
                Q(reason__icontains=query) |
                Q(memo__icontains=query)
            )
        
        if tag_id:
            queryset = queryset.filter(tags__id=tag_id)
            
        if sector:
            queryset = queryset.filter(sector=sector)
        
            
        paginator = Paginator(queryset, 10)
        page = request.GET.get('page', 1)
        
        try:
            diaries = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            diaries = paginator.page(1)
        
        tags = Tag.objects.filter(user=request.user)
        
        context = {
            'diaries': diaries,
            'page_obj': diaries,
            'tags': tags,
            'request': request,
            'current_params': current_params,
        }
        
        if sector and not query and not status and not tag_id:
            return render(request, 'stockdiary/partials/diary_list_sector.html', context)
        elif tag_id and not query and not status and not sector:
            return render(request, 'stockdiary/partials/diary_list_simple.html', context)
        else:
            return render(request, 'stockdiary/partials/diary_list.html', context)
    
    except Exception as e:
        print(f"Diary list error: {str(e)}")
        traceback.print_exc()
        
        return HttpResponse(
            f'<div class="alert alert-danger">日記リストの読み込みに失敗しました: {str(e)}</div>',
            status=500
        )


def tab_content(request, diary_id, tab_type):
    """日記カードのタブコンテンツを表示するビュー"""
    try:
        try:
            diary = StockDiary.objects.get(id=diary_id, user=request.user)
        except StockDiary.DoesNotExist:
            return HttpResponse(
                '<div class="alert alert-warning">指定された日記が見つかりません。</div>', 
                status=404
            )

        context = {
            'diary': diary,
            'is_detail_view': True,
        }
        
        try:
            if tab_type == 'notes':
                notes = diary.notes.all().order_by('-date')[:3]
                context['notes'] = notes
                template_name = 'stockdiary/partials/tab_notes.html'
            
            elif tab_type == 'analysis':
                template_groups = []
                analysis_values = DiaryAnalysisValue.objects.filter(diary=diary).select_related('analysis_item__template')
                
                templates_map = defaultdict(list)
                for value in analysis_values:
                    if hasattr(value.analysis_item, 'template') and value.analysis_item.template:
                        templates_map[value.analysis_item.template.id].append(value)
                
                for template_id, values in templates_map.items():
                    if values:
                        template = values[0].analysis_item.template
                        template_groups.append({
                            'template': template,
                            'values': values[:3]
                        })
                
                context['template_groups'] = template_groups
                template_name = 'stockdiary/partials/tab_analysis.html'
                        
            elif tab_type == 'margin':
                margin_data, latest_margin_data = get_margin_data(diary.stock_symbol, limit=10)
                context['margin_data'] = margin_data
                context['latest_margin_data'] = latest_margin_data
                template_name = 'stockdiary/partials/tab_margin.html'
            
            else:
                return HttpResponse(
                    '<div class="alert alert-warning">無効なタブタイプです。</div>', 
                    status=400
                )

            return render(request, template_name, context)

        except Exception as render_error:
            print(f"タブレンダリングエラー: {str(render_error)}")
            traceback.print_exc()
            return HttpResponse(
                f'<div class="alert alert-danger">タブコンテンツの読み込み中にエラーが発生しました: {str(render_error)}</div>', 
                status=500
            )

    except Exception as e:
        print(f"想定外のエラー: {str(e)}")
        traceback.print_exc()
        return HttpResponse(
            '<div class="alert alert-danger">予期せぬエラーが発生しました。</div>', 
            status=500
        )


def calendar_view(request):
    """カレンダー全体ビュー"""
    today = timezone.now().date()
    month = today.month
    year = today.year
    
    user_diaries = StockDiary.objects.filter(user=request.user)
    
    return render(request, 'stockdiary/calendar.html', {
        'today': today,
        'month': month,
        'year': year,
        'diaries': user_diaries
    })


@login_required
@require_GET
def search_suggestion(request):
    """検索キーワードに基づいて提案を返す"""
    query = request.GET.get('query', '').strip()
    
    if len(query) < 2:
        return HttpResponse('')
    
    stock_matches = StockDiary.objects.filter(
        user=request.user
    ).filter(
        Q(stock_name__icontains=query) | 
        Q(stock_symbol__icontains=query)
    ).distinct().values('stock_name', 'stock_symbol')[:5]
    
    tag_matches = Tag.objects.filter(
        user=request.user, 
        name__icontains=query
    ).values('id', 'name')[:3]
    
    if not stock_matches and not tag_matches:
        return HttpResponse('')
    
    html = '<div class="search-suggestions mt-2">'
    
    if stock_matches:
        html += '<div class="search-suggestion-title"><small>銘柄:</small></div>'
        html += '<div class="search-suggestion-items">'
        for match in stock_matches:
            html += f'<div class="search-suggestion-item" hx-get="/stockdiary/diary-list/?query={match["stock_name"]}" hx-target="#diary-container" hx-push-url="true">'
            html += f'<i class="bi bi-building me-1"></i> {match["stock_name"]} ({match["stock_symbol"]})'
            html += '</div>'
        html += '</div>'
    
    if tag_matches:
        html += '<div class="search-suggestion-title"><small>タグ:</small></div>'
        html += '<div class="search-suggestion-items">'
        for match in tag_matches:
            html += f'<div class="search-suggestion-item" hx-get="/stockdiary/diary-list/?tag={match["id"]}" hx-target="#diary-container" hx-push-url="true">'
            html += f'<i class="bi bi-tag me-1"></i> {match["name"]}'
            html += '</div>'
        html += '</div>'
    
    html += '</div>'
    
    return HttpResponse(html)


@login_required
@require_GET
def context_actions(request, pk):
    """特定の日記に対するコンテキストアクション"""
    try:
        diary = StockDiary.objects.get(id=pk, user=request.user)
    except StockDiary.DoesNotExist:
        return JsonResponse({'error': '日記が見つかりません'}, status=404)
        
    html = render_to_string('stockdiary/partials/context_actions.html', context)
    return HttpResponse(html)


def csrf_failure_view(request, reason=""):
    """CSRF失敗時のカスタムハンドラー"""
    if (hasattr(request, 'user') and 
        request.user.is_authenticated and 
        request.user.username in getattr(settings, 'TEST_ACCOUNT_SETTINGS', {}).get('USERNAMES', [])):
        
        messages.warning(
            request, 
            "テストアカウントの同時利用により一時的なエラーが発生しました。"
            "ページを更新するか、別のテストアカウント（test1, test2, demo1等）をお試しください。"
        )
        return redirect('stockdiary:home')
    
    return render(request, 'errors/csrf_failure.html', {
        'reason': reason,
        'test_accounts': settings.TEST_ACCOUNT_SETTINGS.get('USERNAMES', [])
    }, status=403)


# ==========================================
# 信用倍率API
# ==========================================

@login_required
def api_margin_chart_data(request, diary_id):
    """信用倍率チャートデータAPI"""
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        
        if not diary.stock_symbol:
            return JsonResponse({'error': '証券コードが設定されていません'}, status=400)
        
        period = request.GET.get('period', '3')
        
        market_issue = get_market_issue(diary.stock_symbol)
        if not market_issue:
            return JsonResponse({'error': '銘柄が見つかりません'}, status=404)
        
        queryset = MarginTradingData.objects.filter(issue=market_issue).order_by('-date')
        
        if period == '3':
            queryset = queryset[:12]
        elif period == '6':
            queryset = queryset[:24]
        
        data = list(queryset.values(
            'date', 'outstanding_sales', 'outstanding_purchases',
            'outstanding_sales_change', 'outstanding_purchases_change'
        ))
        
        data.reverse()
        
        chart_data = {
            'labels': [d['date'].strftime('%m/%d') for d in data],
            'datasets': [
                {
                    'label': '信用倍率',
                    'data': [
                        calculate_margin_ratio(d['outstanding_purchases'], d['outstanding_sales'])
                        for d in data
                    ],
                    'borderColor': 'rgb(75, 192, 192)',
                    'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                    'tension': 0.4,
                    'yAxisID': 'y'
                },
                {
                    'label': '売残高',
                    'data': [d['outstanding_sales'] for d in data],
                    'borderColor': 'rgb(255, 99, 132)',
                    'backgroundColor': 'rgba(255, 99, 132, 0.1)',
                    'tension': 0.4,
                    'yAxisID': 'y1',
                    'hidden': True
                },
                {
                    'label': '買残高',
                    'data': [d['outstanding_purchases'] for d in data],
                    'borderColor': 'rgb(54, 162, 235)',
                    'backgroundColor': 'rgba(54, 162, 235, 0.1)',
                    'tension': 0.4,
                    'yAxisID': 'y1',
                    'hidden': True
                }
            ]
        }
        
        ratios = [
            calculate_margin_ratio(d['outstanding_purchases'], d['outstanding_sales'])
            for d in data
        ]
        
        stats = {
            'average': round(statistics.mean(ratios) if ratios else 0, 2),
            'volatility': round(statistics.stdev(ratios) if len(ratios) > 1 else 0, 2),
            'min': round(min(ratios) if ratios else 0, 2),
            'max': round(max(ratios) if ratios else 0, 2),
            'current': round(ratios[-1] if ratios else 0, 2)
        }
        
        alerts = []
        if ratios:
            current_ratio = ratios[-1]
            avg_ratio = stats['average']
            
            if len(ratios) > 3:
                std_dev = stats['volatility']
                if abs(current_ratio - avg_ratio) > 3 * std_dev:
                    alerts.append({
                        'type': 'warning',
                        'message': f'現在の信用倍率({current_ratio:.2f})が過去平均から大きく乖離しています'
                    })
            
            if current_ratio > 5:
                alerts.append({
                    'type': 'info',
                    'message': '信用倍率が5倍を超えています。過度な買い偏重にご注意ください'
                })
            elif current_ratio < 0.2:
                alerts.append({
                    'type': 'warning',
                    'message': '信用倍率が0.2倍を下回っています。売り圧力が非常に強い状況です'
                })
        
        return JsonResponse({
            'chart_data': chart_data,
            'stats': stats,
            'alerts': alerts,
            'data_count': len(data)
        })
        
    except Exception as e:
        print(f"Chart data API error: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required 
def api_margin_compare_data(request, diary_id):
    """銘柄比較データAPI"""
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        symbols = request.GET.get('symbols', '').split(',')
        symbols = [s.strip() for s in symbols if s.strip()]
        
        if not symbols:
            return JsonResponse({'error': '比較銘柄が指定されていません'}, status=400)
        
        symbols = symbols[:4]
        
        compare_data = []
        chart_datasets = []
        colors = [
            'rgb(255, 99, 132)',
            'rgb(54, 162, 235)',
            'rgb(75, 192, 192)',
            'rgb(255, 205, 86)'
        ]
        
        labels = None
        max_data_length = 0
        
        for i, symbol in enumerate(symbols):
            market_issue = get_market_issue(symbol)
            
            if not market_issue:
                continue
                
            margin_data = MarginTradingData.objects.filter(
                issue=market_issue
            ).order_by('-date')[:12]
            
            if not margin_data.exists():
                continue
            
            data_list = list(margin_data.values(
                'date', 'outstanding_sales', 'outstanding_purchases',
                'outstanding_sales_change', 'outstanding_purchases_change'
            ))
            data_list.reverse()
            
            if labels is None:
                labels = [d['date'].strftime('%m/%d') for d in data_list]
                max_data_length = len(data_list)
            
            ratios = [
                calculate_margin_ratio(d['outstanding_purchases'], d['outstanding_sales'])
                for d in data_list
            ]
            
            while len(ratios) < max_data_length:
                ratios.insert(0, None)
            
            chart_datasets.append({
                'label': f'{market_issue.name} ({symbol})',
                'data': ratios,
                'borderColor': colors[i % len(colors)],
                'backgroundColor': colors[i % len(colors)].replace('rgb', 'rgba').replace(')', ', 0.1)'),
                'fill': False,
                'tension': 0.3,
                'pointRadius': 3,
                'pointHoverRadius': 5,
                'borderWidth': 2
            })
            
            valid_ratios = [r for r in ratios if r is not None]
            latest_data = data_list[-1] if data_list else None
            
            compare_data.append({
                'symbol': symbol,
                'name': market_issue.name,
                'current_ratio': valid_ratios[-1] if valid_ratios else 0,
                'average_ratio': round(statistics.mean(valid_ratios) if valid_ratios else 0, 2),
                'volatility': round(statistics.stdev(valid_ratios) if len(valid_ratios) > 1 else 0, 2),
                'min_ratio': round(min(valid_ratios) if valid_ratios else 0, 2),
                'max_ratio': round(max(valid_ratios) if valid_ratios else 0, 2),
                'latest_date': latest_data['date'].strftime('%Y-%m-%d') if latest_data else None,
                'outstanding_sales': latest_data['outstanding_sales'] if latest_data else 0,
                'outstanding_purchases': latest_data['outstanding_purchases'] if latest_data else 0,
                'sales_change': latest_data['outstanding_sales_change'] if latest_data else 0,
                'purchases_change': latest_data['outstanding_purchases_change'] if latest_data else 0
            })
        
        if not chart_datasets:
            return JsonResponse({'error': '比較可能なデータが見つかりませんでした'}, status=404)
        
        chart_data = {
            'labels': labels or [],
            'datasets': chart_datasets
        }
        
        return JsonResponse({
            'chart_data': chart_data,
            'compare_data': compare_data,
            'data_count': len(compare_data)
        })
        
    except Exception as e:
        print(f"Compare data API error: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_margin_sector_suggestions(request, diary_id):
    """業種別銘柄候補API"""
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        
        if not diary.stock_symbol:
            return JsonResponse({'suggestions': []})
        
        company = CompanyMaster.objects.filter(code=diary.stock_symbol).first()
        if not company:
            return JsonResponse({'suggestions': []})
        
        sector = company.industry_name_33 or company.industry_name_17
        scale = company.scale_code
        
        if not sector:
            return JsonResponse({'suggestions': []})
        
        if company.industry_name_33:
            sector_companies = CompanyMaster.objects.filter(
                industry_name_33=sector,
                scale_code=scale
            ).exclude(code=diary.stock_symbol)
        else:
            sector_companies = CompanyMaster.objects.filter(
                industry_name_17=sector,
                scale_code=scale
            ).exclude(code=diary.stock_symbol)
        
        suggestions = []
        
        for comp in sector_companies:
            market_issue = get_market_issue(comp.code)
            
            if not market_issue:
                continue
            
            latest_data = MarginTradingData.objects.filter(
                issue=market_issue
            ).order_by('-date').first()
            
            if latest_data and latest_data.outstanding_sales > 0:
                ratio = calculate_margin_ratio(
                    latest_data.outstanding_purchases,
                    latest_data.outstanding_sales
                )
                
                suggestions.append({
                    'symbol': comp.code,
                    'name': comp.name,
                    'ratio': ratio,
                    'market': comp.market or '東証',
                    'scale': comp.scale_name or '不明',
                    'last_update': latest_data.date.strftime('%m/%d'),
                    'outstanding_sales': latest_data.outstanding_sales,
                    'outstanding_purchases': latest_data.outstanding_purchases
                })
        
        suggestions.sort(key=lambda x: x['ratio'], reverse=True)
        
        return JsonResponse({
            'sector': sector,
            'suggestions': suggestions[:8],
            'total_companies': len(suggestions)
        })
        
    except Exception as e:
        print(f"Sector suggestions API error: {traceback.format_exc()}")
        return JsonResponse({'suggestions': []})


@login_required
def api_margin_sector_data(request, diary_id):
    """業種分析データAPI"""
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        
        if not diary.stock_symbol:
            return JsonResponse({'error': '証券コードが設定されていません'}, status=400)
        
        company = CompanyMaster.objects.filter(code=diary.stock_symbol).first()
        if not company or not company.industry_name_33:
            return JsonResponse({
                'error': '業種情報が見つかりません',
                'suggestions': []
            })
        
        sector_name = company.industry_name_33
        
        sector_companies = CompanyMaster.objects.filter(
            industry_name_33=sector_name
        ).exclude(code=diary.stock_symbol)[:10]
        
        suggestions = []
        sector_ratios = []
        
        for comp in sector_companies:
            market_issue = get_market_issue(comp.code)
            if not market_issue:
                continue
                
            latest_data = MarginTradingData.objects.filter(
                issue=market_issue
            ).order_by('-date').first()
            
            if latest_data and latest_data.outstanding_sales > 0:
                ratio = calculate_margin_ratio(
                    latest_data.outstanding_purchases,
                    latest_data.outstanding_sales
                )
                sector_ratios.append(ratio)
                
                suggestions.append({
                    'symbol': comp.code,
                    'name': comp.name,
                    'ratio': ratio,
                    'scale': comp.scale_name or '不明',
                    'last_update': latest_data.date.strftime('%Y-%m-%d')
                })
        
        sector_stats = {}
        if sector_ratios:
            sector_stats = {
                'sector_name': sector_name,
                'average_ratio': round(statistics.mean(sector_ratios), 2),
                'median_ratio': round(statistics.median(sector_ratios), 2),
                'company_count': len(sector_ratios),
                'min_ratio': round(min(sector_ratios), 2),
                'max_ratio': round(max(sector_ratios), 2)
            }
            
            current_issue = get_market_issue(diary.stock_symbol)
            if current_issue:
                current_data = MarginTradingData.objects.filter(
                    issue=current_issue
                ).order_by('-date').first()
                
                if current_data and current_data.outstanding_sales > 0:
                    current_ratio = calculate_margin_ratio(
                        current_data.outstanding_purchases,
                        current_data.outstanding_sales
                    )
                    higher_count = sum(1 for r in sector_ratios if r > current_ratio)
                    sector_stats['current_ranking'] = higher_count + 1
                    sector_stats['current_ratio'] = current_ratio
        
        suggestions.sort(key=lambda x: x['ratio'], reverse=True)
        
        return JsonResponse({
            'sector_stats': sector_stats,
            'suggestions': suggestions[:5]
        })
        
    except Exception as e:
        print(f"Sector data API error: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_stock_diaries(request, symbol):
    """特定の銘柄の日記一覧をJSON形式で返すAPI"""
    try:
        diaries = StockDiary.objects.filter(
            user=request.user,
            stock_symbol=symbol
        ).order_by('-created_at')
        
        diary_data = []
        for diary in diaries:
            tags = [tag.name for tag in diary.tags.all()]
            
            diary_data.append({
                'id': diary.id,
                'initial_purchase_date': diary.purchase_date.strftime('%Y年%m月%d日'),
                'reason': diary.reason,
                'memo': diary.memo,
                'is_memo': diary.is_memo,
                'tags': tags,
                'created_at': diary.created_at.strftime('%Y年%m月%d日'),
            })
        
        return JsonResponse({
            'diaries': diary_data,
            'count': len(diary_data),
            'stock_symbol': symbol,
            'success': True
        })
        
    except Exception as e:
        print(f"Stock diaries API error: {traceback.format_exc()}")
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)

@login_required
@require_http_methods(["POST"])
def add_transaction(request, diary_id):
    """取引を追加"""
    diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
    
    form = TransactionForm(request.POST, diary=diary)
    
    # バリデーション前に diary を設定（重要！）
    if not form.instance.pk:
        form.instance.diary = diary
    
    if form.is_valid():
        transaction = form.save(commit=False)
        transaction.diary = diary
        
        try:
            transaction.save()  # saveメソッド内でupdate_aggregates()が呼ばれる
            
            # 取引後の状態を記録
            transaction.quantity_after = diary.current_quantity
            transaction.average_price_after = diary.average_purchase_price
            transaction.save(update_fields=['quantity_after', 'average_price_after'])
            
            messages.success(
                request, 
                f'{transaction.get_transaction_type_display()}取引を記録しました'
            )
        except Exception as e:
            messages.error(request, f'取引の記録中にエラーが発生しました: {str(e)}')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
    
    return redirect('stockdiary:detail', pk=diary_id)


@login_required
@require_http_methods(["POST"])
def update_transaction(request, transaction_id):
    """取引を更新"""
    transaction = get_object_or_404(
        Transaction, 
        id=transaction_id, 
        diary__user=request.user
    )
    
    # diaryを取得
    diary = transaction.diary
    
    form = TransactionForm(request.POST, instance=transaction, diary=diary)
    
    # 既存のインスタンスには既に diary が設定されているはずだが、念のため
    if form.instance.diary_id is None:
        form.instance.diary = diary
    
    if form.is_valid():
        try:
            transaction = form.save()
            
            # 取引後の状態を更新
            diary = transaction.diary
            transaction.quantity_after = diary.current_quantity
            transaction.average_price_after = diary.average_purchase_price
            transaction.save(update_fields=['quantity_after', 'average_price_after'])
            
            messages.success(request, '取引を更新しました')
        except Exception as e:
            messages.error(request, f'取引の更新中にエラーが発生しました: {str(e)}')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
    
    return redirect('stockdiary:detail', pk=transaction.diary.id)


@login_required
@require_http_methods(["POST"])
def delete_transaction(request, transaction_id):
    """取引を削除"""
    transaction = get_object_or_404(
        Transaction, 
        id=transaction_id, 
        diary__user=request.user
    )
    
    diary_id = transaction.diary.id
    transaction_date = transaction.transaction_date
    transaction_type = transaction.get_transaction_type_display()
    
    try:
        transaction.delete()  # deleteメソッド内でupdate_aggregates()が呼ばれる
        messages.success(
            request, 
            f'{transaction_date.strftime("%Y年%m月%d日")}の{transaction_type}取引を削除しました'
        )
    except Exception as e:
        messages.error(request, f'取引の削除中にエラーが発生しました: {str(e)}')
    
    return redirect('stockdiary:detail', pk=diary_id)


@login_required
@require_http_methods(["GET"])
def get_transaction(request, transaction_id):
    """取引データを取得（AJAX用）"""
    transaction = get_object_or_404(
        Transaction, 
        id=transaction_id, 
        diary__user=request.user
    )
    
    return JsonResponse({
        'id': transaction.id,
        'transaction_type': transaction.transaction_type,
        'transaction_date': transaction.transaction_date.strftime('%Y-%m-%d'),
        'price': str(transaction.price),
        'quantity': str(transaction.quantity),
        'memo': transaction.memo or ''
    })

# ==========================================
# 株式分割管理ビュー
# ==========================================

@login_required
@require_http_methods(["POST"])
def add_stock_split(request, diary_id):
    """株式分割を追加"""
    diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
    
    form = StockSplitForm(request.POST)
    
    if form.is_valid():
        split = form.save(commit=False)
        split.diary = diary
        
        try:
            split.save()
            messages.success(
                request, 
                f'株式分割情報を追加しました（{split.split_date} / {split.split_ratio}倍）'
            )
            messages.info(
                request,
                '取引履歴で「適用」ボタンをクリックすると、過去の取引が自動調整されます'
            )
        except Exception as e:
            messages.error(request, f'株式分割の追加中にエラーが発生しました: {str(e)}')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
    
    return redirect('stockdiary:detail', pk=diary_id)


@login_required
@require_http_methods(["POST"])
def apply_stock_split(request, split_id):
    """株式分割を適用"""
    split = get_object_or_404(
        StockSplit, 
        id=split_id, 
        diary__user=request.user
    )
    
    if split.is_applied:
        messages.warning(request, 'この株式分割はすでに適用済みです')
        return redirect('stockdiary:detail', pk=split.diary.id)
    
    try:
        split.apply_split()
        messages.success(
            request,
            f'株式分割を適用しました（{split.split_date} / {split.split_ratio}倍）'
        )
        messages.info(
            request,
            f'{split.split_date}以前の取引データが自動調整されました'
        )
    except Exception as e:
        messages.error(request, f'株式分割の適用中にエラーが発生しました: {str(e)}')
    
    return redirect('stockdiary:detail', pk=split.diary.id)


@login_required
@require_http_methods(["POST"])
def delete_stock_split(request, split_id):
    """株式分割を削除"""
    split = get_object_or_404(
        StockSplit, 
        id=split_id, 
        diary__user=request.user
    )
    
    if split.is_applied:
        messages.error(request, '適用済みの株式分割は削除できません')
        return redirect('stockdiary:detail', pk=split.diary.id)
    
    diary_id = split.diary.id
    split_date = split.split_date
    split_ratio = split.split_ratio
    
    try:
        split.delete()
        messages.success(
            request,
            f'株式分割情報を削除しました（{split_date} / {split_ratio}倍）'
        )
    except Exception as e:
        messages.error(request, f'株式分割の削除中にエラーが発生しました: {str(e)}')
    
    return redirect('stockdiary:detail', pk=diary_id)