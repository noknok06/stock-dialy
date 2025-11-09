# analysis_template/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q, Count, Prefetch
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from company_master.models import CompanyMaster
from .models import AnalysisTemplate, TemplateCompany, TemplateMetrics, MetricDefinition
from .forms import (
    AnalysisTemplateForm, CompanySearchForm, TemplateMetricsForm,
    BulkMetricsForm
)


@login_required
def template_list(request):
    """テンプレート一覧表示"""
    templates = AnalysisTemplate.objects.filter(
        user=request.user
    ).prefetch_related(
        'companies'
    ).annotate(
        company_count=Count('companies')
    ).order_by('-updated_at')
    
    # ページネーション
    paginator = Paginator(templates, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_count': templates.count(),
    }
    return render(request, 'analysis_template/list.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def template_create(request):
    """テンプレート作成"""
    if request.method == 'POST':
        form = AnalysisTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.user = request.user
            template.save()
            messages.success(request, 'テンプレートを作成しました')
            return redirect('analysis_template:company_select', pk=template.pk)
    else:
        form = AnalysisTemplateForm()
    
    context = {
        'form': form,
        'action': 'create'
    }
    return render(request, 'analysis_template/form.html', context)


@login_required
def template_detail(request, pk):
    """テンプレート詳細表示"""
    template = get_object_or_404(
        AnalysisTemplate.objects.prefetch_related(
            Prefetch(
                'templatecompany_set',
                queryset=TemplateCompany.objects.select_related('company').order_by('display_order')
            ),
            Prefetch(
                'metrics',
                queryset=TemplateMetrics.objects.select_related('company', 'metric_definition')
            )
        ),
        pk=pk,
        user=request.user
    )
    
    # 企業スコアを計算（再計算が必要な場合のみ）
    if request.GET.get('recalculate') == '1':
        calculate_company_scores(template)
    
    # 企業ごとの指標データを整理
    companies_data = []
    for tc in template.templatecompany_set.all():
        company = tc.company
        metrics = template.metrics.filter(company=company)
        
        # 企業スコアを取得
        try:
            from analysis_template.models import CompanyScore
            score = CompanyScore.objects.get(template=template, company=company)
        except:
            score = None
        
        companies_data.append({
            'company': company,
            'metrics': metrics,
            'display_order': tc.display_order,
            'score': score
        })
    
    # グループ別チャート用データ取得
    chart_data = get_chart_data(template)
    
    # 正規化されたレーダーチャート用データ
    normalized_chart_data = get_normalized_chart_data(template)
    
    # データ充足率
    coverage = get_data_coverage(template)
    
    # ベンチマークデータ
    benchmark_data = get_benchmark_data(template)
    
    # 指標をグループ別に整理
    metrics_by_group = {}
    for group_code, group_name in MetricDefinition.METRIC_GROUPS:
        metrics = MetricDefinition.objects.filter(
            is_active=True,
            metric_group=group_code
        ).order_by('display_order')
        if metrics.exists():
            metrics_by_group[group_code] = {
                'name': group_name,
                'metrics': metrics
            }
    
    # 総合スコアランキング
    from analysis_template.models import CompanyScore
    score_ranking = CompanyScore.objects.filter(template=template).order_by('-total_score')
    
    context = {
        'template': template,
        'companies_data': companies_data,
        'chart_data': chart_data,
        'normalized_chart_data': normalized_chart_data,
        'coverage': coverage,
        'benchmark_data': benchmark_data,
        'metrics_by_group': metrics_by_group,
        'score_ranking': score_ranking,
    }
    return render(request, 'analysis_template/detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def template_update(request, pk):
    """テンプレート編集"""
    template = get_object_or_404(AnalysisTemplate, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = AnalysisTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, 'テンプレートを更新しました')
            return redirect('analysis_template:detail', pk=template.pk)
    else:
        form = AnalysisTemplateForm(instance=template)
    
    context = {
        'form': form,
        'template': template,
        'action': 'update'
    }
    return render(request, 'analysis_template/form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def template_delete(request, pk):
    """テンプレート削除"""
    template = get_object_or_404(AnalysisTemplate, pk=pk, user=request.user)
    
    if request.method == 'POST':
        template_name = template.name
        template.delete()
        messages.success(request, f'「{template_name}」を削除しました')
        return redirect('analysis_template:list')
    
    context = {
        'template': template
    }
    return render(request, 'analysis_template/delete.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def company_select(request, pk):
    """企業選択"""
    template = get_object_or_404(AnalysisTemplate, pk=pk, user=request.user)
    search_form = CompanySearchForm(request.GET or None)
    
    # 検索条件
    companies = CompanyMaster.objects.all()
    
    if search_form.is_valid():
        query = search_form.cleaned_data.get('query')
        industry = search_form.cleaned_data.get('industry')
        market = search_form.cleaned_data.get('market')
        
        if query:
            companies = companies.filter(
                Q(code__icontains=query) | Q(name__icontains=query)
            )
        if industry:
            companies = companies.filter(industry_name_33=industry)
        if market:
            companies = companies.filter(market=market)
    
    # 既に選択されている企業
    selected_companies = template.companies.all()
    selected_codes = set(selected_companies.values_list('code', flat=True))
    
    # ページネーション
    paginator = Paginator(companies.order_by('code'), 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    if request.method == 'POST':
        company_codes = request.POST.getlist('companies')
        
        with transaction.atomic():
            # 既存の選択をクリア
            TemplateCompany.objects.filter(template=template).delete()
            
            # 新しい選択を追加
            for i, code in enumerate(company_codes):
                try:
                    company = CompanyMaster.objects.get(code=code)
                    TemplateCompany.objects.create(
                        template=template,
                        company=company,
                        display_order=i
                    )
                except CompanyMaster.DoesNotExist:
                    pass
        
        messages.success(request, f'{len(company_codes)}社を選択しました')
        return redirect('analysis_template:metrics_input', pk=template.pk)
    
    context = {
        'template': template,
        'search_form': search_form,
        'page_obj': page_obj,
        'selected_companies': selected_companies,
        'selected_codes': selected_codes,
    }
    return render(request, 'analysis_template/company_select.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def metrics_input(request, pk):
    """指標値入力"""
    template = get_object_or_404(AnalysisTemplate, pk=pk, user=request.user)
    companies = template.companies.all().order_by('templatecompany__display_order')
    
    if not companies.exists():
        messages.warning(request, '企業が選択されていません')
        return redirect('analysis_template:company_select', pk=template.pk)
    
    metrics = MetricDefinition.objects.filter(is_active=True).order_by('display_order')
    
    if request.method == 'POST':
        with transaction.atomic():
            for company in companies:
                for metric in metrics:
                    field_name = f'metric_{company.code}_{metric.id}'
                    value = request.POST.get(field_name)
                    fiscal_year = request.POST.get(f'year_{company.code}_{metric.id}', '')
                    notes = request.POST.get(f'notes_{company.code}_{metric.id}', '')
                    
                    if value:
                        try:
                            value_decimal = float(value)
                            TemplateMetrics.objects.update_or_create(
                                template=template,
                                company=company,
                                metric_definition=metric,
                                fiscal_year=fiscal_year,
                                defaults={
                                    'value': value_decimal,
                                    'notes': notes
                                }
                            )
                        except (ValueError, TypeError):
                            continue
        
        messages.success(request, '指標値を保存しました')
        return redirect('analysis_template:detail', pk=template.pk)
    
    # 既存データの取得
    existing_metrics = {}
    for tm in TemplateMetrics.objects.filter(template=template):
        key = (tm.company.code, tm.metric_definition.id)
        existing_metrics[key] = tm
    
    # テーブル形式のデータ構造を作成
    table_data = []
    for company in companies:
        row = {'company': company, 'metrics': []}
        for metric in metrics:
            key = (company.code, metric.id)
            existing = existing_metrics.get(key)
            row['metrics'].append({
                'definition': metric,
                'existing': existing,
                'field_name': f'metric_{company.code}_{metric.id}'
            })
        table_data.append(row)
    
    context = {
        'template': template,
        'companies': companies,
        'metrics': metrics,
        'table_data': table_data,
    }
    return render(request, 'analysis_template/metrics_input.html', context)


@login_required
@require_http_methods(["POST"])
def company_add(request, pk):
    """企業を追加（AJAX）"""
    template = get_object_or_404(AnalysisTemplate, pk=pk, user=request.user)
    company_code = request.POST.get('company_code')
    
    try:
        company = CompanyMaster.objects.get(code=company_code)
        
        # 重複チェック
        if template.companies.filter(code=company_code).exists():
            return JsonResponse({
                'success': False,
                'message': 'この企業は既に追加されています'
            })
        
        # 最大表示順を取得
        max_order = TemplateCompany.objects.filter(template=template).count()
        
        TemplateCompany.objects.create(
            template=template,
            company=company,
            display_order=max_order
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{company.name}を追加しました',
            'company': {
                'code': company.code,
                'name': company.name
            }
        })
    except CompanyMaster.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '指定された株式コードが見つかりません'
        })


@login_required
@require_http_methods(["POST"])
def company_remove(request, pk, company_code):
    """企業を削除"""
    template = get_object_or_404(AnalysisTemplate, pk=pk, user=request.user)
    
    try:
        company = CompanyMaster.objects.get(code=company_code)
        TemplateCompany.objects.filter(template=template, company=company).delete()
        
        # 関連する指標も削除
        TemplateMetrics.objects.filter(template=template, company=company).delete()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'{company.name}を削除しました'
            })
        else:
            messages.success(request, f'{company.name}を削除しました')
            return redirect('analysis_template:company_select', pk=template.pk)
    except CompanyMaster.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': '企業が見つかりません'
            })
        else:
            messages.error(request, '企業が見つかりません')
            return redirect('analysis_template:company_select', pk=template.pk)


@login_required
def chart_data(request, pk):
    """チャートデータ取得（JSON）"""
    template = get_object_or_404(AnalysisTemplate, pk=pk, user=request.user)
    data = get_chart_data(template)
    return JsonResponse(data)


def get_chart_data(template):
    """チャートデータを整形（グループ別）"""
    companies = template.companies.all().order_by('templatecompany__display_order')
    
    # 企業名リスト
    company_labels = [c.name for c in companies]
    
    # グループ別にデータを整理
    grouped_data = {}
    
    for group_code, group_name in MetricDefinition.METRIC_GROUPS:
        metrics = MetricDefinition.objects.filter(
            is_active=True,
            metric_group=group_code,
            chart_suitable=True
        ).order_by('display_order')
        
        datasets = []
        for metric in metrics:
            values = []
            has_data = False
            
            for company in companies:
                try:
                    tm = TemplateMetrics.objects.get(
                        template=template,
                        company=company,
                        metric_definition=metric
                    )
                    values.append(float(tm.value))
                    has_data = True
                except TemplateMetrics.DoesNotExist:
                    values.append(None)
            
            # データが1つでもあれば追加
            if has_data:
                datasets.append({
                    'label': metric.display_name,
                    'data': values,
                    'unit': metric.get_formatted_unit(),
                    'metric_type': metric.metric_type
                })
        
        if datasets:
            grouped_data[group_code] = {
                'name': group_name,
                'labels': company_labels,
                'datasets': datasets
            }
    
    return grouped_data


def get_data_coverage(template):
    """データ充足率を計算"""
    companies = template.companies.all()
    metrics = MetricDefinition.objects.filter(is_active=True)
    
    total_cells = companies.count() * metrics.count()
    if total_cells == 0:
        return 0
    
    filled_cells = TemplateMetrics.objects.filter(template=template).count()
    return round((filled_cells / total_cells) * 100, 1)


def calculate_company_scores(template):
    """企業の総合スコアを計算"""
    from analysis_template.models import CompanyScore, IndustryBenchmark
    
    companies = template.companies.all()
    
    for company in companies:
        # 各グループのスコアを計算
        group_scores = {}
        total_metrics = 0
        total_score_sum = 0
        
        for group_code, group_name in MetricDefinition.METRIC_GROUPS:
            metrics = MetricDefinition.objects.filter(
                is_active=True,
                metric_group=group_code
            )
            
            group_score_sum = 0
            group_metric_count = 0
            
            for metric in metrics:
                try:
                    tm = TemplateMetrics.objects.get(
                        template=template,
                        company=company,
                        metric_definition=metric
                    )
                    
                    # ベンチマークがあれば正規化スコアを計算
                    try:
                        benchmark = IndustryBenchmark.objects.get(
                            industry_code=company.industry_code_33,
                            metric_definition=metric
                        )
                        normalized = benchmark.normalize_value(tm.value)
                        if normalized is not None:
                            group_score_sum += normalized
                            group_metric_count += 1
                    except IndustryBenchmark.DoesNotExist:
                        # ベンチマークがない場合は平均を50として扱う
                        group_score_sum += 50
                        group_metric_count += 1
                
                except TemplateMetrics.DoesNotExist:
                    pass
            
            if group_metric_count > 0:
                group_scores[group_code] = group_score_sum / group_metric_count
                total_metrics += group_metric_count
                total_score_sum += group_score_sum
        
        # 総合スコアを計算
        if total_metrics > 0:
            total_score = total_score_sum / total_metrics
            
            # データ完全性を計算
            all_metrics_count = MetricDefinition.objects.filter(is_active=True).count()
            data_completeness = (total_metrics / all_metrics_count) * 100 if all_metrics_count > 0 else 0
            
            # スコアを保存
            CompanyScore.objects.update_or_create(
                template=template,
                company=company,
                defaults={
                    'total_score': round(total_score, 2),
                    'profitability_score': round(group_scores.get('profitability', 0), 2) or None,
                    'growth_score': round(group_scores.get('growth', 0), 2) or None,
                    'valuation_score': round(group_scores.get('valuation', 0), 2) or None,
                    'financial_health_score': round(group_scores.get('financial_health', 0), 2) or None,
                    'data_completeness': round(data_completeness, 2)
                }
            )
    
    # 順位を更新
    scores = CompanyScore.objects.filter(template=template).order_by('-total_score')
    for rank, score in enumerate(scores, 1):
        score.rank = rank
        score.save(update_fields=['rank'])


def get_normalized_chart_data(template):
    """正規化されたチャートデータを取得（レーダーチャート用）"""
    from analysis_template.models import IndustryBenchmark
    
    companies = template.companies.all().order_by('templatecompany__display_order')
    
    # 企業名リスト
    company_labels = [c.name for c in companies]
    
    # グループ別に正規化データを作成
    grouped_data = {}
    
    for group_code, group_name in MetricDefinition.METRIC_GROUPS:
        if group_code == 'scale':  # 規模は正規化に適さない
            continue
            
        metrics = MetricDefinition.objects.filter(
            is_active=True,
            metric_group=group_code,
            chart_suitable=True
        ).order_by('display_order')
        
        # 指標名のリスト（レーダーチャートの軸）
        metric_labels = [m.display_name for m in metrics]
        
        # 各企業のデータセット
        datasets = []
        
        for company in companies:
            values = []
            has_data = False
            
            for metric in metrics:
                try:
                    tm = TemplateMetrics.objects.get(
                        template=template,
                        company=company,
                        metric_definition=metric
                    )
                    
                    # ベンチマークで正規化
                    try:
                        benchmark = IndustryBenchmark.objects.get(
                            industry_code=company.industry_code_33,
                            metric_definition=metric
                        )
                        normalized = benchmark.normalize_value(tm.value)
                        values.append(normalized if normalized is not None else 0)
                        has_data = True
                    except IndustryBenchmark.DoesNotExist:
                        # ベンチマークがない場合は生の値を使用（50を基準に調整）
                        values.append(50)
                        has_data = True
                
                except TemplateMetrics.DoesNotExist:
                    # データがない場合は0
                    values.append(0)
            
            if has_data:
                datasets.append({
                    'label': company.name,
                    'data': values
                })
        
        if datasets:
            grouped_data[group_code] = {
                'name': group_name,
                'labels': metric_labels,
                'datasets': datasets
            }
    
    return grouped_data


def get_benchmark_data(template):
    """業種別ベンチマークデータを取得"""
    from analysis_template.models import IndustryBenchmark
    
    benchmark_data = {}
    
    for company_data in template.templatecompany_set.select_related('company'):
        company = company_data.company
        industry_code = company.industry_code_33
        
        if not industry_code:
            continue
        
        benchmarks = IndustryBenchmark.objects.filter(
            industry_code=industry_code
        ).select_related('metric_definition')
        
        for benchmark in benchmarks:
            metric_id = benchmark.metric_definition.id
            if metric_id not in benchmark_data:
                benchmark_data[metric_id] = {}
            
            benchmark_data[metric_id][company.code] = {
                'average': float(benchmark.average_value),
                'excellent': float(benchmark.excellent_threshold) if benchmark.excellent_threshold else None,
                'poor': float(benchmark.poor_threshold) if benchmark.poor_threshold else None,
                'industry': benchmark.industry_name
            }
    
    return benchmark_data


@login_required
def company_autocomplete(request):
    """企業名のオートコンプリート"""
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    companies = CompanyMaster.objects.filter(
        Q(code__icontains=query) | Q(name__icontains=query)
    ).order_by('code')[:20]
    
    results = [{
        'code': c.code,
        'name': c.name,
        'market': c.market,
        'industry': c.industry_name_33
    } for c in companies]
    
    return JsonResponse({'results': results})