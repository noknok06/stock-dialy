# analysis_template/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from decimal import Decimal

from .models import (
    AnalysisTemplate, TemplateCompany, TemplateMetrics,
    MetricDefinition, IndustryBenchmark, CompanyScore
)
from .forms import (
    AnalysisTemplateForm, TemplateCompanyFormSet, 
    TemplateMetricsForm, BulkMetricsForm, CompanySearchForm
)
from company_master.models import CompanyMaster


@login_required
def template_list(request):
    """テンプレート一覧"""
    templates = AnalysisTemplate.objects.filter(
        user=request.user
    ).prefetch_related('companies').annotate(
        company_count=Count('companies')
    )
    
    context = {
        'templates': templates,
    }
    return render(request, 'analysis_template/template_list.html', context)


@login_required
def template_create(request):
    """テンプレート作成"""
    if request.method == 'POST':
        form = AnalysisTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.user = request.user
            template.save()
            messages.success(request, 'テンプレートを作成しました。')
            return redirect('analysis_template:edit', pk=template.pk)
    else:
        form = AnalysisTemplateForm()
    
    context = {
        'form': form,
        'is_create': True,
    }
    return render(request, 'analysis_template/template_form.html', context)


@login_required
def template_edit(request, pk):
    """テンプレート編集"""
    template = get_object_or_404(
        AnalysisTemplate,
        pk=pk,
        user=request.user
    )
    
    if request.method == 'POST':
        form = AnalysisTemplateForm(request.POST, instance=template)
        formset = TemplateCompanyFormSet(request.POST, instance=template)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'テンプレートを更新しました。')
            return redirect('analysis_template:detail', pk=template.pk)
    else:
        form = AnalysisTemplateForm(instance=template)
        formset = TemplateCompanyFormSet(instance=template)
    
    context = {
        'form': form,
        'formset': formset,
        'template': template,
        'is_create': False,
    }
    return render(request, 'analysis_template/template_form.html', context)


@login_required
def template_detail(request, pk):
    """テンプレート詳細（レポート表示）"""
    template = get_object_or_404(
        AnalysisTemplate,
        pk=pk,
        user=request.user
    )
    
    # テンプレートに登録されている企業を取得
    companies_data = []
    template_companies = TemplateCompany.objects.filter(
        template=template
    ).select_related('company').order_by('display_order')
    
    for tc in template_companies:
        company = tc.company
        
        # 企業の指標データを取得
        metrics = {}
        template_metrics = TemplateMetrics.objects.filter(
            template=template,
            company=company
        ).select_related('metric_definition')
        
        for tm in template_metrics:
            metric_name = tm.metric_definition.name
            metrics[metric_name] = float(tm.value)
        
        companies_data.append({
            'code': company.code,
            'name': company.name,
            'industry_name_33': company.industry_name_33,
            'industry_code_33': company.industry_code_33,
            'metrics': metrics
        })
    
    # 業種別ベンチマークを取得
    benchmarks = {}
    for company_data in companies_data:
        industry_code = company_data['industry_code_33']
        if industry_code and industry_code not in benchmarks:
            industry_benchmarks = IndustryBenchmark.objects.filter(
                industry_code=industry_code
            ).select_related('metric_definition')
            
            benchmarks[industry_code] = {
                'name': company_data['industry_name_33'],
            }
            
            for ib in industry_benchmarks:
                metric_name = ib.metric_definition.name
                benchmarks[industry_code][metric_name] = {
                    'avg': float(ib.average_value),
                    'excellent': float(ib.excellent_threshold) if ib.excellent_threshold else None,
                    'poor': float(ib.poor_threshold) if ib.poor_threshold else None,
                    'upper': float(ib.upper_quartile) if ib.upper_quartile else None,
                    'lower': float(ib.lower_quartile) if ib.lower_quartile else None,
                }
    
    context = {
        'template': template,
        'companies_data': json.dumps(companies_data),
        'benchmarks_data': json.dumps(benchmarks),
    }
    return render(request, 'analysis_template/template_detail.html', context)


@login_required
def template_delete(request, pk):
    """テンプレート削除"""
    template = get_object_or_404(
        AnalysisTemplate,
        pk=pk,
        user=request.user
    )
    
    if request.method == 'POST':
        template.delete()
        messages.success(request, 'テンプレートを削除しました。')
        return redirect('analysis_template:list')
    
    context = {
        'template': template,
    }
    return render(request, 'analysis_template/template_confirm_delete.html', context)


@login_required
def metrics_edit(request, pk):
    """指標編集"""
    template = get_object_or_404(
        AnalysisTemplate,
        pk=pk,
        user=request.user
    )
    
    if request.method == 'POST':
        form = BulkMetricsForm(request.POST, template=template)
        if form.is_valid():
            company = form.cleaned_data['company']
            fiscal_year = form.cleaned_data.get('fiscal_year', '')
            
            # 各指標の値を保存
            for field_name, value in form.cleaned_data.items():
                if field_name.startswith('metric_') and value is not None:
                    metric_id = field_name.replace('metric_', '')
                    metric_def = MetricDefinition.objects.get(id=metric_id)
                    
                    TemplateMetrics.objects.update_or_create(
                        template=template,
                        company=company,
                        metric_definition=metric_def,
                        fiscal_year=fiscal_year,
                        defaults={'value': value}
                    )
            
            messages.success(request, f'{company.name}の指標を保存しました。')
            return redirect('analysis_template:metrics_edit', pk=template.pk)
    else:
        form = BulkMetricsForm(template=template)
    
    # 登録済みの指標データを取得
    companies = template.companies.all().order_by('code')
    metrics_data = []
    
    for company in companies:
        company_metrics = TemplateMetrics.objects.filter(
            template=template,
            company=company
        ).select_related('metric_definition')
        
        metrics_dict = {
            'company': company,
            'metrics': {}
        }
        
        for tm in company_metrics:
            metrics_dict['metrics'][tm.metric_definition.name] = tm
        
        metrics_data.append(metrics_dict)
    
    # 指標定義一覧
    metric_definitions = MetricDefinition.objects.filter(
        is_active=True
    ).order_by('metric_group', 'display_order')
    
    context = {
        'template': template,
        'form': form,
        'metrics_data': metrics_data,
        'metric_definitions': metric_definitions,
    }
    return render(request, 'analysis_template/metrics_edit.html', context)


@login_required
@require_http_methods(["GET"])
def company_search_ajax(request):
    """企業検索API"""
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    companies = CompanyMaster.objects.filter(
        Q(code__icontains=query) | Q(name__icontains=query)
    )[:20]
    
    results = []
    for company in companies:
        results.append({
            'id': company.id,
            'code': company.code,
            'name': company.name,
            'industry': company.industry_name_33,
            'text': f'{company.code} - {company.name}'
        })
    
    return JsonResponse({'results': results})


@login_required
@require_http_methods(["GET"])
def company_metrics_ajax(request, pk, company_id):
    """企業の指標データ取得API"""
    template = get_object_or_404(
        AnalysisTemplate,
        pk=pk,
        user=request.user
    )
    company = get_object_or_404(CompanyMaster, pk=company_id)
    
    metrics = TemplateMetrics.objects.filter(
        template=template,
        company=company
    ).select_related('metric_definition')
    
    data = {}
    for tm in metrics:
        data[f'metric_{tm.metric_definition.id}'] = str(tm.value)
    
    data['fiscal_year'] = metrics.first().fiscal_year if metrics.exists() else ''
    
    return JsonResponse(data)


@login_required
def calculate_scores(request, pk):
    """スコア計算"""
    template = get_object_or_404(
        AnalysisTemplate,
        pk=pk,
        user=request.user
    )
    
    # 各企業のスコアを計算
    for company in template.companies.all():
        metrics = TemplateMetrics.objects.filter(
            template=template,
            company=company
        ).select_related('metric_definition')
        
        # 業種別ベンチマークを取得
        industry_code = company.industry_code_33
        
        scores_by_group = {}
        total_score = 0
        count = 0
        
        for tm in metrics:
            metric_def = tm.metric_definition
            
            # 業種ベンチマークがある場合は正規化スコアを計算
            try:
                benchmark = IndustryBenchmark.objects.get(
                    industry_code=industry_code,
                    metric_definition=metric_def
                )
                normalized = benchmark.normalize_value(tm.value)
                if normalized is not None:
                    group = metric_def.metric_group
                    if group not in scores_by_group:
                        scores_by_group[group] = []
                    scores_by_group[group].append(normalized)
                    total_score += normalized
                    count += 1
            except IndustryBenchmark.DoesNotExist:
                continue
        
        if count > 0:
            # グループ別スコアを計算
            group_scores = {}
            for group, scores in scores_by_group.items():
                group_scores[group] = sum(scores) / len(scores)
            
            # 総合スコアを保存
            CompanyScore.objects.update_or_create(
                template=template,
                company=company,
                defaults={
                    'total_score': total_score / count,
                    'profitability_score': group_scores.get('profitability'),
                    'growth_score': group_scores.get('growth'),
                    'valuation_score': group_scores.get('valuation'),
                    'financial_health_score': group_scores.get('financial_health'),
                    'data_completeness': (count / metrics.count()) * 100 if metrics.count() > 0 else 0
                }
            )
    
    # ランキングを更新
    scores = CompanyScore.objects.filter(template=template).order_by('-total_score')
    for rank, score in enumerate(scores, start=1):
        score.rank = rank
        score.save(update_fields=['rank'])
    
    messages.success(request, 'スコアを計算しました。')
    return redirect('analysis_template:detail', pk=template.pk)