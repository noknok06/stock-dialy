# earnings_analysis/views/financial.py（新規作成）
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging

from ..models import FinancialAnalysisSession

logger = logging.getLogger(__name__)

class FinancialAnalysisStartView(APIView):
    """財務分析開始API"""
    
    def post(self, request):
        doc_id = request.data.get('doc_id')
        force = request.data.get('force', False)
        analysis_type = request.data.get('analysis_type', 'comprehensive')  # comprehensive, financial_only
        
        if not doc_id:
            return Response(
                {'error': 'doc_idが必要です'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = ComprehensiveAnalysisService()
            user_ip = self._get_client_ip(request)
            
            result = service.start_comprehensive_analysis(doc_id, force, user_ip)
            
            if result['status'] == 'already_analyzed':
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_202_ACCEPTED)
                
        except Exception as e:
            logger.error(f"財務分析開始エラー: {e}")
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


class FinancialAnalysisProgressView(APIView):
    """財務分析進行状況取得API"""
    
    def get(self, request):
        session_id = request.query_params.get('session_id')
        
        if not session_id:
            return Response(
                {'error': 'session_idが必要です'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = ComprehensiveAnalysisService()
            result = service.get_comprehensive_progress(session_id)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"財務分析進行状況取得エラー: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FinancialAnalysisResultView(APIView):
    """財務分析結果取得API"""
    
    def get(self, request):
        session_id = request.query_params.get('session_id')
        
        if not session_id:
            return Response(
                {'error': 'session_idが必要です'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = ComprehensiveAnalysisService()
            result = service.get_comprehensive_result(session_id)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"財務分析結果取得エラー: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FinancialDataAPIView(APIView):
    """企業の財務データ取得API"""
    
    def get(self, request):
        """財務データ一覧取得"""
        from ..models import CompanyFinancialData
        from rest_framework.pagination import PageNumberPagination
        from django.db.models import Q
        
        # フィルタパラメータ
        company_name = request.query_params.get('company', '')
        securities_code = request.query_params.get('securities_code', '')
        edinet_code = request.query_params.get('edinet_code', '')
        period_type = request.query_params.get('period_type', '')
        fiscal_year = request.query_params.get('fiscal_year', '')
        
        try:
            # クエリセット構築
            queryset = CompanyFinancialData.objects.select_related('document', 'company')
            
            # フィルタリング
            if company_name:
                queryset = queryset.filter(
                    Q(company__company_name__icontains=company_name) |
                    Q(document__company_name__icontains=company_name)
                )
            
            if securities_code:
                queryset = queryset.filter(
                    Q(company__securities_code=securities_code) |
                    Q(document__securities_code=securities_code)
                )
            
            if edinet_code:
                queryset = queryset.filter(document__edinet_code=edinet_code)
            
            if period_type:
                queryset = queryset.filter(period_type=period_type)
            
            if fiscal_year:
                queryset = queryset.filter(fiscal_year=int(fiscal_year))
            
            # ページネーション
            paginator = PageNumberPagination()
            paginator.page_size = 20
            page = paginator.paginate_queryset(queryset, request)
            
            # レスポンスデータ構築
            results = []
            for item in page:
                company_name = item.company.company_name if item.company else item.document.company_name
                securities_code = item.company.securities_code if item.company else item.document.securities_code
                
                results.append({
                    'id': item.id,
                    'company_name': company_name,
                    'securities_code': securities_code,
                    'period_type': item.period_type,
                    'period_start': item.period_start,
                    'period_end': item.period_end,
                    'fiscal_year': item.fiscal_year,
                    'financial_data': {
                        'net_sales': float(item.net_sales) if item.net_sales else None,
                        'operating_income': float(item.operating_income) if item.operating_income else None,
                        'net_income': float(item.net_income) if item.net_income else None,
                        'operating_cf': float(item.operating_cf) if item.operating_cf else None,
                        'investing_cf': float(item.investing_cf) if item.investing_cf else None,
                        'financing_cf': float(item.financing_cf) if item.financing_cf else None,
                    },
                    'financial_ratios': {
                        'operating_margin': float(item.operating_margin) if item.operating_margin else None,
                        'net_margin': float(item.net_margin) if item.net_margin else None,
                        'roa': float(item.roa) if item.roa else None,
                        'equity_ratio': float(item.equity_ratio) if item.equity_ratio else None,
                    },
                    'data_quality': {
                        'completeness': item.data_completeness,
                        'confidence': item.extraction_confidence,
                    },
                    'document_info': {
                        'doc_id': item.document.doc_id,
                        'submit_date': item.document.submit_date_time.date(),
                    },
                    'created_at': item.created_at,
                })
            
            return paginator.get_paginated_response(results)
            
        except Exception as e:
            logger.error(f"財務データ取得エラー: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FinancialAnalysisHistoryView(APIView):
    """財務分析履歴取得API"""
    
    def get(self, request):
        """分析履歴一覧取得"""
        from ..models import FinancialAnalysisHistory
        from rest_framework.pagination import PageNumberPagination
        from django.db.models import Q
        
        # フィルタパラメータ
        company_name = request.query_params.get('company', '')
        risk_level = request.query_params.get('risk_level', '')
        date_from = request.query_params.get('date_from', '')
        date_to = request.query_params.get('date_to', '')
        
        try:
            # クエリセット構築
            queryset = FinancialAnalysisHistory.objects.select_related('document')
            
            # フィルタリング
            if company_name:
                queryset = queryset.filter(document__company_name__icontains=company_name)
            
            if risk_level:
                queryset = queryset.filter(risk_level=risk_level)
            
            if date_from:
                queryset = queryset.filter(analysis_date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(analysis_date__lte=date_to)
            
            # ページネーション
            paginator = PageNumberPagination()
            paginator.page_size = 20
            page = paginator.paginate_queryset(queryset, request)
            
            # レスポンスデータ構築
            results = []
            for item in page:
                results.append({
                    'id': item.id,
                    'document': {
                        'doc_id': item.document.doc_id,
                        'company_name': item.document.company_name,
                        'securities_code': item.document.securities_code,
                        'submit_date': item.document.submit_date_time.date(),
                    },
                    'analysis_results': {
                        'overall_health_score': item.overall_health_score,
                        'risk_level': item.risk_level,
                        'cashflow_pattern': item.cashflow_pattern,
                        'management_confidence_score': item.management_confidence_score,
                    },
                    'analysis_metadata': {
                        'analysis_date': item.analysis_date,
                        'analysis_duration': item.analysis_duration,
                        'data_quality': item.data_quality,
                    }
                })
            
            return paginator.get_paginated_response(results)
            
        except Exception as e:
            logger.error(f"分析履歴取得エラー: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FinancialStatsAPIView(APIView):
    """財務分析統計API"""
    
    def get(self, request):
        """財務分析統計情報取得"""
        from ..models import FinancialAnalysisHistory, CompanyFinancialData
        from django.db.models import Count, Avg, Q
        from datetime import datetime, timedelta
        
        try:
            # 基本統計
            total_analyses = FinancialAnalysisHistory.objects.count()
            total_financial_records = CompanyFinancialData.objects.count()
            
            # 過去30日の分析数
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_analyses = FinancialAnalysisHistory.objects.filter(
                analysis_date__gte=thirty_days_ago
            ).count()
            
            # リスクレベル別統計
            risk_stats = FinancialAnalysisHistory.objects.values('risk_level').annotate(
                count=Count('id')
            ).order_by('risk_level')
            
            # キャッシュフローパターン別統計
            cf_pattern_stats = FinancialAnalysisHistory.objects.exclude(
                cashflow_pattern__isnull=True
            ).exclude(
                cashflow_pattern=''
            ).values('cashflow_pattern').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            # 平均健全性スコア
            avg_health_score = FinancialAnalysisHistory.objects.aggregate(
                avg_score=Avg('overall_health_score')
            )['avg_score'] or 0
            
            # 平均経営陣自信度
            avg_confidence_score = FinancialAnalysisHistory.objects.aggregate(
                avg_confidence=Avg('management_confidence_score')
            )['avg_confidence'] or 0
            
            # 期間別財務データ統計
            period_type_stats = CompanyFinancialData.objects.values('period_type').annotate(
                count=Count('id')
            ).order_by('period_type')
            
            # データ品質統計
            high_quality_data = CompanyFinancialData.objects.filter(
                data_completeness__gte=0.8
            ).count()
            
            data_quality_ratio = (high_quality_data / total_financial_records * 100) if total_financial_records > 0 else 0
            
            return Response({
                'summary': {
                    'total_analyses': total_analyses,
                    'total_financial_records': total_financial_records,
                    'recent_analyses_30days': recent_analyses,
                    'avg_health_score': round(avg_health_score, 1),
                    'avg_confidence_score': round(avg_confidence_score, 1),
                    'high_quality_data_ratio': round(data_quality_ratio, 1),
                },
                'risk_level_distribution': list(risk_stats),
                'cashflow_pattern_distribution': list(cf_pattern_stats),
                'period_type_distribution': list(period_type_stats),
                'analysis_quality': {
                    'high_quality_records': high_quality_data,
                    'total_records': total_financial_records,
                    'quality_ratio': round(data_quality_ratio, 1),
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"財務分析統計取得エラー: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )