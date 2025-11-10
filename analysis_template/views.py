# analysis_template/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import csv
from django.http import HttpResponse
from django.db.models import Q, Count, Avg, Max
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import transaction, models
import json
from decimal import Decimal
from common.services.yahoo_finance_service import YahooFinanceService

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
    return render(request, 'analysis_template/template_form.html', context)


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
            companies = companies.filter(industry_code_33=industry)
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
        action = request.POST.get('action', 'replace')  # ⭐ アクションを取得
        
        with transaction.atomic():
            if action == 'replace':
                # ⭐ 置き換えモード: 既存をすべてクリア
                TemplateCompany.objects.filter(template=template).delete()
                start_order = 0
            else:
                # ⭐ 追加モード: 既存の最大display_orderを取得
                max_order = TemplateCompany.objects.filter(
                    template=template
                ).aggregate(models.Max('display_order'))['display_order__max']
                start_order = (max_order or -1) + 1
            
            added_count = 0
            for i, code in enumerate(company_codes):
                try:
                    company = CompanyMaster.objects.get(code=code)
                    
                    # ⭐ 追加モードの場合、既に存在するかチェック
                    if action == 'add':
                        if TemplateCompany.objects.filter(
                            template=template, 
                            company=company
                        ).exists():
                            continue  # 既に存在する場合はスキップ
                    
                    TemplateCompany.objects.create(
                        template=template,
                        company=company,
                        display_order=start_order + i
                    )
                    added_count += 1
                except CompanyMaster.DoesNotExist:
                    pass
        
        if action == 'replace':
            messages.success(request, f'{added_count}社を選択しました')
        else:
            messages.success(request, f'{added_count}社を追加しました')
        
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
    return render(request, 'analysis_template/template_form.html', context)


def get_normalized_chart_data(template):
    """正規化されたチャートデータを取得（レーダーチャート用）
    
    各指標について:
    - 業種ベンチマークがある場合: 業種平均=50として正規化
    - 業種ベンチマークがない場合: テンプレート内の企業平均=50として正規化
    - データがない場合: null（チャートで線が途切れる）
    """
    companies = template.companies.all().order_by('templatecompany__display_order')
    
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
        
        # 各指標ごとにテンプレート内の平均値を計算（ベンチマークがない場合の代替）
        metric_averages = {}
        for metric in metrics:
            values = []
            for company in companies:
                try:
                    tm = TemplateMetrics.objects.get(
                        template=template,
                        company=company,
                        metric_definition=metric
                    )
                    if tm.value is not None:
                        values.append(float(tm.value))
                except TemplateMetrics.DoesNotExist:
                    pass
            
            if values:
                metric_averages[metric.id] = sum(values) / len(values)
            else:
                metric_averages[metric.id] = None
        
        # 各企業のデータセット
        datasets = []
        
        for company in companies:
            values = []
            has_any_data = False
            
            for metric in metrics:
                try:
                    tm = TemplateMetrics.objects.get(
                        template=template,
                        company=company,
                        metric_definition=metric
                    )
                    
                    value = float(tm.value)
                    has_any_data = True
                    
                    # ベンチマークで正規化を試みる
                    try:
                        benchmark = IndustryBenchmark.objects.get(
                            industry_code=company.industry_code_33,
                            metric_definition=metric
                        )
                        normalized = benchmark.normalize_value(tm.value)
                        values.append(normalized if normalized is not None else None)
                    except IndustryBenchmark.DoesNotExist:
                        # ベンチマークがない場合、テンプレート内平均を基準に正規化
                        avg = metric_averages.get(metric.id)
                        if avg and avg != 0:
                            # 平均を50として正規化
                            normalized = (value / avg) * 50
                            # 0-100の範囲に制限
                            normalized = max(0, min(100, normalized))
                            values.append(round(normalized, 1))
                        else:
                            # 平均が0の場合はnull
                            values.append(None)
                
                except TemplateMetrics.DoesNotExist:
                    # データがない場合はnull（チャートで線が途切れる）
                    values.append(None)
            
            # 1つでもデータがあれば追加
            if has_any_data:
                datasets.append({
                    'label': company.name,
                    'data': values
                })
        
        if datasets and metric_labels:
            grouped_data[group_code] = {
                'name': group_name,
                'labels': metric_labels,
                'datasets': datasets,
                'has_benchmark': any(
                    IndustryBenchmark.objects.filter(
                        metric_definition=metric
                    ).exists() for metric in metrics
                )
            }
    
    return grouped_data


@login_required
@require_http_methods(["GET", "POST"])
def metrics_input(request, pk):
    """指標一括入力"""
    template = get_object_or_404(AnalysisTemplate, pk=pk, user=request.user)
    companies = template.companies.all().order_by('templatecompany__display_order')
    
    if not companies.exists():
        messages.warning(request, '企業が選択されていません')
        return redirect('analysis_template:company_select', pk=template.pk)
    
    # 指標定義をグループ別に取得
    metric_groups = {}
    for group_code, group_name in MetricDefinition.METRIC_GROUPS:
        metrics = MetricDefinition.objects.filter(
            is_active=True,
            metric_group=group_code
        ).order_by('display_order')
        
        if metrics.exists():
            metric_groups[group_code] = {
                'name': group_name,
                'metrics': metrics
            }
    
    if request.method == 'POST':
        fiscal_year = request.POST.get('fiscal_year', '')
        saved_count = 0
        
        with transaction.atomic():
            for company in companies:
                for metric in MetricDefinition.objects.filter(is_active=True):
                    field_name = f'metric_{company.id}_{metric.id}'
                    value = request.POST.get(field_name)
                    
                    if value and value.strip():
                        try:
                            value_decimal = Decimal(value)
                            TemplateMetrics.objects.update_or_create(
                                template=template,
                                company=company,
                                metric_definition=metric,
                                fiscal_year=fiscal_year,
                                defaults={'value': value_decimal}
                            )
                            saved_count += 1
                        except (ValueError, Decimal.InvalidOperation):
                            pass
        
        if saved_count > 0:
            messages.success(request, f'{saved_count}件の指標を保存しました')
            return redirect('analysis_template:detail', pk=template.pk)
        else:
            messages.warning(request, '保存するデータがありません')
    
    # 既存データを取得
    existing_data = {}
    latest_fiscal_year = None
    
    for company in companies:
        company_metrics = TemplateMetrics.objects.filter(
            template=template,
            company=company
        ).select_related('metric_definition')
        
        if company_metrics.exists() and not latest_fiscal_year:
            latest_fiscal_year = company_metrics.first().fiscal_year
        
        for tm in company_metrics:
            key = f'metric_{company.id}_{tm.metric_definition.id}'
            existing_data[key] = str(tm.value)
    
    context = {
        'template': template,
        'companies': companies,
        'metric_groups': metric_groups,
        'existing_data': existing_data,
        'latest_fiscal_year': latest_fiscal_year or '',
    }
    return render(request, 'analysis_template/metrics_input.html', context)


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
    
    # 正規化されたチャートデータを取得
    chart_data = get_normalized_chart_data(template)
    
    context = {
        'template': template,
        'companies_data': json.dumps(companies_data),
        'benchmarks_data': json.dumps(benchmarks),
        'chart_data': json.dumps(chart_data),
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
            'metrics': {},
            'first_metric': None,  # ← 追加
        }
        
        for tm in company_metrics:
            metrics_dict['metrics'][tm.metric_definition.name] = tm
        
        # dictの最初の値を first_metric にセット
        if metrics_dict['metrics']:
            metrics_dict['first_metric'] = next(iter(metrics_dict['metrics'].values()))
        
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
    
    # ⭐ fiscal_yearでフィルタしない（最新のデータを取得）
    metrics = TemplateMetrics.objects.filter(
        template=template,
        company=company
    ).select_related('metric_definition')
    
    # デバッグ用ログ出力
    print(f"=== Debug Info ===")
    print(f"Template ID: {template.pk}")
    print(f"Company ID: {company.pk} ({company.name})")
    print(f"Query: {metrics.query}")
    print(f"Count: {metrics.count()}")
    print(f"================")
    
    data = {}
    
    # 指標データを辞書に格納
    for tm in metrics:
        field_name = f'metric_{tm.metric_definition.id}'
        data[field_name] = str(tm.value)
        print(f"  {field_name}: {tm.value}")  # デバッグ出力
    
    # 会計年度を取得（最初のレコードから）
    if metrics.exists():
        data['fiscal_year'] = metrics.first().fiscal_year
    else:
        data['fiscal_year'] = ''
        print("  ⚠️ No metrics found for this company")
    
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

@login_required
@require_http_methods(["POST"])
def company_remove_api(request, pk):
    """企業削除API"""
    template = get_object_or_404(
        AnalysisTemplate,
        pk=pk,
        user=request.user
    )
    
    try:
        data = json.loads(request.body)
        company_code = data.get('company_code')
        
        if not company_code:
            return JsonResponse({
                'success': False,
                'error': '企業コードが指定されていません'
            }, status=400)
        
        # 企業を取得
        try:
            company = CompanyMaster.objects.get(code=company_code)
        except CompanyMaster.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '企業が見つかりません'
            }, status=404)
        
        # テンプレートから企業を削除
        with transaction.atomic():
            # TemplateCompanyを削除（これにより関連する指標データも削除される）
            deleted_count = TemplateCompany.objects.filter(
                template=template,
                company=company
            ).delete()[0]
            
            if deleted_count == 0:
                return JsonResponse({
                    'success': False,
                    'error': 'この企業はテンプレートに登録されていません'
                }, status=404)
            
            # 関連する指標データも削除
            TemplateMetrics.objects.filter(
                template=template,
                company=company
            ).delete()
            
            # スコアも削除
            CompanyScore.objects.filter(
                template=template,
                company=company
            ).delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{company.name}を削除しました'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': '不正なリクエスト形式です'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
        
@login_required
@require_http_methods(["POST"])
def metrics_auto_fetch(request, pk):
    """APIから指標データを自動取得"""
    template = get_object_or_404(AnalysisTemplate, pk=pk, user=request.user)
    
    try:
        data = json.loads(request.body)
        company_codes = data.get('company_codes', [])
        fiscal_year = data.get('fiscal_year', '')
        overwrite = data.get('overwrite', False)  # 既存データを上書きするか
        
        if not company_codes:
            return JsonResponse({
                'success': False,
                'error': '企業が選択されていません'
            }, status=400)
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        results = []
        
        with transaction.atomic():
            for code in company_codes:
                try:
                    # 企業を取得
                    company = CompanyMaster.objects.get(code=code)
                    
                    # APIからデータ取得
                    api_data = YahooFinanceService.fetch_company_data(code, fiscal_year)
                    
                    if not api_data:
                        error_count += 1
                        results.append({
                            'code': code,
                            'name': company.name,
                            'status': 'error',
                            'message': 'APIからデータを取得できませんでした'
                        })
                        continue
                    
                    saved_metrics = []
                    saved_values = {}  # ⭐ 保存した値を格納
                    
                    # 各指標を保存
                    for metric_name, value in api_data.items():
                        try:
                            # 指標定義を取得
                            metric_def = MetricDefinition.objects.get(
                                name=metric_name,
                                is_active=True
                            )
                            
                            # 既存データをチェック
                            existing = TemplateMetrics.objects.filter(
                                template=template,
                                company=company,
                                metric_definition=metric_def,
                                fiscal_year=fiscal_year
                            ).first()
                            
                            if existing and not overwrite:
                                skipped_count += 1
                                continue
                            
                            # データを保存
                            TemplateMetrics.objects.update_or_create(
                                template=template,
                                company=company,
                                metric_definition=metric_def,
                                fiscal_year=fiscal_year,
                                defaults={'value': value}
                            )
                            
                            saved_metrics.append(metric_def.display_name)
                            # ⭐ フィールド名と値をマッピング
                            field_name = f'metric_{company.id}_{metric_def.id}'
                            saved_values[metric_name] = {
                                'field_name': field_name,
                                'value': str(value),
                                'metric_id': metric_def.id
                            }
                            
                        except MetricDefinition.DoesNotExist:
                            logger.warning(f"Metric definition not found: {metric_name}")
                            continue
                    
                    if saved_metrics:
                        success_count += 1
                        results.append({
                            'code': code,
                            'name': company.name,
                            'status': 'success',
                            'metrics_count': len(saved_metrics),
                            'metrics': saved_metrics,
                            'values': saved_values  # ⭐ 値を含める
                        })
                    else:
                        skipped_count += 1
                        results.append({
                            'code': code,
                            'name': company.name,
                            'status': 'skipped',
                            'message': '保存する指標がありませんでした'
                        })
                
                except CompanyMaster.DoesNotExist:
                    error_count += 1
                    results.append({
                        'code': code,
                        'status': 'error',
                        'message': '企業が見つかりません'
                    })
                except Exception as e:
                    error_count += 1
                    results.append({
                        'code': code,
                        'status': 'error',
                        'message': str(e)
                    })
        
        return JsonResponse({
            'success': True,
            'summary': {
                'total': len(company_codes),
                'success': success_count,
                'error': error_count,
                'skipped': skipped_count
            },
            'results': results
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': '不正なリクエスト形式です'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in metrics_auto_fetch: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def check_api_availability(request, pk):
    """APIでデータ取得可能かチェック"""
    template = get_object_or_404(AnalysisTemplate, pk=pk, user=request.user)
    
    company_code = request.GET.get('code')
    if not company_code:
        return JsonResponse({'available': False, 'error': '企業コードが指定されていません'})
    
    available = YahooFinanceService.validate_ticker(company_code)
    
    if available:
        # 取得可能な指標リストも返す
        available_metrics = YahooFinanceService.get_available_metrics()
        return JsonResponse({
            'available': True,
            'metrics': available_metrics
        })
    else:
        return JsonResponse({
            'available': False,
            'error': 'この企業のデータは取得できません'
        })

@login_required
@require_http_methods(["POST"])
def template_duplicate(request, pk):
    """テンプレート複製"""
    original = get_object_or_404(AnalysisTemplate, pk=pk, user=request.user)
    
    try:
        with transaction.atomic():
            # テンプレートを複製
            new_template = AnalysisTemplate.objects.create(
                name=f"{original.name} のコピー",
                description=original.description,
                user=request.user
            )
            
            # 企業を複製
            for tc in TemplateCompany.objects.filter(template=original):
                TemplateCompany.objects.create(
                    template=new_template,
                    company=tc.company,
                    display_order=tc.display_order
                )
            
            # 指標データを複製
            metrics_count = 0
            for tm in TemplateMetrics.objects.filter(template=original):
                TemplateMetrics.objects.create(
                    template=new_template,
                    company=tm.company,
                    metric_definition=tm.metric_definition,
                    value=tm.value,
                    fiscal_year=tm.fiscal_year,
                    notes=tm.notes
                )
                metrics_count += 1
            
            # スコアを複製
            for score in CompanyScore.objects.filter(template=original):
                CompanyScore.objects.create(
                    template=new_template,
                    company=score.company,
                    total_score=score.total_score,
                    profitability_score=score.profitability_score,
                    growth_score=score.growth_score,
                    valuation_score=score.valuation_score,
                    financial_health_score=score.financial_health_score,
                    data_completeness=score.data_completeness,
                    rank=score.rank
                )
        
        messages.success(
            request,
            f'「{original.name}」を複製しました（企業: {original.get_company_count()}社, 指標: {metrics_count}件）'
        )
        return redirect('analysis_template:detail', pk=new_template.pk)
        
    except Exception as e:
        messages.error(request, f'複製に失敗しました: {str(e)}')
        return redirect('analysis_template:detail', pk=pk)


@login_required
@require_http_methods(["GET"])
def template_export(request, pk):
    """テンプレートをCSVエクスポート"""
    template = get_object_or_404(AnalysisTemplate, pk=pk, user=request.user)
    
    # CSVレスポンスを作成
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{template.name}_export.csv"'
    
    writer = csv.writer(response)
    
    # ヘッダー行を作成
    companies = template.companies.all().order_by('templatecompany__display_order')
    metrics = MetricDefinition.objects.filter(is_active=True).order_by('display_order')
    
    header = ['企業コード', '企業名', '業種']
    header.extend([m.display_name for m in metrics])
    writer.writerow(header)
    
    # データ行を作成
    for company in companies:
        row = [company.code, company.name, company.industry_name_33 or '-']
        
        for metric in metrics:
            try:
                tm = TemplateMetrics.objects.get(
                    template=template,
                    company=company,
                    metric_definition=metric
                )
                row.append(str(tm.value))
            except TemplateMetrics.DoesNotExist:
                row.append('')
        
        writer.writerow(row)
    
    return response


@login_required
@require_http_methods(["POST"])
def template_bulk_delete(request):
    """テンプレート一括削除"""
    try:
        data = json.loads(request.body)
        template_ids = data.get('template_ids', [])
        
        if not template_ids:
            return JsonResponse({
                'success': False,
                'error': '削除するテンプレートが選択されていません'
            }, status=400)
        
        # 自分のテンプレートのみ削除
        deleted_count = AnalysisTemplate.objects.filter(
            pk__in=template_ids,
            user=request.user
        ).delete()[0]
        
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count}件のテンプレートを削除しました'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': '不正なリクエスト形式です'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)