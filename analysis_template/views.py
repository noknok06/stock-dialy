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

class AnalysisTemplateListView(LoginRequiredMixin, ListView):
    model = AnalysisTemplate
    template_name = 'analysis_template/list.html'
    context_object_name = 'templates'
    
    def get_queryset(self):
        return AnalysisTemplate.objects.filter(user=self.request.user)

class AnalysisTemplateDetailView(LoginRequiredMixin, DetailView):
    model = AnalysisTemplate
    template_name = 'analysis_template/detail.html'
    context_object_name = 'template'
    
    def get_queryset(self):
        return AnalysisTemplate.objects.filter(user=self.request.user).prefetch_related('items')

class AnalysisTemplateCreateView(LoginRequiredMixin, CreateView):
    model = AnalysisTemplate
    form_class = AnalysisTemplateForm
    template_name = 'analysis_template/form.html'
    success_url = reverse_lazy('analysis_template:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items_formset'] = AnalysisItemFormSet(self.request.POST)
        else:
            # 初期表示時
            formset = AnalysisItemFormSet()
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

class AnalysisTemplateUpdateView(LoginRequiredMixin, UpdateView):
    model = AnalysisTemplate
    form_class = AnalysisTemplateForm
    template_name = 'analysis_template/form.html'
    
    def get_queryset(self):
        return AnalysisTemplate.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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
        
        # レポートデータ作成
        for diary in diaries:
            diary_data = {
                'diary': diary,
                'values': {},
                'conditions_met': 0,
                'total_conditions': 0
            }
            
            # この日記の該当テンプレートの値を処理
            diary_has_values = False
            
            for value in diary.analysis_values.all():
                if value.analysis_item.template_id == template.id:
                    diary_has_values = True
                    item = value.analysis_item
                    
                    # 複合型項目と他の項目タイプによって異なる処理
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
                    
                    # その他の項目タイプも処理
            
            # レポートデータに追加
            if diary_has_values:
                report_data.append(diary_data)
        
        context['report_data'] = report_data
        context['condition_stats'] = condition_stats
        
        return context