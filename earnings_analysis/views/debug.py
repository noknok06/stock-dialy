# earnings_analysis/views/debug.py （新規作成）

from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView
from django.db.models import Count, Q
import logging

from ..models import Company, DocumentMetadata

logger = logging.getLogger(__name__)

class DebugCompanySearchView(TemplateView):
    """企業検索デバッグ用ビュー"""
    
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        
        debug_info = {
            'query': query,
            'query_length': len(query),
            'timestamp': timezone.now().isoformat(),
            'errors': [],
            'warnings': [],
            'results': []
        }
        
        try:
            if not query:
                debug_info['warnings'].append('クエリが空です')
                return JsonResponse(debug_info)
            
            # データベース接続テスト
            total_companies = Company.objects.count()
            total_active_companies = Company.objects.filter(is_active=True).count()
            
            debug_info['database_stats'] = {
                'total_companies': total_companies,
                'active_companies': total_active_companies
            }
            
            # 検索条件構築のテスト
            search_conditions = Q()
            
            # 企業名検索
            name_matches = Company.objects.filter(
                company_name__icontains=query,
                is_active=True
            ).count()
            
            debug_info['search_breakdown'] = {
                'name_matches': name_matches
            }
            
            # 証券コード検索
            if query.isdigit():
                securities_matches = Company.objects.filter(
                    securities_code__icontains=query,
                    is_active=True
                ).count()
                debug_info['search_breakdown']['securities_matches'] = securities_matches
            
            # 実際の検索実行
            search_conditions |= Q(company_name__icontains=query)
            if query.isdigit():
                search_conditions |= Q(securities_code__icontains=query)
            
            companies = Company.objects.filter(
                search_conditions,
                is_active=True
            ).distinct()[:5]  # 最初の5件のみ
            
            for company in companies:
                try:
                    # 書類数の取得テスト
                    doc_count = DocumentMetadata.objects.filter(
                        edinet_code=company.edinet_code,
                        legal_status='1'
                    ).count()
                    
                    debug_info['results'].append({
                        'edinet_code': company.edinet_code,
                        'company_name': company.company_name,
                        'securities_code': company.securities_code,
                        'document_count': doc_count,
                        'has_securities_code': bool(company.securities_code)
                    })
                    
                except Exception as e:
                    debug_info['errors'].append(f'企業 {company.edinet_code} の処理エラー: {str(e)}')
            
            debug_info['total_results'] = len(debug_info['results'])
            
        except Exception as e:
            debug_info['errors'].append(f'検索処理エラー: {str(e)}')
            logger.error(f'デバッグ検索エラー: {e}')
        
        return JsonResponse(debug_info)
