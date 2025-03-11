# analysis_templates/views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
import json

from .models import AnalysisTemplate, TemplateGroup, TemplateField, StockAnalysisData, FieldValue
from .forms import (
    AnalysisTemplateForm, TemplateGroupFormSet, TemplateFieldFormSet,
    FieldValueForm, create_field_value_forms
)
from stockdiary.models import StockDiary

class AnalysisTemplateListView(LoginRequiredMixin, ListView):
    """分析テンプレート一覧ビュー"""
    model = AnalysisTemplate
    template_name = 'analysis_templates/list.html'
    context_object_name = 'templates'
    
    def get_queryset(self):
        queryset = AnalysisTemplate.objects.filter(user=self.request.user)
        
        # 検索フィルター
        query = self.request.GET.get('query', '')
        if query:
            queryset = queryset.filter(name__icontains=query)
            
        return queryset

from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView
from .models import AnalysisTemplate

class AnalysisTemplateDetailView(LoginRequiredMixin, DetailView):
    model = AnalysisTemplate
    template_name = 'analysis_templates/detail.html'
    context_object_name = 'template'
    
    def get_queryset(self):
        return AnalysisTemplate.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template = self.object
        
        # グループごとにフィールドを整理
        groups = template.groups.all().prefetch_related('fields')
        
        # グループなしのフィールドを明示的に取得
        ungrouped_fields = template.fields.filter(group__isnull=True)
        
        context['groups'] = groups
        context['ungrouped_fields'] = ungrouped_fields
        
        # フィールドフォームを辞書形式で渡す
        field_forms = {}
        for field in template.fields.all():
            field_forms[field.id] = (field.order, FieldValueForm(instance=FieldValue(field=field)))
        
        context['field_forms'] = field_forms
        
        # このテンプレートを使用している日記数
        context['usage_count'] = StockAnalysisData.objects.filter(template=template).count()
        
        return context

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except Exception:
            # エラーが発生した場合、テンプレート一覧にリダイレクト
            return redirect('analysis_templates:list')
            
class AnalysisTemplateCreateView(LoginRequiredMixin, CreateView):
    """分析テンプレート作成ビュー"""
    model = AnalysisTemplate
    form_class = AnalysisTemplateForm
    template_name = 'analysis_templates/form.html'
    success_url = reverse_lazy('analysis_templates:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['groups_formset'] = TemplateGroupFormSet(self.request.POST)
            context['fields_formset'] = TemplateFieldFormSet(self.request.POST)
        else:
            # 初期表示時
            context['groups_formset'] = TemplateGroupFormSet()
            context['fields_formset'] = TemplateFieldFormSet()
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        groups_formset = context['groups_formset']
        fields_formset = context['fields_formset']
        
        # ユーザーを設定
        form.instance.user = self.request.user
        
        if groups_formset.is_valid() and fields_formset.is_valid():
            self.object = form.save()
            
            # グループを保存
            groups_formset.instance = self.object
            groups_formset.save()
            
            # フィールドを保存
            fields_formset.instance = self.object
            fields_formset.save()
            
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class AnalysisTemplateUpdateView(LoginRequiredMixin, UpdateView):
    """分析テンプレート更新ビュー"""
    model = AnalysisTemplate
    form_class = AnalysisTemplateForm
    template_name = 'analysis_templates/form.html'
    success_url = reverse_lazy('analysis_templates:list')
    
    def get_queryset(self):
        return AnalysisTemplate.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['groups_formset'] = TemplateGroupFormSet(self.request.POST, instance=self.object)
            context['fields_formset'] = TemplateFieldFormSet(self.request.POST, instance=self.object)
        else:
            context['groups_formset'] = TemplateGroupFormSet(instance=self.object)
            context['fields_formset'] = TemplateFieldFormSet(instance=self.object)
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        groups_formset = context['groups_formset']
        fields_formset = context['fields_formset']
        
        if groups_formset.is_valid() and fields_formset.is_valid():
            self.object = form.save()
            
            # グループを保存
            groups_formset.instance = self.object
            groups_formset.save()
            
            # フィールドを保存
            fields_formset.instance = self.object
            fields_formset.save()
            
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class AnalysisTemplateDeleteView(LoginRequiredMixin, DeleteView):
    """分析テンプレート削除ビュー"""
    model = AnalysisTemplate
    template_name = 'analysis_templates/confirm_delete.html'
    success_url = reverse_lazy('analysis_templates:list')
    
    def get_queryset(self):
        return AnalysisTemplate.objects.filter(user=self.request.user)

# 日記に紐づいた分析データ入力ビュー
class StockAnalysisDataInputView(LoginRequiredMixin, TemplateView):
    """分析データ入力ビュー"""
    template_name = 'analysis_templates/data_input.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        diary_id = self.kwargs.get('diary_id')
        diary = get_object_or_404(StockDiary, id=diary_id, user=self.request.user)
        
        # ユーザーのテンプレート一覧
        templates = AnalysisTemplate.objects.filter(user=self.request.user)
        
        # 選択されたテンプレート
        template_id = self.request.GET.get('template_id')
        selected_template = None
        
        if template_id:
            try:
                selected_template = templates.get(id=template_id)
            except AnalysisTemplate.DoesNotExist:
                pass
        
        # 既存の分析データがあるか確認
        analysis_data = None
        if selected_template:
            analysis_data = StockAnalysisData.objects.filter(
                diary=diary,
                template=selected_template
            ).first()
        
        # フィールド値フォームを生成
        field_forms = []
        if selected_template:
            field_forms = create_field_value_forms(selected_template, analysis_data)
        
        context.update({
            'diary': diary,
            'templates': templates,
            'selected_template': selected_template,
            'analysis_data': analysis_data,
            'field_forms': field_forms
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        diary_id = self.kwargs.get('diary_id')
        diary = get_object_or_404(StockDiary, id=diary_id, user=self.request.user)
        
        template_id = request.POST.get('template_id')
        if not template_id:
            return redirect('analysis_templates:data_input', diary_id=diary_id)
        
        template = get_object_or_404(AnalysisTemplate, id=template_id, user=request.user)
        
        # 既存の分析データを取得または新規作成
        analysis_data, created = StockAnalysisData.objects.get_or_create(
            diary=diary,
            template=template
        )
        
        # テンプレートの全フィールドを取得
        fields = TemplateField.objects.filter(template=template)
        
        # フォームの処理
        for field in fields:
            prefix = f"field_{field.id}"
            
            # 既存の値を取得または新規作成
            field_value, value_created = FieldValue.objects.get_or_create(
                analysis_data=analysis_data,
                field=field
            )
            
            # フィールドタイプに応じた値を設定
            field_type = field.field_type
            
            if field_type in ['number', 'percentage', 'rating']:
                value = request.POST.get(f"{prefix}-number_value", '')
                field_value.number_value = float(value) if value.strip() else None
                
            elif field_type == 'text':
                field_value.text_value = request.POST.get(f"{prefix}-text_value", '')
                
            elif field_type == 'date':
                value = request.POST.get(f"{prefix}-date_value", '')
                field_value.date_value = value if value else None
                
            elif field_type == 'boolean':
                field_value.boolean_value = f"{prefix}-boolean_value" in request.POST
            
            # 値を保存
            field_value.save()
        
        # リダイレクト
        return redirect('stockdiary:detail', pk=diary_id)

# 銘柄比較ビュー
class StockComparisonView(LoginRequiredMixin, TemplateView):
    """銘柄比較ビュー"""
    template_name = 'analysis_templates/comparison.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # ユーザーのテンプレート一覧
        templates = AnalysisTemplate.objects.filter(user=self.request.user)
        
        # 選択されたテンプレート
        template_id = self.request.GET.get('template_id')
        selected_template = None
        
        if template_id:
            try:
                selected_template = templates.get(id=template_id)
            except AnalysisTemplate.DoesNotExist:
                pass
        
        # 選択された銘柄一覧
        stock_ids = self.request.GET.getlist('stocks')
        selected_stocks = []
        
        if stock_ids and selected_template:
            # 選択された銘柄の分析データを取得
            analysis_data_list = StockAnalysisData.objects.filter(
                diary__user=self.request.user,
                template=selected_template,
                diary__id__in=stock_ids
            ).select_related('diary').prefetch_related('field_values', 'field_values__field')
            
            # 銘柄ごとのデータを整理
            for analysis_data in analysis_data_list:
                diary = analysis_data.diary
                
                # フィールド値をマッピング
                field_values = {}
                for field_value in analysis_data.field_values.all():
                    field_values[field_value.field.id] = field_value
                
                selected_stocks.append({
                    'diary': diary,
                    'analysis_data': analysis_data,
                    'field_values': field_values
                })
        
        # ユーザーの全ての日記
        diaries = StockDiary.objects.filter(user=self.request.user).order_by('-purchase_date')
        
        context.update({
            'templates': templates,
            'selected_template': selected_template,
            'diaries': diaries,
            'selected_stocks': selected_stocks
        })
        
        return context

# analysis_templates/views.py (続き)
@login_required
@require_POST
def save_analysis_data(request):
    """分析データをAJAXで保存するAPI"""
    try:
        data = json.loads(request.body)
        
        diary_id = data.get('diary_id')
        template_id = data.get('template_id')
        field_id = data.get('field_id')
        field_type = data.get('field_type')
        value = data.get('value')
        
        if not all([diary_id, template_id, field_id, field_type]):
            return JsonResponse({'success': False, 'error': '必要なパラメータが不足しています'}, status=400)
        
        # 必要なオブジェクトを取得
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        template = get_object_or_404(AnalysisTemplate, id=template_id, user=request.user)
        field = get_object_or_404(TemplateField, id=field_id, template=template)
        
        # 分析データを取得または作成
        analysis_data, created = StockAnalysisData.objects.get_or_create(
            diary=diary,
            template=template
        )
        
        # フィールド値を取得または作成
        field_value, value_created = FieldValue.objects.get_or_create(
            analysis_data=analysis_data,
            field=field
        )
        
        # フィールドタイプに応じた値を設定
        if field_type in ['number', 'percentage', 'rating']:
            try:
                field_value.number_value = float(value) if value is not None and value != '' else None
            except ValueError:
                return JsonResponse({'success': False, 'error': '数値の形式が正しくありません'}, status=400)
                
        elif field_type == 'text':
            field_value.text_value = value
            
        elif field_type == 'date':
            field_value.date_value = value if value else None
            
        elif field_type == 'boolean':
            field_value.boolean_value = bool(value)
        
        # 値を保存
        field_value.save()
        
        # フォーマットされた値を返す
        formatted_value = field_value.get_formatted_value()
        
        return JsonResponse({
            'success': True, 
            'formatted_value': formatted_value
        })
        
    except Exception as e:
        import traceback
        print(f"Error saving analysis data: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def get_template_fields(request, template_id):
    """テンプレートのフィールド一覧を取得するAPI"""
    try:
        template = get_object_or_404(AnalysisTemplate, id=template_id, user=request.user)
        
        # グループを取得
        groups_data = []
        for group in template.groups.all():
            fields_data = []
            for field in group.fields.all():
                fields_data.append({
                    'id': field.id,
                    'label': field.label,
                    'key': field.key,
                    'field_type': field.field_type,
                    'unit': field.unit,
                    'is_required': field.is_required,
                    'default_value': field.default_value,
                    'min_value': field.min_value,
                    'max_value': field.max_value,
                    'benchmark_value': field.benchmark_value
                })
            
            groups_data.append({
                'id': group.id,
                'name': group.name,
                'order': group.order,
                'fields': fields_data
            })
        
        # グループなしのフィールド
        ungrouped_fields = []
        for field in template.fields.filter(group__isnull=True):
            ungrouped_fields.append({
                'id': field.id,
                'label': field.label,
                'key': field.key,
                'field_type': field.field_type,
                'unit': field.unit,
                'is_required': field.is_required,
                'default_value': field.default_value,
                'min_value': field.min_value,
                'max_value': field.max_value,
                'benchmark_value': field.benchmark_value
            })
        
        return JsonResponse({
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'groups': groups_data,
                'ungrouped_fields': ungrouped_fields
            }
        })
        
    except Exception as e:
        import traceback
        print(f"Error getting template fields: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def get_analysis_data(request, diary_id, template_id):
    """日記の分析データを取得するAPI"""
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        template = get_object_or_404(AnalysisTemplate, id=template_id, user=request.user)
        
        # 分析データを取得
        try:
            analysis_data = StockAnalysisData.objects.get(diary=diary, template=template)
        except StockAnalysisData.DoesNotExist:
            return JsonResponse({
                'success': True,
                'diary_id': diary_id,
                'template_id': template_id,
                'field_values': {}
            })
        
        # フィールド値を取得
        field_values = {}
        for field_value in analysis_data.field_values.all():
            field_id = field_value.field.id
            
            # フィールドタイプに応じた値を取得
            field_type = field_value.field.field_type
            if field_type in ['number', 'percentage', 'rating']:
                value = field_value.number_value
            elif field_type == 'text':
                value = field_value.text_value
            elif field_type == 'date':
                value = field_value.date_value.isoformat() if field_value.date_value else None
            elif field_type == 'boolean':
                value = field_value.boolean_value
            else:
                value = None
            
            field_values[field_id] = {
                'value': value,
                'formatted_value': field_value.get_formatted_value()
            }
        
        return JsonResponse({
            'success': True,
            'diary_id': diary_id,
            'template_id': template_id,
            'field_values': field_values
        })
        
    except Exception as e:
        import traceback
        print(f"Error getting analysis data: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

class AnalysisComparisonView(LoginRequiredMixin, TemplateView):
    """複数の銘柄データを比較するビュー"""
    template_name = 'analysis_templates/comparison.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # ユーザーのテンプレート一覧
        templates = AnalysisTemplate.objects.filter(user=self.request.user)
        
        # 選択されたテンプレート
        template_id = self.request.GET.get('template_id')
        selected_template = None
        field_structure = []
        
        if template_id:
            try:
                selected_template = templates.get(id=template_id)
                
                # テンプレートのフィールド構造を取得
                for group in selected_template.groups.all().prefetch_related('fields'):
                    group_data = {
                        'group': group,
                        'fields': list(group.fields.all())
                    }
                    field_structure.append(group_data)
                
                # グループなしのフィールド
                ungrouped_fields = list(selected_template.fields.filter(group__isnull=True))
                if ungrouped_fields:
                    field_structure.append({
                        'group': None,
                        'fields': ungrouped_fields
                    })
                
            except AnalysisTemplate.DoesNotExist:
                pass
        
        # 選択された銘柄一覧
        stock_ids = self.request.GET.getlist('stocks')
        comparison_data = []
        
        if stock_ids and selected_template:
            # 選択された日記を取得
            diaries = StockDiary.objects.filter(
                id__in=stock_ids,
                user=self.request.user
            )
            
            # 各日記の分析データを取得
            for diary in diaries:
                try:
                    analysis_data = StockAnalysisData.objects.get(
                        diary=diary,
                        template=selected_template
                    )
                    
                    # フィールド値をマッピング
                    field_values = {}
                    for field_value in FieldValue.objects.filter(analysis_data=analysis_data):
                        field_values[field_value.field_id] = field_value
                    
                    comparison_data.append({
                        'diary': diary,
                        'field_values': field_values
                    })
                    
                except StockAnalysisData.DoesNotExist:
                    # 分析データがない場合は空のデータを追加
                    comparison_data.append({
                        'diary': diary,
                        'field_values': {}
                    })
        
        # ユーザーの全日記一覧（選択用）
        all_diaries = StockDiary.objects.filter(user=self.request.user).order_by('-purchase_date')
        
        context.update({
            'templates': templates,
            'selected_template': selected_template,
            'all_diaries': all_diaries,
            'comparison_data': comparison_data,
            'field_structure': field_structure,
            'selected_stock_ids': [int(id) for id in stock_ids] if stock_ids else []
        })
        
        return context