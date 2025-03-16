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

from .models import StockDiary, DiaryNote
from .forms import StockDiaryForm, DiaryNoteForm
from tags.models import Tag
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from analysis_template.forms import create_analysis_value_formset

import json
import re
from decimal import Decimal
from datetime import timedelta
from collections import Counter, defaultdict
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
        # checklists の取得を削除
        
        # カレンダー表示用にすべての日記データを追加
        context['all_diaries'] = StockDiary.objects.filter(user=self.request.user)
        
        # checklist_stats の計算を削除
        
        # 保有中の株式を取得
        active_holdings = StockDiary.objects.filter(user=self.request.user, sell_date__isnull=True)
        context['active_holdings_count'] = active_holdings.count()
        
        # 実現損益の計算（売却済みの株式）
        sold_stocks = StockDiary.objects.filter(user=self.request.user, sell_date__isnull=False)
        realized_profit = 0
        for stock in sold_stocks:
            profit = (stock.sell_price - stock.purchase_price) * stock.purchase_quantity
            realized_profit += profit
        
        context['realized_profit'] = realized_profit
        
        # 未実現損益の計算（保有中の株式）
        # 現在の実装はそのまま
        
        return context
        
# stockdiary/views.py のStockDiaryDetailViewを修正
class StockDiaryDetailView(LoginRequiredMixin, DetailView):
    model = StockDiary
    template_name = 'stockdiary/detail.html'
    context_object_name = 'diary'
    
    def get_queryset(self):
        return StockDiary.objects.filter(user=self.request.user)
    
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # 現在表示中の日記IDをセッションに保存
        request.session['current_diary_id'] = self.object.id
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # チェックリスト関連のコードを削除
        
        # 継続記録フォームを追加
        context['note_form'] = DiaryNoteForm(initial={'date': timezone.now().date()})
        
        # 継続記録一覧を追加
        context['notes'] = self.object.notes.all().order_by('-date')
        
        return context

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
class StockDiaryUpdateView(LoginRequiredMixin, UpdateView):
    model = StockDiary
    form_class = StockDiaryForm
    template_name = 'stockdiary/diary_form.html'
    
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


# views.py に以下のクラスとインポートを追加
class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    """投資分析ダッシュボードを表示するビュー"""
    template_name = 'stockdiary/analytics_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # フィルターパラメータの取得
        date_range = self.request.GET.get('date_range', 'all')
        selected_tag = self.request.GET.get('tag', '')
        status = self.request.GET.get('status', 'all')
        sort = self.request.GET.get('sort', 'date_desc')
        
        # 基本クエリ - ログインユーザーの日記
        diaries = StockDiary.objects.filter(user=self.request.user)
        
        # 日付範囲フィルター
        if date_range != 'all':
            today = timezone.now().date()
            if date_range == '1m':
                start_date = today - timedelta(days=30)
            elif date_range == '3m':
                start_date = today - timedelta(days=90)
            elif date_range == '6m':
                start_date = today - timedelta(days=180)
            elif date_range == '1y':
                start_date = today - timedelta(days=365)
            
            diaries = diaries.filter(purchase_date__gte=start_date)
        
        # タグフィルター
        if selected_tag:
            diaries = diaries.filter(tags__id=selected_tag)
        
        # ステータスフィルター
        if status == 'active':
            diaries = diaries.filter(sell_date__isnull=True)
        elif status == 'sold':
            diaries = diaries.filter(sell_date__isnull=False)
        
        # 並び替え
        if sort == 'date_desc':
            diaries = diaries.order_by('-purchase_date')
        elif sort == 'date_asc':
            diaries = diaries.order_by('purchase_date')
        elif sort == 'profit_desc' or sort == 'profit_asc':
            # 利益の計算は複雑なので、Pythonで処理
            diaries = list(diaries)
            # 現在価格の取得（実際の実装ではAPIなどから取得）
            current_prices = self.get_current_prices([diary.stock_symbol for diary in diaries])
            
            # 利益計算
            for diary in diaries:
                if diary.sell_date:
                    diary.profit = (diary.sell_price - diary.purchase_price) * diary.purchase_quantity
                else:
                    current_price = current_prices.get(diary.stock_symbol)
                    if current_price:
                        diary.profit = (Decimal(str(current_price)) - diary.purchase_price) * diary.purchase_quantity
                    else:
                        diary.profit = Decimal('0')
            
            # 並び替え
            diaries.sort(key=lambda x: x.profit, reverse=(sort == 'profit_desc'))
        elif sort == 'price_desc':
            diaries = diaries.order_by('-purchase_price')
        elif sort == 'price_asc':
            diaries = diaries.order_by('purchase_price')
        
        # 統計データの計算
        total_investment = sum(diary.purchase_price * diary.purchase_quantity for diary in diaries)
        
        # 前月比較用のデータ
        last_month = timezone.now().date() - timedelta(days=30)
        last_month_diaries = StockDiary.objects.filter(user=self.request.user, purchase_date__lt=last_month)
        last_month_investment = sum(diary.purchase_price * diary.purchase_quantity for diary in last_month_diaries)
        
        investment_change = total_investment - last_month_investment
        investment_change_percent = (investment_change / last_month_investment * 100) if last_month_investment else 0
        
        # 総利益/損失の計算
        total_profit = Decimal('0')
        current_prices = self.get_current_prices([diary.stock_symbol for diary in diaries])
        
        for diary in diaries:
            if diary.sell_date:
                total_profit += (diary.sell_price - diary.purchase_price) * diary.purchase_quantity
            else:
                current_price = current_prices.get(diary.stock_symbol)
                if current_price:
                    total_profit += (Decimal(str(current_price)) - diary.purchase_price) * diary.purchase_quantity
        
        # 前月の利益
        last_month_profit = Decimal('0')
        for diary in last_month_diaries:
            if diary.sell_date:
                last_month_profit += (diary.sell_price - diary.purchase_price) * diary.purchase_quantity
            else:
                current_price = current_prices.get(diary.stock_symbol)
                if current_price:
                    last_month_profit += (Decimal(str(current_price)) - diary.purchase_price) * diary.purchase_quantity
        
        profit_change = total_profit - last_month_profit
        profit_change_percent = (profit_change / last_month_profit * 100) if last_month_profit else 0
        
        # 保有銘柄数
        active_stocks_count = len([d for d in diaries if not d.sell_date])
        last_month_active_stocks = len([d for d in last_month_diaries if not d.sell_date])
        stocks_count_change = active_stocks_count - last_month_active_stocks
        
        # 平均保有期間
        avg_holding_period = 0
        sold_diaries = [d for d in diaries if d.sell_date]
        if sold_diaries:
            total_days = sum((d.sell_date - d.purchase_date).days for d in sold_diaries)
            avg_holding_period = total_days / len(sold_diaries)
        
        # 前月の平均保有期間
        last_month_avg_holding_period = 0
        last_month_sold = [d for d in last_month_diaries if d.sell_date]
        if last_month_sold:
            last_month_total_days = sum((d.sell_date - d.purchase_date).days for d in last_month_sold)
            last_month_avg_holding_period = last_month_total_days / len(last_month_sold)
        
        holding_period_change = avg_holding_period - last_month_avg_holding_period
        
        # チャートデータの生成
        # self.prepare_chart_data(context, diaries, current_prices)
        
        # 全てのタグを取得
        all_tags = Tag.objects.filter(user=self.request.user)
        
        # コンテキストに追加
        context.update({
            'diaries': diaries,
            'date_range': date_range,
            'selected_tag': selected_tag,
            'status': status,
            'sort': sort,
            'all_tags': all_tags,
            'total_investment': total_investment,
            'investment_change': investment_change,
            'investment_change_percent': investment_change_percent,
            'total_profit': total_profit,
            'profit_change': profit_change,
            'profit_change_percent': profit_change_percent,
            'active_stocks_count': active_stocks_count,
            'stocks_count_change': stocks_count_change,
            'avg_holding_period': avg_holding_period,
            'holding_period_change': holding_period_change,
            'current_prices': current_prices,
        })
        
        return context
        
    def get_current_prices(self, stock_symbols):
        """銘柄コードから現在の株価を取得する（サンプル実装）"""
        # 実際の実装ではYahoo FinanceなどのAPIを使用
        prices = {}
        for symbol in stock_symbols:
            # ランダムな株価を生成（デモ用）
            base_price = 1000 + hash(symbol) % 10000
            random_factor = random.uniform(0.9, 1.1)
            prices[symbol] = base_price * random_factor
        return prices

# 既存のStockDiaryListViewとその他のクラスは変更なし
class DiaryAnalyticsView(LoginRequiredMixin, TemplateView):
    """投資記録分析ダッシュボードを表示するビュー"""
    template_name = 'stockdiary/analytics_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # フィルターパラメータの取得
        date_range = self.request.GET.get('date_range', 'all')
        selected_tag = self.request.GET.get('tag', '')
        status = self.request.GET.get('status', 'all')
        sort = self.request.GET.get('sort', 'date_desc')
        
        # 基本クエリ - ログインユーザーの日記
        diaries = StockDiary.objects.filter(user=self.request.user)
        
        # 日付範囲フィルター
        if date_range != 'all':
            today = timezone.now().date()
            if date_range == '1m':
                start_date = today - timedelta(days=30)
            elif date_range == '3m':
                start_date = today - timedelta(days=90)
            elif date_range == '6m':
                start_date = today - timedelta(days=180)
            elif date_range == '1y':
                start_date = today - timedelta(days=365)
            
            diaries = diaries.filter(purchase_date__gte=start_date)
        
        # タグフィルター
        if selected_tag:
            diaries = diaries.filter(tags__id=selected_tag)
        
        # ステータスフィルター
        if status == 'active':
            diaries = diaries.filter(sell_date__isnull=True)
        elif status == 'sold':
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
        
        # 統計情報の計算
        # 記録した銘柄数
        total_stocks = diaries.count()
        
        # 前月の記録数との比較
        last_month = timezone.now().date() - timedelta(days=30)
        last_month_diaries = StockDiary.objects.filter(
            user=self.request.user, 
            purchase_date__lt=last_month
        )
        last_month_stocks = last_month_diaries.count()
        stocks_change = total_stocks - last_month_stocks
        
        # 使用したタグの数
        tags_used = diaries.values('tags').annotate(count=Count('id')).count()
        last_month_tags = last_month_diaries.values('tags').annotate(count=Count('id')).count()
        tags_change = tags_used - last_month_tags
        
        # 分析テンプレート使用率
        analysis_stats = self.get_analysis_template_stats(diaries)
        
        # 平均記録文字数
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
        if last_month_diaries.exists():
            last_month_lengths = []
            for diary in last_month_diaries:
                raw_text = strip_tags(diary.reason)
                last_month_lengths.append(len(raw_text))
            
            if last_month_lengths:
                last_month_avg_length = int(sum(last_month_lengths) / len(last_month_lengths))
        
        reason_length_change = avg_reason_length - last_month_avg_length
        
        # 記録習慣データの準備
        monthly_data = self.prepare_monthly_data(diaries)
        day_of_week_data = self.prepare_day_of_week_data(diaries)
        activity_heatmap = self.prepare_activity_heatmap(diaries)
        content_length_data = self.prepare_content_length_data(diaries)
        
        # タグ分析データの準備
        tag_frequency_data = self.prepare_tag_frequency_data(diaries)
        tag_timeline_data = self.prepare_tag_timeline_data(diaries)
        tag_correlation_data = self.prepare_tag_correlation_data(diaries)
        
        # 分析テンプレート分析データの準備
        template_usage_data = self.prepare_template_usage_data(diaries)
        template_timeline_data = self.prepare_template_timeline_data(diaries)
        template_item_stats = self.prepare_template_item_stats(diaries)
        
        # タイムラインデータの準備
        timeline_data = self.prepare_timeline_data(diaries)
        recent_trends = self.prepare_recent_trends(diaries)
        holding_period_data = self.prepare_holding_period_data(diaries)
        
        # 全てのタグを取得
        all_tags = Tag.objects.filter(user=self.request.user)
        
        # コンテキストに追加
        context.update({
            'diaries': diaries,
            'date_range': date_range,
            'selected_tag': selected_tag,
            'status': status,
            'sort': sort,
            'all_tags': all_tags,
            
            # 統計情報
            'total_stocks': total_stocks,
            'stocks_change': stocks_change,
            'total_tags': tags_used,
            'tags_change': tags_change,
            'analysis_completion_rate': analysis_stats['avg_completion_rate'],
            'analysis_rate_change': analysis_stats['change'],
            'avg_reason_length': avg_reason_length,
            'reason_length_change': reason_length_change,
            
            # 記録習慣データ
            'monthly_labels': json.dumps(monthly_data['labels']),
            'monthly_counts': json.dumps(monthly_data['counts']),
            'day_of_week_counts': json.dumps(list(day_of_week_data)),
            'activity_heatmap': activity_heatmap,
            'content_length_ranges': json.dumps(content_length_data['ranges']),
            'content_length_counts': json.dumps(content_length_data['counts']),
            
            # タグ分析データ
            'tag_names': json.dumps(tag_frequency_data['names']),
            'tag_counts': json.dumps(tag_frequency_data['counts']),
            'tag_timeline_labels': json.dumps(tag_timeline_data['labels']),
            'tag_timeline_data': mark_safe(json.dumps(tag_timeline_data['datasets'])),
            'top_tags': tag_correlation_data,
            
            # 分析テンプレートデータ
            'template_names': json.dumps(template_usage_data['names']),
            'template_usage_rates': json.dumps(template_usage_data['rates']),
            'template_timeline_labels': json.dumps(template_timeline_data['labels']),
            'template_timeline_data': json.dumps(template_timeline_data['rates']),
            'template_stats': template_item_stats,
            
            # タイムラインデータ
            'diary_timeline': timeline_data,
            'purchase_frequency': recent_trends['purchase_frequency'],
            'avg_holding_period': recent_trends['avg_holding_period'],
            'most_used_tag': recent_trends['most_used_tag'],
            'most_detailed_record': recent_trends['most_detailed_record'],
            'recent_keywords': recent_trends['keywords'],
            'holding_period_ranges': json.dumps(holding_period_data['ranges']),
            'holding_period_counts': json.dumps(holding_period_data['counts']),
        })
        
        return context
    
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

    def prepare_holding_period_data(self, diaries):
        """保有期間分布データを準備"""
        # 保有期間の範囲を定義
        ranges = ['~1週間', '1週間~1ヶ月', '1~3ヶ月', '3~6ヶ月', '6ヶ月~1年', '1年以上']
        counts = [0, 0, 0, 0, 0, 0]
        
        # 売却済みの日記で保有期間を集計
        sold_diaries = diaries.filter(sell_date__isnull=False)
        
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
        
        # 銘柄コードでグループ化
        grouped_diaries = {}
        for diary in active_diaries:
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
        
        context['grouped_diaries'] = grouped_diaries.values()
        
        # 選択された日記ID（更新用）
        diary_id = self.kwargs.get('pk')
        if diary_id:
            try:
                selected_diary = StockDiary.objects.get(
                    id=diary_id,
                    user=self.request.user
                )
                context['selected_diary'] = selected_diary
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
