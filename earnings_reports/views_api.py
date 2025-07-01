"""
earnings_reports/views_api.py
API エンドポイントとエクスポート機能
"""

import json
import csv
import io
from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import Company, Analysis, Document, AnalysisHistory
from .utils.company_utils import export_company_analysis_data, get_company_analysis_stats


@login_required
def export_company_data(request, stock_code):
    """企業分析データのエクスポート"""
    
    company = get_object_or_404(Company, stock_code=stock_code)
    format_type = request.GET.get('format', 'json').lower()
    
    if format_type not in ['json', 'csv']:
        return JsonResponse({'error': 'サポートされていない形式です'}, status=400)
    
    try:
        # データをエクスポート
        export_data = export_company_analysis_data(company, request.user, format_type)
        
        if format_type == 'json':
            response = HttpResponse(export_data, content_type='application/json')
            filename = f"{company.name}_{company.stock_code}_analysis_{datetime.now().strftime('%Y%m%d')}.json"
        else:  # CSV
            response = HttpResponse(export_data, content_type='text/csv')
            filename = f"{company.name}_{company.stock_code}_analysis_{datetime.now().strftime('%Y%m%d')}.csv"
        
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        return JsonResponse({'error': f'エクスポートエラー: {str(e)}'}, status=500)


@login_required
def company_stats_api(request, stock_code):
    """企業統計API"""
    
    company = get_object_or_404(Company, stock_code=stock_code)
    stats = get_company_analysis_stats(company, request.user)
    
    return JsonResponse({
        'company': {
            'stock_code': company.stock_code,
            'name': company.name,
            'market': company.market,
            'sector': company.sector,
            'last_sync': company.last_sync.isoformat() if company.last_sync else None
        },
        'stats': stats
    })


@login_required
def user_stats_api(request):
    """ユーザー統計API"""
    
    # 基本統計
    total_analyses = Analysis.objects.filter(user=request.user).count()
    completed_analyses = Analysis.objects.filter(user=request.user, status='completed').count()
    companies_analyzed = Company.objects.filter(
        documents__analysis__user=request.user
    ).distinct().count()
    
    # 今月の分析数
    this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_analyses = Analysis.objects.filter(
        user=request.user,
        analysis_date__gte=this_month_start
    ).count()
    
    # 平均スコア
    avg_score = Analysis.objects.filter(
        user=request.user,
        status='completed',
        overall_score__isnull=False
    ).aggregate(avg=Avg('overall_score'))['avg']
    
    # 最近の活動
    recent_activity = []
    recent_analyses = Analysis.objects.filter(
        user=request.user,
        status='completed'
    ).select_related('document__company').order_by('-analysis_date')[:5]
    
    for analysis in recent_analyses:
        recent_activity.append({
            'id': analysis.id,
            'company_name': analysis.document.company.name,
            'stock_code': analysis.document.company.stock_code,
            'doc_type': analysis.document.get_doc_type_display(),
            'score': analysis.overall_score,
            'date': analysis.analysis_date.isoformat()
        })
    
    return JsonResponse({
        'total_analyses': total_analyses,
        'completed_analyses': completed_analyses,
        'companies_analyzed': companies_analyzed,
        'this_month_analyses': this_month_analyses,
        'avg_score': round(avg_score, 2) if avg_score else None,
        'recent_activity': recent_activity
    })


@login_required
def analysis_status_api(request, analysis_id):
    """分析状況API"""
    
    analysis = get_object_or_404(Analysis, id=analysis_id, user=request.user)
    
    # 進行状況の計算
    progress_percentage = 0
    if analysis.status == 'pending':
        progress_percentage = 0
    elif analysis.status == 'processing':
        # 処理時間から推定
        if analysis.processing_time:
            estimated_total = 180  # 3分
            progress_percentage = min(90, int((analysis.processing_time / estimated_total) * 100))
        else:
            progress_percentage = 30
    elif analysis.status == 'completed':
        progress_percentage = 100
    elif analysis.status == 'failed':
        progress_percentage = 0
    
    response_data = {
        'id': analysis.id,
        'status': analysis.status,
        'status_display': analysis.get_status_display(),
        'progress_percentage': progress_percentage,
        'overall_score': analysis.overall_score,
        'processing_time': analysis.processing_time,
        'error_message': analysis.error_message,
        'company': {
            'name': analysis.document.company.name,
            'stock_code': analysis.document.company.stock_code
        },
        'document': {
            'type': analysis.document.get_doc_type_display(),
            'description': analysis.document.doc_description,
            'submit_date': analysis.document.submit_date.isoformat()
        }
    }
    
    return JsonResponse(response_data)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def retry_analysis_api(request, analysis_id):
    """分析再実行API"""
    
    analysis = get_object_or_404(Analysis, id=analysis_id, user=request.user)
    
    if analysis.status not in ['failed']:
        return JsonResponse({
            'success': False,
            'error': '再実行できない状況です'
        })
    
    try:
        from .services.analysis_service import EarningsAnalysisService
        
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
        
        # 分析を再実行（非同期）
        from .views import execute_analysis_async
        execute_analysis_async.delay(analysis.id)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def company_search_api(request):
    """企業検索API（高度検索）"""
    
    query = request.GET.get('q', '').strip()
    limit = min(int(request.GET.get('limit', 20)), 50)
    include_stats = request.GET.get('include_stats', 'false').lower() == 'true'
    
    if len(query) < 1:
        return JsonResponse({'companies': []})
    
    # 検索クエリ
    companies = Company.objects.filter(
        Q(stock_code__icontains=query) |
        Q(name__icontains=query) |
        Q(name_kana__icontains=query) |
        Q(sector__icontains=query)
    ).order_by('stock_code')[:limit]
    
    results = []
    for company in companies:
        company_data = {
            'stock_code': company.stock_code,
            'name': company.name,
            'name_kana': company.name_kana,
            'market': company.market,
            'sector': company.sector,
            'last_sync': company.last_sync.isoformat() if company.last_sync else None
        }
        
        if include_stats:
            # 統計情報を含む
            stats = get_company_analysis_stats(company, request.user)
            company_data['stats'] = stats
        
        results.append(company_data)
    
    return JsonResponse({
        'companies': results,
        'total': len(results)
    })


@login_required
def analysis_trends_api(request):
    """分析トレンドAPI"""
    
    # 期間の指定
    days = int(request.GET.get('days', 30))
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # 指定期間の分析データ
    analyses = Analysis.objects.filter(
        user=request.user,
        status='completed',
        analysis_date__gte=start_date,
        analysis_date__lte=end_date
    ).select_related('document__company').order_by('analysis_date')
    
    # 日別の集計
    daily_stats = {}
    for analysis in analyses:
        date_key = analysis.analysis_date.date().isoformat()
        
        if date_key not in daily_stats:
            daily_stats[date_key] = {
                'date': date_key,
                'count': 0,
                'avg_score': 0,
                'scores': [],
                'companies': set()
            }
        
        daily_stats[date_key]['count'] += 1
        daily_stats[date_key]['companies'].add(analysis.document.company.name)
        
        if analysis.overall_score is not None:
            daily_stats[date_key]['scores'].append(analysis.overall_score)
    
    # 平均スコアの計算
    trend_data = []
    for date_key, stats in sorted(daily_stats.items()):
        if stats['scores']:
            avg_score = sum(stats['scores']) / len(stats['scores'])
        else:
            avg_score = None
        
        trend_data.append({
            'date': stats['date'],
            'analysis_count': stats['count'],
            'company_count': len(stats['companies']),
            'avg_score': round(avg_score, 2) if avg_score else None,
            'companies': list(stats['companies'])
        })
    
    return JsonResponse({
        'trend_data': trend_data,
        'period': {
            'start_date': start_date.date().isoformat(),
            'end_date': end_date.date().isoformat(),
            'days': days
        }
    })


@login_required
def industry_benchmark_api(request):
    """業界ベンチマークAPI"""
    
    sector = request.GET.get('sector')
    metric = request.GET.get('metric', 'overall_score')
    
    if not sector:
        return JsonResponse({'error': 'セクター名が必要です'}, status=400)
    
    # 同業種の企業を取得
    sector_companies = Company.objects.filter(sector=sector)
    
    if sector_companies.count() < 3:
        return JsonResponse({
            'benchmark': None,
            'message': 'ベンチマーク計算に十分なデータがありません（最低3社必要）'
        })
    
    # メトリクスに応じた集計
    if metric == 'overall_score':
        scores = Analysis.objects.filter(
            document__company__in=sector_companies,
            status='completed',
            overall_score__isnull=False
        ).values_list('overall_score', flat=True)
        
    elif metric == 'sentiment_score':
        from .models import SentimentAnalysis
        scores = SentimentAnalysis.objects.filter(
            analysis__document__company__in=sector_companies,
            analysis__status='completed'
        ).values_list('positive_score', flat=True)
        
    elif metric == 'cf_quality':
        from .models import CashFlowAnalysis
        scores = CashFlowAnalysis.objects.filter(
            analysis__document__company__in=sector_companies,
            analysis__status='completed'
        ).values_list('cf_quality_score', flat=True)
        
    else:
        return JsonResponse({'error': '無効なメトリクスです'}, status=400)
    
    if not scores:
        return JsonResponse({
            'benchmark': None,
            'message': 'データが不足しています'
        })
    
    # 統計値の計算
    scores_list = list(scores)
    avg_score = sum(scores_list) / len(scores_list)
    min_score = min(scores_list)
    max_score = max(scores_list)
    
    # パーセンタイル計算
    sorted_scores = sorted(scores_list)
    n = len(sorted_scores)
    percentile_25 = sorted_scores[int(n * 0.25)]
    percentile_75 = sorted_scores[int(n * 0.75)]
    
    return JsonResponse({
        'benchmark': {
            'sector': sector,
            'metric': metric,
            'company_count': sector_companies.count(),
            'data_points': len(scores_list),
            'average': round(avg_score, 2),
            'minimum': round(min_score, 2),
            'maximum': round(max_score, 2),
            'percentile_25': round(percentile_25, 2),
            'percentile_75': round(percentile_75, 2)
        }
    })


@login_required
def export_all_data_api(request):
    """全分析データの一括エクスポート"""
    
    format_type = request.GET.get('format', 'json').lower()
    
    if format_type not in ['json', 'csv']:
        return JsonResponse({'error': 'サポートされていない形式です'}, status=400)
    
    # ユーザーの全分析データを取得
    analyses = Analysis.objects.filter(
        user=request.user,
        status='completed'
    ).select_related(
        'document__company', 'sentiment', 'cashflow'
    ).order_by('-analysis_date')
    
    if format_type == 'json':
        # JSON形式でエクスポート
        data = []
        for analysis in analyses:
            item = {
                'analysis_id': analysis.id,
                'analysis_date': analysis.analysis_date.isoformat(),
                'company': {
                    'stock_code': analysis.document.company.stock_code,
                    'name': analysis.document.company.name,
                    'market': analysis.document.company.market,
                    'sector': analysis.document.company.sector
                },
                'document': {
                    'type': analysis.document.doc_type,
                    'type_display': analysis.document.get_doc_type_display(),
                    'description': analysis.document.doc_description,
                    'submit_date': analysis.document.submit_date.isoformat()
                },
                'overall_score': analysis.overall_score,
                'confidence_level': analysis.confidence_level,
                'processing_time': analysis.processing_time
            }
            
            # 感情分析データ
            if hasattr(analysis, 'sentiment'):
                sentiment = analysis.sentiment
                item['sentiment'] = {
                    'positive_score': sentiment.positive_score,
                    'negative_score': sentiment.negative_score,
                    'neutral_score': sentiment.neutral_score,
                    'confidence_keywords_count': sentiment.confidence_keywords_count,
                    'uncertainty_keywords_count': sentiment.uncertainty_keywords_count,
                    'growth_keywords_count': sentiment.growth_keywords_count,
                    'risk_keywords_count': sentiment.risk_keywords_count,
                    'risk_severity': sentiment.risk_severity,
                    'management_confidence_index': sentiment.management_confidence_index
                }
            
            # キャッシュフロー分析データ
            if hasattr(analysis, 'cashflow'):
                cashflow = analysis.cashflow
                item['cashflow'] = {
                    'operating_cf': cashflow.operating_cf,
                    'investing_cf': cashflow.investing_cf,
                    'financing_cf': cashflow.financing_cf,
                    'free_cf': cashflow.free_cf,
                    'pattern': cashflow.pattern,
                    'pattern_score': cashflow.pattern_score,
                    'cf_quality_score': cashflow.cf_quality_score
                }
            
            data.append(item)
        
        response_data = json.dumps(data, ensure_ascii=False, indent=2)
        response = HttpResponse(response_data, content_type='application/json')
        filename = f"all_analysis_data_{request.user.username}_{datetime.now().strftime('%Y%m%d')}.json"
        
    else:  # CSV
        # CSV形式でエクスポート
        output = io.StringIO()
        writer = csv.writer(output)
        
        # ヘッダー
        writer.writerow([
            '分析ID', '分析日時', '企業名', '証券コード', '市場', '業種',
            '書類種別', '書類名', '提出日', '総合スコア', '信頼性', '処理時間',
            'ポジティブ度', 'ネガティブ度', 'ニュートラル度', '自信表現数', '不確実表現数',
            '成長関連数', 'リスク言及数', 'リスク深刻度', '経営陣自信度',
            '営業CF', '投資CF', '財務CF', 'フリーCF', 'CFパターン', 'CFスコア', 'CF品質'
        ])
        
        # データ行
        for analysis in analyses:
            sentiment = getattr(analysis, 'sentiment', None)
            cashflow = getattr(analysis, 'cashflow', None)
            
            writer.writerow([
                analysis.id,
                analysis.analysis_date.strftime('%Y-%m-%d %H:%M:%S'),
                analysis.document.company.name,
                analysis.document.company.stock_code,
                analysis.document.company.market or '',
                analysis.document.company.sector or '',
                analysis.document.get_doc_type_display(),
                analysis.document.doc_description,
                analysis.document.submit_date.strftime('%Y-%m-%d'),
                analysis.overall_score,
                analysis.confidence_level or '',
                analysis.processing_time,
                sentiment.positive_score if sentiment else '',
                sentiment.negative_score if sentiment else '',
                sentiment.neutral_score if sentiment else '',
                sentiment.confidence_keywords_count if sentiment else '',
                sentiment.uncertainty_keywords_count if sentiment else '',
                sentiment.growth_keywords_count if sentiment else '',
                sentiment.risk_keywords_count if sentiment else '',
                sentiment.risk_severity if sentiment else '',
                sentiment.management_confidence_index if sentiment else '',
                cashflow.operating_cf if cashflow else '',
                cashflow.investing_cf if cashflow else '',
                cashflow.financing_cf if cashflow else '',
                cashflow.free_cf if cashflow else '',
                cashflow.get_pattern_display() if cashflow else '',
                cashflow.pattern_score if cashflow else '',
                cashflow.cf_quality_score if cashflow else ''
            ])
        
        response_data = output.getvalue()
        response = HttpResponse(response_data, content_type='text/csv')
        filename = f"all_analysis_data_{request.user.username}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response