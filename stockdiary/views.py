from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.urls import reverse_lazy
from django.db.models import Q, Count, Avg, F, Sum, Min, Max, Case, When, Value, IntegerField
from django.db.models.functions import TruncMonth, ExtractWeekDay, Length
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.template.defaultfilters import truncatechars_html
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required

from django.views.decorators.http import require_GET
from utils.mixins import ObjectNotFoundRedirectMixin
from .utils import process_analysis_values, calculate_analysis_completion_rate
from decimal import Decimal, InvalidOperation
from django.core.paginator import EmptyPage, PageNotAnInteger
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import StockDiary, DiaryNote
from .forms import StockDiaryForm, DiaryNoteForm
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from company_master.models import CompanyMaster
from tags.models import Tag

import statistics
try:
    from margin_trading.models import MarginTradingData, MarketIssue
    MARGIN_TRADING_AVAILABLE = True
except ImportError:
    MARGIN_TRADING_AVAILABLE = False
    # ログに警告を出力
    import logging
    logging.getLogger(__name__).warning(
        "margin_trading アプリが見つかりません。信用倍率機能は無効になります。"
    )
    
from collections import Counter, defaultdict
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponse, Http404
from datetime import datetime, timedelta
import calendar

import mimetypes
from PIL import Image
import os
import io

import traceback

from django.template import engines, Context
from stockdiary.templatetags.stockdiary_filters import mul_filter, sub_filter, div_filter
import html
import json
import re
from django.conf import settings

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

class StockDiaryListView(LoginRequiredMixin, ListView):
    model = StockDiary
    template_name = 'stockdiary/home.html'
    context_object_name = 'diaries'
    paginate_by = 4
    
    def get_queryset(self):
        queryset = StockDiary.objects.filter(user=self.request.user).order_by('-updated_at', '-purchase_date')
        queryset = queryset.select_related('user').prefetch_related('tags', 'notes')
        
        # 検索フィルター
        query = self.request.GET.get('query', '')
        tag_id = self.request.GET.get('tag', '')
        status = self.request.GET.get('status', '')  # 新しいステータスフィルター
        
        if query:
            # 全文検索に拡張 - 銘柄名、シンボル、理由、メモを対象に
            queryset = queryset.filter(
                Q(stock_name__icontains=query) | 
                Q(stock_symbol__icontains=query) |
                Q(reason__icontains=query) |
                Q(memo__icontains=query)
            )

        # 日付範囲フィルター
        date_range = self.request.GET.get('date_range', '')
        if date_range:
            from datetime import timedelta
            today = timezone.now().date()
            
            if date_range == '1w':
                start_date = today - timedelta(days=7)
            elif date_range == '1m':
                start_date = today - timedelta(days=30)
            elif date_range == '3m':
                start_date = today - timedelta(days=90)
            elif date_range == '6m':
                start_date = today - timedelta(days=180)
            elif date_range == '1y':
                start_date = today - timedelta(days=365)
            else:
                start_date = None
                
            if start_date:
                queryset = queryset.filter(purchase_date__gte=start_date)
                        
        if tag_id:
            queryset = queryset.filter(tags__id=tag_id)
        
        # 保有状態によるフィルタリング
        if status == 'active':
            # 保有中（売却日がNullで、メモでない）
            queryset = queryset.filter(
                sell_date__isnull=True,
                purchase_price__isnull=False,
                purchase_quantity__isnull=False
            )
        elif status == 'sold':
            # 売却済み
            queryset = queryset.filter(sell_date__isnull=False)
        elif status == 'memo':
            # メモのみ（購入価格または数量がNullまたはis_memoがTrue）
            queryset = queryset.filter(
                Q(purchase_price__isnull=True) | 
                Q(purchase_quantity__isnull=True) | 
                Q(is_memo=True)
            )
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tags'] = Tag.objects.filter(user=self.request.user)
        
        # カレンダー表示用にすべての日記データを追加（不要なフィールドを除外）
        diaries_query = StockDiary.objects.filter(user=self.request.user)
        context['all_diaries'] = diaries_query.defer(
            'reason', 'memo', 'created_at', 'updated_at',
        )
        
        # 保有中の株式を取得
        active_holdings = StockDiary.objects.filter(
            user=self.request.user, 
            sell_date__isnull=True,
            purchase_price__isnull=False,
            purchase_quantity__isnull=False
        )
        context['active_holdings_count'] = active_holdings.count()
        
        # 実現損益の計算（売却済みの株式）
        sold_stocks = StockDiary.objects.filter(
            user=self.request.user, 
            sell_date__isnull=False,
            purchase_price__isnull=False,
            purchase_quantity__isnull=False
        )
        realized_profit = 0
        for stock in sold_stocks:
            if stock.sell_price is not None and stock.purchase_price is not None and stock.purchase_quantity is not None:
                profit = (stock.sell_price - stock.purchase_price) * stock.purchase_quantity
            else:
                profit = 0
            realized_profit += profit
        
        context['realized_profit'] = realized_profit
            
        # メモと取引記録を分ける
        memo_entries = [d for d in context['diaries'] if d.is_memo or d.purchase_price is None or d.purchase_quantity is None]
        transaction_entries = [d for d in context['diaries'] if not d.is_memo and d.purchase_price is not None and d.purchase_quantity is not None]
        
        context['memo_entries'] = memo_entries
        context['transaction_entries'] = transaction_entries
        
        # 実際の取引のみをカウント
        context['active_holdings_count'] = len([d for d in transaction_entries if d.sell_date is None])
        
        context['current_query'] = self.request.GET.urlencode()
    
        # フォーム用のスピードダイアルアクション
        context['form_actions'] = [
            {
                'type': 'add',
                'url': reverse_lazy('stockdiary:create'),
                'icon': 'bi-plus-lg',
                'label': '詳細作成',  # ラベルを変更して区別する
                'aria_label': '詳細作成' 
            },
            # ここにクイック作成ボタンを追加
            {
                'type': 'quick-add',
                'url': '#',  # モーダルを表示するだけなのでURLは不要
                'icon': 'bi-lightning',
                'label': 'クイック作成',
                'aria_label': 'クイック作成',
                'onclick': 'window.quickDiaryForm.show(); return false;'  # クリック時にモーダルを表示
            },
            {
                'type': 'template',
                'url': reverse_lazy('analysis_template:list'),
                'icon': 'bi-clipboard-data',
                'label': 'テンプレート',
                'aria_label': 'テンプレート' ,
            },
            {
                'type': 'tag',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-tags',
                'label': 'タグ管理',
                'aria_label': 'タグ管理' 
            },
            {
                'type': 'snap',
                'url': reverse_lazy('portfolio:list'),
                'icon': 'bi-camera',
                'label': 'スナップショット',
                'aria_label': 'スナップショット' 
            }
        ]
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                # AJAXリクエストの場合
                self.object_list = self.get_queryset()
                page_size = self.get_paginate_by(self.object_list)
                
                if page_size:
                    paginator = self.get_paginator(self.object_list, page_size)
                    page_number = request.GET.get('page', 1)
                    try:
                        page_obj = paginator.get_page(page_number)
                    except (EmptyPage, PageNotAnInteger):
                        page_obj = paginator.get_page(1)
                    
                    # 日記データをJSON形式で返す
                    from django.http import JsonResponse
                    from django.template.loader import render_to_string
                    
                    data = []
                    for diary in page_obj:
                        try:
                            # 各日記エントリの HTML をレンダリング
                            diary_html = render_to_string('stockdiary/partials/diary_card.html', {
                                'diary': diary,
                                'request': request,
                                'forloop': {'counter': 1}  # forloop.counter の代わり
                            })
                            data.append(diary_html)
                        except Exception as e:
                            # 個別のエントリでエラーが発生した場合はスキップして続行
                            print(f"Error rendering diary {diary.id}: {e}")
                            continue
                    
                    return JsonResponse({
                        'html': data,
                        'has_next': page_obj.has_next(),
                        'next_page': page_obj.next_page_number() if page_obj.has_next() else None
                    })
            except Exception as e:
                # エラーが発生した場合はエラーレスポンスを返す
                import traceback
                print(f"AJAX request error: {e}")
                print(traceback.format_exc())
                return JsonResponse({
                    'error': str(e),
                    'message': 'データの読み込み中にエラーが発生しました。'
                }, status=500)
        
        # 通常のリクエストの場合は既存の処理
        return super().get(request, *args, **kwargs)

# stockdiary/views.py の StockDiaryDetailView クラスを修正

class StockDiaryDetailView(ObjectNotFoundRedirectMixin, LoginRequiredMixin, DetailView):
    model = StockDiary
    template_name = 'stockdiary/detail.html'
    context_object_name = 'diary'
    redirect_url = 'stockdiary:home'
    not_found_message = "日記エントリーが見つかりません。削除された可能性があります。"
    
    def get_queryset(self):
        return StockDiary.objects.filter(user=self.request.user).select_related('user').prefetch_related(
            'notes', 'tags', 'checklist', 'analysis_values__analysis_item'
        )    
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # 現在表示中の日記IDをセッションに保存
        request.session['current_diary_id'] = self.object.id
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 継続記録フォームを追加
        context['note_form'] = DiaryNoteForm(initial={'date': timezone.now().date()})
        
        # 継続記録一覧を追加
        context['notes'] = self.object.notes.all().order_by('-date')
        
        # 分析テンプレート情報を取得
        analysis_templates_info = self._get_analysis_templates_info()
        context['analysis_templates_info'] = analysis_templates_info
        
        # === 信用倍率データの取得 ===
        margin_data, latest_margin_data = self._get_margin_trading_data()
        context['margin_data'] = margin_data
        context['latest_margin_data'] = latest_margin_data
        
        # 関連日記（同じ銘柄コードを持つ日記）を取得
        diary = self.object
        # 現在の日記を含むすべての関連日記を取得（日付順）
        all_related_diaries = StockDiary.objects.filter(
            user=self.request.user,
            stock_symbol=diary.stock_symbol
        ).order_by('purchase_date')
        
        # 総数（現在の日記も含む）
        total_count = all_related_diaries.count()
        
        # 現在の日記のインデックスを特定（タイムライン内での位置）
        current_diary_index = None
        for i, related_diary in enumerate(all_related_diaries):
            if related_diary.id == diary.id:
                current_diary_index = i
                break
        
        # 現在の日記の位置情報をコンテキストに追加
        context['current_diary_index'] = current_diary_index
        context['total_related_count'] = total_count
        
        # 現在の日記以外の関連日記をコンテキストに追加
        # ※順序はすでに purchase_date の昇順
        context['related_diaries'] = all_related_diaries.exclude(id=diary.id)
        context['related_diaries_count'] = total_count - 1  # 現在の日記を除く
        
        # 関連日記の全リスト（現在の日記も含む）をタイムライン表示用に追加
        context['timeline_diaries'] = all_related_diaries
        
        context['diary_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'sell',
                'url': reverse_lazy('stockdiary:sell_specific', kwargs={'pk': diary.id}),
                'icon': 'bi-cash-coin',
                'label': '売却',
                'condition': not diary.sell_date  # 未売却の場合のみ表示
            },
            {
                'type': 'cancel-sell',
                'url': reverse_lazy('stockdiary:cancel_sell', kwargs={'pk': diary.id}),
                'icon': 'bi-arrow-counterclockwise',
                'label': '売却取消',
                'condition': diary.sell_date is not None  # 売却済みの場合のみ表示
            },
            {
                'type': 'edit',
                'url': reverse_lazy('stockdiary:update', kwargs={'pk': diary.id}),
                'icon': 'bi-pencil',
                'label': '編集'
            },
            {
                'type': 'delete',
                'url': reverse_lazy('stockdiary:delete', kwargs={'pk': diary.id}),
                'icon': 'bi-trash',
                'label': '削除'
            }
        ]

        return context
    
    def _get_margin_trading_data(self):
        """信用倍率データを取得するメソッド"""
        margin_data = None
        latest_margin_data = None
        
        diary = self.object
        
        if diary.stock_symbol:
            try:
                # 証券コードから銘柄を検索
                market_issue = MarketIssue.objects.filter(
                    code=str(diary.stock_symbol) + '0'
                ).first()
                
                if market_issue:
                    # 直近10週間のデータを取得
                    margin_queryset = MarginTradingData.objects.filter(
                        issue_id=str(market_issue.id)
                    ).order_by('-date')[:10]
                    
                    # 最新データ
                    latest_margin_data = margin_queryset.first() if margin_queryset else None
                    
                    # リストに変換（テンプレートで使いやすくするため）
                    margin_data = list(margin_queryset)
                
            except Exception as e:
                # エラーが発生した場合はログに記録
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"信用倍率データ取得エラー (diary_id: {diary.id}, symbol: {diary.stock_symbol}): {e}")
        
        return margin_data, latest_margin_data
    
    def _get_analysis_templates_info(self):
        """この日記で使用されている分析テンプレート情報を取得"""
        from analysis_template.models import DiaryAnalysisValue
        from collections import defaultdict
        
        diary = self.object
        
        # この日記の分析値を取得
        analysis_values = DiaryAnalysisValue.objects.filter(
            diary=diary
        ).select_related('analysis_item__template').order_by('analysis_item__order')
        
        if not analysis_values.exists():
            return []
        
        # テンプレートごとにグループ化
        templates_data = defaultdict(lambda: {
            'template': None,
            'total_items': 0,
            'completed_items': 0,
            'completion_rate': 0,
            'values': [],
            'items_with_values': []  # 項目と値のペアを保存
        })
        
        for value in analysis_values:
            template = value.analysis_item.template
            template_id = template.id
            
            # テンプレート情報を設定
            if templates_data[template_id]['template'] is None:
                templates_data[template_id]['template'] = template
                templates_data[template_id]['total_items'] = template.items.count()
            
            # 値を追加
            templates_data[template_id]['values'].append(value)
            
            # 項目と値の詳細情報を追加
            item_with_value = {
                'item': value.analysis_item,
                'value': value,
                'display_value': self._get_analysis_display_value(value),
                'is_completed': self._is_analysis_item_completed(value)
            }
            templates_data[template_id]['items_with_values'].append(item_with_value)
            
            # 完了判定
            if item_with_value['is_completed']:
                templates_data[template_id]['completed_items'] += 1
        
        # 完了率を計算
        result = []
        for template_data in templates_data.values():
            if template_data['total_items'] > 0:
                completion_rate = (template_data['completed_items'] / template_data['total_items']) * 100
                template_data['completion_rate'] = round(completion_rate, 1)
            
            result.append(template_data)
        
        # テンプレート名でソート
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
            if analysis_value.number_value is not None:
                return f"{analysis_value.number_value}"
            return "-"
        
        elif item.item_type == 'select':
            return analysis_value.text_value if analysis_value.text_value else "-"
        
        elif item.item_type == 'text':
            return analysis_value.text_value if analysis_value.text_value else "-"
        
        return "-"

    def _is_analysis_item_completed(self, analysis_value):
        """分析項目が完了しているかどうかを判定"""
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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # フォーム用のスピードダイアルアクション
        context['form_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # ユーザーを設定
        form.instance.user = self.request.user
        
        # 親クラスのform_validを呼び出し、レスポンスを取得
        response = super().form_valid(form)
        
        # 画像ファイルの処理
        image_file = form.cleaned_data.get('image')
        if image_file:
            success = self.object.process_and_save_image(image_file)
            if not success:
                messages.warning(self.request, '日記は作成されましたが、画像の処理に失敗しました。')
        
        # 分析テンプレートが選択されていれば、分析値を処理
        analysis_template_id = self.request.POST.get('analysis_template')
        if analysis_template_id:
            process_analysis_values(self.request, self.object, analysis_template_id)
        
        return response

    def get_initial(self):
        initial = super().get_initial()
        
        # URLパラメータから銘柄情報を取得
        symbol = self.request.GET.get('symbol')
        name = self.request.GET.get('name')
        
        if symbol:
            initial['stock_symbol'] = symbol
        if name:
            initial['stock_name'] = name
        
        return initial


class StockDiaryUpdateView(ObjectNotFoundRedirectMixin, LoginRequiredMixin, UpdateView):
    model = StockDiary
    form_class = StockDiaryForm
    template_name = 'stockdiary/diary_form.html'
    redirect_url = 'stockdiary:home'
    not_found_message = "日記エントリーが見つかりません。削除された可能性があります。"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # フォーム用のスピードダイアルアクション
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
        
        # 画像削除チェックボックスがチェックされている場合
        if request.POST.get('clear_image'):
            success = self.object.delete_image()
            if not success:
                messages.warning(request, '画像の削除に失敗しました。')
        
        return super().post(request, *args, **kwargs)
    
    def form_valid(self, form):
        # 親クラスのform_validを呼び出し
        response = super().form_valid(form)
        
        # 新しい画像ファイルの処理
        image_file = form.cleaned_data.get('image')
        if image_file:
            success = self.object.process_and_save_image(image_file)
            if not success:
                messages.warning(self.request, '日記は更新されましたが、画像の処理に失敗しました。')
        
        # 分析テンプレートが選択されていれば、分析値を処理
        analysis_template_id = self.request.POST.get('analysis_template')
        if analysis_template_id:
            # 既存の分析値を削除（テンプレートが変更された場合に対応）
            DiaryAnalysisValue.objects.filter(diary_id=self.object.id).delete()
            
            # 新しい分析値を処理
            process_analysis_values(self.request, self.object, analysis_template_id)
        
        return response
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # 編集時に、この日記で使用されているテンプレートを取得して選択状態にする
        diary = self.get_object()
        diary_analysis_values = DiaryAnalysisValue.objects.filter(diary=diary).select_related('analysis_item__template')
        
        # 使用されているテンプレートを特定
        used_templates = set()
        for value in diary_analysis_values:
            used_templates.add(value.analysis_item.template_id)
        
        # 最初に使用されているテンプレートを取得
        if used_templates:
            template_id = list(used_templates)[0]  # 複数ある場合は最初のものを使用
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


class StockDiarySellView(LoginRequiredMixin, TemplateView):
    """保有株式の売却入力ページ"""
    template_name = 'stockdiary/diary_sell.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 保有中（売却日がNull）の株式を取得
        active_diaries = StockDiary.objects.filter(
            user=self.request.user,
            sell_date__isnull=True
        ).order_by('stock_symbol', 'purchase_date')
        
        # 株数や購入価格がないエントリーを除外
        valid_diaries = active_diaries.filter(
            purchase_price__isnull=False,
            purchase_quantity__isnull=False
        )
            
        # すべての保有銘柄を保持（フィルタリング前）
        context['active_diaries'] = valid_diaries

        # 銘柄コードでグループ化
        grouped_diaries = {}
        has_valid_entries = False  # 有効なエントリーがあるかのフラグ
        
        for diary in valid_diaries:
            symbol = diary.stock_symbol
            if symbol not in grouped_diaries:
                grouped_diaries[symbol] = {
                    'symbol': symbol,
                    'name': diary.stock_name,
                    'entries': []
                }
            
            # 購入の詳細情報を追加
            grouped_diaries[symbol]['entries'].append({
                'id': diary.id,
                'purchase_date': diary.purchase_date,
                'purchase_price': diary.purchase_price,
                'purchase_quantity': diary.purchase_quantity,
                'total_purchase': diary.purchase_price * diary.purchase_quantity
            })
            has_valid_entries = True
        
        context['grouped_diaries'] = grouped_diaries.values()
        context['has_valid_entries'] = has_valid_entries
        
        # 今日の日付を初期値として設定
        context['today'] = timezone.now().date()

        # スピードダイアル用のアクション
        analytics_actions = [
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
        context['page_actions'] = analytics_actions
                
        # 選択された日記ID（更新用）
        diary_id = self.kwargs.get('pk')
        if diary_id:
            try:
                selected_diary = StockDiary.objects.get(
                    id=diary_id,
                    user=self.request.user,
                    sell_date__isnull=True  # 売却済みでないことを確認
                )
                
                # 購入価格と株数が入力されている場合のみ
                if selected_diary.purchase_price is not None and selected_diary.purchase_quantity is not None:
                    context['selected_diary'] = selected_diary
                    
                    # 売却モーダルを自動的に開くためのフラグを追加
                    context['auto_open_modal'] = True
                    
                    # 選択された日記のシンボルを強調表示するためのフラグ
                    context['highlight_symbol'] = selected_diary.stock_symbol
                    
                    # スピードダイアルの「戻る」ボタンのURLを日記詳細ページに変更
                    analytics_actions[0]['url'] = reverse_lazy('stockdiary:detail', kwargs={'pk': diary_id})
                else:
                    messages.error(self.request, '購入価格と株数が設定されていない日記は売却できません')
            except StockDiary.DoesNotExist:
                pass
        
        return context
    
    def post(self, request, *args, **kwargs):
        diary_id = request.POST.get('diary_id')
        sell_date = request.POST.get('sell_date')
        sell_price = request.POST.get('sell_price')
        
        try:
            # Get the diary entry and update selling info
            diary = StockDiary.objects.get(
                id=diary_id,
                user=request.user
            )
            
            # Check if purchase price and quantity are set
            if diary.purchase_price is None or diary.purchase_quantity is None:
                messages.error(request, '購入価格と株数が設定されていない日記は売却できません')
                return redirect('stockdiary:home')
                
            diary.sell_date = sell_date
            diary.sell_price = Decimal(sell_price)
            diary.save()
            
            messages.success(request, f'{diary.stock_name}の売却情報を登録しました')
            
            # Redirect to the detail page
            return redirect('stockdiary:detail', pk=diary.id)
            
        except StockDiary.DoesNotExist:
            messages.error(request, '指定された日記が見つかりません')
        except Exception as e:
            messages.error(request, f'エラーが発生しました: {str(e)}')
        
        # In case of error, redisplay the same page
        return self.get(request, *args, **kwargs)

class AddDiaryNoteView(LoginRequiredMixin, CreateView):
    """日記エントリーへの継続記録追加"""
    model = DiaryNote
    form_class = DiaryNoteForm
    http_method_names = ['post']
    
    def form_valid(self, form):
        diary_id = self.kwargs.get('pk')
        diary = get_object_or_404(StockDiary, id=diary_id, user=self.request.user)
        form.instance.diary = diary
        
        # 親クラスのform_validを呼び出し、オブジェクトを保存
        response = super().form_valid(form)
        
        # 画像ファイルの処理
        image_file = self.request.FILES.get('image')
        if image_file:
            # ファイルサイズのチェック（10MB以下）
            if image_file.size > 10 * 1024 * 1024:
                messages.error(self.request, '画像ファイルのサイズは10MB以下にしてください')
                return self.form_invalid(form)
            
            # ファイル形式のチェック
            valid_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(image_file, 'content_type') and image_file.content_type not in valid_formats:
                messages.error(self.request, 'JPEG、PNG、GIF、WebP形式の画像ファイルのみアップロード可能です')
                return self.form_invalid(form)
            
            # 画像処理・保存
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
            
            # 売却情報をクリア
            diary.sell_date = None
            diary.sell_price = None
            diary.save()
            
            messages.success(request, f'{diary.stock_name}の売却情報を取り消しました')
        except StockDiary.DoesNotExist:
            messages.error(request, '指定された日記が見つかりません')
        
        # 詳細ページにリダイレクト
        return redirect('stockdiary:detail', pk=diary_id)


# 分析関連ビューは別ファイルに分割することをお勧めします
from django.views.generic import TemplateView

class DeleteDiaryNoteView(LoginRequiredMixin, DeleteView):
    """継続記録を削除するビュー"""
    model = DiaryNote
    template_name = 'stockdiary/note_confirm_delete.html'
    
    def get_queryset(self):
        # ユーザーの日記に紐づいたノートのみを取得
        return DiaryNote.objects.filter(diary__user=self.request.user)
    
    def get_success_url(self):
        # 削除後は日記詳細ページにリダイレクト
        diary_pk = self.kwargs.get('diary_pk')
        return reverse_lazy('stockdiary:detail', kwargs={'pk': diary_pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['diary_pk'] = self.kwargs.get('diary_pk')
        return context        

# views.py

from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
class DiaryTabContentView(LoginRequiredMixin, View):
    def get(self, request, diary_id, tab_type):
        try:
            diary = StockDiary.objects.get(id=diary_id, user=request.user)
            
            # 基本データの事前処理（カスタムフィルター不要）
            context = {
                'diary': diary,
                'diary_id': diary.id,
                'purchase_date': diary.purchase_date.strftime('%Y年%m月%d日')
            }
            
            # 数値のフォーマット処理（intcommaフィルターの代わり）
            if diary.purchase_price is not None:
                context['purchase_price'] = f"{float(diary.purchase_price):,.2f}円"
                
            if diary.purchase_quantity is not None:
                context['purchase_quantity'] = diary.purchase_quantity
                
            # 総投資額の計算（mulフィルターの代わり）
            if diary.purchase_price is not None and diary.purchase_quantity is not None:
                total = float(diary.purchase_price) * diary.purchase_quantity
                context['total_investment'] = f"{total:,.2f}円"
                
            # 売却情報
            if diary.sell_date:
                context['sell_date'] = diary.sell_date.strftime('%Y年%m月%d日')
                
                if diary.sell_price is not None:
                    context['sell_price'] = f"{float(diary.sell_price):,.2f}円"
                    
                    # 損益計算
                    if diary.purchase_price is not None and diary.purchase_quantity is not None:
                        profit = float(diary.sell_price - diary.purchase_price) * diary.purchase_quantity
                        context['profit'] = profit
                        context['profit_formatted'] = f"{profit:,.2f}円"
                        
                        # 損益率計算
                        profit_rate = ((float(diary.sell_price) / float(diary.purchase_price)) - 1) * 100
                        context['profit_rate'] = profit_rate
                        context['profit_rate_formatted'] = f"{profit_rate:.2f}%"
            
            # タブタイプに応じたHTMLを生成
            if tab_type == 'notes':
                html = self._render_notes_tab(diary)
            elif tab_type == 'analysis':
                html = self._render_analysis_tab(diary)
            elif tab_type == 'details':
                html = self._render_details_tab(context)
            elif tab_type == 'margin':  # 信用倍率タブを追加
                html = self._render_margin_tab(diary)
            else:
                return JsonResponse({'error': '無効なタブタイプです'}, status=400)
            
            return JsonResponse({'html': html})
            
        except StockDiary.DoesNotExist:
            return JsonResponse({'error': '日記が見つかりません'}, status=404)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Tab content error: {error_details}")
            return JsonResponse({
                'error': str(e),
                'details': error_details
            }, status=500)

    def _render_margin_tab(self, diary):
        """信用倍率タブのHTMLをテンプレートレンダリングで生成（更新版）"""
        
        # margin_trading アプリが利用できない場合
        if not MARGIN_TRADING_AVAILABLE:
            return '''
            <div class="text-center py-4">
            <div class="text-muted">
                <i class="bi bi-exclamation-triangle" style="font-size: 2rem;"></i>
                <h6 class="mt-3">信用倍率機能は利用できません</h6>
                <p class="mb-0 small">margin_trading アプリが設定されていません</p>
            </div>
            </div>
            '''
        
        # 証券コードが設定されていない場合
        if not diary.stock_symbol:
            return '''
            <div class="text-center py-4">
            <div class="text-muted">
                <i class="bi bi-info-circle" style="font-size: 2rem;"></i>
                <h6 class="mt-3">証券コードが設定されていません</h6>
                <p class="mb-0 small">信用倍率データを取得するには証券コードが必要です</p>
            </div>
            </div>
            '''
        
        try:
            # 銘柄とデータを取得
            market_issue, margin_data = self._get_margin_data(diary.stock_symbol)
            
            if not market_issue:
                return f'''
                <div class="text-center py-4">
                <div class="text-muted">
                    <i class="bi bi-search" style="font-size: 2rem;"></i>
                    <h6 class="mt-3">銘柄が見つかりません</h6>
                    <p class="mb-0 small">証券コード: {diary.stock_symbol}</p>
                </div>
                </div>
                '''
            
            if not margin_data.exists():
                return f'''
                <div class="text-center py-4">
                <div class="text-muted">
                    <i class="bi bi-database-x" style="font-size: 2rem;"></i>
                    <h6 class="mt-3">信用取引データがありません</h6>
                    <p class="mb-0 small">証券コード: {diary.stock_symbol}</p>
                    <p class="mb-0 small">この銘柄の信用取引データが見つかりません</p>
                </div>
                </div>
                '''
            
            # テンプレートコンテキストを準備
            context = {
                'diary': diary,
                'margin_data': margin_data,
                'latest_margin_data': margin_data.first(),
                'request': self.request,  # テンプレートでリクエストが必要な場合
            }
            
            # テンプレートをレンダリング
            from django.template.loader import render_to_string
            
            try:
                return render_to_string('stockdiary/partials/tab_margin.html', context)
            except Exception as template_error:
                # テンプレートエラーの場合はフォールバック
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Margin tab template error: {template_error}", exc_info=True)
                
                return f'''
                <div class="text-center py-4">
                <div class="text-muted">
                    <i class="bi bi-exclamation-triangle text-warning" style="font-size: 2rem;"></i>
                    <h6 class="mt-3">テンプレートエラー</h6>
                    <p class="mb-2 small">信用倍率タブの表示中にエラーが発生しました</p>
                    <button class="btn btn-sm btn-outline-primary" onclick="window.location.reload()">
                    <i class="bi bi-arrow-clockwise me-1"></i>再試行
                    </button>
                </div>
                </div>
                '''
            
        except Exception as e:
            # その他のエラー
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Margin tab rendering error (diary_id: {diary.id}): {e}", exc_info=True)
            
            return f'''
            <div class="text-center py-4">
            <div class="text-muted">
                <i class="bi bi-exclamation-triangle text-warning" style="font-size: 2rem;"></i>
                <h6 class="mt-3">データ取得エラー</h6>
                <p class="mb-2 small">信用倍率データの取得中にエラーが発生しました</p>
                <button class="btn btn-sm btn-outline-primary" onclick="window.location.reload()">
                <i class="bi bi-arrow-clockwise me-1"></i>再試行
                </button>
            </div>
            </div>
            '''

    def _get_margin_data(self, stock_symbol):
        """銘柄データと信用倍率データを取得（ヘルパーメソッド）"""
        try:
            market_issue = MarketIssue.objects.filter(
                code=stock_symbol
            ).first()
            
            margin_data = None
            if market_issue:
                margin_data = MarginTradingData.objects.filter(
                    issue=market_issue
                ).order_by('-date')[:20]  # 20週分のデータ
            
            return market_issue, margin_data
        
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting margin data for symbol {stock_symbol}: {e}")
            return None, None
        
    def _render_chart_tab(self, diary, market_issue, margin_data):
        """チャートタブのコンテンツ"""
        latest_data = margin_data.first() if margin_data else None
        
        # 現在の信用倍率計算
        current_ratio = 0
        ratio_class = "text-muted"
        ratio_level = "不明"
        
        if latest_data and latest_data.outstanding_sales > 0:
            current_ratio = latest_data.outstanding_purchases / latest_data.outstanding_sales
            if current_ratio > 2:
                ratio_class = "text-success"
                ratio_level = "買い優勢"
            elif current_ratio > 1:
                ratio_class = "text-primary" 
                ratio_level = "均衡"
            else:
                ratio_class = "text-danger"
                ratio_level = "売り優勢"
        
        return f'''
        <div class="tab-pane fade show active" id="chart-content" role="tabpanel">
        <!-- 現在値サマリー -->
        <div class="chart-summary mb-3">
            <div class="row g-2">
            <div class="col-6 col-md-3">
                <div class="card border-0 bg-light text-center p-2">
                <div class="small text-muted">現在倍率</div>
                <div class="fw-bold {ratio_class} fs-5">{current_ratio:.2f}倍</div>
                <div class="small text-muted">{ratio_level}</div>
                </div>
            </div>
            <div class="col-6 col-md-3">
                <div class="card border-0 bg-light text-center p-2">
                <div class="small text-muted">更新日</div>
                <div class="fw-bold text-primary">{latest_data.date.strftime('%m/%d') if latest_data else '-'}</div>
                <div class="small text-muted">{latest_data.date.strftime('%Y年') if latest_data else ''}</div>
                </div>
            </div>
            <div class="col-6 col-md-3">
                <div class="card border-0 bg-light text-center p-2">
                <div class="small text-muted">売残高</div>
                <div class="fw-bold text-danger">{latest_data.outstanding_sales:,} if latest_data else 0:</div>
                <div class="small text-muted">株</div>
                </div>
            </div>
            <div class="col-6 col-md-3">
                <div class="card border-0 bg-light text-center p-2">
                <div class="small text-muted">買残高</div>
                <div class="fw-bold text-success">{latest_data.outstanding_purchases:,} if latest_data else 0:</div>
                <div class="small text-muted">株</div>
                </div>
            </div>
            </div>
        </div>
        
        <!-- チャート表示エリア -->
        <div class="chart-container mb-3">
            <div class="card border-0 bg-light">
            <div class="card-body p-2 p-sm-3">
                <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="mb-0">信用倍率推移</h6>
                <div class="btn-group btn-group-sm" role="group">
                    <input type="radio" class="btn-check" name="chartPeriod" id="period3m" value="3" checked>
                    <label class="btn btn-outline-primary" for="period3m">3M</label>
                    <input type="radio" class="btn-check" name="chartPeriod" id="period6m" value="6">
                    <label class="btn btn-outline-primary" for="period6m">6M</label>
                    <input type="radio" class="btn-check" name="chartPeriod" id="periodAll" value="all">
                    <label class="btn btn-outline-primary" for="periodAll">All</label>
                </div>
                </div>
                <div class="position-relative">
                <canvas id="marginChart" style="height: 250px;"></canvas>
                <div id="chartLoading" class="position-absolute top-50 start-50 translate-middle d-none">
                    <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
                </div>
            </div>
            </div>
        </div>
        
        <!-- アラート表示 -->
        <div id="marginAlerts"></div>
        
        <!-- 統計情報 -->
        <div class="chart-stats">
            <div class="row g-2">
            <div class="col-6">
                <div class="card border-0 bg-primary bg-opacity-10">
                <div class="card-body p-2 text-center">
                    <div class="small text-muted">過去平均</div>
                    <div class="fw-semibold" id="avgRatio">-</div>
                </div>
                </div>
            </div>
            <div class="col-6">
                <div class="card border-0 bg-info bg-opacity-10">
                <div class="card-body p-2 text-center">
                    <div class="small text-muted">変動率</div>
                    <div class="fw-semibold" id="volatility">-</div>
                </div>
                </div>
            </div>
            </div>
        </div>
        </div>
        '''

    def _render_compare_tab(self, diary, market_issue):
        """比較タブのコンテンツ"""
        return '''
        <div class="tab-pane fade" id="compare-content" role="tabpanel">
        <!-- 銘柄選択 -->
        <div class="compare-selector mb-3">
            <div class="card border-0 bg-light">
            <div class="card-body p-2 p-sm-3">
                <h6 class="mb-2">比較銘柄選択</h6>
                <div class="row g-2">
                <div class="col-12 col-sm-8">
                    <input type="text" class="form-control form-control-sm" 
                        id="compareSymbolInput" placeholder="証券コードを入力（例：7203）">
                </div>
                <div class="col-12 col-sm-4">
                    <button type="button" class="btn btn-primary btn-sm w-100" 
                            id="addCompareBtn">
                    <i class="bi bi-plus-lg"></i> 追加
                    </button>
                </div>
                </div>
                <div class="mt-2">
                <small class="text-muted">同業種推奨:</small>
                <div id="suggestedSymbols" class="mt-1"></div>
                </div>
            </div>
            </div>
        </div>
        
        <!-- 選択済み銘柄 -->
        <div class="selected-symbols mb-3" id="selectedSymbols">
            <!-- 動的に生成 -->
        </div>
        
        <!-- 比較チャート -->
        <div class="compare-chart" id="compareChartContainer" style="display: none;">
            <div class="card border-0 bg-light">
            <div class="card-body p-2 p-sm-3">
                <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="mb-0">銘柄比較</h6>
                <button type="button" class="btn btn-outline-secondary btn-sm" 
                        id="resetCompareBtn">
                    <i class="bi bi-arrow-counterclockwise"></i> リセット
                </button>
                </div>
                <canvas id="compareChart" style="height: 200px;"></canvas>
            </div>
            </div>
        </div>
        
        <!-- 業種統計 -->
        <div class="sector-stats mt-3" id="sectorStats">
            <!-- APIから動的に生成 -->
        </div>
        </div>
        '''

    def _render_data_tab(self, margin_data):
        """データタブのコンテンツ"""
        html = '''
        <div class="tab-pane fade" id="data-content" role="tabpanel">
        <div class="data-table-container">
            <div class="table-responsive">
            <table class="table table-sm">
                <thead class="table-light">
                <tr>
                    <th class="text-center">日付</th>
                    <th class="text-center">信用倍率</th>
                    <th class="text-center">売残高</th>
                    <th class="text-center">売残増減</th>
                    <th class="text-center">買残高</th>
                    <th class="text-center">買残増減</th>
                </tr>
                </thead>
                <tbody>
        '''
        
        for data in margin_data[:10]:  # 10週分のデータ
            # 信用倍率計算
            ratio = data.outstanding_purchases / data.outstanding_sales if data.outstanding_sales > 0 else 0
            ratio_class = ("text-success" if ratio > 2 else 
                        "text-primary" if ratio > 1 else "text-danger")
            
            # 増減の色分け
            sales_change_class = ("text-danger" if data.outstanding_sales_change > 0 else
                                "text-success" if data.outstanding_sales_change < 0 else "text-muted")
            purchases_change_class = ("text-success" if data.outstanding_purchases_change > 0 else
                                    "text-danger" if data.outstanding_purchases_change < 0 else "text-muted")
            
            # 増減の符号
            sales_change_sign = "+" if data.outstanding_sales_change > 0 else ""
            purchases_change_sign = "+" if data.outstanding_purchases_change > 0 else ""
            
            html += f'''
            <tr>
            <td class="text-center">{data.date.strftime('%m/%d')}</td>
            <td class="text-center">
                <span class="fw-semibold {ratio_class}">{ratio:.2f}</span>
            </td>
            <td class="text-center">{data.outstanding_sales:,}</td>
            <td class="text-center">
                <span class="{sales_change_class} small">
                {sales_change_sign}{data.outstanding_sales_change:,}
                </span>
            </td>
            <td class="text-center">{data.outstanding_purchases:,}</td>
            <td class="text-center">
                <span class="{purchases_change_class} small">
                {purchases_change_sign}{data.outstanding_purchases_change:,}
                </span>
            </td>
            </tr>
            '''
        
        html += '''
                </tbody>
            </table>
            </div>
        </div>
        </div>
        '''
        
        return html

    def _render_margin_javascript(self, diary_id, issue_id):
        """JavaScript初期化コード"""
        return f'''
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            if (typeof window.MarginTabController === 'undefined') {{
                window.MarginTabController = new MarginTabManager({diary_id}, {issue_id});
            }}
        }});
        </script>
        '''

    def _render_margin_unavailable(self):
        """margin_tradingアプリ未使用時の表示"""
        return '''
        <div class="text-center py-4">
        <div class="text-muted">
            <i class="bi bi-exclamation-triangle" style="font-size: 2rem;"></i>
            <h6 class="mt-3">信用倍率機能は利用できません</h6>
            <p class="mb-0 small">margin_trading アプリが設定されていません</p>
        </div>
        </div>
        '''

    def _render_no_symbol(self):
        """証券コード未設定時の表示"""
        return '''
        <div class="text-center py-4">
        <div class="text-muted">
            <i class="bi bi-info-circle" style="font-size: 2rem;"></i>
            <h6 class="mt-3">証券コードが設定されていません</h6>
            <p class="mb-0 small">信用倍率データを取得するには証券コードが必要です</p>
        </div>
        </div>
        '''

    def _render_no_data(self, symbol):
        """データ未存在時の表示"""
        return f'''
        <div class="text-center py-4">
        <div class="text-muted">
            <i class="bi bi-database-x" style="font-size: 2rem;"></i>
            <h6 class="mt-3">信用取引データがありません</h6>
            <p class="mb-0 small">証券コード: {symbol}</p>
        </div>
        </div>
        '''

    def _render_margin_error(self, error_msg):
        """エラー表示"""
        return f'''
        <div class="text-center py-4">
        <div class="text-muted">
            <i class="bi bi-exclamation-triangle text-warning" style="font-size: 2rem;"></i>
            <h6 class="mt-3">データ取得エラー</h6>
            <p class="mb-2 small">信用倍率データの取得中にエラーが発生しました</p>
            <button class="btn btn-sm btn-outline-primary" onclick="window.location.reload()">
            <i class="bi bi-arrow-clockwise me-1"></i>再試行
            </button>
        </div>
        </div>
        '''
        
    def _render_notes_tab(self, diary):
        """継続記録タブのHTMLを直接生成"""
        notes = diary.notes.all().order_by('-date')[:3]
        html = '<div class="px-1 py-2"><div class="notes-timeline">'
        
        if notes.exists():
            for note in notes:
                # 基本情報
                date_str = note.date.strftime('%Y年%m月%d日')
                
                # ノートタイプのバッジカラー
                badge_class = self._get_note_badge_class(note.note_type)
                badge_text = self._get_note_type_display(note.note_type)
                
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
                
                # 価格情報があれば表示
                if note.current_price:
                    price_formatted = f"{float(note.current_price):,.2f}円"
                    html += f'<div class="note-price small mb-1"><span class="text-muted">記録時価格:</span><span class="fw-medium">{price_formatted}</span>'
                    
                    # 価格変化率
                    if diary.purchase_price:
                        price_change = ((float(note.current_price) / float(diary.purchase_price)) - 1) * 100
                        price_change_class = "text-success" if price_change > 0 else "text-danger"
                        price_change_sign = "+" if price_change > 0 else ""
                        html += f'<span class="{price_change_class} ms-2">({price_change_sign}{price_change:.2f}%)</span>'
                    
                    html += '</div>'
                                
                formatted_content = note.content.replace('\n', '<br>')

                # コンテンツ部分のHTMLを生成
                html += f'''
                <div class="note-content bg-light p-2 rounded">
                    {formatted_content}
                </div>
                </div>
                '''
            
            # もっと見るリンク
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

    def _get_margin_data(self, stock_symbol):
        """銘柄データと信用倍率データを取得"""
        market_issue = MarketIssue.objects.filter(
            code=stock_symbol
        ).first()
        
        margin_data = None
        if market_issue:
            margin_data = MarginTradingData.objects.filter(
                issue=market_issue
            ).order_by('-date')[:20]  # 20週分のデータ
        
        return market_issue, margin_data

    def _render_margin_tab_navigation(self):
        """タブナビゲーション"""
        return '''
        <div class="margin-tabs-nav mb-3">
        <div class="nav nav-pills nav-fill" id="marginTabsNav" role="tablist">
            <button class="nav-link active" id="chart-tab" data-bs-toggle="pill" 
                    data-bs-target="#chart-content" type="button" role="tab">
            <i class="bi bi-graph-up d-sm-none"></i>
            <span class="d-none d-sm-inline">チャート</span>
            <span class="d-sm-none">チャート</span>
            </button>
            <button class="nav-link" id="compare-tab" data-bs-toggle="pill" 
                    data-bs-target="#compare-content" type="button" role="tab">
            <i class="bi bi-bar-chart d-sm-none"></i>
            <span class="d-none d-sm-inline">比較</span>
            <span class="d-sm-none">比較</span>
            </button>
            <button class="nav-link" id="data-tab" data-bs-toggle="pill" 
                    data-bs-target="#data-content" type="button" role="tab">
            <i class="bi bi-table d-sm-none"></i>
            <span class="d-none d-sm-inline">データ</span>
            <span class="d-sm-none">データ</span>
            </button>
        </div>
        </div>
        '''
            
    def _render_analysis_tab(self, diary):
        """分析タブのHTMLを直接生成"""
        from analysis_template.models import DiaryAnalysisValue
        
        html = '<div class="px-1 py-2">'
        
        # 分析値を取得してテンプレートごとにグループ化
        analysis_values = DiaryAnalysisValue.objects.filter(diary=diary).select_related('analysis_item__template')
        
        if analysis_values.exists():
            # テンプレートごとにグループ化
            from collections import defaultdict
            templates = defaultdict(list)
            
            for value in analysis_values:
                template = value.analysis_item.template
                templates[template.id].append(value)
            
            for template_id, values in templates.items():
                if not values:
                    continue
                    
                template = values[0].analysis_item.template
                
                # テンプレート名とプログレスバー
                html += f'''
                <div class="analysis-template-summary mb-3" data-template-id="{template.id}">
                  <h6 class="mb-2">
                    <i class="bi bi-clipboard-check"></i> {template.name}
                  </h6>
                  
                  <div class="progress mb-2" style="height: 6px;">
                '''
                
                # 進捗率の計算
                items_count = template.items.count()
                filled_count = len(values)
                completion = int((filled_count / items_count) * 100) if items_count > 0 else 0
                
                html += f'<div class="progress-bar bg-primary" style="width: {completion}%"></div></div>'
                
                # 分析項目
                html += '<div class="analysis-item-preview">'
                
                for i, value in enumerate(values[:5]):  # 最大5項目まで表示
                    item_name = value.analysis_item.name
                    
                    # 値のタイプに基づいて表示
                    if value.analysis_item.item_type == 'boolean_with_value':
                        if value.boolean_value:
                            display_value = "✓"
                        else:
                            display_value = ""
                            
                        if value.number_value is not None:
                            display_value += f" {value.number_value:.2f}"
                        elif value.text_value:
                            display_value += f" {value.text_value}"
                    elif value.analysis_item.item_type == 'number':
                        display_value = f"{float(value.number_value):.2f}" if value.number_value is not None else "-"
                    elif value.analysis_item.item_type == 'boolean':
                        display_value = "はい" if value.boolean_value else "いいえ"
                    elif value.analysis_item.item_type == 'select':
                        display_value = value.text_value or "-"
                    else:
                        display_value = value.text_value or "-"
                    
                    html += f'''
                    <div class="analysis-preview-item">
                      <span class="key">{item_name}:</span>
                      <span class="value">{display_value}</span>
                    </div>
                    '''
                
                # もっと見るリンク
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
    
    def _render_details_tab(self, context):
        """詳細タブのHTMLを直接生成"""
        diary = context['diary']
        html = '<div class="px-1 py-2">'
        
        # 購入情報
        if not diary.is_memo and diary.purchase_price is not None and diary.purchase_quantity is not None:
            html += f'''
            <div class="info-block">
              <div class="info-row">
                <div class="info-item">
                  <div class="info-icon">
                    <i class="bi bi-currency-yen"></i>
                  </div>
                  <div class="info-content">
                    <span class="info-label">購入価格</span>
                    <span class="info-value">{context['purchase_price']}</span>
                  </div>
                </div>

                <div class="info-item">
                  <div class="info-icon">
                    <i class="bi bi-graph-up"></i>
                  </div>
                  <div class="info-content">
                    <span class="info-label">購入数量</span>
                    <span class="info-value">{context['purchase_quantity']}株</span>
                  </div>
                </div>

                <div class="info-item">
                  <div class="info-icon">
                    <i class="bi bi-calendar-date"></i>
                  </div>
                  <div class="info-content">
                    <span class="info-label">購入/メモ日</span>
                    <span class="info-value">{context['purchase_date']}</span>
                  </div>
                </div>

                <div class="info-item">
                  <div class="info-icon">
                    <i class="bi bi-cash-stack"></i>
                  </div>
                  <div class="info-content">
                    <span class="info-label">総投資額</span>
                    <span class="info-value">{context['total_investment']}</span>
                  </div>
                </div>
              </div>
            </div>
            '''
        
        # 売却情報
        if diary.sell_date and diary.purchase_price is not None and diary.purchase_quantity is not None:
            profit_class = "profit" if context.get('profit', 0) > 0 else "loss" if context.get('profit', 0) < 0 else "text-muted"
            profit_sign = "+" if context.get('profit', 0) > 0 else ""
            
            html += f'''
            <div class="sell-info">
              <div class="info-row">
                <div class="info-item">
                  <div class="info-icon">
                    <i class="bi bi-currency-yen"></i>
                  </div>
                  <div class="info-content">
                    <span class="info-label">売却価格</span>
                    <span class="info-value">{context['sell_price']}</span>
                  </div>
                </div>

                <div class="info-item">
                  <div class="info-icon">
                    <i class="bi bi-calendar-check"></i>
                  </div>
                  <div class="info-content">
                    <span class="info-label">売却日</span>
                    <span class="info-value">{context['sell_date']}</span>
                  </div>
                </div>

                <div class="info-item">
                  <div class="info-icon">
                    <i class="bi bi-graph-up-arrow"></i>
                  </div>
                  <div class="info-content">
                    <span class="info-label">損益</span>
                    <span class="{profit_class}">{profit_sign}{context['profit_formatted']}</span>
                  </div>
                </div>

                <div class="info-item">
                  <div class="info-icon">
                    <i class="bi bi-percent"></i>
                  </div>
                  <div class="info-content">
                    <span class="info-label">損益率</span>
                    <span class="{profit_class}">{profit_sign}{context['profit_rate_formatted']}</span>
                  </div>
                </div>
              </div>
            </div>
            '''
        
        html += '</div>'
        return html
    
    def _get_note_badge_class(self, note_type):
        """ノートタイプに応じたバッジクラスを取得"""
        badge_classes = {
            'analysis': 'bg-primary',
            'news': 'bg-info',
            'earnings': 'bg-success',
            'insight': 'bg-warning',
            'risk': 'bg-danger'
        }
        return badge_classes.get(note_type, 'bg-secondary')
    
    def _get_note_type_display(self, note_type):
        """ノートタイプの表示名を取得"""
        type_displays = {
            'analysis': '分析更新',
            'news': 'ニュース',
            'earnings': '決算情報',
            'insight': '新たな気づき',
            'risk': 'リスク要因'
        }
        return type_displays.get(note_type, 'その他')

def diary_list(request):
    """日記リストを表示するビュー（検索・フィルター機能付き）"""
    # HTMX/AJAXリクエストかどうかを確認
    is_htmx = request.headers.get('HX-Request') == 'true' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # 通常のブラウザアクセスの場合はホームページにリダイレクト
    if not is_htmx:
        from django.shortcuts import redirect
        return redirect(f'/stockdiary/?{request.GET.urlencode()}')
    
    try:
        queryset = StockDiary.objects.filter(user=request.user).order_by('-updated_at', '-purchase_date')
        queryset = queryset.select_related('user').prefetch_related('tags', 'notes')
        
        # 検索フィルター
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
        
        # 保有状態によるフィルタリング
        if status == 'active':
            queryset = queryset.filter(
                sell_date__isnull=True,
                purchase_price__isnull=False,
                purchase_quantity__isnull=False
            )
        elif status == 'sold':
            queryset = queryset.filter(sell_date__isnull=False)
        elif status == 'memo':
            queryset = queryset.filter(
                Q(purchase_price__isnull=True) | 
                Q(purchase_quantity__isnull=True) | 
                Q(is_memo=True)
            )
            
        # ページネーション
        paginator = Paginator(queryset, 10)  # モーダルでは1ページ10件に設定
        page = request.GET.get('page', 1)
        
        try:
            diaries = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            diaries = paginator.page(1)
        
        # タグ情報を取得
        tags = Tag.objects.filter(user=request.user)
        
        context = {
            'diaries': diaries,
            'page_obj': diaries,
            'tags': tags,
            'request': request,
            'current_params': current_params,
        }
        
        # モーダル表示の場合は対応するテンプレートを使用
        if sector and not query and not status and not tag_id:
            return render(request, 'stockdiary/partials/diary_list_sector.html', context)
        elif tag_id and not query and not status and not sector:
            return render(request, 'stockdiary/partials/diary_list_simple.html', context)
        else:
            return render(request, 'stockdiary/partials/diary_list.html', context)
    
    except Exception as e:
        import traceback
        print(f"Diary list error: {str(e)}")
        traceback.print_exc()
        
        return HttpResponse(
            f'<div class="alert alert-danger">日記リストの読み込みに失敗しました: {str(e)}</div>',
            status=500
        )

# tab_content 関数にも信用倍率タブを追加
def tab_content(request, diary_id, tab_type):
    """日記カードのタブコンテンツを表示するビュー"""
    try:
        # 厳密なユーザー認証と日記の取得
        try:
            diary = StockDiary.objects.get(id=diary_id, user=request.user)
        except StockDiary.DoesNotExist:
            return HttpResponse(
                '<div class="alert alert-warning">指定された日記が見つかりません。</div>', 
                status=404
            )

        # リファラーから判定（デバッグ用にログ出力）
        referer = request.META.get('HTTP_REFERER', '')
        full_path = request.get_full_path()
        
        # 削除ボタンは常に表示（home画面でもdetail画面でも）
        context = {
            'diary': diary,
            'is_detail_view': True,  # 常にTrueで削除ボタンを表示
        }
        
        try:
            if tab_type == 'notes':
                notes = diary.notes.all().order_by('-date')[:3]
                context['notes'] = notes
                template_name = 'stockdiary/partials/tab_notes.html'
            
            elif tab_type == 'analysis':
                from analysis_template.models import DiaryAnalysisValue
                from collections import defaultdict
                
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
                            'values': values[:3]  # 最初の3項目
                        })
                
                context['template_groups'] = template_groups
                template_name = 'stockdiary/partials/tab_analysis.html'
            
            elif tab_type == 'details':
                if diary.purchase_price and diary.purchase_quantity:
                    context['total_investment'] = diary.purchase_price * diary.purchase_quantity
                    
                    if diary.sell_price and diary.sell_date:
                        profit = (diary.sell_price - diary.purchase_price) * diary.purchase_quantity
                        profit_rate = ((diary.sell_price / diary.purchase_price) - 1) * 100
                        context['profit'] = profit
                        context['profit_rate'] = profit_rate
                
                template_name = 'stockdiary/partials/tab_details.html'
            
            elif tab_type == 'margin':  # 信用倍率タブを追加
                # 信用倍率データを取得
                margin_data = None
                latest_margin_data = None
                
                if diary.stock_symbol:
                    try:
                        market_issue = MarketIssue.objects.filter(
                            str(diary.stock_symbol) + '0'
                        ).first()
                        
                        if market_issue:
                            margin_queryset = MarginTradingData.objects.filter(
                                issue=market_issue
                            ).order_by('-date')[:10]
                            
                            latest_margin_data = margin_queryset.first() if margin_queryset else None
                            margin_data = list(margin_queryset)
                    
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(f"信用倍率データ取得エラー: {e}")
                
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
            import traceback
            traceback.print_exc()
            return HttpResponse(
                f'<div class="alert alert-danger">タブコンテンツの読み込み中にエラーが発生しました: {str(render_error)}</div>', 
                status=500
            )

    except Exception as e:
        print(f"想定外のエラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return HttpResponse(
            '<div class="alert alert-danger">予期せぬエラーが発生しました。</div>', 
            status=500
        )
                             
def calendar_view(request):
    """
    カレンダー全体ビュー - HTMLおよびJavaScriptの挿入問題を回避するために単純なビューを使用
    """
    # ここでカレンダーデータを準備
    today = timezone.now().date()
    month = today.month
    year = today.year
    
    # ユーザーの日記データを取得
    user_diaries = StockDiary.objects.filter(user=request.user)
    
    # 単純なレスポンスを返す
    return render(request, 'stockdiary/calendar.html', {
        'today': today,
        'month': month,
        'year': year,
        'diaries': user_diaries
    })    


@login_required
@require_GET
def search_suggestion(request):
    """
    検索キーワードに基づいて提案を返す
    hx-get="/stockdiary/search-suggestion/" で使用
    """
    query = request.GET.get('query', '').strip()
    
    # 3文字未満はサジェストを出さない
    if len(query) < 2:
        return HttpResponse('')
    
    # ユーザーの日記から検索
    stock_matches = StockDiary.objects.filter(
        user=request.user
    ).filter(
        Q(stock_name__icontains=query) | 
        Q(stock_symbol__icontains=query)
    ).distinct().values('stock_name', 'stock_symbol')[:5]
    
    # タグ検索
    tag_matches = Tag.objects.filter(
        user=request.user, 
        name__icontains=query
    ).values('id', 'name')[:3]
    
    if not stock_matches and not tag_matches:
        return HttpResponse('')
    
    # レスポンスを構築
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
    """
    特定の日記に対するコンテキストアクション
    モバイルで長押し時に表示する
    """
    try:
        diary = StockDiary.objects.get(id=pk, user=request.user)
    except StockDiary.DoesNotExist:
        return JsonResponse({'error': '日記が見つかりません'}, status=404)
    
    # 日記の種類に応じたアクションを決定
    is_memo = diary.is_memo or diary.purchase_price is None or diary.purchase_quantity is None
    is_sold = diary.sell_date is not None
    
    context = {
        'diary': diary,
        'is_memo': is_memo,
        'is_sold': is_sold
    }
    
    html = render_to_string('stockdiary/partials/context_actions.html', context)
    return HttpResponse(html)

def csrf_failure_view(request, reason=""):
    """CSRF失敗時のカスタムハンドラー"""
    
    # テストアカウントの場合は親切なメッセージを表示
    if (hasattr(request, 'user') and 
        request.user.is_authenticated and 
        request.user.username in getattr(settings, 'TEST_ACCOUNT_SETTINGS', {}).get('USERNAMES', [])):
        
        messages.warning(
            request, 
            "テストアカウントの同時利用により一時的なエラーが発生しました。"
            "ページを更新するか、別のテストアカウント（test1, test2, demo1等）をお試しください。"
        )
        return redirect('stockdiary:home')
    
    # 通常ユーザーの場合
    return render(request, 'errors/csrf_failure.html', {
        'reason': reason,
        'test_accounts': settings.TEST_ACCOUNT_SETTINGS.get('USERNAMES', [])
    }, status=403)


class ServeImageView(LoginRequiredMixin, View):
    """ユーザー認証付きの画像配信ビュー"""
    
    def get(self, request, diary_id, image_type, note_id=None):
        try:
            # 日記の所有者確認
            diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
            
            # 画像タイプに応じてファイルパスを取得
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
            
            # サムネイル生成が要求されている場合
            is_thumbnail = request.GET.get('thumbnail') == '1'
            if is_thumbnail:
                return self._serve_thumbnail(image_field, request)
            
            # 通常の画像配信
            return self._serve_image(image_field)
            
        except Exception as e:
            print(f"Image serving error: {str(e)}")
            raise Http404("画像の配信中にエラーが発生しました")
    
    def _serve_image(self, image_field):
        """通常の画像を配信"""
        try:
            # ファイルを開く
            image_file = image_field.open('rb')
            
            # MIMEタイプを判定
            file_path = image_field.name
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = 'image/jpeg'  # デフォルト
            
            # レスポンスを作成
            response = HttpResponse(image_file.read(), content_type=content_type)
            
            # キャッシュヘッダーを設定
            response['Cache-Control'] = 'private, max-age=3600'  # 1時間キャッシュ
            
            # ファイル名を設定
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
            # サムネイルサイズを取得
            width = int(request.GET.get('w', 300))
            height = int(request.GET.get('h', 200))
            
            # サイズ制限
            width = min(max(width, 50), 800)  # 50px〜800px
            height = min(max(height, 50), 600)  # 50px〜600px
            
            # 画像を開く
            image_file = image_field.open('rb')
            img = Image.open(image_file)
            
            # RGBA画像の場合はRGBに変換
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            # サムネイル生成（アスペクト比を保持してクロップ）
            img_ratio = img.width / img.height
            thumb_ratio = width / height
            
            if img_ratio > thumb_ratio:
                # 画像が横長の場合、高さに合わせてリサイズ後、左右をクロップ
                new_height = height
                new_width = int(height * img_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                left = (new_width - width) // 2
                img = img.crop((left, 0, left + width, height))
            else:
                # 画像が縦長の場合、幅に合わせてリサイズ後、上下をクロップ
                new_width = width
                new_height = int(width / img_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                top = (new_height - height) // 2
                img = img.crop((0, top, width, top + height))
            
            # バイトストリームに保存
            output = io.BytesIO()
            
            # WebP形式で保存を試行、失敗した場合はJPEG
            try:
                img.save(output, format='WebP', quality=80, optimize=True)
                content_type = 'image/webp'
            except Exception:
                img.save(output, format='JPEG', quality=80, optimize=True)
                content_type = 'image/jpeg'
            
            output.seek(0)
            
            # レスポンスを作成
            response = HttpResponse(output.getvalue(), content_type=content_type)
            response['Cache-Control'] = 'private, max-age=7200'  # 2時間キャッシュ
            
            image_file.close()
            return response
            
        except Exception as e:
            print(f"Error creating thumbnail: {str(e)}")
            # サムネイル生成に失敗した場合は元画像を配信
            return self._serve_image(image_field)
        

@login_required
def api_margin_chart_data(request, diary_id):
    """信用倍率チャートデータAPI"""
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        
        if not diary.stock_symbol:
            return JsonResponse({'error': '証券コードが設定されていません'}, status=400)
        
        # パラメータ取得
        period = request.GET.get('period', '3')  # 3, 6, all
        
        # 銘柄取得
        market_issue = MarketIssue.objects.filter(code=str(diary.stock_symbol)+'0').first()
        if not market_issue:
            return JsonResponse({'error': '銘柄が見つかりません'}, status=404)
        
        # データ取得
        queryset = MarginTradingData.objects.filter(issue=market_issue).order_by('-date')
        
        # 期間フィルター
        if period == '3':
            queryset = queryset[:12]  # 3ヶ月分
        elif period == '6':
            queryset = queryset[:24]  # 6ヶ月分
        # 'all'の場合はそのまま
        
        data = list(queryset.values(
            'date', 'outstanding_sales', 'outstanding_purchases',
            'outstanding_sales_change', 'outstanding_purchases_change'
        ))
        
        # データを時系列順に並び替え
        data.reverse()
        
        # チャート用データ変換
        chart_data = {
            'labels': [d['date'].strftime('%m/%d') for d in data],
            'datasets': [
                {
                    'label': '信用倍率',
                    'data': [
                        round(d['outstanding_purchases'] / d['outstanding_sales'] if d['outstanding_sales'] > 0 else 0, 2)
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
        
        # 統計データ計算
        ratios = [d['outstanding_purchases'] / d['outstanding_sales'] 
                 if d['outstanding_sales'] > 0 else 0 for d in data]
        
        stats = {
            'average': round(statistics.mean(ratios) if ratios else 0, 2),
            'volatility': round(statistics.stdev(ratios) if len(ratios) > 1 else 0, 2),
            'min': round(min(ratios) if ratios else 0, 2),
            'max': round(max(ratios) if ratios else 0, 2),
            'current': round(ratios[-1] if ratios else 0, 2)
        }
        
        # アラート判定
        alerts = []
        if ratios:
            current_ratio = ratios[-1]
            avg_ratio = stats['average']
            
            # 異常値検知（3σルール）
            if len(ratios) > 3:
                std_dev = stats['volatility']
                if abs(current_ratio - avg_ratio) > 3 * std_dev:
                    alerts.append({
                        'type': 'warning',
                        'message': f'現在の信用倍率({current_ratio:.2f})が過去平均から大きく乖離しています'
                    })
            
            # 水準別アラート
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
        import traceback
        print(f"Chart data API error: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required 
def api_margin_compare_data(request, diary_id):
    """銘柄比較データAPI（修正版）"""
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        symbols = request.GET.get('symbols', '').split(',')
        symbols = [s.strip() for s in symbols if s.strip()]
        
        if not symbols:
            return JsonResponse({'error': '比較銘柄が指定されていません'}, status=400)
        
        # 最大4銘柄まで
        symbols = symbols[:4]
        
        compare_data = []
        chart_datasets = []
        colors = [
            'rgb(255, 99, 132)',   # 赤
            'rgb(54, 162, 235)',   # 青
            'rgb(75, 192, 192)',   # 緑
            'rgb(255, 205, 86)'    # 黄
        ]
        
        labels = None
        max_data_length = 0
        
        for i, symbol in enumerate(symbols):
            # 証券コード処理を統一（'0'を付ける）
            search_code = str(symbol).rstrip('0') + '0'
            market_issue = MarketIssue.objects.filter(code=search_code).first()
            
            if not market_issue:
                # '0'なしでも検索してみる
                market_issue = MarketIssue.objects.filter(code=str(symbol)).first()
            
            if not market_issue:
                continue
                
            # 直近12週のデータを取得
            margin_data = MarginTradingData.objects.filter(
                issue=market_issue
            ).order_by('-date')[:12]
            
            if not margin_data.exists():
                continue
            
            # データ変換
            data_list = list(margin_data.values(
                'date', 'outstanding_sales', 'outstanding_purchases',
                'outstanding_sales_change', 'outstanding_purchases_change'
            ))
            data_list.reverse()  # 時系列順に変更
            
            # ラベルを最初の銘柄から設定
            if labels is None:
                labels = [d['date'].strftime('%m/%d') for d in data_list]
                max_data_length = len(data_list)
            
            # 信用倍率を計算
            ratios = []
            for d in data_list:
                if d['outstanding_sales'] > 0:
                    ratio = round(d['outstanding_purchases'] / d['outstanding_sales'], 2)
                else:
                    ratio = 0
                ratios.append(ratio)
            
            # データの長さを統一（短い場合はnullで埋める）
            while len(ratios) < max_data_length:
                ratios.insert(0, None)
            
            # チャートデータセット
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
            
            # 統計データ
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
        import traceback
        print(f"Compare data API error: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def api_margin_sector_suggestions(request, diary_id):
    """業種別銘柄候補API（新規追加）"""
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        
        if not diary.stock_symbol:
            return JsonResponse({'suggestions': []})
        
        # 現在の銘柄の業種情報を取得
        company = CompanyMaster.objects.filter(code=diary.stock_symbol).first()
        if not company:
            return JsonResponse({'suggestions': []})
        
        # 業種の優先順位: 33業種 > 17業種
        sector = company.industry_name_33 or company.industry_name_17
        scale = company.scale_code
        
        if not sector:
            return JsonResponse({'suggestions': []})
        
        # 同業種の他銘柄を取得
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
            # MarketIssueに存在するかチェック（証券コード統一処理）
            search_code = str(comp.code).rstrip('0') + '0'
            market_issue = MarketIssue.objects.filter(code=search_code).first()
            
            if not market_issue:
                # '0'なしでも検索
                market_issue = MarketIssue.objects.filter(code=str(comp.code)).first()
            
            if not market_issue:
                continue
            
            # 最新の信用倍率データを取得
            latest_data = MarginTradingData.objects.filter(
                issue=market_issue
            ).order_by('-date').first()
            
            if latest_data and latest_data.outstanding_sales > 0:
                ratio = latest_data.outstanding_purchases / latest_data.outstanding_sales
                
                suggestions.append({
                    'symbol': comp.code,
                    'name': comp.name,
                    'ratio': round(ratio, 2),
                    'market': comp.market or '東証',
                    'scale': comp.scale_name or '不明',
                    'last_update': latest_data.date.strftime('%m/%d'),
                    'outstanding_sales': latest_data.outstanding_sales,
                    'outstanding_purchases': latest_data.outstanding_purchases
                })
        
        # 信用倍率でソート（高い順）
        suggestions.sort(key=lambda x: x['ratio'], reverse=True)
        
        return JsonResponse({
            'sector': sector,
            'suggestions': suggestions[:8],  # 上位8銘柄
            'total_companies': len(suggestions)
        })
        
    except Exception as e:
        import traceback
        print(f"Sector suggestions API error: {traceback.format_exc()}")
        return JsonResponse({'suggestions': []})


@login_required
def api_margin_sector_data(request, diary_id):
    """業種分析データAPI"""
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        
        if not diary.stock_symbol:
            return JsonResponse({'error': '証券コードが設定されていません'}, status=400)
        
        # 現在の銘柄の業種を取得
        company = CompanyMaster.objects.filter(code=diary.stock_symbol).first()
        if not company or not company.industry_name_33:
            return JsonResponse({
                'error': '業種情報が見つかりません',
                'suggestions': []
            })
        
        sector_name = company.industry_name_33
        
        # 同業種の他の銘柄を取得
        sector_companies = CompanyMaster.objects.filter(
            industry_name_33=sector_name
        ).exclude(code=diary.stock_symbol)[:10]  # 最大10銘柄
        
        # 同業種銘柄の信用倍率データを取得
        suggestions = []
        sector_ratios = []
        
        for comp in sector_companies:
            market_issue = MarketIssue.objects.filter(code=comp.code).first()
            if not market_issue:
                continue
                
            latest_data = MarginTradingData.objects.filter(
                issue=market_issue
            ).order_by('-date').first()
            
            if latest_data and latest_data.outstanding_sales > 0:
                ratio = latest_data.outstanding_purchases / latest_data.outstanding_sales
                sector_ratios.append(ratio)
                
                suggestions.append({
                    'symbol': comp.code,
                    'name': comp.name,
                    'ratio': round(ratio, 2),
                    'scale': comp.scale_name or '不明',
                    'last_update': latest_data.date.strftime('%Y-%m-%d')
                })
        
        # 業種統計
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
            
            # 現在の銘柄のランキング
            current_issue = MarketIssue.objects.filter(code=diary.stock_symbol).first()
            if current_issue:
                current_data = MarginTradingData.objects.filter(
                    issue=current_issue
                ).order_by('-date').first()
                
                if current_data and current_data.outstanding_sales > 0:
                    current_ratio = current_data.outstanding_purchases / current_data.outstanding_sales
                    higher_count = sum(1 for r in sector_ratios if r > current_ratio)
                    sector_stats['current_ranking'] = higher_count + 1
                    sector_stats['current_ratio'] = round(current_ratio, 2)
        
        # 推奨銘柄（信用倍率順でソート）
        suggestions.sort(key=lambda x: x['ratio'], reverse=True)
        
        return JsonResponse({
            'sector_stats': sector_stats,
            'suggestions': suggestions[:5]  # 上位5銘柄
        })
        
    except Exception as e:
        import traceback
        print(f"Sector data API error: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)        
    
# stockdiary/views.py に以下のメソッドを追加

def _render_margin_tab(self, diary):
    """信用倍率タブのHTMLをテンプレートレンダリングで生成（更新版）"""
    
    # margin_trading アプリが利用できない場合
    if not MARGIN_TRADING_AVAILABLE:
        return '''
        <div class="text-center py-4">
        <div class="text-muted">
            <i class="bi bi-exclamation-triangle" style="font-size: 2rem;"></i>
            <h6 class="mt-3">信用倍率機能は利用できません</h6>
            <p class="mb-0 small">margin_trading アプリが設定されていません</p>
        </div>
        </div>
        '''
    
    # 証券コードが設定されていない場合
    if not diary.stock_symbol:
        return '''
        <div class="text-center py-4">
        <div class="text-muted">
            <i class="bi bi-info-circle" style="font-size: 2rem;"></i>
            <h6 class="mt-3">証券コードが設定されていません</h6>
            <p class="mb-0 small">信用倍率データを取得するには証券コードが必要です</p>
        </div>
        </div>
        '''
    
    try:
        # 銘柄とデータを取得（修正版）
        market_issue, margin_data = self._get_margin_data_fixed(diary.stock_symbol)
        
        if not market_issue:
            return f'''
            <div class="text-center py-4">
            <div class="text-muted">
                <i class="bi bi-search" style="font-size: 2rem;"></i>
                <h6 class="mt-3">銘柄が見つかりません</h6>
                <p class="mb-0 small">証券コード: {diary.stock_symbol}</p>
            </div>
            </div>
            '''
        
        if not margin_data or not margin_data.exists():
            return f'''
            <div class="text-center py-4">
            <div class="text-muted">
                <i class="bi bi-database-x" style="font-size: 2rem;"></i>
                <h6 class="mt-3">信用取引データがありません</h6>
                <p class="mb-0 small">証券コード: {diary.stock_symbol}</p>
                <p class="mb-0 small">この銘柄の信用取引データが見つかりません</p>
            </div>
            </div>
            '''
        
        # テンプレートコンテキストを準備
        context = {
            'diary': diary,
            'margin_data': margin_data,
            'latest_margin_data': margin_data.first(),
            'request': self.request,
        }
        
        # テンプレートをレンダリング
        from django.template.loader import render_to_string
        
        try:
            return render_to_string('stockdiary/partials/tab_margin.html', context)
        except Exception as template_error:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Margin tab template error: {template_error}", exc_info=True)
            
            return f'''
            <div class="text-center py-4">
            <div class="text-muted">
                <i class="bi bi-exclamation-triangle text-warning" style="font-size: 2rem;"></i>
                <h6 class="mt-3">テンプレートエラー</h6>
                <p class="mb-2 small">信用倍率タブの表示中にエラーが発生しました</p>
                <button class="btn btn-sm btn-outline-primary" onclick="window.location.reload()">
                <i class="bi bi-arrow-clockwise me-1"></i>再試行
                </button>
            </div>
            </div>
            '''
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Margin tab rendering error (diary_id: {diary.id}): {e}", exc_info=True)
        
        return f'''
        <div class="text-center py-4">
        <div class="text-muted">
            <i class="bi bi-exclamation-triangle text-warning" style="font-size: 2rem;"></i>
            <h6 class="mt-3">データ取得エラー</h6>
            <p class="mb-2 small">信用倍率データの取得中にエラーが発生しました</p>
            <button class="btn btn-sm btn-outline-primary" onclick="window.location.reload()">
            <i class="bi bi-arrow-clockwise me-1"></i>再試行
            </button>
        </div>
        </div>
        '''
 
def _get_margin_data_fixed(self, stock_symbol):
    """銘柄データと信用倍率データを取得（修正版）"""
    try:
        # 証券コード処理を統一
        search_code = str(stock_symbol).rstrip('0') + '0'
        market_issue = MarketIssue.objects.filter(code=search_code).first()
        
        if not market_issue:
            # '0'なしでも検索
            market_issue = MarketIssue.objects.filter(code=str(stock_symbol)).first()
        
        margin_data = None
        if market_issue:
            margin_data = MarginTradingData.objects.filter(
                issue=market_issue
            ).order_by('-date')[:20]  # 20週分のデータ
        
        return market_issue, margin_data
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting margin data for symbol {stock_symbol}: {e}")
        return None, None
   
class StockListView(LoginRequiredMixin, TemplateView):
    """登録株式一覧を表示するビュー"""
    template_name = 'stockdiary/stock_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # フィルターパラメータの取得
        search_query = self.request.GET.get('q', '').strip()
        sort_by = self.request.GET.get('sort', 'symbol')  # デフォルトは証券コード順
        sector_filter = self.request.GET.get('sector', '')
        
        # ユーザーの日記から一意の株式銘柄を取得
        diary_stocks = StockDiary.objects.filter(user=user).values(
            'stock_symbol', 'stock_name', 'sector'
        ).distinct().order_by('stock_symbol')
        
        # 株式情報を収集
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
                'margin_data_available': False
            }
            
            # 日記件数を取得
            stock_info['diary_count'] = StockDiary.objects.filter(
                user=user, 
                stock_symbol=stock['stock_symbol']
            ).count()
            
            # アクティブな保有があるかチェック
            stock_info['has_active_holdings'] = StockDiary.objects.filter(
                user=user,
                stock_symbol=stock['stock_symbol'],
                sell_date__isnull=True,
                purchase_price__isnull=False,
                purchase_quantity__isnull=False
            ).exists()
            stock_info['has_completed_sales'] = StockDiary.objects.filter(
                user=user,
                stock_symbol=stock['stock_symbol'],
                sell_date__isnull=False,
                purchase_price__isnull=False,
                purchase_quantity__isnull=False
            ).exists()

            # 業種情報を企業マスタから取得
            if not stock_info['sector'] or stock_info['sector'] == '未分類':
                try:
                    company = CompanyMaster.objects.filter(code=stock['stock_symbol']).first()
                    if company:
                        stock_info['sector'] = company.industry_name_33 or company.industry_name_17 or '未分類'
                except:
                    pass
            
            # 信用倍率データを取得（margin_tradingアプリが利用可能な場合のみ）
            if MARGIN_TRADING_AVAILABLE:
                try:
                    # 証券コードから銘柄を検索（'0'を付ける処理）
                    search_code = str(stock['stock_symbol']).rstrip('0') + '0'
                    market_issue = MarketIssue.objects.filter(code=search_code).first()
                    
                    if not market_issue:
                        # '0'なしでも検索
                        market_issue = MarketIssue.objects.filter(code=str(stock['stock_symbol'])).first()
                    
                    if market_issue:
                        # 直近2回分のデータを取得
                        margin_data = MarginTradingData.objects.filter(
                            issue=market_issue
                        ).order_by('-date')[:2]
                        
                        if margin_data.exists():
                            stock_info['margin_data_available'] = True
                            latest_data = margin_data[0]
                            stock_info['latest_date'] = latest_data.date
                            
                            # 現在の信用倍率
                            if latest_data.outstanding_sales > 0:
                                stock_info['current_ratio'] = round(
                                    latest_data.outstanding_purchases / latest_data.outstanding_sales, 2
                                )
                            
                            # 前回の信用倍率（2件以上データがある場合）
                            if len(margin_data) > 1:
                                previous_data = margin_data[1]
                                if previous_data.outstanding_sales > 0:
                                    stock_info['previous_ratio'] = round(
                                        previous_data.outstanding_purchases / previous_data.outstanding_sales, 2
                                    )
                                    
                                    # 変動値を計算
                                    stock_info['ratio_change'] = round(
                                        stock_info['current_ratio'] - stock_info['previous_ratio'], 2
                                    )
                
                except Exception as e:
                    # エラーが発生しても処理を続行
                    import logging
                    logging.getLogger(__name__).warning(f"信用倍率データ取得エラー ({stock['stock_symbol']}): {e}")
            
            stock_list.append(stock_info)
        
        # 検索フィルター
        if search_query:
            stock_list = [
                stock for stock in stock_list
                if search_query.lower() in stock['name'].lower() or 
                   search_query.lower() in stock['symbol'].lower() or
                   search_query.lower() in stock['sector'].lower()
            ]
        
        # 業種フィルター
        if sector_filter:
            stock_list = [stock for stock in stock_list if stock['sector'] == sector_filter]
        
        # ソート処理
        if sort_by == 'name':
            stock_list.sort(key=lambda x: x['name'])
        elif sort_by == 'sector':
            stock_list.sort(key=lambda x: x['sector'])
        elif sort_by == 'current_ratio_desc':
            stock_list.sort(key=lambda x: x['current_ratio'], reverse=True)
        elif sort_by == 'current_ratio_asc':
            stock_list.sort(key=lambda x: x['current_ratio'])
        elif sort_by == 'ratio_change_desc':
            stock_list.sort(key=lambda x: x['ratio_change'], reverse=True)
        elif sort_by == 'ratio_change_asc':
            stock_list.sort(key=lambda x: x['ratio_change'])
        elif sort_by == 'diary_count_desc':
            stock_list.sort(key=lambda x: x['diary_count'], reverse=True)
        else:  # デフォルト: 証券コード順
            stock_list.sort(key=lambda x: x['symbol'])
        
        # 業種一覧（フィルター用）
        sectors = sorted(list(set([stock['sector'] for stock in stock_list])))
        
        # 統計情報
        stats = {
            'total_stocks': len(stock_list),
            'active_holdings': len([s for s in stock_list if s['has_active_holdings']]),
            'margin_data_available': len([s for s in stock_list if s['margin_data_available']]),
            'sectors_count': len(sectors)
        }
        
        # スピードダイアル用のアクション
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
    

@login_required
def api_stock_diaries(request, symbol):
    """特定の銘柄の日記一覧をJSON形式で返すAPI"""
    try:
        # ユーザーの日記から指定された銘柄のものを取得
        diaries = StockDiary.objects.filter(
            user=request.user,
            stock_symbol=symbol
        ).order_by('-purchase_date', '-created_at')
        
        # JSONレスポンス用のデータを作成
        diary_data = []
        for diary in diaries:
            # タグ一覧を取得
            tags = [tag.name for tag in diary.tags.all()]
            
            diary_data.append({
                'id': diary.id,
                'purchase_date': diary.purchase_date.strftime('%Y年%m月%d日'),
                'purchase_price': float(diary.purchase_price) if diary.purchase_price else None,
                'purchase_quantity': diary.purchase_quantity,
                'sell_date': diary.sell_date.strftime('%Y年%m月%d日') if diary.sell_date else None,
                'sell_price': float(diary.sell_price) if diary.sell_price else None,
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
        import traceback
        print(f"Stock diaries API error: {traceback.format_exc()}")
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)
