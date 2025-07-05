# earnings_analysis/views/sentiment_ui.py（統計・管理機能削除版）
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.generic import TemplateView
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import logging

from ..models import DocumentMetadata, SentimentAnalysisSession, SentimentAnalysisHistory

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
        })
        
        return context