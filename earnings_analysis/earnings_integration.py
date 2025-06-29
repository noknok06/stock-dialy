# stockdiary/earnings_integration.py
"""
stockdiaryアプリとearnings_analysisアプリの連携機能
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from datetime import datetime, timedelta
import logging

from .models import StockDiary

logger = logging.getLogger(__name__)


def get_earnings_analysis_for_diary(diary):
    """
    日記エントリーに対応する決算分析データを取得
    
    Args:
        diary: StockDiary インスタンス
        
    Returns:
        決算分析データの辞書またはNone
    """
    try:
        # earnings_analysisアプリがインストールされているかチェック
        from earnings_analysis.models import CompanyEarnings, EarningsReport
        
        # 銘柄コードが4桁の数字でない場合はスキップ
        if not diary.stock_symbol or len(diary.stock_symbol) != 4 or not diary.stock_symbol.isdigit():
            return None
        
        # 対応する企業を検索
        try:
            company = CompanyEarnings.objects.get(company_code=diary.stock_symbol)
        except CompanyEarnings.DoesNotExist:
            return None
        
        # 最新の分析済み報告書を取得
        latest_report = EarningsReport.objects.filter(
            company=company,
            is_processed=True
        ).order_by('-submission_date').first()
        
        if not latest_report:
            return {
                'has_analysis': False,
                'company_name': company.company_name,
                'message': '分析データはまだありません'
            }
        
        analysis_data = {
            'has_analysis': True,
            'company': {
                'name': company.company_name,
                'code': company.company_code,
                'fiscal_year_end_month': company.fiscal_year_end_month
            },
            'latest_report': {
                'fiscal_year': latest_report.fiscal_year,
                'quarter': latest_report.quarter,
                'submission_date': latest_report.submission_date,
                'report_type': latest_report.get_report_type_display()
            },
            'analysis_date': company.latest_analysis_date,
            'cashflow_analysis': None,
            'sentiment_analysis': None
        }
        
        # キャッシュフロー分析データ
        if hasattr(latest_report, 'cashflow_analysis'):
            cf = latest_report.cashflow_analysis
            analysis_data['cashflow_analysis'] = {
                'cf_pattern': cf.cf_pattern,
                'cf_pattern_display': cf.get_cf_pattern_display(),
                'cf_pattern_description': cf.get_cf_pattern_description(),
                'health_score': cf.health_score,
                'health_score_display': cf.get_health_score_display(),
                'operating_cf': float(cf.operating_cf) if cf.operating_cf else None,
                'free_cf': float(cf.free_cf) if cf.free_cf else None,
                'operating_cf_change_rate': float(cf.operating_cf_change_rate) if cf.operating_cf_change_rate else None,
                'analysis_summary': cf.analysis_summary,
                'risk_factors': cf.risk_factors
            }
        
        # 感情分析データ
        if hasattr(latest_report, 'sentiment_analysis'):
            sentiment = latest_report.sentiment_analysis
            analysis_data['sentiment_analysis'] = {
                'sentiment_score': float(sentiment.sentiment_score),
                'confidence_level': sentiment.confidence_level,
                'confidence_level_display': sentiment.get_confidence_level_display(),
                'positive_expressions': sentiment.positive_expressions,
                'negative_expressions': sentiment.negative_expressions,
                'risk_mentions': sentiment.risk_mentions,
                'sentiment_change': float(sentiment.sentiment_change) if sentiment.sentiment_change else None,
                'analysis_summary': sentiment.analysis_summary
            }
        
        return analysis_data
        
    except ImportError:
        # earnings_analysisアプリがインストールされていない場合
        return None
    except Exception as e:
        logger.error(f"Error getting earnings analysis for diary {diary.id}: {str(e)}")
        return None


def get_upcoming_earnings_for_user(user, days_ahead=30):
    """
    ユーザーの保有銘柄の今後の決算予定を取得
    
    Args:
        user: ユーザーインスタンス
        days_ahead: 何日先まで確認するか
        
    Returns:
        決算予定のリスト
    """
    try:
        from earnings_analysis.models import CompanyEarnings
        from earnings_analysis.services import EarningsNotificationService
        
        # ユーザーの保有銘柄を取得
        held_stocks = StockDiary.objects.filter(
            user=user,
            sell_date__isnull=True,
            stock_symbol__isnull=False
        ).exclude(stock_symbol='').values_list('stock_symbol', flat=True).distinct()
        
        upcoming_earnings = []
        notification_service = EarningsNotificationService()
        
        for stock_symbol in held_stocks:
            if len(stock_symbol) == 4 and stock_symbol.isdigit():
                try:
                    company = CompanyEarnings.objects.get(company_code=stock_symbol)
                    
                    # 決算予定日を推定
                    estimated_date = notification_service._estimate_earnings_date(company)
                    
                    if estimated_date:
                        days_until = (estimated_date - datetime.now().date()).days
                        
                        if 0 <= days_until <= days_ahead:
                            upcoming_earnings.append({
                                'stock_symbol': stock_symbol,
                                'company_name': company.company_name,
                                'estimated_date': estimated_date,
                                'days_until': days_until,
                                'fiscal_month': company.fiscal_year_end_month
                            })
                
                except CompanyEarnings.DoesNotExist:
                    continue
        
        # 日付順でソート
        upcoming_earnings.sort(key=lambda x: x['estimated_date'])
        
        return upcoming_earnings
        
    except ImportError:
        return []
    except Exception as e:
        logger.error(f"Error getting upcoming earnings for user {user.id}: {str(e)}")
        return []


@login_required
@require_GET
def get_diary_earnings_analysis(request, diary_id):
    """
    特定の日記エントリーの決算分析データを取得するAPI
    
    Args:
        diary_id: 日記ID
        
    Returns:
        決算分析データのJSON
    """
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        analysis_data = get_earnings_analysis_for_diary(diary)
        
        if analysis_data is None:
            return JsonResponse({
                'success': False,
                'message': '決算分析データが利用できません'
            })
        
        return JsonResponse({
            'success': True,
            'data': analysis_data
        })
        
    except Exception as e:
        logger.error(f"Error getting diary earnings analysis: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_GET
def get_portfolio_earnings_summary(request):
    """
    ポートフォリオ全体の決算分析サマリーを取得するAPI
    
    Returns:
        ポートフォリオサマリーのJSON
    """
    try:
        # ユーザーの保有銘柄を取得
        held_stocks = StockDiary.objects.filter(
            user=request.user,
            sell_date__isnull=True,
            stock_symbol__isnull=False,
            purchase_price__isnull=False,
            purchase_quantity__isnull=False
        ).exclude(stock_symbol='')
        
        portfolio_summary = {
            'total_stocks': held_stocks.count(),
            'analyzed_stocks': 0,
            'cf_patterns': {},
            'health_scores': {},
            'avg_sentiment_score': 0,
            'risk_factors': [],
            'upcoming_earnings': []
        }
        
        # 各銘柄の分析データを集計
        sentiment_scores = []
        
        for diary in held_stocks:
            analysis_data = get_earnings_analysis_for_diary(diary)
            
            if analysis_data and analysis_data.get('has_analysis'):
                portfolio_summary['analyzed_stocks'] += 1
                
                # CFパターンの集計
                if analysis_data.get('cashflow_analysis'):
                    cf_pattern = analysis_data['cashflow_analysis']['cf_pattern']
                    portfolio_summary['cf_patterns'][cf_pattern] = portfolio_summary['cf_patterns'].get(cf_pattern, 0) + 1
                    
                    health_score = analysis_data['cashflow_analysis']['health_score']
                    portfolio_summary['health_scores'][health_score] = portfolio_summary['health_scores'].get(health_score, 0) + 1
                
                # 感情スコアの集計
                if analysis_data.get('sentiment_analysis'):
                    sentiment_scores.append(analysis_data['sentiment_analysis']['sentiment_score'])
        
        # 平均感情スコア
        if sentiment_scores:
            portfolio_summary['avg_sentiment_score'] = round(sum(sentiment_scores) / len(sentiment_scores), 2)
        
        # 今後の決算予定
        portfolio_summary['upcoming_earnings'] = get_upcoming_earnings_for_user(request.user, days_ahead=30)
        
        return JsonResponse({
            'success': True,
            'data': portfolio_summary
        })
        
    except Exception as e:
        logger.error(f"Error getting portfolio earnings summary: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_GET
def render_earnings_widget(request, diary_id):
    """
    日記詳細ページ用の決算分析ウィジェットをレンダリング
    
    Args:
        diary_id: 日記ID
        
    Returns:
        HTMLレスポンス
    """
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        analysis_data = get_earnings_analysis_for_diary(diary)
        
        context = {
            'diary': diary,
            'analysis_data': analysis_data,
            'has_earnings_analysis': analysis_data is not None
        }
        
        html = render_to_string('stockdiary/partials/earnings_widget.html', context, request=request)
        
        return JsonResponse({
            'success': True,
            'html': html
        })
        
    except Exception as e:
        logger.error(f"Error rendering earnings widget: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


def format_cf_pattern_badge(cf_pattern):
    """CFパターン用のバッジクラスを取得"""
    badge_classes = {
        'ideal': 'bg-success',
        'growth': 'bg-primary',
        'danger': 'bg-danger',
        'recovery': 'bg-warning',
        'restructuring': 'bg-secondary',
        'unknown': 'bg-light text-dark'
    }
    return badge_classes.get(cf_pattern, 'bg-secondary')


def format_health_score_badge(health_score):
    """健全性スコア用のバッジクラスを取得"""
    badge_classes = {
        'excellent': 'bg-success',
        'good': 'bg-primary',
        'fair': 'bg-warning',
        'poor': 'bg-danger',
        'critical': 'bg-danger'
    }
    return badge_classes.get(health_score, 'bg-secondary')


def format_confidence_badge(confidence_level):
    """自信度用のバッジクラスを取得"""
    badge_classes = {
        'very_high': 'bg-success',
        'high': 'bg-primary',
        'moderate': 'bg-warning',
        'low': 'bg-danger',
        'very_low': 'bg-danger'
    }
    return badge_classes.get(confidence_level, 'bg-secondary')