# earnings_reports/views.py (最適化版)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.conf import settings

import json
import logging
from datetime import datetime, timedelta

from .models import Company, Document, Analysis, SentimentAnalysis, CashFlowAnalysis, AnalysisHistory
from .forms import StockCodeSearchForm, AnalysisFilterForm
from .services.edinet_service import EDINETService
from .services.analysis_service import EarningsAnalysisService
from .utils.company_utils import get_or_create_company_from_edinet

logger = logging.getLogger('earnings_analysis')


@login_required
def home(request):
    """ホーム画面"""
    if request.method == 'POST':
        return search_company(request)
    
    form = StockCodeSearchForm()
    
    recent_analyses = Analysis.objects.filter(
        user=request.user,
        status='completed'
    ).select_related('document__company').order_by('-analysis_date')[:5]
    
    user_stats = {
        'total_analyses': Analysis.objects.filter(user=request.user).count(),
        'companies_analyzed': Company.objects.filter(
            documents__analyses__user=request.user
        ).distinct().count(),
        'this_month_analyses': Analysis.objects.filter(
            user=request.user,
            analysis_date__gte=timezone.now().replace(day=1)
        ).count()
    }
    
    context = {
        'form': form,
        'recent_analyses': recent_analyses,
        'user_stats': user_stats,
    }
    return render(request, 'earnings_reports/home.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def search_company(request):
    """企業検索・選択"""
    
    if request.method == 'POST':
        form = StockCodeSearchForm(request.POST)
        
        if form.is_valid():
            stock_code = form.cleaned_data['stock_code']
            
            try:
                company = Company.objects.filter(stock_code=stock_code).first()
                
                if not company:
                    edinet_service = EDINETService(settings.EDINET_API_KEY)
                    company = get_or_create_company_from_edinet(stock_code, edinet_service)
                    
                    if not company:
                        messages.error(request, f'証券コード {stock_code} の企業が見つかりませんでした。')
                        return render(request, 'earnings_reports/search_company.html', {'form': form})
                    
                    messages.success(request, f'{company.name} を新規登録しました。')
                
                return redirect('earnings_reports:document_list', stock_code=company.stock_code)
                
            except Exception as e:
                logger.error(f"企業検索エラー: {str(e)}")
                messages.error(request, '企業検索中にエラーが発生しました。しばらく時間をおいてから再試行してください。')
    
    else:
        form = StockCodeSearchForm()
    
    return render(request, 'earnings_reports/search_company.html', {'form': form})


@login_required
@require_http_methods(["GET", "POST"])
def document_list(request, stock_code):
    """書類一覧・選択・分析実行（最適化版）"""
    
    company = get_object_or_404(Company, stock_code=stock_code)
    
    # 書類データの同期チェック（最適化）
    sync_requested = request.GET.get('sync') == '1'
    if sync_requested or should_sync_documents_optimized(company):
        try:
            edinet_service = EDINETService(settings.EDINET_API_KEY)
            sync_result = sync_company_documents_optimized(company, edinet_service)
            
            if sync_requested:
                if sync_result['new_count'] > 0:
                    messages.success(request, f'{sync_result["new_count"]}件の新しい書類を同期しました。')
                else:
                    messages.info(request, '新しい書類はありませんでした。')
                
        except Exception as e:
            logger.warning(f"書類同期エラー: {str(e)}")
            messages.warning(request, '書類情報の同期中にエラーが発生しましたが、既存データで継続します。')
    
    # POST処理 - 書類選択→分析実行
    if request.method == 'POST':
        selected_doc_ids = request.POST.getlist('selected_documents')
        
        if not selected_doc_ids:
            messages.error(request, '分析する書類を選択してください。')
        else:
            # 分析設定を収集
            analysis_settings = {
                'analysis_depth': request.POST.get('analysis_depth', 'basic'),
                'include_sentiment': bool(request.POST.get('include_sentiment')),
                'include_cashflow': bool(request.POST.get('include_cashflow')),
                'compare_previous': bool(request.POST.get('compare_previous')),
                'custom_keywords': [
                    keyword.strip() 
                    for keyword in request.POST.get('custom_keywords', '').split(',') 
                    if keyword.strip()
                ]
            }
            
            # 選択された書類を取得
            selected_documents = Document.objects.filter(
                id__in=selected_doc_ids,
                company=company
            )
            
            # 分析を開始
            analysis_results = start_document_analysis(
                user=request.user,
                documents=selected_documents,
                settings=analysis_settings
            )
            
            if analysis_results['success']:
                messages.success(
                    request, 
                    f'{len(analysis_results["analyses"])}件の分析を開始しました。'
                )
                
                # 分析状況画面へリダイレクト
                analysis_ids = ','.join(str(a.id) for a in analysis_results['analyses'])
                return redirect('earnings_reports:analysis_status', analysis_ids=analysis_ids)
            else:
                messages.error(request, f'分析開始に失敗しました: {analysis_results["error"]}')
    
    # GET処理 - 書類一覧表示
    documents = Document.objects.filter(
        company=company,
        doc_type__in=['120', '130', '140', '350']  # 決算関連書類のみ
    ).order_by('-submit_date')
    
    # 各書類の分析状況をチェック
    for doc in documents:
        doc.latest_analysis = Analysis.objects.filter(
            document=doc,
            user=request.user
        ).order_by('-analysis_date').first()
        
        doc.is_analyzed = (
            doc.latest_analysis and 
            doc.latest_analysis.status == 'completed'
        )
    
    # ページネーション
    paginator = Paginator(documents, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'company': company,
        'documents': page_obj.object_list,
        'page_obj': page_obj,
    }
    return render(request, 'earnings_reports/document_list.html', context)


def should_sync_documents_optimized(company):
    """最適化された書類データの同期判定"""
    
    if not company.last_sync:
        return True
    
    # 最近の書類があるかチェック
    recent_docs = Document.objects.filter(
        company=company,
        submit_date__gte=timezone.now().date() - timedelta(days=7)
    ).exists()
    
    # 最近の書類がない場合のみ同期（頻度を削減）
    if not recent_docs:
        hours_since_sync = (timezone.now() - company.last_sync).total_seconds() / 3600
        return hours_since_sync > 72  # 3日間隔に延長
    
    # 最近の書類がある場合は同期頻度を下げる
    hours_since_sync = (timezone.now() - company.last_sync).total_seconds() / 3600
    return hours_since_sync > 168  # 1週間間隔


def sync_company_documents_optimized(company, edinet_service):
    """最適化された企業書類同期"""
    
    try:
        logger.info(f"書類同期開始: {company.name}")
        
        # 最適化された検索を使用（段階的検索）
        company_docs = edinet_service.search_company_documents_optimized(
            company.stock_code,
            days_back=14,  # 2週間に短縮
            max_results=30  # 上限を削減
        )
        
        if not company_docs:
            logger.info(f"新しい書類なし: {company.name}")
            company.last_sync = timezone.now()
            company.save()
            return {
                'success': True,
                'new_count': 0,
                'updated_count': 0
            }
        
        # 最適化されたバッチ処理
        batch_result = edinet_service.process_documents_batch(company, company_docs)
        
        # 最終同期日時を更新
        company.last_sync = timezone.now()
        company.save()
        
        logger.info(f"書類同期完了: {company.name} - 新規:{batch_result['new']}件, 更新:{batch_result['updated']}件")
        
        return {
            'success': True,
            'new_count': batch_result['new'],
            'updated_count': batch_result['updated']
        }
        
    except Exception as e:
        logger.error(f"書類同期エラー: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'new_count': 0,
            'updated_count': 0
        }


def start_document_analysis(user, documents, settings):
    """書類分析を開始"""
    
    analyses = []
    
    try:
        for document in documents:
            # 新しい分析レコードを作成
            analysis = Analysis.objects.create(
                document=document,
                user=user,
                status='pending',
                settings_json=settings
            )
            
            analyses.append(analysis)
        
        # バックグラウンドで分析実行
        for analysis in analyses:
            execute_analysis_async.delay(analysis.id)
        
        return {
            'success': True,
            'analyses': analyses
        }
        
    except Exception as e:
        logger.error(f"分析開始エラー: {str(e)}")
        
        # 作成済みの分析レコードをクリーンアップ
        for analysis in analyses:
            try:
                analysis.delete()
            except:
                pass
        
        return {
            'success': False,
            'error': str(e),
            'analyses': []
        }


@login_required
def analysis_status(request, analysis_ids):
    """分析状況確認・リアルタイム更新"""
    
    ids = [int(id.strip()) for id in analysis_ids.split(',') if id.strip().isdigit()]
    analyses = Analysis.objects.filter(id__in=ids, user=request.user).select_related('document__company')
    
    if not analyses.exists():
        messages.error(request, '指定された分析が見つかりません。')
        return redirect('earnings_reports:analysis_list')
    
    # AJAX リクエストの場合はJSONで状況を返す
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        status_data = []
        for analysis in analyses:
            status_data.append({
                'id': analysis.id,
                'status': analysis.status,
                'status_display': analysis.get_status_display(),
                'company_name': analysis.document.company.name,
                'doc_type': analysis.document.get_doc_type_display(),
                'overall_score': analysis.overall_score,
                'progress_percentage': get_analysis_progress(analysis),
                'error_message': analysis.error_message,
                'processing_time': analysis.processing_time,
            })
        
        return JsonResponse({
            'analyses': status_data,
            'all_completed': all(a.status in ['completed', 'failed'] for a in analyses)
        })
    
    # 通常のページ表示
    status_counts = {}
    for analysis in analyses:
        status = analysis.get_status_display()
        status_counts[status] = status_counts.get(status, 0) + 1
    
    completed_analyses = analyses.filter(status='completed')
    failed_analyses = analyses.filter(status='failed')
    
    context = {
        'analyses': analyses,
        'status_counts': status_counts,
        'completed_analyses': completed_analyses,
        'failed_analyses': failed_analyses,
        'is_all_completed': analyses.filter(status__in=['completed', 'failed']).count() == analyses.count(),
        'company': analyses.first().document.company if analyses.exists() else None,
    }
    return render(request, 'earnings_reports/analysis_status.html', context)


@login_required
def analysis_detail(request, pk):
    """分析結果詳細"""
    
    analysis = get_object_or_404(Analysis, pk=pk, user=request.user)
    
    if analysis.status != 'completed':
        messages.warning(request, '分析が完了していません。')
        return redirect('earnings_reports:analysis_status', analysis_ids=str(analysis.id))
    
    # 関連データを取得（最新のものを取得）
    sentiment = analysis.sentiment_analyses.order_by('-created_at').first()
    cashflow = analysis.cashflow_analyses.order_by('-created_at').first()
    
    # 前回分析との比較データ
    previous_analysis = Analysis.objects.filter(
        document__company=analysis.document.company,
        user=request.user,
        status='completed',
        analysis_date__lt=analysis.analysis_date
    ).order_by('-analysis_date').first()
    
    context = {
        'analysis': analysis,
        'sentiment': sentiment,
        'cashflow': cashflow,
        'previous_analysis': previous_analysis,
    }
    return render(request, 'earnings_reports/analysis_detail.html', context)


@login_required
def analysis_list(request):
    """分析結果一覧"""
    
    filter_form = AnalysisFilterForm(request.GET or None)
    
    analyses = Analysis.objects.filter(user=request.user).select_related(
        'document__company'
    ).order_by('-analysis_date')
    
    # フィルタ適用
    if filter_form.is_valid():
        if filter_form.cleaned_data['company']:
            analyses = analyses.filter(document__company=filter_form.cleaned_data['company'])
        
        if filter_form.cleaned_data['doc_type']:
            analyses = analyses.filter(document__doc_type=filter_form.cleaned_data['doc_type'])
        
        if filter_form.cleaned_data['status']:
            analyses = analyses.filter(status=filter_form.cleaned_data['status'])
        
        if filter_form.cleaned_data['date_from']:
            analyses = analyses.filter(analysis_date__gte=filter_form.cleaned_data['date_from'])
        
        if filter_form.cleaned_data['date_to']:
            analyses = analyses.filter(analysis_date__lte=filter_form.cleaned_data['date_to'])
        
        if filter_form.cleaned_data['score_min'] is not None:
            analyses = analyses.filter(overall_score__gte=filter_form.cleaned_data['score_min'])
        
        if filter_form.cleaned_data['score_max'] is not None:
            analyses = analyses.filter(overall_score__lte=filter_form.cleaned_data['score_max'])
    
    # ページネーション
    paginator = Paginator(analyses, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'filter_form': filter_form,
        'page_obj': page_obj,
        'analyses': page_obj.object_list,
    }
    return render(request, 'earnings_reports/analysis_list.html', context)


@login_required
def company_dashboard(request, stock_code):
    """企業別ダッシュボード"""
    
    company = get_object_or_404(Company, stock_code=stock_code)
    
    analyses = Analysis.objects.filter(
        document__company=company,
        user=request.user,
        status='completed'
    ).select_related('document').order_by('-analysis_date')[:10]
    
    company_stats = {
        'total_analyses': Analysis.objects.filter(
            document__company=company, 
            user=request.user
        ).count(),
        'latest_analysis': analyses.first(),
        'avg_score': analyses.aggregate(Avg('overall_score'))['overall_score__avg'],
        'documents_count': Document.objects.filter(company=company).count(),
    }
    
    # トレンドデータ（最近12回分）
    trend_analyses = Analysis.objects.filter(
        document__company=company,
        user=request.user,
        status='completed'
    ).select_related('document').prefetch_related(
        'sentiment_analyses', 'cashflow_analyses'
    ).order_by('analysis_date')[:12]
    
    trend_data = {
        'dates': [a.analysis_date.strftime('%Y-%m-%d') for a in trend_analyses],
        'scores': [a.overall_score for a in trend_analyses if a.overall_score],
        'sentiment_positive': [],
        'sentiment_negative': []
    }
    
    # 感情分析トレンドデータ
    for analysis in trend_analyses:
        latest_sentiment = analysis.sentiment_analyses.order_by('-created_at').first()
        if latest_sentiment:
            trend_data['sentiment_positive'].append(latest_sentiment.positive_score)
            trend_data['sentiment_negative'].append(latest_sentiment.negative_score)
        else:
            trend_data['sentiment_positive'].append(None)
            trend_data['sentiment_negative'].append(None)
    
    context = {
        'company': company,
        'analyses': analyses,
        'company_stats': company_stats,
        'trend_data': json.dumps(trend_data),
    }
    return render(request, 'earnings_reports/company_dashboard.html', context)


# API エンドポイント
@login_required
def company_autocomplete(request):
    """企業名オートコンプリート（AJAX）"""
    
    query = request.GET.get('q', '').strip()
    suggestions = []
    
    if len(query) >= 2:
        companies = Company.objects.filter(
            Q(stock_code__icontains=query) | 
            Q(name__icontains=query) |
            Q(name_kana__icontains=query)
        )[:10]
        
        suggestions = [
            {
                'stock_code': company.stock_code,
                'name': company.name,
                'display': f"{company.stock_code} - {company.name}"
            }
            for company in companies
        ]
    
    return JsonResponse({'suggestions': suggestions})


def get_analysis_progress(analysis):
    """分析の進行状況を計算（パーセンテージ）"""
    
    if analysis.status == 'pending':
        return 0
    elif analysis.status == 'processing':
        if analysis.processing_time:
            estimated_total = 180  # 秒
            progress = min(90, (analysis.processing_time / estimated_total) * 100)
            return int(progress)
        return 30
    elif analysis.status == 'completed':
        return 100
    elif analysis.status == 'failed':
        return 0
    
    return 0


# 非同期処理（実際の環境ではCeleryを使用）
class MockAsyncExecutor:
    """開発環境用の非同期処理モック"""
    
    @staticmethod
    def delay(analysis_id):
        """分析を非同期実行（開発環境では同期実行）"""
        import threading
        
        def run_analysis():
            try:
                analysis = Analysis.objects.get(id=analysis_id)
                analysis.status = 'processing'
                analysis.save()
                
                # 実際の分析実行
                service = EarningsAnalysisService()
                service.execute_analysis(analysis)
                
            except Exception as e:
                logger.error(f"分析実行エラー: {str(e)}")
                try:
                    Analysis.objects.filter(id=analysis_id).update(
                        status='failed',
                        error_message=str(e)
                    )
                except:
                    pass
        
        # バックグラウンドスレッドで実行
        thread = threading.Thread(target=run_analysis)
        thread.daemon = True
        thread.start()

# 開発環境では非同期実行
execute_analysis_async = MockAsyncExecutor()