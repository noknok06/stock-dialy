# earnings_analysis/views/sentiment.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse, JsonResponse
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import csv
import json
import logging

from ..models import SentimentAnalysisSession, SentimentAnalysisHistory, DocumentMetadata
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


class SentimentAnalysisExportView(APIView):
    """分析結果エクスポートAPI"""
    
    def get(self, request):
        session_id = request.query_params.get('session_id')
        export_format = request.query_params.get('format', 'json')
        
        if not session_id:
            return Response(
                {'error': 'session_idが必要です'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            session = SentimentAnalysisSession.objects.get(session_id=session_id)
            
            if session.processing_status != 'COMPLETED':
                return Response(
                    {'error': '分析が完了していません'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if export_format == 'csv':
                return self._export_csv(session)
            else:
                return self._export_json(session)
                
        except SentimentAnalysisSession.DoesNotExist:
            return Response(
                {'error': 'セッションが見つかりません'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"エクスポートエラー: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _export_csv(self, session):
        """CSV形式でエクスポート"""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f"sentiment_analysis_{session.document.doc_id}_{timezone.now().strftime('%Y%m%d')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        
        # ヘッダー
        writer.writerow([
            '書類管理番号', '企業名', '書類概要', '全体感情スコア', '感情ラベル',
            '総文数', 'ポジティブ文数', 'ネガティブ文数', '中立文数',
            '分析日時'
        ])
        
        # データ
        result = session.analysis_result
        stats = result.get('statistics', {})
        
        writer.writerow([
            session.document.doc_id,
            session.document.company_name,
            session.document.doc_description,
            session.overall_score,
            session.get_sentiment_label_display(),
            stats.get('total_sentences', 0),
            stats.get('positive_sentences', 0),
            stats.get('negative_sentences', 0),
            stats.get('neutral_sentences', 0),
            session.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
        
        # キーワード情報
        writer.writerow([])
        writer.writerow(['ポジティブキーワード'])
        writer.writerow(['キーワード', 'スコア'])
        
        for keyword in result.get('top_keywords', {}).get('positive', []):
            writer.writerow([keyword['word'], keyword['score']])
        
        writer.writerow([])
        writer.writerow(['ネガティブキーワード'])
        writer.writerow(['キーワード', 'スコア'])
        
        for keyword in result.get('top_keywords', {}).get('negative', []):
            writer.writerow([keyword['word'], keyword['score']])
        
        return response
    
    def _export_json(self, session):
        """JSON形式でエクスポート"""
        export_data = {
            'document_info': {
                'doc_id': session.document.doc_id,
                'company_name': session.document.company_name,
                'doc_description': session.document.doc_description,
                'submit_date': session.document.submit_date_time.isoformat(),
            },
            'analysis_result': session.analysis_result,
            'overall_score': session.overall_score,
            'sentiment_label': session.sentiment_label,
            'analysis_date': session.created_at.isoformat(),
            'session_id': str(session.session_id),
        }
        
        response = HttpResponse(
            json.dumps(export_data, ensure_ascii=False, indent=2),
            content_type='application/json; charset=utf-8'
        )
        
        filename = f"sentiment_analysis_{session.document.doc_id}_{timezone.now().strftime('%Y%m%d')}.json"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response


class SentimentAnalysisStatsView(APIView):
    """感情分析統計API"""
    
    def get(self, request):
        try:
            # 基本統計
            total_analyses = SentimentAnalysisHistory.objects.count()
            recent_analyses = SentimentAnalysisHistory.objects.filter(
                analysis_date__gte=timezone.now() - timedelta(days=30)
            ).count()
            
            # 感情分布
            sentiment_distribution = {}
            for choice in SentimentAnalysisHistory.SENTIMENT_CHOICES:
                count = SentimentAnalysisHistory.objects.filter(
                    sentiment_label=choice[0]
                ).count()
                sentiment_distribution[choice[1]] = count
            
            # 月別分析数
            monthly_stats = []
            for i in range(6):  # 過去6ヶ月
                month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
                month_end = month_start.replace(month=month_start.month+1 if month_start.month < 12 else 1,
                                              year=month_start.year if month_start.month < 12 else month_start.year+1)
                
                count = SentimentAnalysisHistory.objects.filter(
                    analysis_date__gte=month_start,
                    analysis_date__lt=month_end
                ).count()
                
                monthly_stats.append({
                    'month': month_start.strftime('%Y-%m'),
                    'count': count
                })
            
            # アクティブセッション数
            active_sessions = SentimentAnalysisSession.objects.filter(
                processing_status__in=['PENDING', 'PROCESSING'],
                expires_at__gt=timezone.now()
            ).count()
            
            return Response({
                'total_analyses': total_analyses,
                'recent_analyses': recent_analyses,
                'sentiment_distribution': sentiment_distribution,
                'monthly_stats': list(reversed(monthly_stats)),
                'active_sessions': active_sessions,
                'last_updated': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"統計取得エラー: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SentimentAnalysisCleanupView(APIView):
    """クリーンアップ実行API"""
    
    def post(self, request):
        try:
            service = SentimentAnalysisService()
            deleted_count = service.cleanup_expired_sessions()
            
            return Response({
                'message': f'{deleted_count}件の期限切れセッションを削除しました',
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )