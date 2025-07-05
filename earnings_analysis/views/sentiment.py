# earnings_analysis/views/sentiment.py（エクスポート・統計削除版）
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging

from ..models import SentimentAnalysisSession
from ..services.sentiment_analyzer import SentimentAnalysisService

logger = logging.getLogger(__name__)

class SentimentAnalysisStartView(APIView):
    """感情分析開始API"""
    
    def post(self, request):
        doc_id = request.data.get('doc_id')
        force = request.data.get('force', False)
        
        if not doc_id:
            return Response(
                {'error': 'doc_idが必要です'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = SentimentAnalysisService()
            user_ip = self._get_client_ip(request)
            
            result = service.start_analysis(doc_id, force, user_ip)
            
            if result['status'] == 'already_analyzed':
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_202_ACCEPTED)
                
        except Exception as e:
            logger.error(f"感情分析開始エラー: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_client_ip(self, request):
        """クライアントIP取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SentimentAnalysisProgressView(APIView):
    """進行状況取得API"""
    
    def get(self, request):
        session_id = request.query_params.get('session_id')
        
        if not session_id:
            return Response(
                {'error': 'session_idが必要です'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = SentimentAnalysisService()
            result = service.get_progress(session_id)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"進行状況取得エラー: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SentimentAnalysisResultView(APIView):
    """分析結果取得API"""
    
    def get(self, request):
        session_id = request.query_params.get('session_id')
        
        if not session_id:
            return Response(
                {'error': 'session_idが必要です'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = SentimentAnalysisService()
            result = service.get_result(session_id)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"分析結果取得エラー: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )