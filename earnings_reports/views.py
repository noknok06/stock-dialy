"""
earnings_reports/views.py
決算分析アプリのビュー
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
from .forms import (StockCodeSearchForm, DocumentSelectionForm, AnalysisSettingsForm, 
                   CompanyRegistrationForm, AnalysisFilterForm, BulkAnalysisForm)
from .services.edinet_service import EDINETService
from .services.analysis_service import EarningsAnalysisService
from .utils.company_utils import get_or_create_company_from_edinet

logger = logging.getLogger('earnings_analysis')


@login_required
def home(request):
    """ホーム画面 - 分析開始"""
    form = StockCodeSearchForm()
    
    # 最近の分析結果
    recent_analyses = Analysis.objects.filter(
        user=request.user,
        status='completed'
    ).select_related('document__company').order_by('-analysis_date')[:5]
    
    # ユーザー統計
    user_stats = {
        'total_analyses': Analysis.objects.filter(user=request.user).count(),
        'companies_analyzed': Company.objects.filter(
            documents__analysis__user=request.user
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
                
                # 書類一覧画面へリダイレクト
                return redirect('earnings_reports:document_list', stock_code=company.stock_code)
                
            except Exception as e:
                logger.error(f"企業検索エラー: {str(e)}")
                messages.error(request, '企業検索中にエラーが発生しました。しばらく時間をおいてから再試行してください。')
    
    else:
        form = StockCodeSearchForm()
    
    return render(request, 'earnings_reports/search_company.html', {'form': form})


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
def document_list(request, stock_code):
    """書類一覧・選択"""
    
    company = get_object_or_404(Company, stock_code=stock_code)
    
    # EDINETから最新書類を同期
    try:
        edinet_service = EDINETService(settings.EDINET_API_KEY)
        sync_company_documents(company, edinet_service)
    except Exception as e:
        logger.warning(f"書類同期エラー: {str(e)}")
        messages.warning(request, '書類情報の同期中にエラーが発生しましたが、既存データで継続します。')
    
    # 書類一覧取得
    documents = Document.objects.filter(
        company=company,
        doc_type__in=['120', '130', '140', '350']  # 決算関連書類のみ
    ).order_by('-submit_date')
    
    # ページネーション
    paginator = Paginator(documents, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 選択フォーム
    if request.method == 'POST':
        form = DocumentSelectionForm(company=company, data=request.POST)
        
        if form.is_valid():
            selected_docs = form.cleaned_data['selected_documents']
            doc_ids = [str(doc.id) for doc in selected_docs]
            
            # セッションに保存して分析設定画面へ
            request.session['selected_document_ids'] = doc_ids
            return redirect('earnings_reports:analysis_settings', stock_code=stock_code)
    
    else:
        form = DocumentSelectionForm(company=company)
    
    context = {
        'company': company,
        'form': form,
        'page_obj': page_obj,
        'documents': page_obj.object_list,
    }
    return render(request, 'earnings_reports/document_list.html', context)


@login_required
def analysis_settings(request, stock_code):
    """分析設定"""
    
    company = get_object_or_404(Company, stock_code=stock_code)
    
    # セッションから選択書類を取得
    doc_ids = request.session.get('selected_document_ids', [])
    
    if not doc_ids:
        messages.error(request, '分析対象の書類が選択されていません。')
        return redirect('earnings_reports:document_list', stock_code=stock_code)
    
    selected_docs = Document.objects.filter(id__in=doc_ids, company=company)
    
    if request.method == 'POST':
        form = AnalysisSettingsForm(request.POST)
        
        if form.is_valid():
            # 分析実行
            settings_data = {
                'analysis_depth': form.cleaned_data['analysis_depth'],
                'include_sentiment': form.cleaned_data['include_sentiment'],
                'include_cashflow': form.cleaned_data['include_cashflow'],
                'compare_previous': form.cleaned_data['compare_previous'],
                'notify_on_completion': form.cleaned_data['notify_on_completion'],
                'custom_keywords': form.cleaned_data['custom_keywords'],
            }
            
            # 分析実行（バックグラウンド処理）
            analysis_ids = start_analysis_batch(request.user, selected_docs, settings_data)
            
            if analysis_ids:
                messages.success(request, f'{len(analysis_ids)}件の分析を開始しました。')
                return redirect('earnings_reports:analysis_status', analysis_ids=','.join(map(str, analysis_ids)))
            else:
                messages.error(request, '分析の開始に失敗しました。')
    
    else:
        form = AnalysisSettingsForm()
    
    context = {
        'company': company,
        'selected_docs': selected_docs,
        'form': form,
    }
    return render(request, 'earnings_reports/analysis_settings.html', context)


@login_required
def analysis_status(request, analysis_ids):
    """分析状況確認"""
    
    ids = [int(id.strip()) for id in analysis_ids.split(',') if id.strip().isdigit()]
    analyses = Analysis.objects.filter(id__in=ids, user=request.user)
    
    # 進行状況の集計
    status_counts = {}
    for analysis in analyses:
        status = analysis.get_status_display()
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # 完了した分析があれば結果画面へのリンクを表示
    completed_analyses = analyses.filter(status='completed')
    
    context = {
        'analyses': analyses,
        'status_counts': status_counts,
        'completed_analyses': completed_analyses,
        'is_all_completed': analyses.filter(status__in=['completed', 'failed']).count() == analyses.count(),
    }
    return render(request, 'earnings_reports/analysis_status.html', context)


@login_required
def analysis_detail(request, pk):
    """分析結果詳細"""
    
    analysis = get_object_or_404(Analysis, pk=pk, user=request.user)
    
    if analysis.status != 'completed':
        messages.warning(request, '分析が完了していません。')
        return redirect('earnings_reports:analysis_status', analysis_ids=str(analysis.id))
    
    # 関連データを取得
    sentiment = getattr(analysis, 'sentiment', None)
    cashflow = getattr(analysis, 'cashflow', None)
    
    # 前回分析との比較データ
    previous_analysis = Analysis.objects.filter(
        document__company=analysis.document.company,
        user=request.user,
        status='completed',
        analysis_date__lt=analysis.analysis_date
    ).order_by('-analysis_date').first()
    
    # チャート用データ
    chart_data = prepare_chart_data(analysis, sentiment, cashflow)
    
    context = {
        'analysis': analysis,
        'sentiment': sentiment,
        'cashflow': cashflow,
        'previous_analysis': previous_analysis,
        'chart_data': json.dumps(chart_data),
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
    """企業別ダッシュボード"""
    
    company = get_object_or_404(Company, stock_code=stock_code)
    
    # 企業の分析履歴
    analyses = Analysis.objects.filter(
        document__company=company,
        user=request.user,
        status='completed'
    ).order_by('-analysis_date')[:10]
    
    # 企業統計
    company_stats = {
        'total_analyses': analyses.count(),
        'latest_analysis': analyses.first(),
        'avg_score': analyses.aggregate(Avg('overall_score'))['overall_score__avg'],
        'documents_count': Document.objects.filter(company=company).count(),
    }
    
    # トレンドデータ
    trend_data = prepare_company_trend_data(company, request.user)
    
    context = {
        'company': company,
        'analyses': analyses,
        'company_stats': company_stats,
        'trend_data': json.dumps(trend_data),
    }
    return render(request, 'earnings_reports/company_dashboard.html', context)


# ========================================
# ユーティリティ関数
# ========================================

def sync_company_documents(company, edinet_service):
    """企業の書類情報をEDINETと同期"""
    
    try:
        # 最近30日の書類を検索
        company_docs = edinet_service.search_company_documents(
            company.stock_code, 
            days_back=30,
            max_results=50
        )
        
        synced_count = 0
        
        for doc_info in company_docs:
            doc_id, company_name, doc_description, submit_date, doc_type, sec_code = doc_info
            
            # 書類が既に存在するかチェック
            if not Document.objects.filter(doc_id=doc_id).exists():
                # 新しい書類を作成
                Document.objects.create(
                    doc_id=doc_id,
                    company=company,
                    doc_type=doc_type,
                    doc_description=doc_description,
                    submit_date=datetime.strptime(submit_date, '%Y-%m-%d').date(),
                )
                synced_count += 1
        
        # 最終同期日時を更新
        company.last_sync = timezone.now()
        company.save()
        
        logger.info(f"企業{company.name}の書類同期完了: {synced_count}件の新規書類")
        
    except Exception as e:
        logger.error(f"書類同期エラー: {str(e)}")
        raise


def start_analysis_batch(user, documents, settings_data):
    """分析バッチ開始"""
    
    analysis_ids = []
    
    try:
        for document in documents:
            # 既存の分析をチェック
            existing_analysis = Analysis.objects.filter(
                document=document,
                user=user
            ).first()
            
            if existing_analysis and existing_analysis.status == 'completed':
                # 再分析確認
                messages.info(user, f'{document.doc_description} は既に分析済みです。再分析を実行します。')
            
            # 新しい分析レコードを作成
            analysis = Analysis.objects.create(
                document=document,
                user=user,
                status='pending',
                settings_json=settings_data
            )
            
            analysis_ids.append(analysis.id)
        
        # バックグラウンドで分析実行（非同期処理）
        # 本番環境ではCeleryなどを使用
        for analysis_id in analysis_ids:
            execute_analysis_async.delay(analysis_id)
        
        return analysis_ids
        
    except Exception as e:
        logger.error(f"分析バッチ開始エラー: {str(e)}")
        return []


def prepare_chart_data(analysis, sentiment, cashflow):
    """チャート用データ準備"""
    
    chart_data = {
        'sentiment': {},
        'cashflow': {},
        'overall': {}
    }
    
    # 感情分析チャートデータ
    if sentiment:
        chart_data['sentiment'] = {
            'scores': {
                'positive': sentiment.positive_score,
                'negative': sentiment.negative_score,
                'neutral': sentiment.neutral_score
            },
            'keywords': {
                'confidence': sentiment.confidence_keywords_count,
                'uncertainty': sentiment.uncertainty_keywords_count,
                'growth': sentiment.growth_keywords_count,
                'risk': sentiment.risk_keywords_count
            }
        }
    
    # キャッシュフローチャートデータ
    if cashflow:
        chart_data['cashflow'] = {
            'amounts': {
                'operating': cashflow.operating_cf,
                'investing': cashflow.investing_cf,
                'financing': cashflow.financing_cf,
                'free': cashflow.free_cf
            },
            'pattern': cashflow.pattern,
            'score': cashflow.pattern_score
        }
    
    # 総合データ
    chart_data['overall'] = {
        'score': analysis.overall_score,
        'confidence': analysis.confidence_level
    }
    
    return chart_data


def prepare_company_trend_data(company, user):
    """企業トレンドデータ準備"""
    
    analyses = Analysis.objects.filter(
        document__company=company,
        user=user,
        status='completed'
    ).order_by('analysis_date')[:12]  # 最近12回分
    
    trend_data = {
        'dates': [],
        'scores': [],
        'sentiment_trends': {
            'positive': [],
            'negative': [],
            'confidence': []
        }
    }
    
    for analysis in analyses:
        trend_data['dates'].append(analysis.analysis_date.strftime('%Y-%m-%d'))
        trend_data['scores'].append(analysis.overall_score)
        
        if hasattr(analysis, 'sentiment'):
            sentiment = analysis.sentiment
            trend_data['sentiment_trends']['positive'].append(sentiment.positive_score)
            trend_data['sentiment_trends']['negative'].append(sentiment.negative_score)
            trend_data['sentiment_trends']['confidence'].append(sentiment.management_confidence_index)
    
    return trend_data


# ========================================
# 非同期処理（実際の環境ではCeleryを使用）
# ========================================

class MockAsyncExecutor:
    """開発環境用の非同期処理モック"""
    
    @staticmethod
    def delay(analysis_id):
        """分析を非同期実行（開発環境では同期実行）"""
        try:
            analysis = Analysis.objects.get(id=analysis_id)
            analysis.status = 'processing'
            analysis.save()
            
            # 実際の分析実行
            service = EarningsAnalysisService()
            service.execute_analysis(analysis)
            
        except Exception as e:
            logger.error(f"分析実行エラー: {str(e)}")
            Analysis.objects.filter(id=analysis_id).update(
                status='failed',
                error_message=str(e)
            )

# 開発環境では同期実行
execute_analysis_async = MockAsyncExecutor()