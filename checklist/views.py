# checklist/views.py
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from .models import Checklist, ChecklistItem
from .forms import ChecklistForm, ChecklistItemFormSet
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt  # 開発中のみ使用（本番環境では適切なCSRF保護を実装すること
import json
from stockdiary.models import StockDiary
from .models import ChecklistItem, DiaryChecklistItem

class ChecklistListView(LoginRequiredMixin, ListView):
    model = Checklist
    template_name = 'checklist/list.html'
    context_object_name = 'checklists'
    
    def get_queryset(self):
        queryset = Checklist.objects.filter(user=self.request.user)
        
        # 検索フィルター
        query = self.request.GET.get('query', '')
        if query:
            queryset = queryset.filter(name__icontains=query)
            
        return queryset

class ChecklistDetailView(LoginRequiredMixin, DetailView):
    model = Checklist
    template_name = 'checklist/detail.html'
    context_object_name = 'checklist'
    
    def get_queryset(self):
        return Checklist.objects.filter(user=self.request.user)

class ChecklistCreateView(LoginRequiredMixin, CreateView):
    model = Checklist
    form_class = ChecklistForm
    template_name = 'checklist/form.html'
    success_url = reverse_lazy('checklist:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items_formset'] = ChecklistItemFormSet(self.request.POST)
        else:
            # 初期表示時
            formset = ChecklistItemFormSet()
            # 最初の項目の表示順を1に設定
            formset.forms[0].initial = {'order': 1}
            context['items_formset'] = formset
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']
        
        # ユーザーを設定
        form.instance.user = self.request.user
        
        if items_formset.is_valid():
            self.object = form.save()
            items_formset.instance = self.object
            items_formset.save()
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class ChecklistUpdateView(LoginRequiredMixin, UpdateView):
    model = Checklist
    form_class = ChecklistForm
    template_name = 'checklist/form.html'
    success_url = reverse_lazy('checklist:list')
    
    def get_queryset(self):
        return Checklist.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items_formset'] = ChecklistItemFormSet(self.request.POST, instance=self.object)
        else:
            context['items_formset'] = ChecklistItemFormSet(instance=self.object)
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']
        
        if items_formset.is_valid():
            self.object = form.save()
            items_formset.instance = self.object
            items_formset.save()
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class ChecklistDeleteView(LoginRequiredMixin, DeleteView):
    model = Checklist
    template_name = 'checklist/confirm_delete.html'
    success_url = reverse_lazy('checklist:list')
    
    def get_queryset(self):
        return Checklist.objects.filter(user=self.request.user)

# checklist/views.py
@login_required
@require_POST
@csrf_exempt  # 開発中のみ使用
def toggle_checklist_item(request, item_id):
    try:
        # デバッグ出力を追加
        print(f"Received request for item_id: {item_id}")
        print(f"Request body: {request.body}")
        
        # リクエストからデータを取得（例外処理を改善）
        try:
            data = json.loads(request.body)
            status = data.get('status', False)
        except json.JSONDecodeError:
            print("JSON decode error")
            # フォームデータとして処理を試みる
            status = request.POST.get('status') == 'true'
        
        print(f"Status value: {status}")
        
        # チェックリストアイテムを取得
        try:
            item = ChecklistItem.objects.get(id=item_id)
            print(f"Found checklist item: {item}")
        except ChecklistItem.DoesNotExist:
            print(f"Checklist item {item_id} not found")
            return JsonResponse({'error': 'チェックリストアイテムが見つかりません'}, status=404)
        
        # 日記IDを取得（URLパラメータからも取得できるように修正）
        diary_id = request.session.get('current_diary_id')
        if not diary_id:
            # URLからの取得も試みる
            diary_id = request.POST.get('diary_id') or request.GET.get('diary_id')
            
        if not diary_id:
            print("No diary ID found")
            return JsonResponse({'error': '日記IDが見つかりません'}, status=400)
            
        try:
            diary = StockDiary.objects.get(id=diary_id, user=request.user)
            print(f"Found diary: {diary}")
        except StockDiary.DoesNotExist:
            print(f"Diary {diary_id} not found")
            return JsonResponse({'error': '日記が見つかりません'}, status=404)
        
        # DiaryChecklistItemを取得または作成
        diary_item, created = DiaryChecklistItem.objects.get_or_create(
            diary=diary,
            checklist_item=item,
            defaults={'status': status}
        )
        
        # 既存のアイテムの場合は状態を更新
        if not created:
            diary_item.status = status
            diary_item.save()
        
        print(f"Successfully updated item status to {status}")
        return JsonResponse({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        import traceback
        print(f"Error in toggle_checklist_item: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)