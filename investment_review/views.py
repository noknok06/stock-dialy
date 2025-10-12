# investment_review/views.py
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q
from django.core.paginator import Paginator
import threading
import logging

from .models import InvestmentReview, ReviewInsight
from .services.gemini_analysis import GeminiInvestmentAnalyzer
from .models import InvestmentReview, ReviewInsight, PortfolioEvaluation, PortfolioEvaluationInsight
from .services.portfolio_analyzer import PortfolioAnalyzer
from stockdiary.models import StockDiary

logger = logging.getLogger(__name__)


class InvestmentReviewListView(LoginRequiredMixin, ListView):
    """投資振り返りレポート一覧"""
    model = InvestmentReview
    template_name = 'investment_review/review_list.html'
    context_object_name = 'reviews'
    paginate_by = 10
    
    def get_queryset(self):
        return InvestmentReview.objects.filter(user=self.request.user).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 統計情報
        reviews = self.get_queryset()
        context['stats'] = {
            'total_reviews': reviews.count(),
            'completed_reviews': reviews.filter(status='completed').count(),
            'pending_reviews': reviews.filter(status='pending').count(),
            'recent_review': reviews.filter(status='completed').first()
        }
        
        # スピードダイアル用のアクション
        context['page_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'add',
                'url': reverse_lazy('investment_review:create_monthly'),
                'icon': 'bi-plus-lg',
                'label': '月次振り返り作成'
            }
        ]
        
        return context


class InvestmentReviewDetailView(LoginRequiredMixin, DetailView):
    """投資振り返りレポート詳細"""
    model = InvestmentReview
    template_name = 'investment_review/review_detail.html'
    context_object_name = 'review'
    
    def get_queryset(self):
        return InvestmentReview.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        review = self.object
        
        # インサイトをタイプ別に整理（テンプレートフレンドリーなキー名に変換）
        insights_by_type = {}
        insight_type_mapping = {
            '強み・良い点': 'strengths',
            '弱み・改善点': 'weaknesses', 
            '中立的現状判断': 'neutral',
            '推奨アクション': 'recommendations',
            'リスク評価': 'risk_assessment',
            '機会・チャンス': 'opportunities'
        }
        
        for insight in review.insights.all():
            insight_type = insight.get_insight_type_display()
            # 英語キーに変換
            english_key = insight_type_mapping.get(insight_type, insight_type.replace('・', '_').replace(' ', '_'))
            
            if english_key not in insights_by_type:
                insights_by_type[english_key] = []
            insights_by_type[english_key].append(insight)
        
        # 日本語表示名もコンテキストに追加
        insight_display_names = {
            'strengths': '強み・良い点',
            'weaknesses': '弱み・改善点',
            'neutral': '中立的現状判断', 
            'recommendations': '推奨アクション',
            'risk_assessment': 'リスク評価',
            'opportunities': '機会・チャンス'
        }
        
        context['insights_by_type'] = insights_by_type
        context['insight_display_names'] = insight_display_names
        
        # 分析データの詳細表示用処理
        analysis_data = review.analysis_data
        if analysis_data:
            context['analysis_summary'] = self._prepare_analysis_summary(analysis_data)
        
        # スピードダイアル用のアクション
        context['page_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('investment_review:list'),
                'icon': 'bi-arrow-left',
                'label': '一覧に戻る'
            },
            {
                'type': 'refresh',
                'url': reverse_lazy('investment_review:regenerate', kwargs={'pk': review.pk}),
                'icon': 'bi-arrow-clockwise',
                'label': '再分析',
                'condition': review.status == 'completed'
            },
            {
                'type': 'delete',
                'url': reverse_lazy('investment_review:delete', kwargs={'pk': review.pk}),
                'icon': 'bi-trash',
                'label': '削除'
            }
        ]
        
        return context

    
    def _prepare_analysis_summary(self, analysis_data):
        """分析データのサマリーを準備"""
        summary = {}
        
        # 基本統計のハイライト
        if 'basic_stats' in analysis_data:
            stats = analysis_data['basic_stats']
            summary['basic_highlights'] = [
                f"総記録数: {stats.get('total_entries', 0)}件",
                f"分析記録率: {stats.get('analysis_rate', 0)}%",
                f"保有中: {stats.get('active_holdings', 0)}銘柄"
            ]
        
        # 損益ハイライト  
        if 'profit_loss' in analysis_data:
            pl = analysis_data['profit_loss']
            summary['profit_highlights'] = [
                f"総損益: {pl.get('total_profit_loss', 0):,.0f}円",
                f"勝率: {pl.get('win_rate', 0)}%",
                f"ROI: {pl.get('roi', 0)}%"
            ]
        
        # 行動パターンハイライト
        if 'pattern_analysis' in analysis_data:
            pattern = analysis_data['pattern_analysis']
            summary['pattern_highlights'] = [
                f"平均保有期間: {pattern.get('avg_holding_period', 0)}日",
                f"詳細分析率: {pattern.get('analysis_depth_rate', 0)}%"
            ]
        
        return summary


class CreateMonthlyReviewView(LoginRequiredMixin, TemplateView):
    """月次振り返りレポート作成"""
    template_name = 'investment_review/create_monthly.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 最近3ヶ月のオプションを提供
        now = timezone.now().date()
        month_options = []
        
        for i in range(3):
            if now.month - i <= 0:
                target_year = now.year - 1
                target_month = now.month - i + 12
            else:
                target_year = now.year
                target_month = now.month - i
            
            # その月にデータがあるかチェック
            start_date = datetime(target_year, target_month, 1).date()
            if target_month == 12:
                end_date = datetime(target_year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(target_year, target_month + 1, 1).date() - timedelta(days=1)
            
            diary_count = StockDiary.objects.filter(
                user=self.request.user,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            ).count()
            
            month_options.append({
                'year': target_year,
                'month': target_month,
                'display': f"{target_year}年{target_month}月",
                'diary_count': diary_count,
                'has_data': diary_count > 0
            })
        
        context['month_options'] = month_options
        
        # 既存のレビュー確認
        existing_reviews = InvestmentReview.objects.filter(
            user=self.request.user,
            review_type='monthly'
        ).order_by('-created_at')[:5]
        
        context['existing_reviews'] = existing_reviews
        
        # スピードダイアル用のアクション
        context['page_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('investment_review:list'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        
        return context
    
    def post(self, request, *args, **kwargs):
        """月次レビューの作成処理"""
        try:
            year = int(request.POST.get('year'))
            month = int(request.POST.get('month'))
            
            # 月次レビューを作成
            review = InvestmentReview.create_monthly_review(request.user, year, month)
            
            if review.status == 'completed':
                messages.info(request, f"{year}年{month}月のレビューは既に存在します。")
                return redirect('investment_review:detail', pk=review.pk)
            
            # バックグラウンドで分析を実行
            self._start_analysis_background(review)
            
            messages.success(request, f"{year}年{month}月の振り返りレポートの分析を開始しました。")
            return redirect('investment_review:detail', pk=review.pk)
            
        except (ValueError, TypeError) as e:
            messages.error(request, "無効な年月が指定されました。")
            return self.get(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"月次レビュー作成エラー: {e}")
            messages.error(request, "レビューの作成中にエラーが発生しました。")
            return self.get(request, *args, **kwargs)
    
    def _start_analysis_background(self, review):
        """バックグラウンドで分析を開始"""
        def run_analysis():
            try:
                review.status = 'processing'
                review.save(update_fields=['status'])
                
                # 分析実行
                analyzer = GeminiInvestmentAnalyzer()
                result = analyzer.analyze_investment_records(
                    review.user, 
                    review.start_date, 
                    review.end_date
                )
                
                # 結果を保存
                review.analysis_data = result.get('analysis_data', {})
                review.professional_insights = result.get('professional_insights', '')
                
                # 統計情報を更新
                analysis_data = result.get('analysis_data', {})
                if 'basic_stats' in analysis_data:
                    stats = analysis_data['basic_stats']
                    review.total_entries = stats.get('total_entries', 0)
                    review.active_holdings = stats.get('active_holdings', 0)  
                    review.completed_trades = stats.get('completed_trades', 0)
                    review.memo_entries = stats.get('memo_entries', 0)
                
                # インサイトを保存
                self._save_insights(review, result)
                
                review.status = 'completed'
                review.analysis_completed_at = timezone.now()
                review.save()
                
            except Exception as e:
                logger.error(f"バックグラウンド分析エラー: {e}")
                review.status = 'failed'
                review.save(update_fields=['status'])
        
        # バックグラウンドスレッドで実行
        thread = threading.Thread(target=run_analysis)
        thread.daemon = True
        thread.start()
    
    def _save_insights(self, review, analysis_result):
        """インサイトをデータベースに保存"""
        try:
            # 既存のインサイトを削除
            review.insights.all().delete()
            
            # 強みを保存
            for i, strength in enumerate(analysis_result.get('strengths', [])[:5]):
                ReviewInsight.objects.create(
                    review=review,
                    insight_type='strength',
                    title=f"強み {i+1}",
                    content=strength,
                    priority=5-i
                )
            
            # 改善点を保存  
            for i, improvement in enumerate(analysis_result.get('improvement_areas', [])[:5]):
                ReviewInsight.objects.create(
                    review=review,
                    insight_type='weakness',
                    title=f"改善点 {i+1}",
                    content=improvement,
                    priority=5-i
                )
            
            # アクション項目を保存
            for i, action in enumerate(analysis_result.get('action_items', [])[:5]):
                ReviewInsight.objects.create(
                    review=review,
                    insight_type='recommendation',
                    title=f"推奨アクション {i+1}",
                    content=action,
                    priority=5-i
                )
                
        except Exception as e:
            logger.error(f"インサイト保存エラー: {e}")


class RegenerateReviewView(LoginRequiredMixin, TemplateView):
    """レビューの再分析"""
    
    def post(self, request, pk):
        review = get_object_or_404(InvestmentReview, pk=pk, user=request.user)
        
        if review.status == 'processing':
            messages.warning(request, "このレビューは現在分析中です。")
            return redirect('investment_review:detail', pk=pk)
        
        # 再分析を開始
        create_view = CreateMonthlyReviewView()
        create_view._start_analysis_background(review)
        
        messages.success(request, "レビューの再分析を開始しました。")
        return redirect('investment_review:detail', pk=pk)


class ReviewAnalysisStatusView(LoginRequiredMixin, TemplateView):
    """分析状況をAJAXで確認"""
    
    def get(self, request, pk):
        try:
            review = InvestmentReview.objects.get(pk=pk, user=request.user)
            
            return JsonResponse({
                'status': review.status,
                'progress': 100 if review.status == 'completed' else 
                          50 if review.status == 'processing' else 0,
                'message': {
                    'pending': '分析待ち',
                    'processing': '分析中...',
                    'completed': '分析完了',
                    'failed': '分析に失敗しました'
                }.get(review.status, '不明な状態'),
                'completed_at': review.analysis_completed_at.isoformat() if review.analysis_completed_at else None
            })
            
        except InvestmentReview.DoesNotExist:
            return JsonResponse({'error': 'レビューが見つかりません'}, status=404)
        except Exception as e:
            logger.error(f"ステータス確認エラー: {e}")
            return JsonResponse({'error': '状態確認に失敗しました'}, status=500)


class DeleteReviewView(LoginRequiredMixin, TemplateView):
    """レビューの削除"""
    
    def post(self, request, pk):
        review = get_object_or_404(InvestmentReview, pk=pk, user=request.user)
        
        review_title = review.title
        review.delete()
        
        messages.success(request, f"「{review_title}」を削除しました。")
        return redirect('investment_review:list')


class InvestmentReviewDashboardView(LoginRequiredMixin, TemplateView):
    """投資振り返りダッシュボード"""
    template_name = 'investment_review/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # 最新のレビュー
        latest_reviews = InvestmentReview.objects.filter(
            user=user, 
            status='completed'
        ).order_by('-analysis_completed_at')[:5]
        
        # 統計サマリー
        total_reviews = InvestmentReview.objects.filter(user=user).count()
        completed_reviews = InvestmentReview.objects.filter(user=user, status='completed').count()
        
        # 直近30日のデータ概要
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        recent_diaries = StockDiary.objects.filter(
            user=user,
            created_at__date__gte=thirty_days_ago
        )
        
        context.update({
            'latest_reviews': latest_reviews,
            'total_reviews': total_reviews,
            'completed_reviews': completed_reviews,
            'recent_diaries_count': recent_diaries.count(),
            'can_create_monthly': recent_diaries.count() > 0,
            'page_actions': [
                {
                    'type': 'back',
                    'url': reverse_lazy('stockdiary:home'),
                    'icon': 'bi-arrow-left',
                    'label': '戻る'
                },
                {
                    'type': 'add',
                    'url': reverse_lazy('investment_review:create_monthly'),
                    'icon': 'bi-plus-lg',
                    'label': '新しい振り返り'
                },
                {
                    'type': 'list',
                    'url': reverse_lazy('investment_review:list'),
                    'icon': 'bi-list',
                    'label': '全レビュー'
                }
            ]
        })
        
        return context
    

class PortfolioEvaluationView(LoginRequiredMixin, TemplateView):
    """現在保有株式のポートフォリオ評価"""
    template_name = 'investment_review/portfolio_evaluation.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 現在保有している株式の数を確認
        current_holdings_count = StockDiary.objects.filter(
            user=self.request.user,
            sell_date__isnull=True,
            purchase_price__isnull=False,
            purchase_quantity__isnull=False,
            is_memo=False
        ).count()
        
        # 過去の評価履歴
        recent_evaluations = PortfolioEvaluation.objects.filter(
            user=self.request.user,
            status='completed'
        ).order_by('-evaluation_date')[:5]
        
        context.update({
            'current_holdings_count': current_holdings_count,
            'has_holdings': current_holdings_count > 0,
            'recent_evaluations': recent_evaluations,
            'page_title': 'ポートフォリオ評価',
            'page_subtitle': '現在保有している株式の包括的な分析と評価',
            'page_actions': [
                {
                    'type': 'back',
                    'url': reverse_lazy('investment_review:list'),
                    'icon': 'bi-arrow-left',
                    'label': '振り返り一覧に戻る'
                },
                {
                    'type': 'history',
                    'url': reverse_lazy('investment_review:portfolio_history'),
                    'icon': 'bi-clock-history',
                    'label': '評価履歴'
                },
                {
                    'type': 'stocks',
                    'url': reverse_lazy('stockdiary:stock_list'),
                    'icon': 'bi-building',
                    'label': '銘柄一覧'
                }
            ]
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        """ポートフォリオ評価の実行"""
        try:
            # 新しい評価レコードを作成
            evaluation = PortfolioEvaluation.objects.create(
                user=request.user,
                status='pending'
            )
            
            # バックグラウンドで評価を実行
            self._start_portfolio_evaluation_background(evaluation)
            
            messages.success(request, "ポートフォリオの評価分析を開始しました。しばらくお待ちください。")
            return JsonResponse({
                'status': 'started',
                'message': '評価分析を開始しました',
                'evaluation_id': evaluation.id,
                'redirect_url': str(reverse_lazy('investment_review:portfolio_evaluation_detail', 
                                                kwargs={'pk': evaluation.id}))
            })
            
        except Exception as e:
            logger.error(f"ポートフォリオ評価開始エラー: {e}")
            return JsonResponse({
                'status': 'error',
                'message': f'評価の開始中にエラーが発生しました: {str(e)}'
            }, status=500)
    
    def _start_portfolio_evaluation_background(self, evaluation: PortfolioEvaluation):
        """バックグラウンドでポートフォリオ評価を実行"""
        def run_evaluation():
            try:
                # ステータスを更新
                evaluation.status = 'processing'
                evaluation.save(update_fields=['status'])
                
                # 分析実行
                analyzer = GeminiInvestmentAnalyzer()
                result = analyzer.analyze_current_portfolio(evaluation.user)
                
                # 結果をモデルに保存
                self._save_evaluation_result(evaluation, result)
                
            except Exception as e:
                logger.error(f"バックグラウンドポートフォリオ評価エラー: {e}")
                evaluation.status = 'failed'
                evaluation.save(update_fields=['status'])
        
        # バックグラウンドスレッドで実行
        thread = threading.Thread(target=run_evaluation)
        thread.daemon = True
        thread.start()
    
    def _save_evaluation_result(self, evaluation: PortfolioEvaluation, result: dict):
        """評価結果をデータベースに保存"""
        try:
            # 基本データの保存
            portfolio_data = result.get('portfolio_data', {})
            market_context = result.get('market_context', {})
            
            evaluation.portfolio_data = portfolio_data
            evaluation.market_context = market_context
            evaluation.professional_evaluation = result.get('professional_evaluation', '')
            evaluation.api_used = result.get('api_used', False)
            
            # 統計データの保存
            if portfolio_data.get('status') == 'success':
                evaluation.total_holdings = portfolio_data.get('total_holdings', 0)
                evaluation.total_portfolio_value = portfolio_data.get('total_portfolio_value')
                
                performance_analysis = portfolio_data.get('performance_analysis', {})
                evaluation.total_investment = performance_analysis.get('total_investment')
                evaluation.total_return_pct = performance_analysis.get('total_return_pct')
            
            evaluation.status = 'completed'
            evaluation.completed_at = timezone.now()
            evaluation.save()
            
            # インサイトの保存
            self._save_evaluation_insights(evaluation, result)
            
        except Exception as e:
            logger.error(f"評価結果保存エラー: {e}")
            evaluation.status = 'failed'
            evaluation.save(update_fields=['status'])
    
    def _save_evaluation_insights(self, evaluation: PortfolioEvaluation, result: dict):
        """評価インサイトを保存"""
        try:
            # 既存のインサイトを削除
            evaluation.insights.all().delete()
            
            # 強みを保存
            for i, strength in enumerate(result.get('strengths', [])[:5]):
                PortfolioEvaluationInsight.objects.create(
                    evaluation=evaluation,
                    insight_type='strength',
                    title=f"強み {i+1}",
                    content=strength,
                    priority=5-i
                )
            
            # 弱み・リスクを保存
            for i, weakness in enumerate(result.get('weaknesses', [])[:5]):
                PortfolioEvaluationInsight.objects.create(
                    evaluation=evaluation,
                    insight_type='weakness',
                    title=f"弱み・リスク {i+1}",
                    content=weakness,
                    priority=5-i
                )
            
            # 中立的評価を保存
            for i, neutral in enumerate(result.get('neutral_assessment', [])[:3]):
                PortfolioEvaluationInsight.objects.create(
                    evaluation=evaluation,
                    insight_type='neutral',
                    title=f"現状判断 {i+1}",
                    content=neutral,
                    priority=3-i
                )
            
            # 改善提案を保存
            for i, recommendation in enumerate(result.get('actionable_recommendations', [])[:5]):
                PortfolioEvaluationInsight.objects.create(
                    evaluation=evaluation,
                    insight_type='recommendation',
                    title=f"改善提案 {i+1}",
                    content=recommendation,
                    priority=5-i
                )
            
            # リスク評価を保存
            if result.get('risk_assessment'):
                PortfolioEvaluationInsight.objects.create(
                    evaluation=evaluation,
                    insight_type='risk_assessment',
                    title="リスク評価",
                    content=result.get('risk_assessment'),
                    priority=5
                )
            
            # 市場ポジショニングを保存
            if result.get('market_positioning'):
                PortfolioEvaluationInsight.objects.create(
                    evaluation=evaluation,
                    insight_type='market_positioning',
                    title="市場ポジショニング",
                    content=result.get('market_positioning'),
                    priority=5
                )
                
        except Exception as e:
            logger.error(f"インサイト保存エラー: {e}")


class PortfolioEvaluationDetailView(LoginRequiredMixin, DetailView):
    """ポートフォリオ評価詳細"""
    model = PortfolioEvaluation
    template_name = 'investment_review/portfolio_evaluation_detail.html'
    context_object_name = 'evaluation'
    
    def get_queryset(self):
        return PortfolioEvaluation.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        evaluation = self.object
        
        # インサイトをタイプ別に整理（テンプレートフレンドリーなキー名に変換）
        insights_by_type = {}
        insight_type_mapping = {
            '強み・ポジティブ要素': 'strengths',
            '弱み・リスク要素': 'weaknesses', 
            '中立的現状判断': 'neutral',
            '改善提案': 'recommendations',
            'リスク評価': 'risk_assessment',
            '市場ポジショニング': 'market_positioning'
        }
        
        for insight in evaluation.insights.all():
            insight_type = insight.get_insight_type_display()
            # 英語キーに変換、フォールバックとして元のキーも保持
            english_key = insight_type_mapping.get(insight_type, insight_type.replace('・', '_').replace(' ', '_'))
            
            if english_key not in insights_by_type:
                insights_by_type[english_key] = []
            insights_by_type[english_key].append(insight)
        
        # 日本語表示名もコンテキストに追加
        insight_display_names = {
            'strengths': '強み・ポジティブ要素',
            'weaknesses': '弱み・リスク要素',
            'neutral': '中立的現状判断', 
            'recommendations': '改善提案',
            'risk_assessment': 'リスク評価',
            'market_positioning': '市場ポジショニング'
        }
        
        context.update({
            'insights_by_type': insights_by_type,
            'insight_display_names': insight_display_names,
            'page_title': f'ポートフォリオ評価詳細',
            'page_subtitle': f'{evaluation.get_evaluation_period_display()} の評価結果',
            'page_actions': [
                {
                    'type': 'back',
                    'url': reverse_lazy('investment_review:portfolio_evaluation'),
                    'icon': 'bi-arrow-left',
                    'label': '評価画面に戻る'
                },
                {
                    'type': 'list',
                    'url': reverse_lazy('investment_review:portfolio_history'),
                    'icon': 'bi-list',
                    'label': '評価履歴'
                },
                {
                    'type': 'refresh',
                    'url': '',
                    'icon': 'bi-arrow-clockwise',
                    'label': '再読み込み',
                    'onclick': 'location.reload()'
                },
                {
                    'type': 'delete',
                    'url': reverse_lazy('investment_review:portfolio_evaluation_delete', 
                                      kwargs={'pk': evaluation.pk}),
                    'icon': 'bi-trash',
                    'label': '削除'
                }
            ]
        })
        
        return context


class PortfolioEvaluationHistoryView(LoginRequiredMixin, ListView):
    """ポートフォリオ評価履歴"""
    model = PortfolioEvaluation
    template_name = 'investment_review/portfolio_evaluation_history.html'
    context_object_name = 'evaluations'
    paginate_by = 20
    
    def get_queryset(self):
        return PortfolioEvaluation.objects.filter(
            user=self.request.user
        ).order_by('-evaluation_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 統計情報
        evaluations = self.get_queryset()
        completed_evaluations = evaluations.filter(status='completed')
        
        context.update({
            'page_title': 'ポートフォリオ評価履歴',
            'page_subtitle': '過去のポートフォリオ評価結果',
            'stats': {
                'total_evaluations': evaluations.count(),
                'completed_evaluations': completed_evaluations.count(),
                'latest_evaluation': completed_evaluations.first()
            },
            'page_actions': [
                {
                    'type': 'back',
                    'url': reverse_lazy('investment_review:portfolio_evaluation'),
                    'icon': 'bi-arrow-left',
                    'label': '評価画面に戻る'
                },
                {
                    'type': 'add',
                    'url': reverse_lazy('investment_review:portfolio_evaluation'),
                    'icon': 'bi-plus-lg',
                    'label': '新しい評価'
                }
            ]
        })
        
        return context


class PortfolioEvaluationDeleteView(LoginRequiredMixin, TemplateView):
    """ポートフォリオ評価削除"""
    
    def post(self, request, pk):
        evaluation = get_object_or_404(PortfolioEvaluation, pk=pk, user=request.user)
        
        evaluation_title = f"{evaluation.title} ({evaluation.get_evaluation_period_display()})"
        evaluation.delete()
        
        messages.success(request, f"「{evaluation_title}」を削除しました。")
        return redirect('investment_review:portfolio_history')


class PortfolioEvaluationStatusAPIView(LoginRequiredMixin, DetailView):
    """ポートフォリオ評価状況をAJAXで確認"""
    model = PortfolioEvaluation
    
    def get_queryset(self):
        return PortfolioEvaluation.objects.filter(user=self.request.user)
    
    def get(self, request, pk):
        try:
            evaluation = self.get_object()
            
            return JsonResponse({
                'status': evaluation.status,
                'progress': {
                    'pending': 0,
                    'processing': 50,
                    'completed': 100,
                    'failed': 0
                }.get(evaluation.status, 0),
                'message': {
                    'pending': '分析待ち',
                    'processing': '分析中...',
                    'completed': '分析完了',
                    'failed': '分析に失敗しました'
                }.get(evaluation.status, '不明な状態'),
                'completed': evaluation.status == 'completed',
                'completed_at': evaluation.completed_at.isoformat() if evaluation.completed_at else None,
                'result_summary': {
                    'total_holdings': evaluation.total_holdings,
                    'total_return_pct': float(evaluation.total_return_pct) if evaluation.total_return_pct else None,
                    'api_used': evaluation.api_used
                } if evaluation.status == 'completed' else None
            })
            
        except PortfolioEvaluation.DoesNotExist:
            return JsonResponse({'error': '評価が見つかりません'}, status=404)
        except Exception as e:
            logger.error(f"評価ステータス確認エラー: {e}")
            return JsonResponse({'error': '状態確認に失敗しました'}, status=500)


class PortfolioComparisonView(LoginRequiredMixin, TemplateView):
    """ポートフォリオの時系列比較"""
    template_name = 'investment_review/portfolio_comparison.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 過去のポートフォリオ評価履歴があれば取得
        # （将来的な拡張のための準備）
        context.update({
            'page_title': 'ポートフォリオ比較',
            'page_subtitle': '時系列でのポートフォリオ変化の分析',
            'feature_status': 'coming_soon',
            'page_actions': [
                {
                    'type': 'back',
                    'url': reverse_lazy('investment_review:portfolio_evaluation'),
                    'icon': 'bi-arrow-left',
                    'label': '評価画面に戻る'
                }
            ]
        })
        
        return context
    
    
class PortfolioEvaluationStatusView(LoginRequiredMixin, TemplateView):
    """ポートフォリオ評価の進行状況と結果表示"""
    template_name = 'investment_review/portfolio_evaluation_result.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        from django.core.cache import cache
        cache_key = f"portfolio_evaluation_{self.request.user.id}"
        
        # 評価結果を取得
        evaluation_result = cache.get(cache_key)
        status_info = cache.get(f"{cache_key}_status")
        
        if evaluation_result:
            context.update({
                'evaluation_completed': True,
                'evaluation_result': evaluation_result,
                'status_info': status_info or {'status': 'completed', 'progress': 100},
                'page_title': 'ポートフォリオ評価結果',
                'page_subtitle': 'AI による投資家目線での包括的な評価'
            })
        else:
            context.update({
                'evaluation_completed': False,
                'status_info': status_info or {'status': 'pending', 'progress': 0},
                'page_title': 'ポートフォリオ評価中',
                'page_subtitle': '分析実行中です...'
            })
        
        # スピードダイアル用のアクション
        context['page_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('investment_review:portfolio_evaluation'),
                'icon': 'bi-arrow-left',
                'label': '評価画面に戻る'
            },
            {
                'type': 'refresh',
                'url': '',
                'icon': 'bi-arrow-clockwise',
                'label': '再読み込み',
                'onclick': 'location.reload()'
            },
            {
                'type': 'home',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-house',
                'label': 'ホーム'
            }
        ]
        
        return context

