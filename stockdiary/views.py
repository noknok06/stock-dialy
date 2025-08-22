from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
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
from .models import StockDiary, DiaryNote
from .forms import StockDiaryForm, DiaryNoteForm
from tags.models import Tag
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from utils.mixins import ObjectNotFoundRedirectMixin
from .utils import process_analysis_values, calculate_analysis_completion_rate
from .analytics import DiaryAnalytics  # 追加: DiaryAnalytics クラスをインポート
from decimal import Decimal, InvalidOperation
from django.core.paginator import EmptyPage, PageNotAnInteger

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



class DiaryAnalyticsView(LoginRequiredMixin, TemplateView):
    """投資記録分析ダッシュボードを表示するビュー"""
    template_name = 'stockdiary/analytics_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # フィルターパラメータの取得
        date_range = self.request.GET.get('date_range', 'all')
        selected_tag = self.request.GET.get('tag', '')
        status = self.request.GET.get('status', 'all')
        sort = self.request.GET.get('sort', 'date_desc')
        
        # フィルターパラメータの準備
        filter_params = self._prepare_filter_params(date_range, selected_tag, status)
        
        # 基本データの取得
        diaries = self._get_filtered_diaries(user, filter_params, sort)
        all_diaries = StockDiary.objects.filter(user=user)
        tags = Tag.objects.filter(user=user).distinct()
        
        # 保有中と売却済みの株式を分離 (メモかどうかの判定は保持)
        active_diaries = [d for d in diaries if not d.sell_date]
        sold_diaries = [d for d in diaries if d.sell_date]
        
        # 分析インスタンスを作成
        analytics = DiaryAnalytics(user)
        
        # 各種分析データを収集
        stats = analytics.collect_stats(diaries, all_diaries)
        investment_data = analytics.get_investment_summary_data(diaries, all_diaries, active_diaries, sold_diaries)
        tag_data = analytics.get_tag_analysis_data(diaries)
        template_data = analytics.get_template_analysis_data(filter_params)
        activity_data = analytics.get_activity_analysis_data(diaries, all_diaries)
        
        # 追加の分析データ
        holding_period_data = analytics.prepare_holding_period_data(diaries)
        recent_trends = analytics.prepare_recent_trends(diaries)
        
        sector_data = analytics.get_sector_analysis_data(diaries, all_diaries)
        context.update(sector_data)
            
        # スピードダイアルのアクションを定義
        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'tag',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-tags',
                'label': 'タグ管理'
            },
            {
                'type': 'template',
                'url': reverse_lazy('analysis_template:list'),
                'icon': 'bi-clipboard-data',
                'label': 'テンプレート'
            }
        ]
        context['page_actions'] = analytics_actions
        
        # コンテキストの構築
        context.update({
            'diaries': diaries,
            'all_diaries': all_diaries,
            'date_range': date_range,
            'selected_tag': selected_tag,
            'status': status,
            'sort': sort,
            'all_tags': tags,
            **stats,
            **investment_data,
            **tag_data,
            **template_data,
            **activity_data,
            'holding_period_ranges': holding_period_data['ranges'],
            'holding_period_counts': holding_period_data['counts'],
            'purchase_frequency': recent_trends['purchase_frequency'],
            'most_used_tag': recent_trends['most_used_tag'],
            'most_detailed_record': recent_trends['most_detailed_record'],
            'recent_keywords': recent_trends['keywords'],
        })
        
        return context
        
    def _prepare_filter_params(self, date_range, tag_id, status):
        """フィルターパラメータを準備"""
        filter_params = {
            'date_from': None,
            'tag_id': tag_id,
            'status': status
        }
        
        # 日付フィルターの設定
        if date_range != 'all':
            today = timezone.now().date()
            if date_range == '1m':
                filter_params['date_from'] = today - timedelta(days=30)
            elif date_range == '3m':
                filter_params['date_from'] = today - timedelta(days=90)
            elif date_range == '6m':
                filter_params['date_from'] = today - timedelta(days=180)
            elif date_range == '1y':
                filter_params['date_from'] = today - timedelta(days=365)
        
        return filter_params
    
    def _get_filtered_diaries(self, user, filter_params, sort='date_desc'):
        """フィルター条件に基づいて日記を取得"""
        diaries = StockDiary.objects.filter(user=user)
        
        diaries = diaries.select_related('user').prefetch_related(
            'tags', 
            'notes',
            'analysis_values__analysis_item__template'
        )

        # 日付でフィルタリング
        if filter_params.get('date_from'):
            diaries = diaries.filter(purchase_date__gte=filter_params['date_from'])
        
        # タグでフィルタリング
        if filter_params.get('tag_id'):
            diaries = diaries.filter(tags__id=filter_params['tag_id'])
        
        # ステータスでフィルタリング（保有中/売却済み）
        if filter_params.get('status') == 'active':
            diaries = diaries.filter(sell_date__isnull=True)
        elif filter_params.get('status') == 'sold':
            diaries = diaries.filter(sell_date__isnull=False)
        
        # 並び替え
        if sort == 'date_desc':
            diaries = diaries.order_by('-created_at', '-purchase_date')
        elif sort == 'date_asc':
            diaries = diaries.order_by('created_at', 'purchase_date')
        elif sort == 'reason_desc':
            # 理由フィールドの長さで並べ替え
            diaries = diaries.annotate(reason_length=Length('reason')).order_by('-reason_length')
        elif sort == 'reason_asc':
            diaries = diaries.annotate(reason_length=Length('reason')).order_by('reason_length')
        
        return diaries.select_related('user').prefetch_related('tags')

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
        """信用倍率タブのHTMLを直接生成（修正版）"""
        html = '<div class="px-1 py-2">'
        
        # margin_trading アプリが利用できない場合
        if not MARGIN_TRADING_AVAILABLE:
            html += '''
            <div class="text-center py-4">
            <div class="text-muted">
                <i class="bi bi-exclamation-triangle" style="font-size: 2rem;"></i>
                <h6 class="mt-3">信用倍率機能は利用できません</h6>
                <p class="mb-0 small">margin_trading アプリが設定されていません</p>
            </div>
            </div>
            '''
            html += '</div>'
            return html
        
        # 証券コードが設定されていない場合
        if not diary.stock_symbol:
            html += '''
            <div class="text-center py-4">
            <div class="text-muted">
                <i class="bi bi-info-circle" style="font-size: 2rem;"></i>
                <h6 class="mt-3">証券コードが設定されていません</h6>
                <p class="mb-0 small">信用倍率データを取得するには証券コードが必要です</p>
            </div>
            </div>
            '''
            html += '</div>'
            return html
        
        try:
            # 証券コードから銘柄を検索
            market_issue = MarketIssue.objects.filter(
                code=diary.stock_symbol
            ).first()
            
            if market_issue:
                # 直近のデータを取得
                margin_data = MarginTradingData.objects.filter(
                    issue=market_issue
                ).order_by('-date')[:5]  # ホームタブでは5週分
                
                if margin_data.exists():
                    latest_data = margin_data.first()
                    
                    # 🔥 修正：正しい信用倍率計算（買残÷売残）
                    if latest_data.outstanding_sales > 0:
                        ratio = latest_data.outstanding_purchases / latest_data.outstanding_sales
                        # 🔥 修正：色分けロジックも修正
                        if ratio > 2:
                            ratio_class = "text-success"  # 高倍率＝買い優勢＝緑
                        elif ratio > 1:
                            ratio_class = "text-primary"  # 中倍率＝青
                        else:
                            ratio_class = "text-danger"   # 低倍率＝売り優勢＝赤
                    else:
                        ratio = 0
                        ratio_class = "text-muted"
                    
                    # サマリーカード
                    html += f'''
                    <div class="margin-summary-compact mb-3">
                    <div class="row g-2">
                        <div class="col-6">
                        <div class="card border-0 bg-light text-center p-2">
                            <div class="small text-muted">信用倍率</div>
                            <div class="fw-bold {ratio_class}">{ratio:.2f}倍</div>
                            <div class="small text-muted">買残÷売残</div>
                        </div>
                        </div>
                        <div class="col-6">
                        <div class="card border-0 bg-light text-center p-2">
                            <div class="small text-muted">更新日</div>
                            <div class="fw-bold text-primary">{latest_data.date.strftime('%m/%d')}</div>
                        </div>
                        </div>
                    </div>
                    </div>
                    '''
                    
                    # 残高情報
                    html += '<div class="margin-data-compact">'
                    for i, data in enumerate(margin_data[:3]):  # 最大3件表示
                        date_str = data.date.strftime('%m/%d')
                        
                        # 🔥 修正：正しい信用倍率計算（買残÷売残）
                        if data.outstanding_sales > 0:
                            data_ratio = data.outstanding_purchases / data.outstanding_sales
                            # 🔥 修正：色分けロジックも修正
                            if data_ratio > 2:
                                ratio_class = "text-success"
                            elif data_ratio > 1:
                                ratio_class = "text-primary"
                            else:
                                ratio_class = "text-danger"
                        else:
                            data_ratio = 0
                            ratio_class = "text-muted"
                        
                        html += f'''
                        <div class="margin-item-compact d-flex justify-content-between align-items-center py-2 {'border-bottom' if i < 2 else ''}">
                        <div>
                            <div class="fw-medium">{date_str}</div>
                            <div class="small text-muted">
                            買: {data.outstanding_purchases:,} / 売: {data.outstanding_sales:,}
                            </div>
                        </div>
                        <div class="text-end">
                            <div class="fw-bold {ratio_class}">{data_ratio:.2f}倍</div>
                        </div>
                        </div>
                        '''
                    
                    html += '</div>'
                    
                    # 詳細リンク
                    html += f'''
                    <div class="text-end mt-3">
                    <a href="/stockdiary/{diary.id}/" class="text-primary text-decoration-none small">
                        詳細を見る <i class="bi bi-arrow-right"></i>
                    </a>
                    </div>
                    '''
                else:
                    html += '''
                    <div class="text-center py-4">
                    <div class="text-muted">
                        <i class="bi bi-database-x" style="font-size: 2rem;"></i>
                        <h6 class="mt-3">信用取引データがありません</h6>
                        <p class="mb-0 small">この銘柄の信用取引データが見つかりません</p>
                    </div>
                    </div>
                    '''
            else:
                html += f'''
                <div class="text-center py-4">
                <div class="text-muted">
                    <i class="bi bi-search" style="font-size: 2rem;"></i>
                    <h6 class="mt-3">銘柄が見つかりません</h6>
                    <p class="mb-0 small">証券コード: {diary.stock_symbol}</p>
                    <p class="mb-0 small">JPXデータベースに登録されていない可能性があります</p>
                </div>
                </div>
                '''
        
        except Exception as e:
            # エラーが発生した場合
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"信用倍率タブレンダリングエラー (diary_id: {diary.id}): {e}", exc_info=True)
            
            html += f'''
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
        
        html += '</div>'
        return html

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

def calendar_partial(request):
    """カレンダー部分レンダリング用ビュー"""
    try:
        view_type = request.GET.get('view', 'desktop')
        
        # 月を取得（指定がなければ現在の月）
        month_param = request.GET.get('month')
        if month_param:
            try:
                year, month = map(int, month_param.split('-'))
                current_date = datetime(year, month, 1)
            except (ValueError, TypeError):
                current_date = timezone.now().replace(day=1)
        else:
            current_date = timezone.now().replace(day=1)
        
        # 前月と次月
        prev_month = (current_date - timedelta(days=1)).replace(day=1)
        next_month = (current_date.replace(day=28) + timedelta(days=5)).replace(day=1)
        
        # 今日の日付
        today = timezone.now().date()
        
        # カレンダーの日付を生成
        _, days_in_month = calendar.monthrange(current_date.year, current_date.month)
        first_day_weekday = current_date.weekday()
        
        # 日本のカレンダーは日曜始まり (0) なので調整
        first_day_weekday = (first_day_weekday + 1) % 7
        
        # 前月の日付を埋める
        pre_days = []
        if first_day_weekday > 0:
            prev_month_last_day = (current_date - timedelta(days=1)).day
            for i in range(first_day_weekday):
                day_date = prev_month.replace(day=prev_month_last_day - first_day_weekday + i + 1)
                pre_days.append({
                    'day': day_date.day,
                    'date': day_date.date(),
                    'is_other_month': True,
                    'is_today': day_date.date() == today,
                    'has_events': False,
                    'event_types': []
                })
        
        # 現在の月の日付
        current_days = []
        for i in range(1, days_in_month + 1):
            day_date = current_date.replace(day=i)
            
            # イベントをデータベースから取得
            date_str = day_date.date().strftime('%Y-%m-%d')
            events = StockDiary.objects.filter(
                user=request.user,
                purchase_date=date_str
            ).values('id', 'is_memo')
            
            sell_events = StockDiary.objects.filter(
                user=request.user,
                sell_date=date_str
            ).values('id')
            
            has_events = events.exists() or sell_events.exists()
            event_types = []
            
            if has_events:
                # イベントタイプの決定
                if any(not e['is_memo'] for e in events):
                    event_types.append('purchase')
                
                if any(e['is_memo'] for e in events):
                    event_types.append('memo')
                
                if sell_events.exists():
                    event_types.append('sell')
            
            current_days.append({
                'day': i,
                'date': day_date.date(),
                'is_other_month': False,
                'is_today': day_date.date() == today,
                'has_events': has_events,
                'event_types': event_types
            })
        
        # 翌月の日付を埋める
        post_days = []
        total_days = len(pre_days) + len(current_days)
        remaining_cells = 42 - total_days  # 6行x7列=42セル
        
        for i in range(1, remaining_cells + 1):
            day_date = next_month.replace(day=i)
            post_days.append({
                'day': i,
                'date': day_date.date(),
                'is_other_month': True,
                'is_today': day_date.date() == today,
                'has_events': False,
                'event_types': []
            })
        
        # 週ごとにグループ化
        all_days = pre_days + current_days + post_days
        calendar_weeks = [all_days[i:i+7] for i in range(0, len(all_days), 7)]
        
        context = {
            'view': view_type,
            'current_date': current_date,
            'prev_month': prev_month,
            'next_month': next_month,
            'today': today,
            'calendar_weeks': calendar_weeks,
        }
        
        return render(request, 'stockdiary/partials/calendar_partial.html', context)
    
    except Exception as e:
        import traceback
        print(f"Calendar rendering error: {str(e)}")
        traceback.print_exc()
        
        return HttpResponse(
            f'<div class="alert alert-danger">カレンダーの読み込みに失敗しました: {str(e)}</div>',
            status=500
        )

def day_events(request):
    """特定の日付のイベントを表示するビュー"""
    try:
        date_str = request.GET.get('date')
        view_type = request.GET.get('view', 'desktop')
        
        # 日付パースのエラーハンドリング
        try:
            event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            # 無効な日付の場合は今日の日付を使用
            event_date = timezone.now().date()
        
        # クエリのデバッグ
        print(f"Fetching events for date: {event_date}, view: {view_type}")
        
        # 指定日付のイベントを取得
        purchase_events = StockDiary.objects.filter(
            user=request.user,
            purchase_date=event_date
        ).select_related('user')
        
        sell_events = StockDiary.objects.filter(
            user=request.user,
            sell_date=event_date
        ).select_related('user')
        
        # デバッグログ
        print(f"Found {purchase_events.count()} purchase events and {sell_events.count()} sell events")
        
        # イベントリストの作成
        events = []
        
        for diary in purchase_events:
            events.append({
                'title': diary.stock_name,
                'symbol': diary.stock_symbol,
                'url': reverse('stockdiary:detail', kwargs={'pk': diary.id}),
                'event_type': 'memo' if diary.is_memo else 'purchase',
                'price': diary.purchase_price,
                'quantity': diary.purchase_quantity
            })
        
        for diary in sell_events:
            events.append({
                'title': diary.stock_name,
                'symbol': diary.stock_symbol,
                'url': reverse('stockdiary:detail', kwargs={'pk': diary.id}),
                'event_type': 'sell',
                'price': diary.sell_price,
                'quantity': diary.purchase_quantity
            })
        
        events_count = len(events)
        
        # リストの先頭5件だけを表示
        events = events[:5]
        
        context = {
            'date': event_date,
            'events': events,
            'events_count': events_count,
            'view': view_type
        }
        
        return render(request, 'stockdiary/partials/day_events.html', context)
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Day events error: {str(e)}")
        print(error_details)
        
        return HttpResponse(
            f'<div class="alert alert-warning m-2"><i class="bi bi-exclamation-triangle me-2"></i>イベントの読み込みに失敗しました。</div>',
            status=200  # 500ではなく200を返す
        )

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
                            code=diary.stock_symbol
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