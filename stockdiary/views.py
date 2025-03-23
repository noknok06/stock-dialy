from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
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
from django.views.generic import View

from .models import StockDiary, DiaryNote
from .forms import StockDiaryForm, DiaryNoteForm
from tags.models import Tag
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from analysis_template.forms import create_analysis_value_formset
from utils.mixins import ObjectNotFoundRedirectMixin

import json
import re
from decimal import Decimal
from datetime import timedelta
from collections import Counter, defaultdict
import secrets
import random


# stockdiary/views.py のStockDiaryListViewクラスを修正
class StockDiaryListView(LoginRequiredMixin, ListView):
    model = StockDiary
    template_name = 'stockdiary/home.html'
    context_object_name = 'diaries'
    paginate_by = 9  # 1ページに表示する日記の数（3×3のグリッド）
    
    # process_checklist_items メソッドを削除
    
    def get_queryset(self):
        queryset = StockDiary.objects.filter(user=self.request.user).order_by('-purchase_date')
        
        # 検索フィルター
        query = self.request.GET.get('query', '')
        tag_id = self.request.GET.get('tag', '')
        
        if query:
            queryset = queryset.filter(
                Q(stock_name__icontains=query) | 
                Q(stock_symbol__icontains=query)
            )
        
        if tag_id:
            queryset = queryset.filter(tags__id=tag_id)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tags'] = Tag.objects.filter(user=self.request.user)
        
        # カレンダー表示用にすべての日記データを追加
        # select_related を使用しつつ、不要なフィールドを defer で除外
        diaries_query = StockDiary.objects.filter(user=self.request.user)
        
        # select_related が必要な場合は使用
        # diaries_query = diaries_query.select_related('user')
        
        # 不要なフィールドを defer で除外
        context['all_diaries'] = diaries_query.defer(
            'reason', 'memo', 'created_at', 'updated_at',
            # その他の大きいフィールドやカレンダー表示に不要なフィールド
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
                profit = 0  # あるいは別の適切なデフォルト値
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
        form_actions = [
            {
                'type': 'add',
                'url': reverse_lazy('stockdiary:create'),
                'icon': 'bi-plus-lg',
                'label': '新規作成'
            },
            {
                'type': 'template',
                'url': reverse_lazy('analysis_template:list'),
                'icon': 'bi-clipboard-data',
                'label': 'テンプレート'
            },
            {
                'type': 'tag',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-tags',
                'label': 'タグ管理'
            },
            {
                'type': 'snap',
                'url': reverse_lazy('portfolio:list'),
                'icon': 'bi-camera',
                'label': 'スナップショット'
            }
        ]
        context['form_actions'] = form_actions
        return context
# stockdiary/views.py のStockDiaryDetailViewを修正
# views.py の修正方法

class StockDiaryDetailView(ObjectNotFoundRedirectMixin, LoginRequiredMixin, DetailView):
    model = StockDiary
    template_name = 'stockdiary/detail.html'
    context_object_name = 'diary'
    redirect_url = 'stockdiary:home'
    not_found_message = "日記エントリーが見つかりません。削除された可能性があります。"
    
    def get_queryset(self):
        return StockDiary.objects.filter(user=self.request.user)
    
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
        
        # スピードダイアルのアクションを定義
        # この部分を追加 ↓
        diary = self.object
        diary_actions = [
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
            # ここに売却取消アクションを追加
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
        context['diary_actions'] = diary_actions  # この行を必ず追加する
        
        return context

class StockDiaryCreateView(LoginRequiredMixin, CreateView):
    model = StockDiary
    form_class = StockDiaryForm
    template_name = 'stockdiary/diary_form.html'
    success_url = reverse_lazy('stockdiary:home')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # フォーム用のスピードダイアルアクション
        form_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'template',
                'url': reverse_lazy('analysis_template:list'),
                'icon': 'bi-clipboard-data',
                'label': 'テンプレート'
            },
            {
                'type': 'tag',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-tags',
                'label': 'タグ管理'
            }
        ]
        context['form_actions'] = form_actions
        
        return context


    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # ユーザーを設定
        form.instance.user = self.request.user
        
        # 保存する前に分析テンプレートID取得
        analysis_template_id = self.request.POST.get('analysis_template')
        
        # 親クラスのform_validを呼び出し、レスポンスを取得
        response = super().form_valid(form)
        
        # チェックリスト項目のステータスを処理する部分を削除
        
        # 分析テンプレートが選択されていれば、分析値を処理
        if analysis_template_id:
            self.process_analysis_values(analysis_template_id)
        
        return response

    # process_checklist_items メソッドを削除
    def process_analysis_values(self, template_id):
        """分析テンプレート値を処理する"""
        try:
            template = AnalysisTemplate.objects.get(id=template_id, user=self.request.user)
            
            # テンプレートの各項目を取得
            items = template.items.all()
            
            # 各項目の値を保存
            for item in items:
                item_id = item.id
                
                # 複合型の場合、boolean値と実際の値（数値またはテキスト）を両方処理
                if item.item_type == 'boolean_with_value':
                    boolean_field_name = f'analysis_item_{item_id}_boolean'
                    value_field_name = f'analysis_item_{item_id}_value'
                    
                    boolean_value = boolean_field_name in self.request.POST
                    actual_value = self.request.POST.get(value_field_name, '')
                    
                    # 少なくとも1つの値がある場合のみレコードを作成
                    if boolean_value or actual_value:
                        analysis_value = DiaryAnalysisValue(
                            diary=self.object,
                            analysis_item=item,
                            boolean_value=boolean_value
                        )
                        
                        # 実際の値が数値かテキストか判断して適切なフィールドに設定
                        try:
                            float_value = float(actual_value)
                            analysis_value.number_value = float_value
                        except (ValueError, TypeError):
                            if actual_value:
                                analysis_value.text_value = actual_value
                        
                        analysis_value.save()
                    
                elif item.item_type == 'boolean':
                    # 通常のチェックボックス
                    field_name = f'analysis_item_{item_id}'
                    boolean_value = field_name in self.request.POST
                    
                    analysis_value = DiaryAnalysisValue(
                        diary=self.object,
                        analysis_item=item,
                        boolean_value=boolean_value
                    )
                    
                    analysis_value.save()
                    
                elif item.item_type == 'number':
                    # 数値型
                    field_name = f'analysis_item_{item_id}'
                    value = self.request.POST.get(field_name, '')
                    
                    if value:
                        try:
                            number_value = float(value)
                            analysis_value = DiaryAnalysisValue(
                                diary=self.object,
                                analysis_item=item,
                                number_value=number_value
                            )
                            analysis_value.save()
                        except ValueError:
                            # 数値変換エラーの場合はスキップ
                            pass
                            
                else:  # text または select
                    # テキスト型または選択肢型
                    field_name = f'analysis_item_{item_id}'
                    value = self.request.POST.get(field_name, '')
                    
                    if value:
                        analysis_value = DiaryAnalysisValue(
                            diary=self.object,
                            analysis_item=item,
                            text_value=value
                        )
                        analysis_value.save()
                    
        except AnalysisTemplate.DoesNotExist:
            pass  # テンプレートが存在しない場合は何もしない

    def process_checklist_items(self):
        """チェックリスト項目のステータスを処理する"""
        from checklist.models import DiaryChecklistItem, ChecklistItem
        
        # リクエストからチェックリスト項目のステータスを取得
        item_statuses = {}
        
        for key, value in self.request.POST.items():
            if key.startswith('checklist_item_status[') and key.endswith(']'):
                # キーから項目IDを抽出
                item_id_str = key[len('checklist_item_status['):-1]
                try:
                    item_id = int(item_id_str)
                    item_statuses[item_id] = value == '1' or value == 'on' or value == 'true'
                except ValueError:
                    continue
        
        if not item_statuses:
            return  # ステータスがなければ何もしない
        
        # 既存のDiaryChecklistItemを取得
        existing_items = DiaryChecklistItem.objects.filter(diary=self.object)
        existing_item_ids = {item.checklist_item_id: item for item in existing_items}
        
        # チェックリスト項目IDのリストを取得
        checklist_item_ids = list(item_statuses.keys())
        
        # 存在するチェックリスト項目を確認
        valid_items = ChecklistItem.objects.filter(id__in=checklist_item_ids)
        valid_item_ids = {item.id for item in valid_items}
        
        # 項目ごとにDiaryChecklistItemを作成または更新
        for item_id, status in item_statuses.items():
            if item_id not in valid_item_ids:
                continue  # 無効な項目IDはスキップ
            
            if item_id in existing_item_ids:
                # 既存のアイテムを更新
                diary_item = existing_item_ids[item_id]
                diary_item.status = status
                diary_item.save()
            else:
                # 新しいアイテムを作成
                DiaryChecklistItem.objects.create(
                    diary=self.object,
                    checklist_item_id=item_id,
                    status=status
                )
                
class StockDiaryUpdateView(ObjectNotFoundRedirectMixin, LoginRequiredMixin, UpdateView):
    model = StockDiary
    form_class = StockDiaryForm
    template_name = 'stockdiary/diary_form.html'
    redirect_url = 'stockdiary:home'
    not_found_message = "日記エントリーが見つかりません。削除された可能性があります。"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # フォーム用のスピードダイアルアクション
        form_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:detail', kwargs={'pk': self.object.pk}),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'template',
                'url': reverse_lazy('analysis_template:list'),
                'icon': 'bi-clipboard-data',
                'label': 'テンプレート'
            },
            {
                'type': 'tag',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-tags',
                'label': 'タグ管理'
            }
        ]
        context['form_actions'] = form_actions
        
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
        # 分析テンプレートID取得
        analysis_template_id = self.request.POST.get('analysis_template')
        
        # 親クラスのform_validを呼び出し
        response = super().form_valid(form)
        
        # 分析テンプレートが選択されていれば、分析値を処理
        if analysis_template_id:
            # 既存の分析値を削除（テンプレートが変更された場合に対応）
            diary_id = self.object.id
            DiaryAnalysisValue.objects.filter(diary_id=diary_id).delete()
            
            # 新しい分析値を処理
            self.process_analysis_values(analysis_template_id)
        
        return response
    
    def process_analysis_values(self, template_id):
        """分析テンプレート値を処理する"""
        try:
            template = AnalysisTemplate.objects.get(id=template_id, user=self.request.user)
            
            # テンプレートの各項目を取得
            items = template.items.all()
            
            # 各項目の値を保存
            for item in items:
                item_id = item.id
                
                # 複合型の場合、boolean値と実際の値（数値またはテキスト）を両方処理
                if item.item_type == 'boolean_with_value':
                    boolean_field_name = f'analysis_item_{item_id}_boolean'
                    value_field_name = f'analysis_item_{item_id}_value'
                    
                    boolean_value = boolean_field_name in self.request.POST
                    actual_value = self.request.POST.get(value_field_name, '')
                    
                    # 少なくとも1つの値がある場合のみレコードを作成
                    if boolean_value or actual_value:
                        analysis_value = DiaryAnalysisValue(
                            diary=self.object,
                            analysis_item=item,
                            boolean_value=boolean_value
                        )
                        
                        # 実際の値が数値かテキストか判断して適切なフィールドに設定
                        try:
                            float_value = float(actual_value)
                            analysis_value.number_value = float_value
                        except (ValueError, TypeError):
                            if actual_value:
                                analysis_value.text_value = actual_value
                        
                        analysis_value.save()
                
                elif item.item_type == 'boolean':
                    # 通常のチェックボックス
                    field_name = f'analysis_item_{item_id}'
                    boolean_value = field_name in self.request.POST
                    
                    analysis_value = DiaryAnalysisValue(
                        diary=self.object,
                        analysis_item=item,
                        boolean_value=boolean_value
                    )
                    
                    analysis_value.save()
                    
                elif item.item_type == 'number':
                    # 数値型
                    field_name = f'analysis_item_{item_id}'
                    value = self.request.POST.get(field_name, '')
                    
                    if value:
                        try:
                            number_value = float(value)
                            analysis_value = DiaryAnalysisValue(
                                diary=self.object,
                                analysis_item=item,
                                number_value=number_value
                            )
                            analysis_value.save()
                        except ValueError:
                            # 数値変換エラーの場合はスキップ
                            pass
                            
                else:  # text または select
                    # テキスト型または選択肢型
                    field_name = f'analysis_item_{item_id}'
                    value = self.request.POST.get(field_name, '')
                    
                    if value:
                        analysis_value = DiaryAnalysisValue(
                            diary=self.object,
                            analysis_item=item,
                            text_value=value
                        )
                        analysis_value.save()
                    
        except AnalysisTemplate.DoesNotExist:
            pass  # テンプレートが存在しない場合は何もしない               
class StockDiaryDeleteView(LoginRequiredMixin, DeleteView):
    model = StockDiary
    template_name = 'stockdiary/diary_confirm_delete.html'
    success_url = reverse_lazy('stockdiary:home')
    
    def get_queryset(self):
        return StockDiary.objects.filter(user=self.request.user)

   
# 既存のStockDiaryListViewとその他のクラスは変更なし
class DiaryAnalyticsView(LoginRequiredMixin, TemplateView):
    """投資記録分析ダッシュボードを表示するビュー"""
    template_name = 'stockdiary/analytics_dashboard.html'
    
    # DiaryAnalyticsView の get_context_data メソッドの修正部分

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # フィルターパラメータの取得
        date_range = self.request.GET.get('date_range', 'all')
        selected_tag = self.request.GET.get('tag', '')
        status = self.request.GET.get('status', 'all')
        sort = self.request.GET.get('sort', 'date_desc')
        
        # フィルターパラメータの準備
        filter_params = {
            'date_from': None,
            'tag_id': selected_tag,
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
        
        # 基本データの取得
        diaries = self.get_filtered_diaries(user, filter_params, sort)
        all_diaries = StockDiary.objects.filter(user=user)
        tags = Tag.objects.filter(user=user).distinct()
        
        # 保有中と売却済みの株式を分離 (メモかどうかの判定は保持)
        active_diaries = [d for d in diaries if not d.sell_date]
        sold_diaries = [d for d in diaries if d.sell_date]
        
        # 1. 統計データの収集
        stats = self.collect_stats(user, diaries, all_diaries)
        
        # 2. 投資状況サマリー関連のデータ
        investment_data = self.get_investment_summary_data(user, diaries, all_diaries, active_diaries, sold_diaries)
        
        # 3. タグ分析データの取得
        tag_data = self.get_tag_analysis_data(user, diaries)
        
        # 4. 分析テンプレートデータの取得
        template_data = self.get_template_analysis_data(user, filter_params)
        
        # 5. 活動分析データの取得
        activity_data = self.get_activity_analysis_data(user, diaries, all_diaries)
        
        # 既存の分析データ準備コードを呼び出す
        monthly_data = self.prepare_monthly_data(diaries)
        day_of_week_data = self.prepare_day_of_week_data(diaries)
        activity_heatmap = self.prepare_activity_heatmap(diaries)
        content_length_data = self.prepare_content_length_data(diaries)
        tag_frequency_data = self.prepare_tag_frequency_data(diaries)
        tag_timeline_data = self.prepare_tag_timeline_data(diaries)
        tag_correlation_data = self.prepare_tag_correlation_data(diaries)
        template_usage_data = self.prepare_template_usage_data(diaries)
        template_timeline_data = self.prepare_template_timeline_data(diaries)
        template_item_stats = self.prepare_template_item_stats(diaries)
        timeline_data = self.prepare_timeline_data(diaries)
        recent_trends = self.prepare_recent_trends(diaries)
        holding_period_data = self.prepare_holding_period_data(diaries)
        
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
                'url': reverse_lazy('tags:list'),  # タグ管理ページのURL
                'icon': 'bi-tags',
                'label': 'タグ管理'
            },
            {
                'type': 'template',
                'url': reverse_lazy('analysis_template:list'),  # テンプレート分析ページのURL
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
            
            # 既存のデータを追加
            'monthly_labels': json.dumps(monthly_data['labels']),
            'monthly_counts': json.dumps(monthly_data['counts']),
            'day_of_week_counts': json.dumps(list(day_of_week_data)),
            'activity_heatmap': activity_heatmap,
            'content_length_ranges': json.dumps(content_length_data['ranges']),
            'content_length_counts': json.dumps(content_length_data['counts']),
            'tag_names': json.dumps(tag_frequency_data['names']),
            'tag_counts': json.dumps(tag_frequency_data['counts']),
            'tag_timeline_labels': json.dumps(tag_timeline_data['labels']),
            'tag_timeline_data': mark_safe(json.dumps(tag_timeline_data['datasets'])),
            'top_tags': tag_correlation_data,
            'template_names': json.dumps(template_usage_data['names']),
            'template_usage_rates': json.dumps(template_usage_data['rates']),
            'template_timeline_labels': json.dumps(template_timeline_data['labels']),
            'template_timeline_data': json.dumps(template_timeline_data['rates']),
            'template_stats': template_item_stats,
            'diary_timeline': timeline_data,
            'purchase_frequency': recent_trends['purchase_frequency'],
            'most_used_tag': recent_trends['most_used_tag'],
            'most_detailed_record': recent_trends['most_detailed_record'],
            'recent_keywords': recent_trends['keywords'],
            'holding_period_ranges': json.dumps(holding_period_data['ranges']),
            'holding_period_counts': json.dumps(holding_period_data['counts']),
        })
        
        return context            
    def get_current_prices(self, stock_symbols):
        """銘柄コードから現在の株価を取得する関数"""
        # デモ用に擬似的な株価データを生成
        prices = {}
        for symbol in stock_symbols:
            # 実際のAPIが実装されるまで、購入価格に基づいた擬似的な株価を生成
            # 対応する日記を検索して購入価格を取得
            diary = None
            try:
                # 最新の日記を取得
                diary = StockDiary.objects.filter(
                    user=self.request.user,
                    stock_symbol=symbol,
                    sell_date__isnull=True
                ).latest('purchase_date')
            except StockDiary.DoesNotExist:
                pass
            
            if diary:
                # ランダムな価格変動を適用（-15%〜+15%）
                base_price = float(diary.purchase_price)
                random_factor = 0.85 + (secrets.SystemRandom().random() * 0.3)  # セキュアな乱数生成
                current_price = base_price * random_factor
                prices[symbol] = round(current_price, 2)
            else:
                # 日記が見つからない場合はデフォルト値
                prices[symbol] = 1000.0
        
        return prices
    
    def get_analysis_template_stats(self, diaries):
        """分析テンプレートの統計情報を取得"""
        # 使用率を計算
        total_completion = 0
        completion_count = 0
        
        # 日記IDのリストを取得（効率化のため）
        diary_ids = list(diaries.values_list('id', flat=True))
        
        if not diary_ids:
            return {
                'avg_completion_rate': 0,
                'change': 0
            }
        
        # 一度に必要な分析値を取得
        diary_analysis_values = DiaryAnalysisValue.objects.filter(
            diary_id__in=diary_ids
        ).select_related('analysis_item__template')
        
        # 日記ごとの分析値を整理
        diary_values_map = defaultdict(list)
        for value in diary_analysis_values:
            diary_values_map[value.diary_id].append(value)
        
        for diary in diaries:
            diary_values = diary_values_map.get(diary.id, [])
            
            # 各日記の分析テンプレートを取得
            templates_used = set()
            for value in diary_values:
                templates_used.add(value.analysis_item.template_id)
            
            for template_id in templates_used:
                try:
                    template = AnalysisTemplate.objects.get(id=template_id)
                    items = template.items.all()
                    total_items = items.count()
                    
                    if total_items > 0:
                        # テンプレート項目への入力率を計算
                        filled_items = 0
                        for item in items:
                            # この日記のこの項目の値があるか確認
                            has_value = False
                            for value in diary_values:
                                if value.analysis_item_id == item.id:
                                    # 項目タイプに応じて値が存在するか確認
                                    if item.item_type == 'number' and value.number_value is not None:
                                        has_value = True
                                    elif item.item_type == 'boolean' and value.boolean_value is not None:
                                        has_value = True
                                    elif item.item_type == 'boolean_with_value' and (value.boolean_value is not None or value.number_value is not None or value.text_value):
                                        has_value = True
                                    elif value.text_value:
                                        has_value = True
                                    break
                            
                            if has_value:
                                filled_items += 1
                        
                        completion_rate = (filled_items / total_items) * 100
                        total_completion += completion_rate
                        completion_count += 1
                except AnalysisTemplate.DoesNotExist:
                    pass
        
        avg_completion_rate = 0
        if completion_count > 0:
            avg_completion_rate = total_completion / completion_count
        
        # 前月との比較
        last_month = timezone.now().date() - timedelta(days=30)
        last_month_diaries = StockDiary.objects.filter(
            user=self.request.user, 
            purchase_date__lt=last_month
        )
        
        last_month_total = 0
        last_month_count = 0
        
        # 前月の日記IDリスト
        last_month_diary_ids = list(last_month_diaries.values_list('id', flat=True))
        
        if last_month_diary_ids:
            # 前月の分析値
            last_month_values = DiaryAnalysisValue.objects.filter(
                diary_id__in=last_month_diary_ids
            ).select_related('analysis_item__template')
            
            # 日記ごとの分析値をマッピング
            last_month_values_map = defaultdict(list)
            for value in last_month_values:
                last_month_values_map[value.diary_id].append(value)
            
            for diary in last_month_diaries:
                diary_values = last_month_values_map.get(diary.id, [])
                
                # 各日記のテンプレートを取得
                templates_used = set()
                for value in diary_values:
                    templates_used.add(value.analysis_item.template_id)
                
                for template_id in templates_used:
                    try:
                        template = AnalysisTemplate.objects.get(id=template_id)
                        items = template.items.all()
                        total_items = items.count()
                        
                        if total_items > 0:
                            # テンプレート項目への入力率を計算
                            filled_items = 0
                            for item in items:
                                # この日記のこの項目の値があるか確認
                                has_value = False
                                for value in diary_values:
                                    if value.analysis_item_id == item.id:
                                        # 項目タイプに応じて値が存在するか確認
                                        if item.item_type == 'number' and value.number_value is not None:
                                            has_value = True
                                        elif item.item_type == 'boolean' and value.boolean_value is not None:
                                            has_value = True
                                        elif item.item_type == 'boolean_with_value' and (value.boolean_value is not None or value.number_value is not None or value.text_value):
                                            has_value = True
                                        elif value.text_value:
                                            has_value = True
                                        break
                                
                                if has_value:
                                    filled_items += 1
                            
                            completion_rate = (filled_items / total_items) * 100
                            last_month_total += completion_rate
                            last_month_count += 1
                    except AnalysisTemplate.DoesNotExist:
                        pass
        
        last_month_avg = 0
        if last_month_count > 0:
            last_month_avg = last_month_total / last_month_count
        
        change = avg_completion_rate - last_month_avg
        
        return {
            'avg_completion_rate': avg_completion_rate,
            'change': change
        }
    
    def get_filtered_diaries(self, user, filter_params, sort='date_desc'):
        """フィルター条件に基づいて日記を取得"""
        diaries = StockDiary.objects.filter(user=user)
        
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
    
    # collect_stats メソッドの修正

    def collect_stats(self, user, diaries, all_diaries):
        """基本的な統計データを収集"""
        from django.db.models import Avg, Sum, Count, F, ExpressionWrapper, fields
        from django.db.models.functions import Length
        
        # 現在の月の開始日
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        
        # 前月の日付範囲
        prev_month_end = current_month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        
        # 銘柄数の統計 - メモを含めてすべてカウント
        total_stocks = diaries.count()
        prev_month_stocks = all_diaries.filter(
            created_at__gte=prev_month_start,
            created_at__lt=current_month_start
        ).count()
        stocks_change = total_stocks - prev_month_stocks
        
        # タグの統計
        total_tags = Tag.objects.filter(stockdiary__in=diaries).distinct().count()
        prev_month_tags = Tag.objects.filter(
            stockdiary__in=all_diaries,
            stockdiary__created_at__gte=prev_month_start,
            stockdiary__created_at__lt=current_month_start
        ).distinct().count()
        tags_change = total_tags - prev_month_tags
        
        # 分析項目達成率
        # 現在の平均完了率
        current_completion = self.calculate_analysis_completion_rate(user, diaries)
        
        # 前月の平均完了率
        prev_month_diaries = all_diaries.filter(
            created_at__gte=prev_month_start,
            created_at__lt=current_month_start
        )
        prev_completion = self.calculate_analysis_completion_rate(user, prev_month_diaries)
        
        checklist_completion_rate = current_completion
        checklist_rate_change = current_completion - prev_completion
        
        # 平均記録文字数 - すべてのエントリーを対象（メモも含む）
        avg_reason_length = 0
        if diaries.exists():
            # HTMLタグを除去して純粋なテキスト長を計算
            reason_lengths = []
            for diary in diaries:
                raw_text = strip_tags(diary.reason)
                reason_lengths.append(len(raw_text))
            
            if reason_lengths:
                avg_reason_length = int(sum(reason_lengths) / len(reason_lengths))
        
        # 前月の平均記録文字数
        last_month_avg_length = 0
        if prev_month_diaries.exists():
            last_month_lengths = []
            for diary in prev_month_diaries:
                raw_text = strip_tags(diary.reason)
                last_month_lengths.append(len(raw_text))
            
            if last_month_lengths:
                last_month_avg_length = int(sum(last_month_lengths) / len(last_month_lengths))
        
        reason_length_change = avg_reason_length - last_month_avg_length
        
        return {
            'total_stocks': total_stocks,
            'stocks_change': stocks_change,
            'total_tags': total_tags,
            'tags_change': tags_change,
            'checklist_completion_rate': checklist_completion_rate,
            'checklist_rate_change': checklist_rate_change,
            'avg_reason_length': avg_reason_length,
            'reason_length_change': reason_length_change
        }    
    
    def calculate_analysis_completion_rate(self, user, diaries):
        """分析項目の平均完了率を計算"""
        if not diaries.exists():
            return 0
        
        diary_ids = diaries.values_list('id', flat=True)
        
        # 日記に対する分析値を取得
        analysis_values = DiaryAnalysisValue.objects.filter(
            diary_id__in=diary_ids
        ).select_related('analysis_item')
        
        # 日記IDごとに分析値をグループ化
        diary_values = {}
        for value in analysis_values:
            diary_id = value.diary_id
            if diary_id not in diary_values:
                diary_values[diary_id] = {
                    'template_items': {},
                    'completed_items': 0,
                    'total_items': 0
                }
            
            template_id = value.analysis_item.template_id
            if template_id not in diary_values[diary_id]['template_items']:
                diary_values[diary_id]['template_items'][template_id] = {
                    'items': [],
                    'completed': 0,
                    'total': 0
                }
            
            diary_values[diary_id]['template_items'][template_id]['items'].append(value)
        
        # 各日記の各テンプレートの項目数を取得
        for diary_id, data in diary_values.items():
            for template_id, template_data in data['template_items'].items():
                template = AnalysisTemplate.objects.get(id=template_id)
                total_items = template.items.count()
                template_data['total'] = total_items
                
                # 完了項目数を計算
                for value in template_data['items']:
                    if value.analysis_item.item_type == 'boolean' or value.analysis_item.item_type == 'boolean_with_value':
                        if value.boolean_value:
                            template_data['completed'] += 1
                    elif value.analysis_item.item_type == 'number':
                        if value.number_value is not None:
                            template_data['completed'] += 1
                    elif value.analysis_item.item_type == 'select' or value.analysis_item.item_type == 'text':
                        if value.text_value:
                            template_data['completed'] += 1
                
                data['completed_items'] += template_data['completed']
                data['total_items'] += template_data['total']
        
        # 全体の完了率を計算
        total_completed = 0
        total_items = 0
        for data in diary_values.values():
            total_completed += data['completed_items']
            total_items += data['total_items']
        
        completion_rate = (total_completed / total_items * 100) if total_items > 0 else 0
        return completion_rate
        
    def get_tag_analysis_data(self, user, diaries):
        """タグ分析データを取得"""
        from django.db.models import Count, Avg, Sum, F, ExpressionWrapper, fields
        from django.db.models.functions import TruncMonth
        from collections import defaultdict
        import json
        
        # タグ使用頻度
        tag_counts = Tag.objects.filter(
            stockdiary__in=diaries
        ).annotate(
            count=Count('stockdiary')
        ).order_by('-count')
        
        # 上位10件のタグ
        top_tags = list(tag_counts[:10])
        
        # タグ名とカウントのリスト
        tag_names = [tag.name for tag in top_tags]
        tag_counts_list = [tag.count for tag in top_tags]
        
        # タグの合計使用回数
        total_tag_usage = sum(tag_counts_list) if tag_counts_list else 0
        
        # タグごとのパーセンテージを計算
        for tag in top_tags:
            tag.percentage = (tag.count / total_tag_usage * 100) if total_tag_usage > 0 else 0
        
        # タグごとの投資パフォーマンス
        tag_performance = []
        most_profitable_tag = None
        max_profit_rate = -999  # 最も低い値で初期化
        
        for tag in tag_counts:
            # タグが付いた日記を取得
            tag_diaries = diaries.filter(tags=tag)
            
            # 平均保有期間
            avg_holding_period = 0
            profit_rate_sum = 0
            profit_sum = 0
            count_with_profit = 0
            
            for diary in tag_diaries:
                # 価格・数量情報があるエントリーのみ処理
                if diary.sell_date and diary.purchase_price is not None and diary.purchase_quantity is not None and diary.sell_price is not None:
                    try:
                        # 保有期間
                        holding_period = (diary.sell_date - diary.purchase_date).days
                        avg_holding_period += holding_period
                        
                        # 収益率
                        profit_rate = ((diary.sell_price - diary.purchase_price) / diary.purchase_price) * 100
                        profit_rate_sum += profit_rate
                        
                        # 総利益
                        profit = (diary.sell_price - diary.purchase_price) * diary.purchase_quantity
                        profit_sum += profit
                        
                        count_with_profit += 1
                    except (TypeError, ZeroDivisionError):
                        # 価格が0やNoneの場合のエラー処理
                        continue

            # デフォルト値を設定
            avg_profit_rate = 0
            
            if count_with_profit > 0:
                avg_holding_period /= count_with_profit
                avg_profit_rate = profit_rate_sum / count_with_profit
            
            # 最も収益率の高いタグを更新
            if avg_profit_rate > max_profit_rate:
                max_profit_rate = avg_profit_rate
                most_profitable_tag = tag.name
            
            tag_performance.append({
                'name': tag.name,
                'count': tag.count,
                'avg_holding_period': round(avg_holding_period, 1),
                'avg_profit_rate': round(avg_profit_rate, 2),
                'total_profit': profit_sum
            })
        
        # タグの時系列使用状況
        six_months_ago = timezone.now() - timedelta(days=180)
        tag_timeline = StockDiary.objects.filter(
            user=user,
            purchase_date__gte=six_months_ago
        ).prefetch_related('tags').annotate(
            month=TruncMonth('purchase_date')
        )
        
        # 月ごとにタグの使用回数を集計
        tag_month_data = defaultdict(lambda: defaultdict(int))
        
        for diary in tag_timeline:
            month_str = diary.month.strftime('%Y-%m')
            for tag in diary.tags.all():
                tag_month_data[month_str][tag.id] += 1
        
        # 月のリストを生成（過去6ヶ月）
        months = []
        current = timezone.now()
        for i in range(5, -1, -1):
            month = (current - timedelta(days=30 * i)).strftime('%Y-%m')
            months.append(month)
        
        # 上位5タグの時系列データを準備
        top_5_tags = tag_counts[:5]
        tag_timeline_data = []
        
        for tag in top_5_tags:
            data_points = [tag_month_data[month].get(tag.id, 0) for month in months]
            tag_timeline_data.append({
                'label': tag.name,
                'data': data_points,
                'borderColor': f'rgba({hash(tag.name) % 255}, {(hash(tag.name) * 2) % 255}, {(hash(tag.name) * 3) % 255}, 0.7)',
                'backgroundColor': f'rgba({hash(tag.name) % 255}, {(hash(tag.name) * 2) % 255}, {(hash(tag.name) * 3) % 255}, 0.1)',
                'fill': True,
                'tension': 0.4
            })
        
        return {
            'tag_names': json.dumps(tag_names),
            'tag_counts': json.dumps(tag_counts_list),
            'top_tags': top_tags,
            'most_profitable_tag': most_profitable_tag if most_profitable_tag else "データなし",
            'tag_performance': tag_performance,
            'tag_timeline_labels': json.dumps(months),
            'tag_timeline_data': json.dumps(tag_timeline_data)
        }
  
    def get_template_analysis_data(self, user, filter_params=None):
        """分析テンプレートのデータを取得・分析する関数"""
        from django.db.models import Count, Avg, Max, Min, F, Q, Case, When, Value, IntegerField, FloatField
        from django.db.models.functions import Coalesce, TruncMonth
        from datetime import timedelta
        import json
        from collections import defaultdict, Counter
        
        # 基本的なフィルタリング - ユーザーのデータのみ
        templates = AnalysisTemplate.objects.filter(user=user)
        template_ids = list(templates.values_list('id', flat=True))
        
        # 日記に紐づく分析値を取得
        analysis_values = DiaryAnalysisValue.objects.filter(
            analysis_item__template__id__in=template_ids,
            diary__user=user
        ).select_related('diary', 'analysis_item', 'analysis_item__template')
        
        # フィルターが提供されている場合の絞り込み
        if filter_params:
            if 'date_from' in filter_params and filter_params['date_from']:
                analysis_values = analysis_values.filter(diary__purchase_date__gte=filter_params['date_from'])
            if 'tag_id' in filter_params and filter_params['tag_id']:
                analysis_values = analysis_values.filter(diary__tags__id=filter_params['tag_id'])
            if 'status' in filter_params and filter_params['status'] == 'active':
                analysis_values = analysis_values.filter(diary__sell_date__isnull=True)
            elif 'status' in filter_params and filter_params['status'] == 'sold':
                analysis_values = analysis_values.filter(diary__sell_date__isnull=False)
        
        # テンプレート使用統計データの収集
        template_stats = []
        template_usage_counts = {}
        
        # テンプレートIDごとに分析値をグループ化
        template_values = defaultdict(list)
        for value in analysis_values:
            template_id = value.analysis_item.template.id
            template_values[template_id].append(value)
        
        for template in templates:
            # このテンプレートの分析値
            values = template_values.get(template.id, [])
            
            # 使用回数計算 - ユニークな日記IDの数
            diary_ids = set(v.diary_id for v in values)
            usage_count = len(diary_ids)
            template_usage_counts[template.id] = usage_count
            
            # 最新の使用日を取得
            last_used = None
            if values:
                latest_values = sorted(values, key=lambda x: x.diary.purchase_date, reverse=True)
                if latest_values:
                    last_used = latest_values[0].diary.purchase_date
            
            # 平均完了率の計算 - 各日記ごとの完了項目数/全項目数
            total_items = template.items.count()
            completion_rates = []
            
            # 日記ごとに完了率を計算
            for diary_id in diary_ids:
                diary_values = [v for v in values if v.diary_id == diary_id]
                completed_items = 0
                
                for value in diary_values:
                    if value.analysis_item.item_type == 'boolean' or value.analysis_item.item_type == 'boolean_with_value':
                        if value.boolean_value:
                            completed_items += 1
                    elif value.analysis_item.item_type == 'number':
                        if value.number_value is not None:
                            completed_items += 1
                    elif value.analysis_item.item_type == 'select' or value.analysis_item.item_type == 'text':
                        if value.text_value:
                            completed_items += 1
                
                if total_items > 0:
                    completion_rate = (completed_items / total_items) * 100
                    completion_rates.append(completion_rate)
            
            avg_completion_rate = sum(completion_rates) / len(completion_rates) if completion_rates else 0
            
            # 使用トレンドの計算（過去3ヶ月と比較した前月）
            trend = 0
            if usage_count > 0:
                # 前月の使用回数
                one_month_ago = timezone.now() - timedelta(days=30)
                two_months_ago = timezone.now() - timedelta(days=60)
                
                prev_month_count = DiaryAnalysisValue.objects.filter(
                    analysis_item__template_id=template.id,
                    diary__user=user,
                    diary__purchase_date__gte=two_months_ago,
                    diary__purchase_date__lt=one_month_ago
                ).values('diary').distinct().count()
                
                if prev_month_count > 0:
                    # 前月と比較した成長率
                    trend = ((usage_count - prev_month_count) / prev_month_count) * 100
                else:
                    trend = 100 if usage_count > 0 else 0
            
            template_stats.append({
                'id': template.id,
                'name': template.name,
                'usage_count': usage_count,
                'avg_completion_rate': avg_completion_rate,
                'last_used': last_used,
                'trend': trend
            })
        
        # テンプレート種類別の分布
        template_categories = {
            '財務分析': ['PER', 'PBR', 'ROE', '配当', '収益', '財務', '利益'],
            'テクニカル分析': ['RSI', 'MACD', 'ボリンジャー', '移動平均', 'チャート'],
            'ファンダメンタル分析': ['成長', '競争', '優位', '市場'],
            'バリュー投資': ['割安', 'バフェット', '長期'],
            '投資心理': ['心理', 'バイアス', '感情'],
            'ESG評価': ['ESG', '環境', '社会', 'ガバナンス']
        }
        
        template_type_data = defaultdict(int)
        template_type_labels = []
        
        for template in templates:
            categorized = False
            for category, keywords in template_categories.items():
                if any(keyword in template.name or keyword in template.description for keyword in keywords):
                    template_type_data[category] += template_usage_counts.get(template.id, 0)
                    if category not in template_type_labels:
                        template_type_labels.append(category)
                    categorized = True
                    break
            
            if not categorized:
                template_type_data['その他'] += template_usage_counts.get(template.id, 0)
                if 'その他' not in template_type_labels:
                    template_type_labels.append('その他')
        
        # 最もよく使われるテンプレート
        most_used_template = None
        if template_stats:
            most_used = max(template_stats, key=lambda x: x['usage_count'])
            if most_used['usage_count'] > 0:
                most_used_template = {
                    'name': most_used['name'],
                    'count': most_used['usage_count']
                }
        
        # 最も完了率が高いテンプレート
        highest_completion_template = None
        if template_stats:
            highest_completion = max(template_stats, key=lambda x: x['avg_completion_rate'])
            if highest_completion['avg_completion_rate'] > 0:
                highest_completion_template = {
                    'name': highest_completion['name'],
                    'rate': highest_completion['avg_completion_rate']
                }
        
        # 最も改善が見られたテンプレート（トレンド値が最も高い）
        most_improved_template = None
        improved_templates = [t for t in template_stats if t['trend'] > 0]
        if improved_templates:
            most_improved = max(improved_templates, key=lambda x: x['trend'])
            most_improved_template = {
                'name': most_improved['name'],
                'improvement': most_improved['trend']
            }
        
        # テンプレート使用回数の時系列データ
        # 過去6ヶ月の月ごとの使用回数を集計
        six_months_ago = timezone.now() - timedelta(days=180)
        monthly_usage = DiaryAnalysisValue.objects.filter(
            analysis_item__template__id__in=template_ids,
            diary__user=user,
            diary__purchase_date__gte=six_months_ago
        ).annotate(
            month=TruncMonth('diary__purchase_date')
        ).values('month', 'analysis_item__template_id').annotate(
            count=Count('diary_id', distinct=True)
        ).order_by('month')
        
        # 月ごとの使用回数をテンプレート別に集計
        monthly_data = defaultdict(lambda: defaultdict(int))
        for entry in monthly_usage:
            month_str = entry['month'].strftime('%Y-%m')
            template_id = entry['analysis_item__template_id']
            monthly_data[month_str][template_id] = entry['count']
        
        # 月のリストを生成（過去6ヶ月）
        months = []
        current = timezone.now()
        for i in range(5, -1, -1):
            month = (current - timedelta(days=30 * i)).strftime('%Y-%m')
            months.append(month)
        
        # テンプレート使用回数の時系列データをJSON形式で準備
        template_usage_labels = months
        template_usage_data = []
        for template in templates:
            data_points = [monthly_data[month].get(template.id, 0) for month in months]
            template_usage_data.append({
                'name': template.name,
                'data': data_points
            })
        
        # テンプレート完了率の計算（チェックリスト完了率のチャート用）
        checklist_names = []
        checklist_completion_rates = []
        
        for template in template_stats:
            if template['usage_count'] > 0:  # 使用されたテンプレートのみ
                checklist_names.append(template['name'])
                checklist_completion_rates.append(round(template['avg_completion_rate'], 1))
        
        # 分析項目レベルの分析
        items_analysis = []
        
        # 各テンプレートの各項目の使用状況を分析
        for template in templates:
            template_items = template.items.all()
            
            for item in template_items:
                # この分析項目の値を取得
                item_values = [v for v in template_values.get(template.id, []) if v.analysis_item_id == item.id]
                
                # 使用回数
                usage_count = len(item_values)
                
                # 完了率
                completion_count = 0
                for value in item_values:
                    if item.item_type == 'boolean' or item.item_type == 'boolean_with_value':
                        if value.boolean_value:
                            completion_count += 1
                    elif item.item_type == 'number':
                        if value.number_value is not None:
                            completion_count += 1
                    elif item.item_type == 'select' or item.item_type == 'text':
                        if value.text_value:
                            completion_count += 1
                
                completion_rate = (completion_count / usage_count * 100) if usage_count > 0 else 0
                
                # 平均値（数値項目の場合）
                average_value = None
                if item.item_type == 'number' and item_values:
                    number_values = [v.number_value for v in item_values if v.number_value is not None]
                    if number_values:
                        average_value = sum(number_values) / len(number_values)
                
                # 最頻値（選択項目の場合）
                most_common_value = None
                if item.item_type == 'select' and item_values:
                    text_values = [v.text_value for v in item_values if v.text_value]
                    if text_values:
                        counter = Counter(text_values)
                        most_common_value = counter.most_common(1)[0][0]
                
                items_analysis.append({
                    'template_id': template.id,
                    'template_name': template.name,
                    'id': item.id,
                    'name': item.name,
                    'item_type': item.item_type,
                    'usage_count': usage_count,
                    'completion_rate': round(completion_rate, 1),
                    'average_value': average_value,
                    'most_common_value': most_common_value
                })
        
        # 完了率の推移チャート用データ
        completion_trend_labels = months
        completion_trend_data = []
        
        for month in months:
            month_diary_ids = DiaryAnalysisValue.objects.filter(
                analysis_item__template__id__in=template_ids,
                diary__user=user,
                diary__purchase_date__year=int(month.split('-')[0]),
                diary__purchase_date__month=int(month.split('-')[1])
            ).values('diary_id').distinct()
            
            month_completion_rates = []
            
            for diary_id in month_diary_ids:
                diary_id = diary_id['diary_id']
                diary_template_values = defaultdict(list)
                
                diary_values = DiaryAnalysisValue.objects.filter(
                    diary_id=diary_id,
                    analysis_item__template__id__in=template_ids
                ).select_related('analysis_item')
                
                for value in diary_values:
                    template_id = value.analysis_item.template_id
                    diary_template_values[template_id].append(value)
                
                # 各テンプレートごとの完了率を計算
                for template_id, values in diary_template_values.items():
                    template = AnalysisTemplate.objects.get(id=template_id)
                    total_items = template.items.count()
                    completed_items = 0
                    
                    for value in values:
                        if value.analysis_item.item_type == 'boolean' or value.analysis_item.item_type == 'boolean_with_value':
                            if value.boolean_value:
                                completed_items += 1
                        elif value.analysis_item.item_type == 'number':
                            if value.number_value is not None:
                                completed_items += 1
                        elif value.analysis_item.item_type == 'select' or value.analysis_item.item_type == 'text':
                            if value.text_value:
                                completed_items += 1
                    
                    if total_items > 0:
                        completion_rate = (completed_items / total_items) * 100
                        month_completion_rates.append(completion_rate)
            
            avg_month_completion = sum(month_completion_rates) / len(month_completion_rates) if month_completion_rates else 0
            completion_trend_data.append(round(avg_month_completion, 1))
        
        # テンプレート関連のコンテキストデータを整理
        template_context = {
            'template_stats': template_stats,
            'most_used_template': most_used_template,
            'highest_completion_template': highest_completion_template,
            'most_improved_template': most_improved_template,
            'template_usage_labels': json.dumps(template_usage_labels),
            'template_usage_data': json.dumps([sum(entry['data']) for entry in template_usage_data]),
            'template_type_labels': json.dumps(template_type_labels),
            'template_type_data': json.dumps([template_type_data[label] for label in template_type_labels]),
            'checklist_names': json.dumps(checklist_names),
            'checklist_completion_rates': json.dumps(checklist_completion_rates),
            'completion_trend_labels': json.dumps(completion_trend_labels),
            'completion_trend_data': json.dumps(completion_trend_data),
            'items_analysis': items_analysis,
            'all_templates': templates
        }
        
        return template_context
        
    def get_activity_analysis_data(self, user, diaries, all_diaries):
        """活動分析データを取得"""
        from django.db.models import Count
        from django.db.models.functions import TruncMonth
        from datetime import timedelta
        import json
        from collections import defaultdict
        
        # 活動ヒートマップ用のデータ（過去30日間）
        activity_heatmap = []
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        
        for i in range(31):
            day = thirty_days_ago + timedelta(days=i)
            day_count = all_diaries.filter(purchase_date=day).count()
            
            # ヒートマップの強度レベル（0-5）
            if day_count == 0:
                level = 0
            elif day_count == 1:
                level = 1
            elif day_count == 2:
                level = 2
            elif day_count <= 4:
                level = 3
            elif day_count <= 6:
                level = 4
            else:
                level = 5
            
            activity_heatmap.append({
                'date': day.strftime('%Y-%m-%d'),
                'day': day.day,
                'count': day_count,
                'level': level
            })
        
        # 月ごとの記録数
        monthly_data = all_diaries.annotate(
            month=TruncMonth('purchase_date')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        last_6_months = []
        current = timezone.now()
        for i in range(5, -1, -1):
            month = (current - timedelta(days=30 * i))
            last_6_months.append(month.strftime('%Y-%m'))
        
        monthly_counts = []
        for month_str in last_6_months:
            year, month = map(int, month_str.split('-'))
            count = 0
            for data in monthly_data:
                if data['month'].year == year and data['month'].month == month:
                    count = data['count']
                    break
            monthly_counts.append(count)
        
        # 曜日別記録数
        day_of_week_counts = [0] * 7  # 0: 月曜日, 6: 日曜日
        
        for diary in all_diaries:
            day_of_week = diary.purchase_date.weekday()
            day_of_week_counts[day_of_week] += 1
        
        # 最も記録が多い曜日
        max_day_index = day_of_week_counts.index(max(day_of_week_counts))
        weekdays = ['月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日', '日曜日']
        most_active_day = weekdays[max_day_index]
        
        # 平日/週末のパターン
        weekday_sum = sum(day_of_week_counts[:5])
        weekend_sum = sum(day_of_week_counts[5:])
        
        if weekday_sum > weekend_sum * 2:
            weekday_pattern = "主に平日"
        elif weekend_sum > weekday_sum * 2:
            weekday_pattern = "主に週末"
        elif weekday_sum > weekend_sum:
            weekday_pattern = "平日が多め"
        elif weekend_sum > weekday_sum:
            weekday_pattern = "週末が多め"
        else:
            weekday_pattern = "平日と週末で均等"
        
        # 月平均記録数
        monthly_avg_records = sum(monthly_counts) / len(monthly_counts) if monthly_counts else 0
        
        # 最も活発な月
        if monthly_counts:
            max_month_index = monthly_counts.index(max(monthly_counts))
            most_active_month = last_6_months[max_month_index]
            most_active_month = f"{most_active_month[:4]}年{most_active_month[5:]}月"
        else:
            most_active_month = None
        
        # 購入頻度
        total_days = (timezone.now().date() - all_diaries.order_by('purchase_date').first().purchase_date).days if all_diaries.exists() else 0
        purchase_frequency = total_days / all_diaries.count() if all_diaries.exists() else 0
        
        # 記録内容の長さ分布
        from django.db.models.functions import Length
        
        lengths = all_diaries.annotate(
            content_length=Length('reason')
        ).values_list('content_length', flat=True)
        
        # 長さの範囲を定義
        length_ranges = ['〜200字', '201-500字', '501-1000字', '1001-2000字', '2001字〜']
        length_counts = [0] * 5
        
        for length in lengths:
            if length <= 200:
                length_counts[0] += 1
            elif length <= 500:
                length_counts[1] += 1
            elif length <= 1000:
                length_counts[2] += 1
            elif length <= 2000:
                length_counts[3] += 1
            else:
                length_counts[4] += 1
        
        return {
            'activity_heatmap': activity_heatmap,
            'monthly_labels': json.dumps(last_6_months),
            'monthly_counts': json.dumps(monthly_counts),
            'day_of_week_counts': json.dumps(day_of_week_counts),
            'most_active_day': most_active_day,
            'weekday_pattern': weekday_pattern,
            'monthly_avg_records': round(monthly_avg_records, 1),
            'most_active_month': most_active_month,
            'purchase_frequency': round(purchase_frequency, 1),
            'content_length_ranges': json.dumps(length_ranges),
            'content_length_counts': json.dumps(length_counts)
        }

    def prepare_monthly_data(self, diaries):
        """月別記録数データを準備"""
        # 過去12ヶ月の月ラベルを生成
        today = timezone.now().date()
        labels = []
        counts = []
        
        for i in range(11, -1, -1):
            month_date = (today.replace(day=1) - timedelta(days=i*30))
            month_str = month_date.strftime('%Y年%m月')
            labels.append(month_str)
            
            month_start = month_date.replace(day=1)
            if month_date.month == 12:
                month_end = month_date.replace(year=month_date.year+1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = month_date.replace(month=month_date.month+1, day=1) - timedelta(days=1)
            
            # その月の記録数をカウント
            count = diaries.filter(purchase_date__gte=month_start, purchase_date__lte=month_end).count()
            counts.append(count)
        
        return {
            'labels': labels,
            'counts': counts
        }
    
    def prepare_day_of_week_data(self, diaries):
        """曜日別記録数データを準備"""
        # 曜日ごとの記録数をカウント（0=月曜、6=日曜）
        day_counts = [0, 0, 0, 0, 0, 0, 0]
        
        # Djangoの曜日は日曜が1、土曜が7なので調整
        day_mapping = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
        
        day_of_week_counts = diaries.annotate(
            weekday=ExtractWeekDay('purchase_date')
        ).values('weekday').annotate(count=Count('id'))
        
        for item in day_of_week_counts:
            # Djangoの曜日をJavaScriptの曜日インデックスに変換
            weekday = day_mapping.get(item['weekday'], 0)
            day_counts[weekday] = item['count']
        
        return day_counts
    
    def prepare_activity_heatmap(self, diaries):
        """活動ヒートマップデータを準備"""
        # 過去1ヶ月のカレンダーヒートマップを生成
        today = timezone.now().date()
        start_date = today - timedelta(days=30)  # 30日（約1ヶ月）に変更
        
        # 日付ごとの記録数を集計
        date_counts = {}
        for diary in diaries.filter(purchase_date__gte=start_date):
            date_str = diary.purchase_date.strftime('%Y-%m-%d')
            if date_str in date_counts:
                date_counts[date_str] += 1
            else:
                date_counts[date_str] = 1
        
        # 最大値を見つけて正規化用に使用
        max_count = max(date_counts.values()) if date_counts else 1
        
        # カレンダーデータを生成
        heatmap_data = []
        current_date = start_date
        
        while current_date <= today:
            date_str = current_date.strftime('%Y-%m-%d')
            count = date_counts.get(date_str, 0)
            
            # ヒートマップレベルを計算（0～5）
            level = 0
            if count > 0:
                level = min(5, int((count / max_count) * 5) + 1)
            
            heatmap_data.append({
                'date': date_str,
                'day': current_date.day,
                'count': count,
                'level': level
            })
            
            current_date += timedelta(days=1)
        
        return heatmap_data
            
    def prepare_content_length_data(self, diaries):
        """記録内容の長さ分布データを準備"""
        length_ranges = ['~200文字', '201~500文字', '501~1000文字', '1001~2000文字', '2001文字~']
        length_counts = [0, 0, 0, 0, 0]
        
        for diary in diaries:
            # HTMLタグを除去して純粋なテキスト長を計算
            text = strip_tags(diary.reason)
            length = len(text)
            
            if length <= 200:
                length_counts[0] += 1
            elif length <= 500:
                length_counts[1] += 1
            elif length <= 1000:
                length_counts[2] += 1
            elif length <= 2000:
                length_counts[3] += 1
            else:
                length_counts[4] += 1
        
        return {
            'ranges': length_ranges,
            'counts': length_counts
        }
    
    def prepare_tag_frequency_data(self, diaries):
        """タグ使用頻度データを準備"""
        # 各タグの使用回数を集計
        tag_usage = {}
        
        for diary in diaries:
            for tag in diary.tags.all():
                if tag.name in tag_usage:
                    tag_usage[tag.name] += 1
                else:
                    tag_usage[tag.name] = 1
        
        # 使用頻度順にソート
        sorted_tags = sorted(tag_usage.items(), key=lambda x: x[1], reverse=True)
        
        # 上位10タグを抽出
        top_tags = sorted_tags[:10]
        tag_names = [tag[0] for tag in top_tags]
        tag_counts = [tag[1] for tag in top_tags]
        
        return {
            'names': tag_names,
            'counts': tag_counts
        }
    
    def prepare_tag_timeline_data(self, diaries):
        """タグの時系列変化データを準備"""
        # 過去6ヶ月の月ラベルを生成
        today = timezone.now().date()
        labels = []
        
        for i in range(5, -1, -1):
            month_date = (today.replace(day=1) - timedelta(days=i*30))
            month_str = month_date.strftime('%Y年%m月')
            labels.append(month_str)
        
        # 上位5タグの使用頻度推移を追跡
        top_tags = self.prepare_tag_frequency_data(diaries)['names'][:5]
        tag_data = {}
        
        for tag_name in top_tags:
            tag_data[tag_name] = [0] * len(labels)
        
        # 各月ごとのタグ使用回数を集計
        for i, month_label in enumerate(labels):
            month_date = timezone.now().date().replace(day=1) - timedelta(days=(5-i)*30)
            month_start = month_date.replace(day=1)
            if month_date.month == 12:
                month_end = month_date.replace(year=month_date.year+1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = month_date.replace(month=month_date.month+1, day=1) - timedelta(days=1)
            
            # その月の日記を取得
            month_diaries = diaries.filter(purchase_date__gte=month_start, purchase_date__lte=month_end)
            
            # タグの使用回数をカウント
            for diary in month_diaries:
                for tag in diary.tags.all():
                    if tag.name in tag_data:
                        tag_data[tag.name][i] += 1
        
        # データセットを構築
        datasets = []
        colors = ['rgba(79, 70, 229, 1)', 'rgba(16, 185, 129, 1)', 'rgba(245, 158, 11, 1)', 
                'rgba(239, 68, 68, 1)', 'rgba(59, 130, 246, 1)']
        
        for i, (tag_name, counts) in enumerate(tag_data.items()):
            color_index = i % len(colors)
            datasets.append({
                'label': tag_name,
                'data': counts,
                'borderColor': colors[color_index],
                'backgroundColor': colors[color_index],
                'borderWidth': 2,
                'fill': False, 
                'tension': 0.4
            })
        
        return {
            'labels': labels,
            'datasets': datasets
        }
    
    def prepare_tag_correlation_data(self, diaries):
        """タグの相関関係データを準備"""
        # タグごとの使用回数と、一緒に使われる他のタグを集計
        tag_usage = {}
        tag_correlations = {}
        
        for diary in diaries:
            tags = list(diary.tags.all().values_list('name', flat=True))
            
            # 各タグの使用回数をカウント
            for tag in tags:
                if tag in tag_usage:
                    tag_usage[tag] += 1
                else:
                    tag_usage[tag] = 1
                    tag_correlations[tag] = {}
                
                # 他のタグとの相関を記録
                for other_tag in tags:
                    if tag != other_tag:
                        if other_tag in tag_correlations[tag]:
                            tag_correlations[tag][other_tag] += 1
                        else:
                            tag_correlations[tag][other_tag] = 1
        
        # 使用頻度順にソート
        sorted_tags = sorted(tag_usage.items(), key=lambda x: x[1], reverse=True)
        
        # 上位5タグとその関連タグを抽出
        top_tags_data = []
        for tag_name, count in sorted_tags[:5]:
            related_tags = []
            
            if tag_name in tag_correlations:
                # 関連タグを使用頻度順にソート
                sorted_correlations = sorted(tag_correlations[tag_name].items(), key=lambda x: x[1], reverse=True)
                
                # 上位3つの関連タグを抽出
                for related_tag, related_count in sorted_correlations[:3]:
                    related_tags.append({
                        'name': related_tag,
                        'count': related_count
                    })
            
            top_tags_data.append({
                'name': tag_name,
                'count': count,
                'related_tags': related_tags
            })
        
        return top_tags_data
    
    def prepare_timeline_data(self, diaries):
        """タイムラインデータを準備"""
        timeline_entries = []
        
        # 日記を日付順に並べ替え
        sorted_diaries = sorted(
            diaries, 
            key=lambda x: x.sell_date if x.sell_date else x.purchase_date,
            reverse=True
        )
        
        # 最新の20件を取得
        recent_diaries = sorted_diaries[:20]
        
        for diary in recent_diaries:
            # 購入エントリー
            purchase_entry = {
                'date': diary.purchase_date.strftime('%Y年%m月%d日'),
                'action': '購入',
                'stock_name': diary.stock_name,
                'stock_symbol': diary.stock_symbol,
                'tags': list(diary.tags.all().values_list('name', flat=True)),
                'reason_excerpt': truncatechars_html(diary.reason, 100),
                'sell_date': None,
                'is_profit': False,
                'holding_period': None
            }
            
            # 売却が完了している場合
            if diary.sell_date:
                # 保有期間を計算
                holding_period = (diary.sell_date - diary.purchase_date).days
                # 利益かどうかを判定
                is_profit = diary.sell_price > diary.purchase_price
                
                purchase_entry['sell_date'] = diary.sell_date
                purchase_entry['is_profit'] = is_profit
                purchase_entry['holding_period'] = holding_period
            
            timeline_entries.append(purchase_entry)
        
        return timeline_entries

    def prepare_recent_trends(self, diaries):
        """最近の投資傾向データを準備"""
        # 購入頻度
        purchase_frequency = 30  # デフォルト値
        if diaries.count() >= 2:
            date_sorted = diaries.order_by('-purchase_date')
            first_date = date_sorted.first().purchase_date
            last_date = date_sorted.last().purchase_date
            date_range = (first_date - last_date).days
            if date_range > 0 and diaries.count() > 1:
                purchase_frequency = round(date_range / (diaries.count() - 1))
        
        # 平均保有期間
        avg_holding_period = 0
        sold_diaries = diaries.filter(sell_date__isnull=False)
        if sold_diaries.exists():
            total_days = sum((d.sell_date - d.purchase_date).days for d in sold_diaries)
            avg_holding_period = round(total_days / sold_diaries.count())
        
        # よく使うタグ
        most_used_tag = "なし"
        tag_counts = {}
        for diary in diaries:
            for tag in diary.tags.all():
                if tag.name in tag_counts:
                    tag_counts[tag.name] += 1
                else:
                    tag_counts[tag.name] = 1
        
        if tag_counts:
            most_used_tag = max(tag_counts.items(), key=lambda x: x[1])[0]
        
        # 最も詳細な記録
        most_detailed_record = "なし"
        max_length = 0
        for diary in diaries:
            text_length = len(strip_tags(diary.reason))
            if text_length > max_length:
                max_length = text_length
                most_detailed_record = diary.stock_name
        
        # キーワード抽出
        keywords = []
        if diaries.count() > 0:
            # 最新10件の日記から頻出単語を抽出
            recent_diaries = diaries.order_by('-purchase_date')[:10]
            text_content = ' '.join([strip_tags(d.reason) for d in recent_diaries])
            
            # 簡易的な形態素解析（実際は形態素解析ライブラリを使用するべき）
            # 一般的な日本語のストップワード
            stop_words = ['の', 'に', 'は', 'を', 'た', 'が', 'で', 'て', 'と', 'し', 'れ', 'さ', 'ある', 'いる', 'する', 'から', 'など', 'こと', 'これ', 'それ', 'もの']
            
            # 単語の簡易的な抽出（より精緻な形態素解析が必要）
            words = re.findall(r'\w+', text_content)
            word_counts = Counter(word for word in words if len(word) > 1 and word not in stop_words)
            
            # 上位5キーワードを抽出
            keywords = [{'word': word, 'count': count} for word, count in word_counts.most_common(5)]
        
        return {
            'purchase_frequency': purchase_frequency,
            'avg_holding_period': avg_holding_period,
            'most_used_tag': most_used_tag,
            'most_detailed_record': most_detailed_record,
            'keywords': keywords
        }

    # DiaryAnalyticsView の他の部分も修正

    # prepare_holding_period_data メソッドを修正
    def prepare_holding_period_data(self, diaries):
        """保有期間分布データを準備"""
        # 保有期間の範囲を定義
        ranges = ['~1週間', '1週間~1ヶ月', '1~3ヶ月', '3~6ヶ月', '6ヶ月~1年', '1年以上']
        counts = [0, 0, 0, 0, 0, 0]
        
        # 売却済みの日記で保有期間を集計 (None値のチェックを追加)
        sold_diaries = [
            d for d in diaries.filter(sell_date__isnull=False)
            if d.purchase_price is not None and d.purchase_quantity is not None
        ]
        
        for diary in sold_diaries:
            holding_period = (diary.sell_date - diary.purchase_date).days
            
            if holding_period <= 7:
                counts[0] += 1
            elif holding_period <= 30:
                counts[1] += 1
            elif holding_period <= 90:
                counts[2] += 1
            elif holding_period <= 180:
                counts[3] += 1
            elif holding_period <= 365:
                counts[4] += 1
            else:
                counts[5] += 1
        
        return {
            'ranges': ranges,
            'counts': counts
        }

    # prepare_recent_trends メソッドを修正
    def prepare_recent_trends(self, diaries):
        """最近の投資傾向データを準備"""
        # 価格・数量情報があるエントリーだけをフィルタリング
        valid_diaries = [d for d in diaries if d.purchase_price is not None and d.purchase_quantity is not None]
        
        # 購入頻度
        purchase_frequency = 30  # デフォルト値
        if len(valid_diaries) >= 2:
            sorted_diaries = sorted(valid_diaries, key=lambda x: x.purchase_date, reverse=True)
            first_date = sorted_diaries[0].purchase_date
            last_date = sorted_diaries[-1].purchase_date
            date_range = (first_date - last_date).days
            if date_range > 0 and len(valid_diaries) > 1:
                purchase_frequency = round(date_range / (len(valid_diaries) - 1))
        
        # 平均保有期間
        avg_holding_period = 0
        sold_diaries = [d for d in valid_diaries if d.sell_date]
        if sold_diaries:
            total_days = sum((d.sell_date - d.purchase_date).days for d in sold_diaries)
            avg_holding_period = round(total_days / len(sold_diaries))
        
        # よく使うタグ
        most_used_tag = "なし"
        tag_counts = {}
        for diary in diaries:  # すべての日記を対象（メモも含む）
            for tag in diary.tags.all():
                if tag.name in tag_counts:
                    tag_counts[tag.name] += 1
                else:
                    tag_counts[tag.name] = 1
        
        if tag_counts:
            most_used_tag = max(tag_counts.items(), key=lambda x: x[1])[0]
        
        # 最も詳細な記録
        most_detailed_record = "なし"
        max_length = 0
        for diary in diaries:  # すべての日記を対象（メモも含む）
            text_length = len(strip_tags(diary.reason))
            if text_length > max_length:
                max_length = text_length
                most_detailed_record = diary.stock_name
        
        # キーワード抽出
        keywords = []
        if diaries.count() > 0:
            # 最新10件の日記から頻出単語を抽出
            recent_diaries = diaries.order_by('-purchase_date')[:10]
            text_content = ' '.join([strip_tags(d.reason) for d in recent_diaries])
            
            # 簡易的な形態素解析（実際は形態素解析ライブラリを使用するべき）
            # 一般的な日本語のストップワード
            stop_words = ['の', 'に', 'は', 'を', 'た', 'が', 'で', 'て', 'と', 'し', 'れ', 'さ', 'ある', 'いる', 'する', 'から', 'など', 'こと', 'これ', 'それ', 'もの']
            
            # 単語の簡易的な抽出（より精緻な形態素解析が必要）
            words = re.findall(r'\w+', text_content)
            word_counts = Counter(word for word in words if len(word) > 1 and word not in stop_words)
            
            # 上位5キーワードを抽出
            keywords = [{'word': word, 'count': count} for word, count in word_counts.most_common(5)]
        
        return {
            'purchase_frequency': purchase_frequency,
            'avg_holding_period': avg_holding_period,
            'most_used_tag': most_used_tag,
            'most_detailed_record': most_detailed_record,
            'keywords': keywords
        }
    def prepare_template_usage_data(self, diaries):
        """分析テンプレート使用率データを準備"""
        # 各テンプレートの使用率を計算
        template_usage = {}
        
        # 日記IDのリストを取得
        diary_ids = list(diaries.values_list('id', flat=True))
        
        if not diary_ids:
            return {
                'names': [],
                'rates': []
            }
        
        # ユーザーの全テンプレートを取得
        templates = AnalysisTemplate.objects.filter(user=self.request.user)
        
        # DiaryAnalysisValueを取得
        analysis_values = DiaryAnalysisValue.objects.filter(
            diary_id__in=diary_ids
        ).select_related('analysis_item__template')
        
        # 日記とテンプレートで分析値をマッピング
        diary_template_values = defaultdict(lambda: defaultdict(list))
        for value in analysis_values:
            diary_template_values[value.diary_id][value.analysis_item.template_id].append(value)
        
        for template in templates:
            template_completion_rates = []
            
            for diary in diaries:
                # この日記でこのテンプレートの項目が使われているか確認
                values = diary_template_values.get(diary.id, {}).get(template.id, [])
                
                if values:
                    # テンプレートの項目数
                    items = template.items.all()
                    total_items = items.count()
                    
                    if total_items > 0:
                        # 項目への入力率を計算
                        filled_items = 0
                        
                        for item in items:
                            # この項目に値が入力されているか確認
                            has_value = False
                            for value in values:
                                if value.analysis_item_id == item.id:
                                    # 項目タイプに応じて値が存在するか確認
                                    if item.item_type == 'number' and value.number_value is not None:
                                        has_value = True
                                    elif item.item_type == 'boolean' and value.boolean_value is not None:
                                        has_value = True
                                    elif item.item_type == 'boolean_with_value' and (value.boolean_value is not None or value.number_value is not None or value.text_value):
                                        has_value = True
                                    elif value.text_value:
                                        has_value = True
                                    break
                            
                            if has_value:
                                filled_items += 1
                        
                        completion_rate = (filled_items / total_items) * 100
                        template_completion_rates.append(completion_rate)
            
            # 平均使用率を計算
            if template_completion_rates:
                avg_rate = sum(template_completion_rates) / len(template_completion_rates)
                template_usage[template.name] = avg_rate
        
        # 使用率順にソート
        sorted_templates = sorted(template_usage.items(), key=lambda x: x[1], reverse=True)
        
        template_names = []
        template_rates = []
        
        for name, rate in sorted_templates:
            template_names.append(name)
            template_rates.append(round(rate, 1))
        
        return {
            'names': template_names,
            'rates': template_rates
        }

    def prepare_template_timeline_data(self, diaries):
        """分析テンプレート使用率の時系列変化データを準備"""
        # 過去6ヶ月の月ラベルを生成
        today = timezone.now().date()
        labels = []
        monthly_rates = []
        
        for i in range(5, -1, -1):
            month_date = (today.replace(day=1) - timedelta(days=i*30))
            month_str = month_date.strftime('%Y年%m月')
            labels.append(month_str)
            
            month_start = month_date.replace(day=1)
            if month_date.month == 12:
                month_end = month_date.replace(year=month_date.year+1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = month_date.replace(month=month_date.month+1, day=1) - timedelta(days=1)
            
            # その月の日記を取得
            month_diaries = diaries.filter(purchase_date__gte=month_start, purchase_date__lte=month_end)
            
            # 日記IDのリストを取得
            month_diary_ids = list(month_diaries.values_list('id', flat=True))
            
            # テンプレート使用率を計算
            total_completion = 0
            completion_count = 0
            
            if month_diary_ids:
                # その月の分析値を取得
                month_values = DiaryAnalysisValue.objects.filter(
                    diary_id__in=month_diary_ids
                ).select_related('analysis_item__template')
                
                # 日記別とテンプレート別の分析値をマッピング
                diary_template_values = defaultdict(lambda: defaultdict(list))
                for value in month_values:
                    diary_template_values[value.diary_id][value.analysis_item.template_id].append(value)
                
                for diary in month_diaries:
                    # この日記で使われているテンプレートを取得
                    templates_used = set()
                    for template_values in diary_template_values.get(diary.id, {}).values():
                        for value in template_values:
                            templates_used.add(value.analysis_item.template_id)
                    
                    for template_id in templates_used:
                        try:
                            template = AnalysisTemplate.objects.get(id=template_id)
                            items = template.items.all()
                            total_items = items.count()
                            
                            if total_items > 0:
                                # テンプレート項目の入力率を計算
                                values = diary_template_values[diary.id][template_id]
                                filled_items = 0
                                
                                for item in items:
                                    # この項目に値が入力されているか確認
                                    has_value = False
                                    for value in values:
                                        if value.analysis_item_id == item.id:
                                            # 項目タイプに応じて値が存在するか確認
                                            if item.item_type == 'number' and value.number_value is not None:
                                                has_value = True
                                            elif item.item_type == 'boolean' and value.boolean_value is not None:
                                                has_value = True
                                            elif item.item_type == 'boolean_with_value' and (value.boolean_value is not None or value.number_value is not None or value.text_value):
                                                has_value = True
                                            elif value.text_value:
                                                has_value = True
                                            break
                                    
                                    if has_value:
                                        filled_items += 1
                                
                                completion_rate = (filled_items / total_items) * 100
                                total_completion += completion_rate
                                completion_count += 1
                        except AnalysisTemplate.DoesNotExist:
                            pass
            
            # 平均使用率を計算
            month_rate = 0
            if completion_count > 0:
                month_rate = total_completion / completion_count
            
            monthly_rates.append(round(month_rate, 1))
        
        return {
            'labels': labels,
            'rates': monthly_rates
        }

    def prepare_template_item_stats(self, diaries):
        """分析テンプレート項目の統計情報を準備"""
        template_stats = []
        
        # ユーザーのテンプレートを取得
        templates = AnalysisTemplate.objects.filter(user=self.request.user)
        
        # 日記IDのリストを取得
        diary_ids = list(diaries.values_list('id', flat=True))
        
        if not diary_ids:
            return []
        
        # DiaryAnalysisValueを一度に取得
        all_analysis_values = DiaryAnalysisValue.objects.filter(
            diary_id__in=diary_ids
        ).select_related('analysis_item__template')
        
        # 分析項目別に値をマッピング
        item_values = defaultdict(list)
        for value in all_analysis_values:
            item_values[value.analysis_item_id].append(value)
        
        for template in templates:
            # このテンプレートを使用している日記を取得
            template_values = [v for v in all_analysis_values if v.analysis_item.template_id == template.id]
            template_diary_ids = set(v.diary_id for v in template_values)
            usage_count = len(template_diary_ids)
            
            if usage_count > 0:
                # テンプレート項目ごとの入力率を計算
                items = template.items.all()
                item_completion = {}
                
                for item in items:
                    # この項目の分析値
                    values = item_values.get(item.id, [])
                    total_usages = len(template_diary_ids)
                    
                    if total_usages > 0:
                        # 値が入力されている数を集計
                        filled_count = 0
                        
                        for diary_id in template_diary_ids:
                            # この日記のこの項目に値があるか確認
                            has_value = False
                            for value in values:
                                if value.diary_id == diary_id:
                                    # 項目タイプに応じた確認
                                    if item.item_type == 'number' and value.number_value is not None:
                                        has_value = True
                                    elif item.item_type == 'boolean' and value.boolean_value is not None:
                                        has_value = True
                                    elif item.item_type == 'boolean_with_value' and (value.boolean_value is not None or value.number_value is not None or value.text_value):
                                        has_value = True
                                    elif value.text_value:
                                        has_value = True
                                    break
                            
                            if has_value:
                                filled_count += 1
                        
                        completion_rate = (filled_count / total_usages) * 100
                        item_completion[item.name] = completion_rate
                
                # 最も入力されやすい項目と最も入力されにくい項目を特定
                most_completed = "なし"
                least_completed = "なし"
                if item_completion:
                    most_completed = max(item_completion.items(), key=lambda x: x[1])[0]
                    least_completed = min(item_completion.items(), key=lambda x: x[1])[0]
                
                # テンプレート全体の平均入力率を計算
                average_completion = sum(item_completion.values()) / len(item_completion) if item_completion else 0
                
                template_stats.append({
                    'name': template.name,
                    'usage_count': usage_count,
                    'completion_rate': round(average_completion, 1),
                    'most_completed': most_completed,
                    'least_completed': least_completed
                })
        
        return template_stats

    def get_investment_summary_data(self, user, diaries, all_diaries, active_diaries, sold_diaries):
        """投資状況サマリー関連のデータを取得"""
        # メモエントリー（is_memo=True または price/quantity が None）をフィルタリング
        transaction_diaries = [d for d in diaries if not (d.is_memo or d.purchase_price is None or d.purchase_quantity is None)]
        transaction_active_diaries = [d for d in active_diaries if not (d.is_memo or d.purchase_price is None or d.purchase_quantity is None)]
        transaction_sold_diaries = [d for d in sold_diaries if not (d.is_memo or d.purchase_price is None or d.purchase_quantity is None)]
        
        # 1. 総投資額の計算 - メモを除外
        total_investment = sum(
            d.purchase_price * d.purchase_quantity 
            for d in transaction_diaries
        )
        
        # 2. 前月比較用のデータ
        last_month = timezone.now().date() - timedelta(days=30)
        last_month_diaries = StockDiary.objects.filter(
            user=user, 
            purchase_date__lt=last_month
        )
        # メモを除外して計算
        last_month_transactions = [d for d in last_month_diaries if not (d.is_memo or d.purchase_price is None or d.purchase_quantity is None)]
        last_month_investment = sum(
            d.purchase_price * d.purchase_quantity 
            for d in last_month_transactions
        )
        
        investment_change = total_investment - last_month_investment
        investment_change_percent = (investment_change / last_month_investment * 100) if last_month_investment else 0
        
        # 3. 実現利益（売却済み株式の損益）
        realized_profit = Decimal('0')
        for diary in transaction_sold_diaries:
            profit = (diary.sell_price - diary.purchase_price) * diary.purchase_quantity
            realized_profit += profit
        
        # 4. 現在の保有総額（購入額ベース、API依存なし）
        active_investment = sum(
            d.purchase_price * d.purchase_quantity 
            for d in transaction_active_diaries
        )

        # 5. 総利益/損失 = 実現利益のみ（未実現利益は考慮しない）
        total_profit = realized_profit
                
        # 6. 前月の利益比較（売却済みのみ）
        last_month_sold = [d for d in last_month_transactions if d.sell_date]
        last_month_profit = Decimal('0')
        
        # 前月の実現利益
        for diary in last_month_sold:
            last_month_profit += (diary.sell_price - diary.purchase_price) * diary.purchase_quantity
        
        profit_change = total_profit - last_month_profit
        profit_change_percent = (profit_change / last_month_profit * 100) if last_month_profit else 0
        
        # 7. 保有銘柄数 - メモエントリーではない銘柄のみカウント
        active_stocks_count = len(transaction_active_diaries)
        last_month_active_stocks = len([d for d in last_month_transactions if not d.sell_date])
        stocks_count_change = active_stocks_count - last_month_active_stocks
        
        # 8. 平均保有期間（売却済みのみ）
        avg_holding_period = 0
        if transaction_sold_diaries:
            total_days = sum((d.sell_date - d.purchase_date).days for d in transaction_sold_diaries)
            avg_holding_period = total_days / len(transaction_sold_diaries)
        
        # 前月の平均保有期間 - メモエントリーを除外
        last_month_avg_holding_period = 0
        if last_month_sold:
            last_month_total_days = sum((d.sell_date - d.purchase_date).days for d in last_month_sold)
            last_month_avg_holding_period = last_month_total_days / len(last_month_sold)
        
        holding_period_change = avg_holding_period - last_month_avg_holding_period
        
        return {
            'total_investment': total_investment,
            'active_investment': active_investment,
            'investment_change': investment_change,
            'investment_change_percent': investment_change_percent,
            'total_profit': total_profit,
            'profit_change': profit_change,
            'profit_change_percent': profit_change_percent,
            'active_stocks_count': active_stocks_count,
            'stocks_count_change': stocks_count_change,
            'avg_holding_period': avg_holding_period,
            'holding_period_change': holding_period_change,
            'realized_profit': realized_profit,
            'active_holdings_count': active_stocks_count,
        }
        
    # prepare_holding_period_data メソッドを追加
    def prepare_holding_period_data(self, diaries):
        """保有期間分布データを準備"""
        # 保有期間の範囲を定義
        ranges = ['~1週間', '1週間~1ヶ月', '1~3ヶ月', '3~6ヶ月', '6ヶ月~1年', '1年以上']
        counts = [0, 0, 0, 0, 0, 0]
        
        # 売却済みの日記で保有期間を集計 (None値のチェックを追加)
        sold_diaries = [
            d for d in diaries.filter(sell_date__isnull=False)
            if d.purchase_price is not None and d.purchase_quantity is not None
        ]
        
        for diary in sold_diaries:
            holding_period = (diary.sell_date - diary.purchase_date).days
            
            if holding_period <= 7:
                counts[0] += 1
            elif holding_period <= 30:
                counts[1] += 1
            elif holding_period <= 90:
                counts[2] += 1
            elif holding_period <= 180:
                counts[3] += 1
            elif holding_period <= 365:
                counts[4] += 1
            else:
                counts[5] += 1
        
        return {
            'ranges': ranges,
            'counts': counts
        }

    # prepare_recent_trends メソッドを追加
    def prepare_recent_trends(self, diaries):
        """最近の投資傾向データを準備"""
        # 価格・数量情報があるエントリーだけをフィルタリング
        valid_diaries = [d for d in diaries if d.purchase_price is not None and d.purchase_quantity is not None]
        
        # 購入頻度
        purchase_frequency = 30  # デフォルト値
        if len(valid_diaries) >= 2:
            sorted_diaries = sorted(valid_diaries, key=lambda x: x.purchase_date, reverse=True)
            first_date = sorted_diaries[0].purchase_date
            last_date = sorted_diaries[-1].purchase_date
            date_range = (first_date - last_date).days
            if date_range > 0 and len(valid_diaries) > 1:
                purchase_frequency = round(date_range / (len(valid_diaries) - 1))
        
        # 平均保有期間
        avg_holding_period = 0
        sold_diaries = [d for d in valid_diaries if d.sell_date]
        if sold_diaries:
            total_days = sum((d.sell_date - d.purchase_date).days for d in sold_diaries)
            avg_holding_period = round(total_days / len(sold_diaries))
        
        # よく使うタグ
        most_used_tag = "なし"
        tag_counts = {}
        for diary in diaries:  # すべての日記を対象（メモも含む）
            for tag in diary.tags.all():
                if tag.name in tag_counts:
                    tag_counts[tag.name] += 1
                else:
                    tag_counts[tag.name] = 1
        
        if tag_counts:
            most_used_tag = max(tag_counts.items(), key=lambda x: x[1])[0]
        
        # 最も詳細な記録
        most_detailed_record = "なし"
        max_length = 0
        for diary in diaries:  # すべての日記を対象（メモも含む）
            text_length = len(strip_tags(diary.reason))
            if text_length > max_length:
                max_length = text_length
                most_detailed_record = diary.stock_name
        
        # キーワード抽出
        keywords = []
        if diaries.count() > 0:
            # 最新10件の日記から頻出単語を抽出
            recent_diaries = diaries.order_by('-purchase_date')[:10]
            text_content = ' '.join([strip_tags(d.reason) for d in recent_diaries])
            
            # 簡易的な形態素解析（実際は形態素解析ライブラリを使用するべき）
            # 一般的な日本語のストップワード
            stop_words = ['の', 'に', 'は', 'を', 'た', 'が', 'で', 'て', 'と', 'し', 'れ', 'さ', 'ある', 'いる', 'する', 'から', 'など', 'こと', 'これ', 'それ', 'もの']
            
            # 単語の簡易的な抽出（より精緻な形態素解析が必要）
            words = re.findall(r'\w+', text_content)
            word_counts = Counter(word for word in words if len(word) > 1 and word not in stop_words)
            
            # 上位5キーワードを抽出
            keywords = [{'word': word, 'count': count} for word, count in word_counts.most_common(5)]
        
        return {
            'purchase_frequency': purchase_frequency,
            'avg_holding_period': avg_holding_period,
            'most_used_tag': most_used_tag,
            'most_detailed_record': most_detailed_record,
            'keywords': keywords
        }
        
    # collect_stats メソッドを修正
    def collect_stats(self, user, diaries, all_diaries):
        """基本的な統計データを収集"""
        from django.db.models import Avg, Sum, Count, F, ExpressionWrapper, fields
        from django.db.models.functions import Length
        
        # 現在の月の開始日
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        
        # 前月の日付範囲
        prev_month_end = current_month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        
        # 銘柄数の統計 - メモを含めてすべてカウント
        total_stocks = diaries.count()
        prev_month_stocks = all_diaries.filter(
            created_at__gte=prev_month_start,
            created_at__lt=current_month_start
        ).count()
        stocks_change = total_stocks - prev_month_stocks
        
        # タグの統計
        total_tags = Tag.objects.filter(stockdiary__in=diaries).distinct().count()
        prev_month_tags = Tag.objects.filter(
            stockdiary__in=all_diaries,
            stockdiary__created_at__gte=prev_month_start,
            stockdiary__created_at__lt=current_month_start
        ).distinct().count()
        tags_change = total_tags - prev_month_tags
        
        # 分析項目達成率
        # 現在の平均完了率
        current_completion = self.calculate_analysis_completion_rate(user, diaries)
        
        # 前月の平均完了率
        prev_month_diaries = all_diaries.filter(
            created_at__gte=prev_month_start,
            created_at__lt=current_month_start
        )
        prev_completion = self.calculate_analysis_completion_rate(user, prev_month_diaries)
        
        checklist_completion_rate = current_completion
        checklist_rate_change = current_completion - prev_completion
        
        # 平均記録文字数 - すべてのエントリーを対象（メモも含む）
        avg_reason_length = 0
        if diaries.exists():
            # HTMLタグを除去して純粋なテキスト長を計算
            reason_lengths = []
            for diary in diaries:
                raw_text = strip_tags(diary.reason)
                reason_lengths.append(len(raw_text))
            
            if reason_lengths:
                avg_reason_length = int(sum(reason_lengths) / len(reason_lengths))
        
        # 前月の平均記録文字数
        last_month_avg_length = 0
        if prev_month_diaries.exists():
            last_month_lengths = []
            for diary in prev_month_diaries:
                raw_text = strip_tags(diary.reason)
                last_month_lengths.append(len(raw_text))
            
            if last_month_lengths:
                last_month_avg_length = int(sum(last_month_lengths) / len(last_month_lengths))
        
        reason_length_change = avg_reason_length - last_month_avg_length
        
        return {
            'total_stocks': total_stocks,
            'stocks_change': stocks_change,
            'total_tags': total_tags,
            'tags_change': tags_change,
            'checklist_completion_rate': checklist_completion_rate,
            'checklist_rate_change': checklist_rate_change,
            'avg_reason_length': avg_reason_length,
            'reason_length_change': reason_length_change
        }

# stockdiary/views.py に追加
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
            },
            # 分析ページに必要な他のアクションを追加
        ]
        context['page_actions'] = analytics_actions
                
        # 選択された日記ID（更新用）
        diary_id = self.kwargs.get('pk')
        if diary_id:
            try:
                selected_diary = StockDiary.objects.get(
                    id=diary_id,
                    user=self.request.user
                )
                
                # 購入価格と株数が入力されている場合のみ
                if selected_diary.purchase_price is not None and selected_diary.purchase_quantity is not None:
                    context['selected_diary'] = selected_diary
                else:
                    messages.error(self.request, '購入価格と株数が設定されていない日記は売却できません')
                    # リダイレクトはここでは返せないので、メッセージだけ追加
            except StockDiary.DoesNotExist:
                pass
        
        return context
    
    def post(self, request, *args, **kwargs):
        diary_id = request.POST.get('diary_id')
        sell_date = request.POST.get('sell_date')
        sell_price = request.POST.get('sell_price')
        
        try:
            # 日記エントリーを取得して売却情報を更新
            diary = StockDiary.objects.get(
                id=diary_id,
                user=request.user
            )
            
            # 購入価格と株数が設定されているか確認
            if diary.purchase_price is None or diary.purchase_quantity is None:
                messages.error(request, '購入価格と株数が設定されていない日記は売却できません')
                return redirect('stockdiary:home')
                
            diary.sell_date = sell_date
            diary.sell_price = Decimal(sell_price)
            diary.save()
            
            messages.success(request, f'{diary.stock_name}の売却情報を登録しました')
            
            # ホームページまたは詳細ページにリダイレクト
            return redirect('stockdiary:detail', pk=diary.id)
            
        except StockDiary.DoesNotExist:
            messages.error(request, '指定された日記が見つかりません')
        except Exception as e:
            messages.error(request, f'エラーが発生しました: {str(e)}')
        
        # エラー時は同じページを再表示
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
                    # URLを保持したままリダイレクトはできないので、メッセージだけ追加
            except StockDiary.DoesNotExist:
                pass
        
        return context
    
    def post(self, request, *args, **kwargs):
        diary_id = request.POST.get('diary_id')
        sell_date = request.POST.get('sell_date')
        sell_price = request.POST.get('sell_price')
        
        try:
            # 日記エントリーを取得して売却情報を更新
            diary = StockDiary.objects.get(
                id=diary_id,
                user=request.user
            )
            
            # 購入価格と株数が設定されているか確認
            if diary.purchase_price is None or diary.purchase_quantity is None:
                messages.error(request, '購入価格と株数が設定されていない日記は売却できません')
                return redirect('stockdiary:home')
                
            diary.sell_date = sell_date
            diary.sell_price = Decimal(sell_price)
            diary.save()
            
            messages.success(request, f'{diary.stock_name}の売却情報を登録しました')
            
            # ホームページまたは詳細ページにリダイレクト
            return redirect('stockdiary:detail', pk=diary.id)
            
        except StockDiary.DoesNotExist:
            messages.error(request, '指定された日記が見つかりません')
        except Exception as e:
            messages.error(request, f'エラーが発生しました: {str(e)}')
        
        # エラー時は同じページを再表示
        return self.get(request, *args, **kwargs)