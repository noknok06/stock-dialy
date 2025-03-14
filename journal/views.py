# journal/views.py
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.db.models import Q
import json
import datetime
import requests

from .models import JournalEntry, Stock, ThesisChangeTracker
from .forms import JournalEntryForm, StockForm, StockSearchForm
from analysis_template.models import AnalysisTemplate, DiaryAnalysisValue

class StockListView(LoginRequiredMixin, ListView):
    """銘柄一覧を表示するビュー"""
    model = Stock
    template_name = 'journal/stock_list.html'
    context_object_name = 'stocks'
    
    def get_queryset(self):
        queryset = Stock.objects.filter(user=self.request.user)
        
        # 検索フォームからのフィルタリング
        form = StockSearchForm(self.request.GET)
        if form.is_valid():
            query = form.cleaned_data.get('query')
            status = form.cleaned_data.get('status')
            industry = form.cleaned_data.get('industry')
            
            if query:
                queryset = queryset.filter(
                    Q(symbol__icontains=query) | 
                    Q(name__icontains=query)
                )
            
            if status and status != 'all':
                queryset = queryset.filter(status=status)
            
            if industry:
                queryset = queryset.filter(industry__icontains=industry)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = StockSearchForm(self.request.GET)
        
        # 銘柄ステータス別の集計
        context['watching_count'] = Stock.objects.filter(user=self.request.user, status='watching').count()
        context['holding_count'] = Stock.objects.filter(user=self.request.user, status='holding').count()
        context['sold_count'] = Stock.objects.filter(user=self.request.user, status='sold').count()
        
        return context

class StockDetailView(LoginRequiredMixin, DetailView):
    """銘柄の詳細とタイムラインを表示するビュー"""
    model = Stock
    template_name = 'journal/stock_detail.html'
    context_object_name = 'stock'
    
    def get_queryset(self):
        return Stock.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock = self.object
        
        # 銘柄に関連する日記エントリーを取得
        context['journal_entries'] = JournalEntry.objects.filter(
            stock=stock
        ).order_by('-entry_date')
        
        # 最新の株価データを取得
        context['current_price'], context['daily_change'] = self.get_stock_price(stock.symbol)
        
        # チャート用の株価データを取得
        context['price_data'] = self.get_price_chart_data(stock.symbol)
        
        # 保有中の場合、パフォーマンスを計算
        if stock.status == 'holding' and stock.purchase_price:
            context['stock_performance'] = (
                (context['current_price'] - float(stock.purchase_price)) / 
                float(stock.purchase_price) * 100
            )
        
        # 売却済みの場合、保有期間リターンを計算
        if stock.status == 'sold' and stock.purchase_price and stock.sell_price:
            context['holding_return'] = (
                (float(stock.sell_price) - float(stock.purchase_price)) / 
                float(stock.purchase_price) * 100
            )
        
        # 投資判断の変化ポイントを取得
        context['thesis_changes'] = ThesisChangeTracker.objects.filter(
            stock=stock
        ).select_related('from_entry', 'to_entry').order_by('-created_at')
        
        return context
    
    def get_stock_price(self, symbol):
        """Yahoo Finance APIから株価を取得"""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.T"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            data = response.json()
            
            if 'chart' in data and 'result' in data['chart'] and len(data['chart']['result']) > 0:
                meta = data['chart']['result'][0]['meta']
                
                # 現在価格を取得
                current_price = meta.get('regularMarketPrice', 0)
                
                # 前日比を計算 (%)
                prev_close = meta.get('previousClose')
                if current_price is not None and prev_close is not None and prev_close > 0:
                    daily_change = ((current_price - prev_close) / prev_close) * 100
                else:
                    daily_change = 0
                
                return current_price, daily_change
            
            return 0, 0
        except Exception as e:
            print(f"株価取得エラー: {str(e)}")
            return 0, 0
    
    def get_price_chart_data(self, symbol):
        """チャート用の株価データを取得"""
        try:
            # 1年分のデータを取得
            end_time = int(datetime.datetime.now().timestamp())
            start_time = end_time - (365 * 24 * 60 * 60)  # 1年前
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.T?period1={start_time}&period2={end_time}&interval=1d"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            data = response.json()
            
            if 'chart' in data and 'result' in data['chart'] and len(data['chart']['result']) > 0:
                result = data['chart']['result'][0]
                timestamps = result['timestamp']
                quotes = result['indicators']['quote'][0]
                
                # 日付と株価のリストを作成
                dates = []
                prices = []
                
                for i, timestamp in enumerate(timestamps):
                    if 'close' in quotes and i < len(quotes['close']) and quotes['close'][i] is not None:
                        dt = datetime.datetime.fromtimestamp(timestamp)
                        dates.append(dt.strftime('%Y-%m-%d'))
                        prices.append(quotes['close'][i])
                
                return {'dates': dates, 'prices': prices}
            
            return {'dates': [], 'prices': []}
        except Exception as e:
            print(f"株価チャートデータ取得エラー: {str(e)}")
            return {'dates': [], 'prices': []}

class StockCreateView(LoginRequiredMixin, CreateView):
    """新規銘柄を作成するビュー"""
    model = Stock
    form_class = StockForm
    template_name = 'journal/stock_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_success_url(self):
        return reverse('journal:stock_detail', kwargs={'pk': self.object.pk})

class StockUpdateView(LoginRequiredMixin, UpdateView):
    """銘柄情報を編集するビュー"""
    model = Stock
    form_class = StockForm
    template_name = 'journal/stock_form.html'
    
    def get_queryset(self):
        return Stock.objects.filter(user=self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_success_url(self):
        return reverse('journal:stock_detail', kwargs={'pk': self.object.pk})

class JournalEntryListView(LoginRequiredMixin, ListView):
    """投資判断記録の一覧を表示するビュー"""
    model = JournalEntry
    template_name = 'journal/journal_list.html'
    context_object_name = 'entries'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = JournalEntry.objects.filter(user=self.request.user)
        
        # 検索フィルタリング
        stock_id = self.request.GET.get('stock')
        entry_type = self.request.GET.get('type')
        tag_id = self.request.GET.get('tag')
        query = self.request.GET.get('query')
        
        if stock_id:
            queryset = queryset.filter(stock_id=stock_id)
        
        if entry_type:
            queryset = queryset.filter(entry_type=entry_type)
        
        if tag_id:
            queryset = queryset.filter(tags__id=tag_id)
        
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | 
                Q(content__icontains=query)
            )
        
        return queryset.order_by('-entry_date', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 銘柄リスト（フィルター用）
        context['stocks'] = Stock.objects.filter(user=self.request.user)
        
        # 記録タイプ別のカウント
        context['watch_count'] = JournalEntry.objects.filter(user=self.request.user, entry_type='watch').count()
        context['research_count'] = JournalEntry.objects.filter(user=self.request.user, entry_type='research').count()
        context['trade_count'] = JournalEntry.objects.filter(user=self.request.user, entry_type='trade').count()
        context['holding_count'] = JournalEntry.objects.filter(user=self.request.user, entry_type='holding').count()
        context['market_count'] = JournalEntry.objects.filter(user=self.request.user, entry_type='market').count()
        
        return context

class JournalEntryDetailView(LoginRequiredMixin, DetailView):
    """投資判断記録の詳細を表示するビュー"""
    model = JournalEntry
    template_name = 'journal/journal_detail.html'
    context_object_name = 'entry'
    
    def get_queryset(self):
        return JournalEntry.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entry = self.object
        
        # 前後のエントリー
        context['previous_entry'] = JournalEntry.objects.filter(
            user=self.request.user,
            stock=entry.stock,
            entry_date__lt=entry.entry_date
        ).order_by('-entry_date').first()
        
        context['next_entry'] = JournalEntry.objects.filter(
            user=self.request.user,
            stock=entry.stock,
            entry_date__gt=entry.entry_date
        ).order_by('entry_date').first()
        
        # 分析テンプレート値を取得
        if entry.analysis_template:
            context['analysis_values'] = DiaryAnalysisValue.objects.filter(
                diary_entry=entry
            ).select_related('analysis_item')
        
        # チェックリスト項目のステータスを取得
        context['checklist_items'] = entry.checklist_items.all().select_related(
            'checklist_item', 'checklist_item__checklist'
        )
        
        # 投資判断の変化（このエントリーが起点または終点）
        context['thesis_changes_from'] = ThesisChangeTracker.objects.filter(
            from_entry=entry
        ).select_related('to_entry')
        
        context['thesis_changes_to'] = ThesisChangeTracker.objects.filter(
            to_entry=entry
        ).select_related('from_entry')
        
        return context

class JournalEntryCreateView(LoginRequiredMixin, CreateView):
    """新規投資判断記録を作成するビュー"""
    model = JournalEntry
    form_class = JournalEntryForm
    template_name = 'journal/journal_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        
        # 前回のエントリーがあれば取得
        stock_id = self.request.GET.get('stock')
        if stock_id:
            previous_entry = JournalEntry.objects.filter(
                user=self.request.user,
                stock_id=stock_id
            ).order_by('-entry_date').first()
            
            if previous_entry:
                kwargs['previous_entry'] = previous_entry
        
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        
        # GETパラメータから初期値を設定
        stock_id = self.request.GET.get('stock')
        entry_type = self.request.GET.get('type')
        
        if stock_id:
            initial['stock'] = stock_id
        
        if entry_type and entry_type in dict(JournalEntry.ENTRY_TYPE_CHOICES).keys():
            initial['entry_type'] = entry_type
        
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 前回のエントリーがあれば取得
        stock_id = self.request.GET.get('stock')
        if stock_id:
            try:
                stock = Stock.objects.get(id=stock_id, user=self.request.user)
                context['stock'] = stock
                
                previous_entry = JournalEntry.objects.filter(
                    user=self.request.user,
                    stock=stock
                ).order_by('-entry_date').first()
                
                if previous_entry:
                    context['previous_entry'] = previous_entry
            except Stock.DoesNotExist:
                pass
        
        return context
    
    def get_success_url(self):
        return reverse('journal:journal_detail', kwargs={'pk': self.object.pk})

class JournalEntryUpdateView(LoginRequiredMixin, UpdateView):
    """投資判断記録を編集するビュー"""
    model = JournalEntry
    form_class = JournalEntryForm
    template_name = 'journal/journal_form.html'
    
    def get_queryset(self):
        return JournalEntry.objects.filter(user=self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        
        # 前回のエントリーがあれば設定
        entry = self.get_object()
        previous_entry = JournalEntry.objects.filter(
            user=self.request.user,
            stock=entry.stock,
            entry_date__lt=entry.entry_date
        ).order_by('-entry_date').first()
        
        if previous_entry:
            kwargs['previous_entry'] = previous_entry
        
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entry = self.get_object()
        
        # 前回のエントリーを取得
        previous_entry = JournalEntry.objects.filter(
            user=self.request.user,
            stock=entry.stock,
            entry_date__lt=entry.entry_date
        ).order_by('-entry_date').first()
        
        if previous_entry:
            context['previous_entry'] = previous_entry
        
        return context
    
    def get_success_url(self):
        return reverse('journal:journal_detail', kwargs={'pk': self.object.pk})

class JournalEntryDeleteView(LoginRequiredMixin, DeleteView):
    """投資判断記録を削除するビュー"""
    model = JournalEntry
    template_name = 'journal/journal_confirm_delete.html'
    
    def get_queryset(self):
        return JournalEntry.objects.filter(user=self.request.user)
    
    def get_success_url(self):
        # 削除後は銘柄の詳細ページに戻る
        return reverse('journal:stock_detail', kwargs={'pk': self.object.stock.pk})

class DashboardView(LoginRequiredMixin, TemplateView):
    """投資記録ダッシュボードを表示するビュー"""
    template_name = 'journal/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # ポートフォリオの概要
        context['watching_stocks'] = Stock.objects.filter(
            user=self.request.user, 
            status='watching'
        ).count()
        
        context['holding_stocks'] = Stock.objects.filter(
            user=self.request.user, 
            status='holding'
        ).count()
        
        context['sold_stocks'] = Stock.objects.filter(
            user=self.request.user, 
            status='sold'
        ).count()
        
        # 記録活動の統計
        context['total_entries'] = JournalEntry.objects.filter(
            user=self.request.user
        ).count()
        
        # 最近の記録
        context['recent_entries'] = JournalEntry.objects.filter(
            user=self.request.user
        ).order_by('-created_at')[:5]
        
        # 最近の投資判断変化
        context['recent_changes'] = ThesisChangeTracker.objects.filter(
            stock__user=self.request.user
        ).select_related('stock', 'from_entry', 'to_entry').order_by('-created_at')[:5]
        
        # 保有中銘柄のパフォーマンス
        holding_stocks = Stock.objects.filter(
            user=self.request.user, 
            status='holding'
        ).exclude(purchase_price__isnull=True)
        
        context['holding_performances'] = []
        
        for stock in holding_stocks:
            current_price, _ = self.get_stock_price(stock.symbol)
            if current_price > 0 and stock.purchase_price:
                performance = (current_price - float(stock.purchase_price)) / float(stock.purchase_price) * 100
                context['holding_performances'].append({
                    'stock': stock,
                    'current_price': current_price,
                    'performance': performance
                })
        
        return context
    
    def get_stock_price(self, symbol):
        """Yahoo Finance APIから株価を取得"""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.T"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            data = response.json()
            
            if 'chart' in data and 'result' in data['chart'] and len(data['chart']['result']) > 0:
                meta = data['chart']['result'][0]['meta']
                
                # 現在価格を取得
                current_price = meta.get('regularMarketPrice', 0)
                
                # 前日比を計算 (%)
                prev_close = meta.get('previousClose')
                if current_price is not None and prev_close is not None and prev_close > 0:
                    daily_change = ((current_price - prev_close) / prev_close) * 100
                else:
                    daily_change = 0
                
                return current_price, daily_change
            
            return 0, 0
        except Exception as e:
            print(f"株価取得エラー: {str(e)}")
            return 0, 0

            