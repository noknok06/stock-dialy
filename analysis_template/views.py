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

        # レポート用のデータ構造を構築
        report_data = []
        for diary in diaries:
            # この日記のこのテンプレートの分析項目値が存在するかチェック
            has_values = any(
                value.analysis_item.template_id == template.id 
                for value in diary.analysis_values.all()
            )
            
            if has_values:
                diary_data = {
                    'diary': diary,
                    'values': {}
                }
                
                # 分析項目ごとの値を設定
                for value in diary.analysis_values.all():
                    if value.analysis_item.template_id == template.id:
                        if value.analysis_item.item_type == 'number':
                            diary_data['values'][value.analysis_item.id] = value.number_value
                        else:
                            diary_data['values'][value.analysis_item.id] = value.text_value
                
                report_data.append(diary_data)
        
        context['report_data'] = report_data
        return context