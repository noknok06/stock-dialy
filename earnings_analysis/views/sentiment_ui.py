# earnings_analysis/views/sentiment_ui.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.generic import TemplateView
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import logging
from django.db import models

from ..models import DocumentMetadata, SentimentAnalysisSession, SentimentAnalysisHistory
from ..services.sentiment_analyzer import SentimentAnalysisService

logger = logging.getLogger(__name__)

class SentimentAnalysisView(TemplateView):
    """感情分析専用ページ"""
    template_name = 'earnings_analysis/sentiment/analysis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc_id = kwargs.get('doc_id')
        
        # 書類情報取得
        document = get_object_or_404(
            DocumentMetadata,
            doc_id=doc_id,
            legal_status='1'
        )
        
        # 最新の分析結果確認
        latest_session = SentimentAnalysisSession.objects.filter(
            document=document,
            processing_status='COMPLETED'
        ).order_by('-created_at').first()
        
        # 過去の分析履歴
        analysis_history = SentimentAnalysisHistory.objects.filter(
            document=document
        ).order_by('-analysis_date')[:5]
        
        context.update({
            'document': document,
            'latest_session': latest_session,
            'analysis_history': analysis_history,
            'has_recent_analysis': latest_session and latest_session.created_at >= timezone.now() - timedelta(hours=1),
        })
        
        return context


class SentimentResultView(TemplateView):
    """感情分析結果表示ページ"""
    template_name = 'earnings_analysis/sentiment/result.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session_id = kwargs.get('session_id')
        
        # セッション情報取得
        session = get_object_or_404(
            SentimentAnalysisSession,
            session_id=session_id
        )
        
        if session.is_expired:
            messages.error(self.request, 'セッションが期限切れです。')
            return redirect('earnings_analysis:document-detail-ui', doc_id=session.document.doc_id)
        
        # 関連書類の感情分析履歴
        related_analyses = SentimentAnalysisHistory.objects.filter(
            document__edinet_code=session.document.edinet_code
        ).exclude(
            document=session.document
        ).order_by('-analysis_date')[:5]
        
        context.update({
            'session': session,
            'document': session.document,
            'related_analyses': related_analyses,
            'export_url_base': reverse('earnings_analysis:sentiment-export'),
        })
        
        return context


class SentimentStatsView(TemplateView):
    """感情分析統計ページ"""
    template_name = 'earnings_analysis/sentiment/stats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # 基本統計
            total_analyses = SentimentAnalysisHistory.objects.count()
            recent_analyses = SentimentAnalysisHistory.objects.filter(
                analysis_date__gte=timezone.now() - timedelta(days=30)
            ).count()
            
            # 感情分布統計
            sentiment_stats = {}
            for choice_key, choice_label in SentimentAnalysisHistory.SENTIMENT_CHOICES:
                count = SentimentAnalysisHistory.objects.filter(
                    sentiment_label=choice_key
                ).count()
                sentiment_stats[choice_label] = {
                    'count': count,
                    'percentage': round((count / total_analyses * 100) if total_analyses > 0 else 0, 1)
                }
            
            # 月別統計
            monthly_stats = []
            for i in range(6):  # 過去6ヶ月
                month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
                try:
                    if month_start.month == 12:
                        month_end = month_start.replace(year=month_start.year+1, month=1)
                    else:
                        month_end = month_start.replace(month=month_start.month+1)
                except:
                    month_end = timezone.now()
                
                count = SentimentAnalysisHistory.objects.filter(
                    analysis_date__gte=month_start,
                    analysis_date__lt=month_end
                ).count()
                
                monthly_stats.append({
                    'month': month_start.strftime('%Y年%m月'),
                    'count': count
                })
            
            # アクティブセッション
            active_sessions = SentimentAnalysisSession.objects.filter(
                processing_status__in=['PENDING', 'PROCESSING'],
                expires_at__gt=timezone.now()
            ).count()
            
            # 人気企業TOP10
            top_companies = SentimentAnalysisHistory.objects.values(
                'document__company_name', 'document__edinet_code'
            ).annotate(
                analysis_count=models.Count('id')
            ).order_by('-analysis_count')[:10]
            
            context.update({
                'total_analyses': total_analyses,
                'recent_analyses': recent_analyses,
                'sentiment_stats': sentiment_stats,
                'monthly_stats': list(reversed(monthly_stats)),
                'active_sessions': active_sessions,
                'top_companies': top_companies,
            })
            
        except Exception as e:
            logger.error(f"感情分析統計取得エラー: {e}")
            context.update({
                'total_analyses': 0,
                'recent_analyses': 0,
                'sentiment_stats': {},
                'monthly_stats': [],
                'active_sessions': 0,
                'top_companies': [],
                'error_message': '統計情報の取得中にエラーが発生しました。'
            })
        
        return context


class SentimentManagementView(TemplateView):
    """感情分析管理ページ"""
    template_name = 'earnings_analysis/sentiment/management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # セッション一覧
        sessions = SentimentAnalysisSession.objects.select_related('document').order_by('-created_at')[:20]
        
        # システム統計
        system_stats = {
            'total_sessions': SentimentAnalysisSession.objects.count(),
            'completed_sessions': SentimentAnalysisSession.objects.filter(processing_status='COMPLETED').count(),
            'failed_sessions': SentimentAnalysisSession.objects.filter(processing_status='FAILED').count(),
            'expired_sessions': SentimentAnalysisSession.objects.filter(expires_at__lt=timezone.now()).count(),
        }
        
        context.update({
            'sessions': sessions,
            'system_stats': system_stats,
        })
        
        return context