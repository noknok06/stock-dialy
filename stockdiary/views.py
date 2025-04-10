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

from .models import StockDiary, DiaryNote
from .forms import StockDiaryForm, DiaryNoteForm
from tags.models import Tag
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from utils.mixins import ObjectNotFoundRedirectMixin
from .utils import process_analysis_values, calculate_analysis_completion_rate
from .analytics import DiaryAnalytics  # 追加: DiaryAnalytics クラスをインポート
from decimal import Decimal, InvalidOperation
from django.core.paginator import EmptyPage, PageNotAnInteger

from collections import Counter, defaultdict
from datetime import timedelta

import traceback

from django.template import engines, Context
from django.contrib.humanize.templatetags.humanize import intcomma
from stockdiary.templatetags.stockdiary_filters import mul_filter, sub_filter, div_filter
import html
import json
import re


class StockDiaryListView(LoginRequiredMixin, ListView):
    model = StockDiary
    template_name = 'stockdiary/home.html'
    context_object_name = 'diaries'
    paginate_by = 4
    
    def get_queryset(self):
        queryset = StockDiary.objects.filter(user=self.request.user).order_by('-purchase_date')
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
        
        # 関連日記（同じ銘柄コードを持つ日記）を取得
        diary = self.object
        if diary.stock_symbol:  # 銘柄コードが存在する場合のみ
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

    def form_valid(self, form):
        # 親クラスのform_validを呼び出し
        response = super().form_valid(form)
        
        # 分析テンプレートが選択されていれば、分析値を処理
        analysis_template_id = self.request.POST.get('analysis_template')
        if analysis_template_id:
            # 既存の分析値を削除（テンプレートが変更された場合に対応）
            DiaryAnalysisValue.objects.filter(diary_id=self.object.id).delete()
            
            # 新しい分析値を処理
            process_analysis_values(self.request, self.object, analysis_template_id)
        
        return response


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
        messages.success(self.request, "継続記録を追加しました")
        return super().form_valid(form)
    
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
            diaries = diaries.order_by('-purchase_date')
        elif sort == 'date_asc':
            diaries = diaries.order_by('purchase_date')
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