# earnings_analysis/api.py（簡略化版）
"""
オンデマンド決算分析API

特定企業の個別分析に特化したAPIエンドポイント
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.core.cache import cache
from django.conf import settings
import json
import logging
import time

from .analysis_service import OnDemandAnalysisService
from .models import CompanyEarnings, EarningsAlert

logger = logging.getLogger(__name__)


@login_required
@require_GET
def analyze_company(request, company_code):
    """
    特定企業の決算分析を実行または取得
    
    Args:
        company_code: 証券コード（例: "7203"）
        
    Query Parameters:
        force_refresh: true の場合、キャッシュを無視して再分析
        
    Returns:
        分析結果のJSON
    """
    try:
        # レート制限チェック
        if not _check_rate_limit(request, company_code):
            return JsonResponse({
                'success': False,
                'error': '分析リクエストが多すぎます。しばらく時間をおいてから再試行してください。'
            }, status=429)
        
        # パラメータ取得
        force_refresh = request.GET.get('force_refresh', '').lower() == 'true'
        
        # 分析サービスの実行
        analysis_service = OnDemandAnalysisService()
        result = analysis_service.get_or_analyze_company(company_code, force_refresh)
        
        # レート制限カウンタを更新
        _update_rate_limit(request, company_code)
        
        if result['success']:
            return JsonResponse(result)
        else:
            status_code = 404 if '見つかりません' in result.get('error', '') else 500
            return JsonResponse(result, status=status_code)
        
    except Exception as e:
        logger.error(f"Error in analyze_company for {company_code}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'分析処理中にエラーが発生しました: {str(e)}'
        }, status=500)


@login_required
@require_GET
def search_companies(request):
    """
    企業検索API
    
    Query Parameters:
        query: 検索クエリ（企業名または証券コード）
        limit: 検索結果の上限（デフォルト: 20）
        
    Returns:
        検索結果のJSON
    """
    try:
        query = request.GET.get('query', '').strip()
        limit = int(request.GET.get('limit', 20))
        
        if len(query) < 2:
            return JsonResponse({
                'success': False,
                'error': '検索キーワードは2文字以上で入力してください',
                'results': []
            }, status=400)
        
        if limit > 100:  # 上限制限
            limit = 100
        
        # 検索実行
        analysis_service = OnDemandAnalysisService()
        result = analysis_service.search_companies(query, limit)
        
        return JsonResponse(result)
        
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': '無効なlimitパラメータです',
            'results': []
        }, status=400)
    except Exception as e:
        logger.error(f"Error in search_companies: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'検索処理中にエラーが発生しました: {str(e)}',
            'results': []
        }, status=500)


@login_required
@require_GET
def get_analysis_status(request, company_code):
    """
    企業の分析状況を取得
    
    Args:
        company_code: 証券コード
        
    Returns:
        分析状況のJSON
    """
    try:
        company = CompanyEarnings.objects.filter(company_code=company_code).first()
        
        if not company:
            return JsonResponse({
                'success': False,
                'error': '企業が見つかりません',
                'has_analysis': False
            }, status=404)
        
        # 最新分析の確認
        from .models import EarningsReport
        latest_report = EarningsReport.objects.filter(
            company=company,
            is_processed=True
        ).order_by('-submission_date').first()
        
        status_info = {
            'success': True,
            'company_code': company_code,
            'company_name': company.company_name,
            'has_analysis': latest_report is not None,
            'latest_analysis_date': company.latest_analysis_date.isoformat() if company.latest_analysis_date else None,
            'can_analyze': True  # オンデマンド分析なので常に可能
        }
        
        if latest_report:
            status_info.update({
                'latest_fiscal_year': latest_report.fiscal_year,
                'latest_quarter': latest_report.quarter,
                'report_submission_date': latest_report.submission_date.isoformat() if latest_report.submission_date else None
            })
        
        return JsonResponse(status_info)
        
    except Exception as e:
        logger.error(f"Error in get_analysis_status for {company_code}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def setup_earnings_alert(request):
    """
    決算アラートの設定
    
    Body:
        {
            "company_code": "7203",
            "alert_types": ["earnings_release", "analysis_complete"],
            "days_before_earnings": 7
        }
    """
    try:
        data = json.loads(request.body)
        company_code = data.get('company_code')
        alert_types = data.get('alert_types', [])
        days_before = data.get('days_before_earnings', 7)
        
        if not company_code:
            return JsonResponse({
                'success': False,
                'error': '企業コードが指定されていません'
            }, status=400)
        
        company = get_object_or_404(CompanyEarnings, company_code=company_code)
        
        # 既存アラートを削除
        EarningsAlert.objects.filter(
            user=request.user,
            company=company
        ).delete()
        
        # 新しいアラートを設定
        created_alerts = []
        for alert_type in alert_types:
            if alert_type in ['earnings_release', 'analysis_complete']:
                alert = EarningsAlert.objects.create(
                    user=request.user,
                    company=company,
                    alert_type=alert_type,
                    days_before_earnings=days_before,
                    is_enabled=True
                )
                created_alerts.append(alert.get_alert_type_display())
        
        return JsonResponse({
            'success': True,
            'message': f'{company.company_name}のアラートを設定しました',
            'alerts': created_alerts
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': '無効なJSONデータです'
        }, status=400)
    except Exception as e:
        logger.error(f"Error setting up earnings alert: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_GET
def get_user_alerts(request):
    """
    ユーザーのアラート設定一覧を取得
    
    Returns:
        アラート設定のJSON
    """
    try:
        alerts = EarningsAlert.objects.filter(
            user=request.user
        ).select_related('company').order_by('company__company_name')
        
        alert_data = []
        for alert in alerts:
            alert_data.append({
                'id': alert.id,
                'company': {
                    'code': alert.company.company_code,
                    'name': alert.company.company_name
                },
                'alert_type': alert.alert_type,
                'alert_type_display': alert.get_alert_type_display(),
                'days_before_earnings': alert.days_before_earnings,
                'is_enabled': alert.is_enabled,
                'created_at': alert.created_at.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'data': alert_data
        })
        
    except Exception as e:
        logger.error(f"Error getting user alerts: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_GET
def get_portfolio_analysis(request):
    """
    ユーザーのポートフォリオ銘柄の分析結果を一括取得
    stockdiaryアプリとの連携用
    
    Returns:
        ポートフォリオ分析結果のJSON
    """
    try:
        # stockdiaryから保有銘柄を取得
        from stockdiary.models import StockDiary
        
        # ユーザーの保有銘柄（売却していないもの）
        held_stocks = StockDiary.objects.filter(
            user=request.user,
            sell_date__isnull=True,
            stock_symbol__isnull=False
        ).exclude(stock_symbol='').values_list('stock_symbol', flat=True).distinct()
        
        portfolio_analysis = []
        analysis_service = OnDemandAnalysisService()
        
        for stock_symbol in held_stocks:
            try:
                # 4桁の場合は証券コードとして扱う
                if len(stock_symbol) == 4 and stock_symbol.isdigit():
                    # 分析状況のみ取得（実際の分析は実行しない）
                    company = CompanyEarnings.objects.filter(
                        company_code=stock_symbol
                    ).first()
                    
                    if company:
                        # 最新分析データの要約を取得
                        from .models import EarningsReport
                        latest_report = EarningsReport.objects.filter(
                            company=company,
                            is_processed=True
                        ).order_by('-submission_date').first()
                        
                        analysis_summary = {
                            'stock_symbol': stock_symbol,
                            'company_name': company.company_name,
                            'has_analysis': latest_report is not None,
                            'latest_analysis_date': company.latest_analysis_date.isoformat() if company.latest_analysis_date else None,
                            'cf_pattern': None,
                            'health_score': None,
                            'sentiment_score': None,
                            'confidence_level': None
                        }
                        
                        if latest_report:
                            if hasattr(latest_report, 'cashflow_analysis'):
                                cf = latest_report.cashflow_analysis
                                analysis_summary.update({
                                    'cf_pattern': cf.cf_pattern,
                                    'health_score': cf.health_score
                                })
                            
                            if hasattr(latest_report, 'sentiment_analysis'):
                                sentiment = latest_report.sentiment_analysis
                                analysis_summary.update({
                                    'sentiment_score': float(sentiment.sentiment_score),
                                    'confidence_level': sentiment.confidence_level
                                })
                        
                        portfolio_analysis.append(analysis_summary)
                
            except Exception as e:
                logger.warning(f"Error analyzing stock {stock_symbol}: {str(e)}")
                continue
        
        return JsonResponse({
            'success': True,
            'data': {
                'portfolio_analysis': portfolio_analysis,
                'total_stocks': len(held_stocks),
                'analyzed_stocks': len(portfolio_analysis)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting portfolio analysis: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_GET
def get_analysis_summary(request):
    """
    分析サマリー統計を取得
    
    Returns:
        分析統計のJSON
    """
    try:
        from django.db.models import Count, Avg
        from datetime import datetime, timedelta
        
        # 期間指定
        period = request.GET.get('period', '1m')
        
        if period == '1w':
            start_date = datetime.now().date() - timedelta(days=7)
        elif period == '1m':
            start_date = datetime.now().date() - timedelta(days=30)
        elif period == '3m':
            start_date = datetime.now().date() - timedelta(days=90)
        else:
            start_date = datetime.now().date() - timedelta(days=30)
        
        # 基本統計
        from .models import EarningsReport, CashFlowAnalysis, SentimentAnalysis
        
        total_companies = CompanyEarnings.objects.filter(is_active=True).count()
        analyzed_companies = CompanyEarnings.objects.filter(
            latest_analysis_date__gte=start_date
        ).count()
        
        recent_reports = EarningsReport.objects.filter(
            submission_date__gte=start_date,
            is_processed=True
        ).count()
        
        # CFパターン分布
        cf_patterns = CashFlowAnalysis.objects.filter(
            report__submission_date__gte=start_date
        ).values('cf_pattern').annotate(count=Count('cf_pattern'))
        
        # 健全性スコア分布
        health_scores = CashFlowAnalysis.objects.filter(
            report__submission_date__gte=start_date
        ).values('health_score').annotate(count=Count('health_score'))
        
        # 感情スコア平均
        avg_sentiment = SentimentAnalysis.objects.filter(
            report__submission_date__gte=start_date
        ).aggregate(avg_score=Avg('sentiment_score'))
        
        summary = {
            'period': period,
            'statistics': {
                'total_companies': total_companies,
                'analyzed_companies': analyzed_companies,
                'recent_reports': recent_reports,
                'analysis_coverage': round((analyzed_companies / max(total_companies, 1)) * 100, 1)
            },
            'cashflow_patterns': {item['cf_pattern']: item['count'] for item in cf_patterns},
            'health_scores': {item['health_score']: item['count'] for item in health_scores},
            'average_sentiment_score': round(avg_sentiment['avg_score'] or 0, 2)
        }
        
        return JsonResponse({
            'success': True,
            'data': summary
        })
        
    except Exception as e:
        logger.error(f"Error getting analysis summary: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def _check_rate_limit(request, company_code):
    """レート制限をチェック"""
    try:
        rate_limit_settings = getattr(settings, 'RATE_LIMIT', {}).get('analysis_requests', {})
        limit = rate_limit_settings.get('limit', 10)
        period = rate_limit_settings.get('period', 3600)
        
        # ユーザー別のレート制限キー
        cache_key = f"analysis_rate_limit_{request.user.id}_{company_code}"
        
        current_count = cache.get(cache_key, 0)
        
        return current_count < limit
        
    except Exception:
        return True  # エラー時は制限しない


def _update_rate_limit(request, company_code):
    """レート制限カウンタを更新"""
    try:
        rate_limit_settings = getattr(settings, 'RATE_LIMIT', {}).get('analysis_requests', {})
        period = rate_limit_settings.get('period', 3600)
        
        cache_key = f"analysis_rate_limit_{request.user.id}_{company_code}"
        
        current_count = cache.get(cache_key, 0)
        cache.set(cache_key, current_count + 1, period)
        
    except Exception:
        pass  # エラー時は何もしない


@method_decorator(csrf_exempt, name='dispatch')
class QuickAnalysisView(View):
    """クイック分析API（開発・テスト用）"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            company_code = data.get('company_code')
            
            if not company_code:
                return JsonResponse({
                    'success': False,
                    'error': '企業コードが指定されていません'
                }, status=400)
            
            # 認証チェック（開発環境では緩く）
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': '認証が必要です'
                }, status=401)
            
            # 分析実行
            analysis_service = OnDemandAnalysisService()
            result = analysis_service.get_or_analyze_company(company_code, force_refresh=True)
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': '無効なJSONデータです'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in quick analysis: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)