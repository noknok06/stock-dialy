# tags/views.py
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from .models import Tag
from django import forms
from datetime import datetime


from subscriptions.mixins import SubscriptionLimitCheckMixin

class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'})
        }

class TagListView(LoginRequiredMixin, ListView):
    model = Tag
    template_name = 'tags/tag_list.html'
    context_object_name = 'tags'
    
    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # スピードダイアルのアクションを定義
        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'add',
                'url': reverse_lazy('tags:create'),
                'icon': 'bi-plus-lg',
                'label': '新規作成'
            }
        ]
        context['page_actions'] = analytics_actions
        return context

class TagDetailView(LoginRequiredMixin, DetailView):
    model = Tag
    template_name = 'tags/tag_detail.html'
    context_object_name = 'tag'
    
    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tag = self.object
        
        # このタグが設定されている日記を取得
        diaries = tag.stockdiary_set.select_related('user').prefetch_related('tags').order_by('-created_at')
        
        # 銘柄ごとにグループ化
        stock_groups = {}
        for diary in diaries:
            symbol = diary.stock_symbol or 'unknown'
            if symbol not in stock_groups:
                stock_groups[symbol] = {
                    'symbol': diary.stock_symbol,
                    'name': diary.stock_name,
                    'sector': diary.sector,
                    'diaries': [],
                    'total_entries': 0,
                    'active_holdings': 0,
                    'completed_sales': 0,
                    'memo_entries': 0,
                    'latest_date': None,
                    'earliest_date': None
                }
            
            stock_groups[symbol]['diaries'].append(diary)
            stock_groups[symbol]['total_entries'] += 1
            
            # latest_date と earliest_date の更新
            if stock_groups[symbol]['latest_date'] is None or diary.created_at > stock_groups[symbol]['latest_date']:
                stock_groups[symbol]['latest_date'] = diary.created_at
            
            if stock_groups[symbol]['earliest_date'] is None or diary.created_at < stock_groups[symbol]['earliest_date']:
                stock_groups[symbol]['earliest_date'] = diary.created_at
                
        # 銘柄リストをソート（最新日付順）
        stock_list = list(stock_groups.values())
        
        # latest_date と earliest_date が None の場合に適切な値を設定
        stock_list.sort(key=lambda x: x['latest_date'] or datetime.min, reverse=True)
        
        # 統計情報
        stats = {
            'total_diaries': diaries.count(),
            'unique_stocks': len(stock_groups),
            'active_holdings': sum(stock['active_holdings'] for stock in stock_list),
            'completed_sales': sum(stock['completed_sales'] for stock in stock_list),
            'memo_entries': sum(stock['memo_entries'] for stock in stock_list),
        }
        
        # 保有状況フィルター
        status_filter = self.request.GET.get('status', 'all')
        if status_filter == 'active':
            stock_list = [stock for stock in stock_list if stock['active_holdings'] > 0]
        elif status_filter == 'sold':
            stock_list = [stock for stock in stock_list if stock['completed_sales'] > 0]
        elif status_filter == 'memo':
            stock_list = [stock for stock in stock_list if stock['memo_entries'] > 0]
        
        # 検索フィルター
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            stock_list = [
                stock for stock in stock_list
                if (stock['name'] and search_query.lower() in stock['name'].lower()) or
                (stock['symbol'] and search_query.lower() in stock['symbol'].lower()) or
                (stock['sector'] and search_query.lower() in stock['sector'].lower())
            ]
        
        context.update({
            'stock_list': stock_list,
            'stats': stats,
            'status_filter': status_filter,
            'search_query': search_query,
        })
        
        # スピードダイアル用のアクション
        context['page_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'edit',
                'url': reverse_lazy('tags:update', kwargs={'pk': tag.pk}),
                'icon': 'bi-pencil',
                'label': 'タグ編集'
            },
            {
                'type': 'add',
                'url': reverse_lazy('stockdiary:create'),
                'icon': 'bi-plus-lg',
                'label': '新規作成'
            }
        ]
        
        return context

class TagCreateView(SubscriptionLimitCheckMixin, LoginRequiredMixin, CreateView):
    model = Tag
    form_class = TagForm
    template_name = 'tags/tag_form.html'
    success_url = reverse_lazy('tags:list')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # スピードダイアルのアクションを定義
        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        context['page_actions'] = analytics_actions
        return context

class TagUpdateView(LoginRequiredMixin, UpdateView):
    model = Tag
    form_class = TagForm
    template_name = 'tags/tag_form.html'
    success_url = reverse_lazy('tags:list')
    
    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # スピードダイアルのアクションを定義
        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        context['page_actions'] = analytics_actions
        return context

class TagDeleteView(LoginRequiredMixin, DeleteView):
    model = Tag
    template_name = 'tags/tag_confirm_delete.html'
    success_url = reverse_lazy('tags:list')
    
    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # スピードダイアルのアクションを定義
        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        context['page_actions'] = analytics_actions
        return context