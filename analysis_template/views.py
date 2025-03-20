# analysis_template/views.py
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Prefetch
from django.db import transaction

from .models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from .forms import AnalysisTemplateForm, AnalysisItemFormSet, create_analysis_value_formset
from stockdiary.models import StockDiary
from subscriptions.mixins import SubscriptionLimitCheckMixin

class AnalysisTemplateListView(LoginRequiredMixin, ListView):
    model = AnalysisTemplate
    template_name = 'analysis_template/list.html'
    context_object_name = 'templates'
    
    def get_queryset(self):
        return AnalysisTemplate.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'add',
                'url': reverse_lazy('analysis_template:create'),  # テンプレート作成ページ
                'icon': 'bi-plus-lg',
                'label': '新規テンプレート'
            },
        ]
        context['page_actions'] = analytics_actions
        return context

class AnalysisTemplateDetailView(LoginRequiredMixin, DetailView):
    model = AnalysisTemplate
    template_name = 'analysis_template/detail.html'
    context_object_name = 'template'
    
    def get_queryset(self):
        return AnalysisTemplate.objects.filter(user=self.request.user).prefetch_related('items')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        diary = self.object
        user = self.request.user
        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'report',
                'url': reverse_lazy('analysis_template:report', kwargs={'pk': diary.id}),
                'icon': 'bi-file-bar-graph',
                'label': 'レポート'
            },
            {
                'type': 'edit',
                'url': reverse_lazy('analysis_template:update', kwargs={'pk': diary.id}),
                'icon': 'bi-pencil',
                'label': '編集'
            },
        ]
        context['page_actions'] = analytics_actions
        return context
        
class AnalysisTemplateCreateView(SubscriptionLimitCheckMixin, LoginRequiredMixin, CreateView):
    model = AnalysisTemplate
    form_class = AnalysisTemplateForm
    template_name = 'analysis_template/form.html'
    success_url = reverse_lazy('analysis_template:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if self.request.POST:
            context['items_formset'] = AnalysisItemFormSet(self.request.POST)
        else:
            # 初期表示時
            formset = AnalysisItemFormSet()
            # 最初の項目の表示順を1に設定
            formset.forms[0].initial = {'order': 1}
            context['items_formset'] = formset

        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('analysis_template:list'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        context['page_actions'] = analytics_actions

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

class AnalysisTemplateUpdateView(LoginRequiredMixin, UpdateView):
    model = AnalysisTemplate
    form_class = AnalysisTemplateForm
    template_name = 'analysis_template/form.html'
    
    def get_queryset(self):
        return AnalysisTemplate.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        diary = self.object

        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('analysis_template:detail', kwargs={'pk': diary.id}),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        context['page_actions'] = analytics_actions
        
        if self.request.POST:
            context['items_formset'] = AnalysisItemFormSet(self.request.POST, instance=self.object)
        else:
            context['items_formset'] = AnalysisItemFormSet(instance=self.object)
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']
        
        if items_formset.is_valid():
            self.object = form.save()
            items_formset.instance = self.object
            items_formset.save()
            return redirect('analysis_template:detail', pk=self.object.pk)
        else:
            return self.render_to_response(self.get_context_data(form=form))
            
    def get_success_url(self):
        return reverse_lazy('analysis_template:detail', kwargs={'pk': self.object.pk})

class AnalysisTemplateDeleteView(LoginRequiredMixin, DeleteView):
    model = AnalysisTemplate
    template_name = 'analysis_template/confirm_delete.html'
    success_url = reverse_lazy('analysis_template:list')
    
    def get_queryset(self):
        return AnalysisTemplate.objects.filter(user=self.request.user)

# views.py の AnalysisReportView クラスの修正版

# analysis_template/views.py の AnalysisReportView クラスの修正版

# analysis_template/views.py の AnalysisReportView クラスの修正版

class AnalysisReportView(LoginRequiredMixin, DetailView):
    """テンプレートに基づいた分析レポートを表示するビュー"""
    model = AnalysisTemplate
    template_name = 'analysis_template/report.html'
    context_object_name = 'template'
    
    def get_queryset(self):
        return AnalysisTemplate.objects.filter(user=self.request.user).prefetch_related('items')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template = self.object
        
        # フィルターを取得
        condition_filter = self.request.GET.get('condition_filter')
        
        # テンプレートを使用している日記を取得
        diaries = StockDiary.objects.filter(
            user=self.request.user
        ).prefetch_related(
            Prefetch(
                'analysis_values',
                queryset=DiaryAnalysisValue.objects.filter(
                    analysis_item__template=template
                ).select_related('analysis_item')
            )
        )

        # 統計情報とレポートデータの準備
        report_data = []
        condition_stats = {}  # 条件達成統計
        total_completion = 0
        total_items_count = 0
        
        # テンプレートの項目数を取得
        template_items_count = template.items.count()
        
        # レポートデータ作成
        for diary in diaries:
            diary_data = {
                'diary': diary,
                'values': {},
                'conditions_met': 0,
                'total_conditions': 0,
                'completion_rate': 0
            }
            
            # 現在の日記のテンプレート項目に対する分析値を取得
            diary_analysis_values = {value.analysis_item_id: value for value in diary.analysis_values.all() 
                                    if value.analysis_item.template_id == template.id}
            
            completed_items = 0
            diary_has_values = len(diary_analysis_values) > 0
            
            # すべてのテンプレート項目をループ処理
            for item in template.items.all():
                value = diary_analysis_values.get(item.id)
                
                # 値が存在しない場合は空の値として処理
                if not value:
                    if item.item_type == 'boolean_with_value':
                        diary_data['values'][item.id] = {
                            'boolean_value': None,
                            'number_value': None,
                            'text_value': None
                        }
                    elif item.item_type == 'boolean':
                        diary_data['values'][item.id] = None
                    elif item.item_type == 'number':
                        diary_data['values'][item.id] = None
                    else:  # text または select
                        diary_data['values'][item.id] = None
                    continue
                
                # 項目タイプによって異なる処理
                if item.item_type == 'boolean_with_value':
                    # Boolean値と数値/テキスト値の両方を保持
                    diary_data['values'][item.id] = {
                        'boolean_value': value.boolean_value,
                        'number_value': value.number_value,
                        'text_value': value.text_value
                    }
                    
                    # 条件達成状況の更新
                    diary_data['total_conditions'] += 1
                    if value.boolean_value:
                        diary_data['conditions_met'] += 1
                        completed_items += 1
                
                elif item.item_type == 'boolean':
                    diary_data['values'][item.id] = value.boolean_value
                    if value.boolean_value:
                        completed_items += 1
                    
                elif item.item_type == 'number':
                    diary_data['values'][item.id] = value.number_value
                    if value.number_value is not None:
                        completed_items += 1
                    
                else:  # text または select
                    diary_data['values'][item.id] = value.text_value
                    if value.text_value:
                        completed_items += 1
            
            # 完了率を計算 - 分析値の有無に関わらず、すべての日記について計算
            if template_items_count > 0 and diary_has_values:
                completion_rate = (completed_items / template_items_count) * 100
                diary_data['completion_rate'] = round(completion_rate, 1)
                total_completion += completion_rate
                total_items_count += 1
            
            # レポートデータに追加（分析値がある場合のみ）
            if diary_has_values:
                report_data.append(diary_data)
        
        # テンプレート平均完了率の計算
        avg_completion_rate = 0
        if total_items_count > 0:
            avg_completion_rate = total_completion / total_items_count
        
        context['report_data'] = report_data
        context['condition_stats'] = condition_stats
        context['avg_completion_rate'] = round(avg_completion_rate, 1)
        
        # 項目別の完了状況を計算
        items_completion = []
        for item in template.items.all():
            item_data = {
                'id': item.id,
                'name': item.name,
                'description': item.description,
                'item_type': item.item_type,
                'completed_count': 0,
                'total_count': 0,
                'completion_rate': 0
            }
            
            # すべての日記データについて項目の完了状況を確認
            for diary_data in report_data:
                # すべての日記で項目の総数をインクリメント
                item_data['total_count'] += 1
                
                # 該当項目の値を取得
                if item.id in diary_data['values']:
                    value = diary_data['values'][item.id]
                    
                    # 項目タイプに応じて完了判定
                    if item.item_type == 'boolean_with_value':
                        if value and value['boolean_value']:
                            item_data['completed_count'] += 1
                    elif item.item_type == 'boolean':
                        if value:
                            item_data['completed_count'] += 1
                    elif item.item_type == 'number':
                        if value is not None:
                            item_data['completed_count'] += 1
                    else:  # text または select
                        if value:
                            item_data['completed_count'] += 1
            
            # 完了率を計算
            if item_data['total_count'] > 0:
                item_data['completion_rate'] = round((item_data['completed_count'] / item_data['total_count']) * 100, 1)
            
            items_completion.append(item_data)
        
        context['items_completion'] = items_completion

        diary = self.object
        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('analysis_template:detail', kwargs={'pk': diary.id}),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        context['page_actions'] = analytics_actions

        return context