# earnings_analysis/views.py
"""
決算分析アプリのメインビュー
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from .models import CompanyEarnings, EarningsReport, CashFlowAnalysis, SentimentAnalysis
from .analysis_service import OnDemandAnalysisService

logger = logging.getLogger(__name__)


class EarningsMainView(LoginRequiredMixin, TemplateView):
    """決算分析メイン画面"""
    template_name = 'earnings_analysis/main.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 統計情報を取得
        stats = self._get_dashboard_stats()
        context['stats'] = stats
        
        # 最新の分析結果を取得
        recent_analyses = self._get_recent_analyses(limit=5)
        context['recent_analyses'] = recent_analyses
        
        return context
    
    def _get_dashboard_stats(self):
        """ダッシュボード用の統計情報を取得"""
        try:
            # 今月の開始日
            today = timezone.now().date()
            month_start = today.replace(day=1)
            
            # 基本統計
            total_companies = CompanyEarnings.objects.filter(is_active=True).count()
            analyzed_this_month = EarningsReport.objects.filter(
                is_processed=True,
                created_at__gte=month_start
            ).count()
            
            # stockdiaryアプリとの連携（保有銘柄数）
            portfolio_holdings = 0
            try:
                from stockdiary.models import StockDiary
                if hasattr(self.request, 'user') and self.request.user.is_authenticated:
                    portfolio_holdings = StockDiary.objects.filter(
                        user=self.request.user,
                        sell_date__isnull=True,
                        purchase_price__isnull=False,
                        purchase_quantity__isnull=False
                    ).count()
            except ImportError:
                pass
            
            # 平均感情スコア
            avg_sentiment = SentimentAnalysis.objects.filter(
                created_at__gte=month_start
            ).aggregate(
                avg_score=Avg('sentiment_score')
            )['avg_score'] or 0
            
            return {
                'total_companies': total_companies,
                'analyzed_this_month': analyzed_this_month,
                'portfolio_holdings': portfolio_holdings,
                'avg_sentiment': round(avg_sentiment, 1)
            }
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {str(e)}")
            return {
                'total_companies': 0,
                'analyzed_this_month': 0,
                'portfolio_holdings': 0,
                'avg_sentiment': 0
            }
    
    def _get_recent_analyses(self, limit=5):
        """最新の分析結果を取得"""
        try:
            recent_reports = EarningsReport.objects.filter(
                is_processed=True
            ).select_related(
                'company'
            ).prefetch_related(
                'cashflow_analysis',
                'sentiment_analysis'
            ).order_by('-created_at')[:limit]
            
            analyses = []
            for report in recent_reports:
                analysis = {
                    'company': report.company,
                    'report': report,
                    'analysis_date': report.created_at.date(),
                    'sentiment_analysis': getattr(report, 'sentiment_analysis', None),
                    'cashflow_analysis': getattr(report, 'cashflow_analysis', None)
                }
                analyses.append(analysis)
            
            return analyses
        except Exception as e:
            logger.error(f"Error getting recent analyses: {str(e)}")
            return []


@login_required
@require_GET
def search_companies_view(request):
    """企業検索のビュー（HTML返却）- 修正版"""
    try:
        query = request.GET.get('query', '').strip()
        
        if len(query) < 2:
            return render(request, 'earnings_analysis/partials/search_results.html', {
                'results': [],
                'query': query
            })
        
        results = []
        
        # 1. 既存の分析済み企業から検索
        from .models import CompanyEarnings, EarningsReport
        from django.db.models import Q
        
        existing_companies = CompanyEarnings.objects.filter(
            Q(company_name__icontains=query) | 
            Q(company_code__icontains=query)
        ).filter(is_active=True)
        
        for company in existing_companies:
            # 最新分析日を取得
            latest_report = EarningsReport.objects.filter(
                company=company,
                is_processed=True
            ).order_by('-submission_date').first()
            
            results.append({
                'company_code': company.company_code,
                'company_name': company.company_name,
                'industry': '既存分析企業',
                'market': '東証',
                'has_analysis': latest_report is not None,
                'latest_analysis_date': latest_report.submission_date if latest_report else None
            })
        
        # 2. 4桁の数字が入力された場合は、未登録でも候補として表示
        if query.isdigit() and len(query) == 4:
            found_codes = [r['company_code'] for r in results]
            if query not in found_codes:
                results.append({
                    'company_code': query,
                    'company_name': f'企業コード{query}（未登録）',
                    'industry': '不明',
                    'market': '不明',
                    'has_analysis': False,
                    'latest_analysis_date': None
                })
        
        # 3. company_masterからも検索（可能であれば）
        try:
            from company_master.models import CompanyMaster
            
            found_codes = [r['company_code'] for r in results]
            
            master_companies = CompanyMaster.objects.filter(
                Q(name__icontains=query) | 
                Q(code__icontains=query)
            ).exclude(code__in=found_codes)[:10]
            
            for company in master_companies:
                earnings_company = CompanyEarnings.objects.filter(
                    company_code=company.code
                ).first()
                
                results.append({
                    'company_code': company.code,
                    'company_name': company.name,
                    'industry': company.industry_name_33 or company.industry_name_17 or "不明",
                    'market': company.market or "東証",
                    'has_analysis': earnings_company is not None,
                    'latest_analysis_date': earnings_company.latest_analysis_date if earnings_company and earnings_company.latest_analysis_date else None
                })
                
        except ImportError:
            # company_masterが利用できない場合はスキップ
            pass
        
        context = {
            'results': results[:20],  # 最大20件
            'total_count': len(results),
            'query': query
        }
        
        return render(request, 'earnings_analysis/partials/search_results.html', context)
        
    except Exception as e:
        logger.error(f"Error in search_companies_view: {str(e)}")
        return render(request, 'earnings_analysis/partials/search_results.html', {
            'results': [],
            'query': query,
            'error': str(e)
        })

@login_required
@require_GET
def analysis_detail_view(request, company_code):
    """分析詳細のビュー（HTML返却）"""
    try:
        # 分析サービスを使用して詳細データを取得
        analysis_service = OnDemandAnalysisService()
        result = analysis_service.get_or_analyze_company(company_code, force_refresh=False)
        
        return render(request, 'earnings_analysis/partials/analysis_detail.html', result)
        
    except Exception as e:
        logger.error(f"Error in analysis_detail_view for {company_code}: {str(e)}")
        return render(request, 'earnings_analysis/partials/analysis_detail.html', {
            'success': False,
            'error': str(e),
            'company_code': company_code
        })


@login_required
@require_GET
def portfolio_analysis_view(request):
    """ポートフォリオ分析のビュー（HTML返却）"""
    try:
        # 分析サービスを使用してポートフォリオ分析を取得
        analysis_service = OnDemandAnalysisService()
        result = analysis_service.get_portfolio_analysis()
        
        if result['success']:
            # データを整理してテンプレートに渡す
            portfolio_data = result['data']
            
            # CFパターンと健全性スコアの分布を計算
            cf_patterns = {}
            health_scores = {}
            
            for stock in portfolio_data.get('portfolio_analysis', []):
                if stock.get('cf_pattern'):
                    cf_patterns[stock['cf_pattern']] = cf_patterns.get(stock['cf_pattern'], 0) + 1
                if stock.get('health_score'):
                    health_scores[stock['health_score']] = health_scores.get(stock['health_score'], 0) + 1
            
            portfolio_data['cf_patterns'] = cf_patterns
            portfolio_data['health_scores'] = health_scores
            
            context = {
                'success': True,
                'data': portfolio_data
            }
        else:
            context = {
                'success': False,
                'message': result.get('error', 'ポートフォリオ分析の取得に失敗しました')
            }
        
        return render(request, 'earnings_analysis/partials/portfolio_analysis.html', context)
        
    except Exception as e:
        logger.error(f"Error in portfolio_analysis_view: {str(e)}")
        return render(request, 'earnings_analysis/partials/portfolio_analysis.html', {
            'success': False,
            'message': str(e)
        })


@login_required
@require_GET
def company_status_view(request, company_code):
    """企業の分析状況を取得（JSON返却）"""
    try:
        analysis_service = OnDemandAnalysisService()
        result = analysis_service.get_analysis_status(company_code)
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Error in company_status_view for {company_code}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_GET
def refresh_analysis_view(request, company_code):
    """分析を強制的に再実行（JSON返却）"""
    try:
        analysis_service = OnDemandAnalysisService()
        result = analysis_service.get_or_analyze_company(company_code, force_refresh=True)
        
        if result['success']:
            # 再分析成功時は最新の分析結果リストをHTMLで返却
            recent_analyses = EarningsMainView()._get_recent_analyses(limit=5)
            html = render_to_string('earnings_analysis/partials/recent_analyses.html', {
                'recent_analyses': recent_analyses
            })
            return JsonResponse({
                'success': True,
                'html': html,
                'message': f"{result['company']['name']}の分析が完了しました"
            })
        else:
            return JsonResponse(result, status=400)
        
    except Exception as e:
        logger.error(f"Error in refresh_analysis_view for {company_code}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


class EarningsCompareView(LoginRequiredMixin, TemplateView):
    """企業比較分析画面（将来的に実装）"""
    template_name = 'earnings_analysis/compare.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 比較機能は今後実装
        context['message'] = '企業比較機能は近日公開予定です'
        return context


@login_required
@require_GET
def recent_analyses_partial(request):
    """最新分析結果のパーシャル取得"""
    try:
        main_view = EarningsMainView()
        recent_analyses = main_view._get_recent_analyses(limit=10)
        
        return render(request, 'earnings_analysis/partials/recent_analyses.html', {
            'recent_analyses': recent_analyses
        })
        
    except Exception as e:
        logger.error(f"Error in recent_analyses_partial: {str(e)}")
        return render(request, 'earnings_analysis/partials/recent_analyses.html', {
            'recent_analyses': [],
            'error': str(e)
        })


@login_required  
@require_GET
def industry_analysis_view(request):
    """業界分析ビュー（将来実装用）"""
    try:
        # 業界別の分析結果を集計
        industry_stats = {}
        
        # 業界別CF分析
        cf_analyses = CashFlowAnalysis.objects.select_related(
            'report__company'
        ).values(
            'report__company__company_name',
            'cf_pattern',
            'health_score'
        )
        
        # 業界別感情分析
        sentiment_analyses = SentimentAnalysis.objects.select_related(
            'report__company'
        ).values(
            'report__company__company_name',
            'sentiment_score',
            'confidence_level'
        )
        
        # 今後の機能として実装予定
        context = {
            'industry_stats': industry_stats,
            'message': '業界分析機能は開発中です'
        }
        
        return render(request, 'earnings_analysis/industry.html', context)
        
    except Exception as e:
        logger.error(f"Error in industry_analysis_view: {str(e)}")
        return render(request, 'earnings_analysis/industry.html', {
            'error': str(e)
        })


def get_company_analysis_summary(company_code):
    """企業の分析結果要約を取得（他のアプリから呼び出し用）"""
    """
    stockdiaryアプリなど他のアプリから呼び出すためのヘルパー関数
    """
    try:
        company = CompanyEarnings.objects.filter(
            company_code=company_code
        ).first()
        
        if not company:
            return None
        
        latest_report = EarningsReport.objects.filter(
            company=company,
            is_processed=True
        ).order_by('-submission_date').first()
        
        if not latest_report:
            return None
        
        summary = {
            'company_name': company.company_name,
            'company_code': company.company_code,
            'analysis_date': latest_report.created_at.date(),
            'fiscal_year': latest_report.fiscal_year,
            'quarter': latest_report.quarter,
            'has_cashflow': hasattr(latest_report, 'cashflow_analysis'),
            'has_sentiment': hasattr(latest_report, 'sentiment_analysis')
        }
        
        # キャッシュフロー分析結果
        if hasattr(latest_report, 'cashflow_analysis'):
            cf = latest_report.cashflow_analysis
            summary['cashflow'] = {
                'cf_pattern': cf.cf_pattern,
                'health_score': cf.health_score,
                'operating_cf': float(cf.operating_cf or 0),
                'free_cf': float(cf.free_cf or 0)
            }
        
        # 感情分析結果
        if hasattr(latest_report, 'sentiment_analysis'):
            sentiment = latest_report.sentiment_analysis
            summary['sentiment'] = {
                'sentiment_score': float(sentiment.sentiment_score),
                'confidence_level': sentiment.confidence_level,
                'risk_mentions': sentiment.risk_mentions
            }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting company analysis summary for {company_code}: {str(e)}")
        return None