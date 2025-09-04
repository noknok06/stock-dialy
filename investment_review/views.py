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
            },
            {
                'type': 'analytics',
                'url': reverse_lazy('stockdiary:analytics'),
                'icon': 'bi-graph-up',
                'label': '投資分析'
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
        
        # インサイトをタイプ別に整理
        insights_by_type = {}
        for insight in review.insights.all():
            insight_type = insight.get_insight_type_display()
            if insight_type not in insights_by_type:
                insights_by_type[insight_type] = []
            insights_by_type[insight_type].append(insight)
        
        context['insights_by_type'] = insights_by_type
        
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