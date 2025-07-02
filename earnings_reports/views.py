"""
earnings_reports/views.py
改善されたビュー - 書類選択から即座に分析実行
"""

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
    """ホーム画面 - 分析開始（修正版）"""
    # StockCodeSearchForm を POST でも処理
    if request.method == 'POST':
        return search_company(request)
    
    form = StockCodeSearchForm()
    
    # 最近の分析結果（関連名を修正）
    recent_analyses = Analysis.objects.filter(
        user=request.user,
        status='completed'
    ).select_related('document__company').order_by('-analysis_date')[:5]
    
    # ユーザー統計（関連名を修正）
    user_stats = {
        'total_analyses': Analysis.objects.filter(user=request.user).count(),
        'companies_analyzed': Company.objects.filter(
            documents__analyses__user=request.user  # analysis → analyses に修正
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
                # 1. DB内検索
                company = Company.objects.filter(stock_code=stock_code).first()
                
                if not company:
                    # 2. EDINETから検索・作成
                    edinet_service = EDINETService(settings.EDINET_API_KEY)
                    company = get_or_create_company_from_edinet(stock_code, edinet_service)
                    
                    if not company:
                        messages.error(request, f'証券コード {stock_code} の企業が見つかりませんでした。')
                        return render(request, 'earnings_reports/search_company.html', {'form': form})
                    
                    messages.success(request, f'{company.name} を新規登録しました。')
                
                # 書類一覧画面へリダイレクト
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
    """書類一覧・選択・分析実行"""
    
    company = get_object_or_404(Company, stock_code=stock_code)
    
    # 書類データの同期チェック
    sync_requested = request.GET.get('sync') == '1'
    if sync_requested or should_sync_documents(company):
        try:
            edinet_service = EDINETService(settings.EDINET_API_KEY)
            sync_result = sync_company_documents(company, edinet_service)
            
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
    # 進行状況の集計
    status_counts = {}
    for analysis in analyses:
        status = analysis.get_status_display()
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # 完了した分析
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
    """分析結果詳細（修正版）"""
    
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
    
    # フィルタフォーム
    filter_form = AnalysisFilterForm(request.GET or None)
    
    # 基本クエリ
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
    """企業別ダッシュボード（修正版）"""
    
    company = get_object_or_404(Company, stock_code=stock_code)
    
    # 企業の分析履歴
    analyses = Analysis.objects.filter(
        document__company=company,
        user=request.user,
        status='completed'
    ).select_related('document').order_by('-analysis_date')[:10]
    
    # 企業統計
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

def get_company_analysis_stats(company, user):
    """企業の分析統計を取得（修正版）"""
    
    from django.db.models import Count, Avg, Max, Q
    
    # 基本統計
    total_documents = Document.objects.filter(company=company).count()
    total_analyses = Analysis.objects.filter(
        document__company=company,
        user=user
    ).count()
    
    # 完了した分析の統計
    completed_analyses = Analysis.objects.filter(
        document__company=company,
        user=user,
        status='completed'
    )
    
    avg_score = completed_analyses.aggregate(
        avg_score=Avg('overall_score')
    )['avg_score']
    
    latest_analysis = completed_analyses.order_by('-analysis_date').first()
    
    # 書類種別ごとの統計
    doc_type_stats = Document.objects.filter(company=company).values(
        'doc_type'
    ).annotate(
        count=Count('id'),
        analyzed_count=Count(
            'analyses', 
            filter=Q(analyses__user=user, analyses__status='completed')
        )
    )
    
    return {
        'total_documents': total_documents,
        'total_analyses': total_analyses,
        'completed_analyses': completed_analyses.count(),
        'avg_score': round(avg_score, 2) if avg_score else None,
        'latest_analysis': latest_analysis,
        'doc_type_stats': list(doc_type_stats),
        'last_sync': company.last_sync,
    }
# ========================================
# API エンドポイント
# ========================================

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


@login_required
@require_http_methods(["POST"])
def retry_analysis(request, analysis_id):
    """分析再実行"""
    
    analysis = get_object_or_404(Analysis, id=analysis_id, user=request.user)
    
    if analysis.status not in ['failed']:
        return JsonResponse({
            'success': False, 
            'error': '再実行できない状況です'
        })
    
    try:
        # 分析状態をリセット
        analysis.status = 'pending'
        analysis.error_message = ''
        analysis.processing_time = None
        analysis.overall_score = None
        analysis.save()
        
        # 関連する分析結果をクリア
        if hasattr(analysis, 'sentiment'):
            analysis.sentiment.delete()
        if hasattr(analysis, 'cashflow'):
            analysis.cashflow.delete()
        
        # 分析を再実行
        execute_analysis_async.delay(analysis.id)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"分析再実行エラー: {str(e)}")
        return JsonResponse({
            'success': False, 
            'error': str(e)
        })


# ========================================
# ユーティリティ関数
# ========================================

def should_sync_documents(company):
    """書類データの同期が必要かチェック"""
    
    if not company.last_sync:
        return True
    
    # 24時間以上同期していない場合
    hours_since_sync = (timezone.now() - company.last_sync).total_seconds() / 3600
    return hours_since_sync > 24


def sync_company_documents(company, edinet_service):
    """企業の書類情報をEDINETと同期（最適化版）"""
    
    try:
        logger.info(f"書類同期開始: {company.name}")
        
        # 最適化された検索を使用
        company_docs = edinet_service.search_company_documents_optimized(
            company.stock_code, 
            days_back=30,  # 30日に短縮
            max_results=100  # 上限を設定
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
        
        # バッチ処理で効率化
        new_count, updated_count = process_documents_batch(company, company_docs)
        
        # 最終同期日時を更新
        company.last_sync = timezone.now()
        company.save()
        
        logger.info(f"書類同期完了: {company.name} - 新規:{new_count}件, 更新:{updated_count}件")
        
        return {
            'success': True,
            'new_count': new_count,
            'updated_count': updated_count
        }
        
    except Exception as e:
        logger.error(f"書類同期エラー: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'new_count': 0,
            'updated_count': 0
        }

def process_documents_batch(company, company_docs):
    """書類のバッチ処理（新規追加）"""
    from django.db import transaction
    
    new_count = 0
    updated_count = 0
    
    # 既存書類IDを一括取得してメモリ上でチェック
    existing_doc_ids = set(
        Document.objects.filter(company=company)
        .values_list('doc_id', flat=True)
    )
    
    docs_to_create = []
    docs_to_update = []
    
    for doc_info in company_docs:
        doc_id, company_name, doc_description, submit_date, doc_type, sec_code = doc_info
        
        try:
            submit_date_obj = datetime.strptime(submit_date, '%Y-%m-%d').date()
            
            if doc_id not in existing_doc_ids:
                # 新規作成対象
                docs_to_create.append(Document(
                    doc_id=doc_id,
                    company=company,
                    doc_type=doc_type,
                    doc_description=doc_description,
                    submit_date=submit_date_obj,
                ))
                new_count += 1
            else:
                # 更新の必要性をチェック（簡略化）
                existing_doc = Document.objects.filter(
                    doc_id=doc_id, company=company
                ).first()
                
                if (existing_doc and 
                    (existing_doc.doc_description != doc_description or 
                     existing_doc.submit_date != submit_date_obj)):
                    existing_doc.doc_description = doc_description
                    existing_doc.submit_date = submit_date_obj
                    docs_to_update.append(existing_doc)
                    updated_count += 1
                    
        except Exception as e:
            logger.warning(f"書類{doc_id}の処理エラー: {str(e)}")
            continue
    
    # バッチ作成・更新
    with transaction.atomic():
        if docs_to_create:
            Document.objects.bulk_create(docs_to_create, batch_size=50)
        
        if docs_to_update:
            Document.objects.bulk_update(
                docs_to_update, 
                ['doc_description', 'submit_date'], 
                batch_size=50
            )
    
    return new_count, updated_count


def start_document_analysis(user, documents, settings):
    """書類分析を開始"""
    
    analyses = []
    
    try:
        for document in documents:
            # 既存の分析をチェック
            existing_analysis = Analysis.objects.filter(
                document=document,
                user=user
            ).order_by('-analysis_date').first()
            
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


def get_analysis_progress(analysis):
    """分析の進行状況を計算（パーセンテージ）"""
    
    if analysis.status == 'pending':
        return 0
    elif analysis.status == 'processing':
        # 処理時間から概算で進行状況を推定
        if analysis.processing_time:
            # 平均処理時間を3分と仮定
            estimated_total = 180  # 秒
            progress = min(90, (analysis.processing_time / estimated_total) * 100)
            return int(progress)
        return 30  # デフォルト値
    elif analysis.status == 'completed':
        return 100
    elif analysis.status == 'failed':
        return 0
    
    return 0


# ========================================
# 非同期処理（実際の環境ではCeleryを使用）
# ========================================

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