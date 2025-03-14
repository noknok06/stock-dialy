# watchlist/views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.db.models import Q

from .models import WatchlistEntry, WatchlistNote
from .forms import WatchlistEntryForm, WatchlistNoteForm
from tags.models import Tag
from stockdiary.models import StockDiary

class WatchlistEntryListView(LoginRequiredMixin, ListView):
    """ウォッチリストの一覧表示"""
    model = WatchlistEntry
    template_name = 'watchlist/entry_list.html'
    context_object_name = 'entries'
    
    def get_queryset(self):
        queryset = WatchlistEntry.objects.filter(user=self.request.user).order_by('-updated_at')
        
        # 検索フィルター
        query = self.request.GET.get('query', '')
        status = self.request.GET.get('status', '')
        priority = self.request.GET.get('priority', '')
        tag_id = self.request.GET.get('tag', '')
        
        if query:
            queryset = queryset.filter(
                Q(stock_name__icontains=query) | 
                Q(stock_symbol__icontains=query)
            )
        
        if status:
            queryset = queryset.filter(status=status)
            
        if priority:
            queryset = queryset.filter(priority=priority)
            
        if tag_id:
            queryset = queryset.filter(tags__id=tag_id)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tags'] = Tag.objects.filter(user=self.request.user)
        return context

class WatchlistEntryDetailView(LoginRequiredMixin, DetailView):
    """ウォッチリストエントリーの詳細表示"""
    model = WatchlistEntry
    template_name = 'watchlist/entry_detail.html'
    context_object_name = 'entry'
    
    def get_queryset(self):
        return WatchlistEntry.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notes'] = self.object.notes.all().order_by('-date')
        context['note_form'] = WatchlistNoteForm(initial={'date': timezone.now().date()})
        
        # 同じ銘柄の購入記録があるか確認
        stock_symbol = self.object.stock_symbol
        context['related_diaries'] = StockDiary.objects.filter(
            user=self.request.user,
            stock_symbol=stock_symbol
        ).order_by('-purchase_date')
        
        return context

class WatchlistEntryCreateView(LoginRequiredMixin, CreateView):
    """ウォッチリストエントリーの新規作成"""
    model = WatchlistEntry
    form_class = WatchlistEntryForm
    template_name = 'watchlist/entry_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "ウォッチリストエントリーを作成しました")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('watchlist:detail', kwargs={'pk': self.object.pk})

class WatchlistEntryUpdateView(LoginRequiredMixin, UpdateView):
    """ウォッチリストエントリーの編集"""
    model = WatchlistEntry
    form_class = WatchlistEntryForm
    template_name = 'watchlist/entry_form.html'
    
    def get_queryset(self):
        return WatchlistEntry.objects.filter(user=self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, "ウォッチリストエントリーを更新しました")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('watchlist:detail', kwargs={'pk': self.object.pk})

class WatchlistEntryDeleteView(LoginRequiredMixin, DeleteView):
    """ウォッチリストエントリーの削除"""
    model = WatchlistEntry
    template_name = 'watchlist/entry_confirm_delete.html'
    success_url = reverse_lazy('watchlist:list')
    
    def get_queryset(self):
        return WatchlistEntry.objects.filter(user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "ウォッチリストエントリーを削除しました")
        return super().delete(request, *args, **kwargs)

class AddNoteView(LoginRequiredMixin, CreateView):
    """ウォッチリストエントリーへのメモ追加"""
    model = WatchlistNote
    form_class = WatchlistNoteForm
    http_method_names = ['post']
    
    def form_valid(self, form):
        entry_id = self.kwargs.get('pk')
        entry = get_object_or_404(WatchlistEntry, id=entry_id, user=self.request.user)
        form.instance.entry = entry
        messages.success(self.request, "メモを追加しました")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('watchlist:detail', kwargs={'pk': self.kwargs.get('pk')})
    
    def form_invalid(self, form):
        entry_id = self.kwargs.get('pk')
        return HttpResponseRedirect(reverse_lazy('watchlist:detail', kwargs={'pk': entry_id}))

# ウォッチリストから日記を作成
class CreateDiaryFromWatchlistView(LoginRequiredMixin, UpdateView):
    """ウォッチリストから日記を作成"""
    model = WatchlistEntry
    fields = ['status']
    
    def get_queryset(self):
        return WatchlistEntry.objects.filter(user=self.request.user)
    
    def form_valid(self, form):
        entry = self.object
        
        # ステータスを購入済みに更新
        entry.status = 'bought'
        entry.save()
        
        # 日記の作成ページにリダイレクト（パラメータで情報を渡す）
        return redirect(
            f"{reverse_lazy('stockdiary:create')}?stock_symbol={entry.stock_symbol}"
            f"&stock_name={entry.stock_name}&analysis={entry.analysis}"
        )