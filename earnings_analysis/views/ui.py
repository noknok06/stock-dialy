# earnings_analysis/views/ui.py（書類種別表示名対応版）
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count
from django.views.generic import TemplateView
from django.urls import reverse
from django.utils import timezone
import json
import logging
from datetime import datetime, timedelta

from ..models import Company, DocumentMetadata

logger = logging.getLogger(__name__)

class IndexView(TemplateView):
    """トップページ - 企業検索"""
    template_name = 'earnings_analysis/simple_index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 基本統計情報のみ
        try:
            total_companies = Company.objects.filter(is_active=True).count()
            total_documents = DocumentMetadata.objects.filter(legal_status='1').count()
            
            # タイムゾーンを考慮した日付計算
            seven_days_ago = timezone.now() - timedelta(days=7)
            recent_documents_count = DocumentMetadata.objects.filter(
                created_at__gte=seven_days_ago,
                legal_status='1'
            ).count()
            
            context.update({
                'total_companies': total_companies,
                'total_documents': total_documents,
                'recent_documents_count': recent_documents_count,
            })
        except Exception as e:
            logger.error(f"統計情報取得エラー: {e}")
            context.update({
                'total_companies': 0,
                'total_documents': 0,
                'recent_documents_count': 0,
            })
        
        return context


class CompanyDetailView(TemplateView):
    """企業詳細ページ"""
    template_name = 'earnings_analysis/company_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        edinet_code = kwargs.get('edinet_code')
        
        # 企業情報取得
        company = get_object_or_404(
            Company,
            edinet_code=edinet_code,
            is_active=True
        )
        
        # 分析適合書類と その他書類を分けて取得
        documents_data = DocumentMetadata.get_documents_by_company(
            edinet_code=edinet_code, 
            analysis_suitable_first=True
        )
        
        suitable_documents = documents_data['suitable'][:10]
        other_documents = documents_data['others'][:20]
        
        # 最新の決算関連書類（ワンクリック分析用）
        latest_financial = DocumentMetadata.get_latest_financial_document(edinet_code)
        
        # 分析推奨書類（上位3件）
        recommended_docs = DocumentMetadata.get_recommended_for_analysis(edinet_code, limit=3)
        
        # 企業の統計情報
        try:
            total_documents = DocumentMetadata.objects.filter(
                edinet_code=edinet_code,
                legal_status='1'
            ).count()
            
            # 書類種別統計（表示名付き）
            doc_type_stats_raw = DocumentMetadata.objects.filter(
                edinet_code=edinet_code,
                legal_status='1'
            ).values('doc_type_code').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            doc_type_stats = []
            for stat in doc_type_stats_raw:
                doc_type_code = stat['doc_type_code']
                display_name = DocumentMetadata.DOC_TYPE_DISPLAY_NAMES.get(
                    doc_type_code, f'書類種別{doc_type_code}'
                )
                doc_type_stats.append({
                    'doc_type_code': doc_type_code,
                    'display_name': display_name,
                    'count': stat['count']
                })
            
            # 最新書類日付
            latest_doc = DocumentMetadata.objects.filter(
                edinet_code=edinet_code,
                legal_status='1'
            ).order_by('-submit_date_time').first()
            
            # 分析履歴の確認
            has_recent_analysis = False
            if latest_financial:
                has_recent_analysis = latest_financial.has_recent_analysis(hours=1)
            
        except Exception as e:
            logger.error(f"企業統計取得エラー: {e}")
            total_documents = 0
            doc_type_stats = []
            latest_doc = None
            has_recent_analysis = False
        
        # 関連企業（同じ証券コードまたは類似企業名）
        related_companies = []
        if company.securities_code:
            related_companies = Company.objects.filter(
                securities_code=company.securities_code,
                is_active=True
            ).exclude(edinet_code=edinet_code)[:3]
        
        context.update({
            'company': company,
            'suitable_documents': suitable_documents,
            'other_documents': other_documents,
            'latest_financial': latest_financial,
            'recommended_docs': recommended_docs,
            'total_documents': total_documents,
            'doc_type_stats': doc_type_stats,
            'latest_doc': latest_doc,
            'has_recent_analysis': has_recent_analysis,
            'related_companies': related_companies,
            'show_other_documents': len(other_documents) > 0,
        })
        
        return context


class DocumentListView(TemplateView):
    """書類一覧ページ（書類種別表示名対応版）"""
    template_name = 'earnings_analysis/simple_document_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # クエリパラメータ取得
        company_query = self.request.GET.get('company', '').strip()
        doc_type = self.request.GET.get('doc_type', '')
        doc_type_name = self.request.GET.get('doc_type_name', '')  # 表示名での検索
        from_date = self.request.GET.get('from_date', '')
        to_date = self.request.GET.get('to_date', '')
        page = self.request.GET.get('page', 1)
        
        # 基本クエリセット
        documents = DocumentMetadata.objects.filter(legal_status='1')
        
        # 全体のデータ数
        total_all_documents = DocumentMetadata.objects.count()
        total_active_documents = documents.count()
        
        # フィルタリング（改良版）
        if company_query:
            search_conditions = Q()
            
            # 1. 企業名での検索（大文字小文字区別なし）
            search_conditions |= Q(company_name__icontains=company_query)
            
            # 2. 証券コードでの検索（改良版）
            if company_query.isdigit():
                if len(company_query) == 4:
                    search_conditions |= Q(securities_code__startswith=company_query)
                    search_conditions |= Q(securities_code__exact=company_query)
                elif len(company_query) == 5:
                    search_conditions |= Q(securities_code__exact=company_query)
                    search_conditions |= Q(securities_code__startswith=company_query[:4])
                else:
                    search_conditions |= Q(securities_code__icontains=company_query)
            
            # 3. EDINETコードでの検索
            if len(company_query) == 6:
                search_conditions |= Q(edinet_code__iexact=company_query)
            
            # 4. 英数字混合の場合
            if not company_query.isdigit():
                search_conditions |= Q(securities_code__icontains=company_query)
                search_conditions |= Q(edinet_code__icontains=company_query)
            
            documents = documents.filter(search_conditions)
        
        # 書類種別フィルタリング
        if doc_type:
            # 従来のコードでのフィルタリング
            documents = documents.filter(doc_type_code=doc_type)
        elif doc_type_name:
            # 表示名でのフィルタリング（逆引き）
            matching_code = None
            for code, name in DocumentMetadata.DOC_TYPE_DISPLAY_NAMES.items():
                if name == doc_type_name:
                    matching_code = code
                    break
            if matching_code:
                documents = documents.filter(doc_type_code=matching_code)
        
        # その他のフィルタリング
        if from_date:
            try:
                from_dt = timezone.make_aware(datetime.strptime(from_date, '%Y-%m-%d'))
                documents = documents.filter(submit_date_time__gte=from_dt)
            except ValueError:
                pass
        
        if to_date:
            try:
                to_dt = timezone.make_aware(datetime.strptime(to_date, '%Y-%m-%d'))
                to_dt_end = to_dt + timedelta(days=1)
                documents = documents.filter(submit_date_time__lt=to_dt_end)
            except ValueError:
                pass
        
        # ソート
        documents = documents.order_by('-submit_date_time')
        
        # ページネーション
        paginator = Paginator(documents, 20)
        try:
            documents_page = paginator.page(page)
        except PageNotAnInteger:
            documents_page = paginator.page(1)
        except EmptyPage:
            documents_page = paginator.page(paginator.num_pages)
        
        # 書類種別の選択肢（表示名付き、カテゴリ別）
        try:
            # カテゴリ別の選択肢も取得
            categorized_choices = DocumentMetadata.get_doc_type_choices_for_filter()
            
        except Exception as e:
            logger.error(f"書類種別選択肢取得エラー: {e}")
            categorized_choices = []
        
        # 現在の検索パラメータの表示名を解決
        selected_doc_type_name = ''
        if doc_type:
            selected_doc_type_name = DocumentMetadata.DOC_TYPE_DISPLAY_NAMES.get(
                doc_type, f'書類種別{doc_type}'
            )
        elif doc_type_name:
            selected_doc_type_name = doc_type_name
        
        # デバッグ情報
        debug_info = {
            'total_all_documents': total_all_documents,
            'total_active_documents': total_active_documents,
            'filtered_count': paginator.count,
            'search_query': company_query,
            'has_data': total_active_documents > 0,
            'selected_doc_type': doc_type,
            'selected_doc_type_name': selected_doc_type_name,
        }
        
        context.update({
            'documents': documents_page,
            'categorized_choices': categorized_choices,
            'search_params': {
                'company': company_query,
                'doc_type': doc_type,
                'doc_type_name': doc_type_name,
                'from_date': from_date,
                'to_date': to_date,
            },
            'selected_doc_type_name': selected_doc_type_name,
            'total_count': paginator.count,
            'debug_info': debug_info,
        })
        
        return context


class DocumentDetailView(TemplateView):
    """書類詳細ページ"""
    template_name = 'earnings_analysis/simple_document_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc_id = kwargs.get('doc_id')
        
        document = get_object_or_404(
            DocumentMetadata,
            doc_id=doc_id,
            legal_status='1'
        )
        
        # 同一企業の関連書類
        try:
            related_documents = DocumentMetadata.objects.filter(
                edinet_code=document.edinet_code,
                legal_status='1'
            ).exclude(
                doc_id=doc_id
            ).order_by('-submit_date_time')[:5]
        except Exception:
            related_documents = []
        
        context.update({
            'document': document,
            'related_documents': related_documents,
            'download_url_base': reverse('earnings_analysis:document-download', args=[doc_id]),
        })
        
        return context


class CompanySearchAPIView(TemplateView):
    """企業検索API"""
    
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        
        if len(query) < 1:
            return JsonResponse({'results': []})
        
        try:
            # 企業検索
            companies = self._search_companies_with_stats(query)
            
            results = []
            for company_data in companies[:15]:
                company = company_data['company']
                
                # 最新決算書類の情報
                latest_financial = None
                try:
                    latest_financial = DocumentMetadata.objects.filter(
                        edinet_code=company.edinet_code,
                        legal_status='1',
                        doc_type_code__in=['120', '130', '140', '150', '160']
                    ).order_by('-submit_date_time').first()
                except Exception as e:
                    logger.debug(f"最新決算書類取得エラー: {e}")
                
                result = {
                    'edinet_code': company.edinet_code,
                    'securities_code': company.securities_code or '',
                    'company_name': company.company_name,
                    'company_name_kana': company.company_name_kana or '',
                    'document_count': company_data['document_count'],
                    'financial_count': company_data['financial_count'],
                    'has_analysis_ready': company_data['financial_count'] > 0,
                    'latest_financial_date': None,
                    'latest_financial_type': None,
                    'latest_financial_type_name': None,  # 表示名を追加
                    'match_type': self._get_match_type(query, company),
                    'relevance_score': self._calculate_relevance_score(query, company)
                }
                
                # 最新決算情報（表示名付き）
                if latest_financial:
                    result.update({
                        'latest_financial_date': latest_financial.submit_date_time.strftime('%Y-%m-%d'),
                        'latest_financial_type': latest_financial.doc_description[:30] + '...' if len(latest_financial.doc_description) > 30 else latest_financial.doc_description,
                        'latest_financial_type_name': latest_financial.doc_type_display_name,
                    })
                
                results.append(result)
            
            # 関連度順でソート
            results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            return JsonResponse({
                'results': results,
                'query': query,
                'total_found': len(results)
            })
            
        except Exception as e:
            logger.error(f"企業検索エラー: {e}")
            return JsonResponse({
                'results': [], 
                'error': str(e),
                'query': query
            })
    
    def _search_companies_with_stats(self, query):
        """統計情報付きの企業検索"""
        search_conditions = Q()
        
        # 1. 企業名での検索
        search_conditions |= Q(company_name__istartswith=query)
        search_conditions |= Q(company_name__icontains=query)
        
        # カナ名での検索
        if query:
            search_conditions |= Q(company_name_kana__icontains=query)
        
        # 2. 証券コードでの検索
        if query.isdigit():
            search_conditions |= Q(securities_code__exact=query)
            search_conditions |= Q(securities_code__startswith=query)
            
            if len(query) == 4:
                search_conditions |= Q(securities_code__exact=query + '0')
            elif len(query) == 5 and query.endswith('0'):
                search_conditions |= Q(securities_code__exact=query[:4])
        
        # 3. EDINETコードでの検索
        if len(query) == 6 and query.upper().startswith('E'):
            search_conditions |= Q(edinet_code__iexact=query)
        elif query.upper().startswith('E'):
            search_conditions |= Q(edinet_code__istartswith=query.upper())
        
        # 企業を取得
        companies = Company.objects.filter(
            search_conditions,
            is_active=True
        ).distinct()
        
        # 各企業の統計を取得
        results = []
        for company in companies:
            try:
                # 書類数の計算
                total_docs = DocumentMetadata.objects.filter(
                    edinet_code=company.edinet_code,
                    legal_status='1'
                ).count()
                
                # 決算書類数の計算
                financial_docs = DocumentMetadata.objects.filter(
                    edinet_code=company.edinet_code,
                    legal_status='1',
                    doc_type_code__in=['120', '130', '140', '150', '160']
                ).count()
                
                results.append({
                    'company': company,
                    'document_count': total_docs,
                    'financial_count': financial_docs
                })
                
            except Exception as e:
                logger.debug(f"企業統計取得エラー ({company.edinet_code}): {e}")
                results.append({
                    'company': company,
                    'document_count': 0,
                    'financial_count': 0
                })
        
        return results
    
    def _get_match_type(self, query, company):
        """マッチタイプの判定"""
        query_lower = query.lower()
        company_name_lower = company.company_name.lower()
        
        # 証券コード完全一致
        if company.securities_code and company.securities_code == query:
            return 'securities_exact'
        
        # 企業名前方一致
        if company_name_lower.startswith(query_lower):
            return 'name_prefix'
        
        # 証券コード前方一致
        if company.securities_code and company.securities_code.startswith(query):
            return 'securities_prefix'
        
        # 企業名部分一致
        if query_lower in company_name_lower:
            return 'name_partial'
        
        return 'other'
    
    def _calculate_relevance_score(self, query, company):
        """関連度スコアの計算"""
        score = 0
        query_lower = query.lower()
        company_name_lower = company.company_name.lower()
        
        # マッチタイプによるスコア
        match_type = self._get_match_type(query, company)
        match_scores = {
            'securities_exact': 1000,
            'name_prefix': 900,
            'securities_prefix': 800,
            'name_partial': 700,
            'other': 500
        }
        score += match_scores.get(match_type, 0)
        
        # 企業名の長さ（短いほど高スコア）
        if query_lower in company_name_lower:
            score += max(0, 100 - len(company.company_name))
        
        # 証券コードの有無
        if company.securities_code:
            score += 50
        
        return score


class DocumentTypeAPIView(TemplateView):
    """書類種別API（新規追加）"""
    
    def get(self, request, *args, **kwargs):
        try:
            
            # カテゴリ別の書類種別
            categorized_types = DocumentMetadata.get_doc_type_choices_for_filter()
            
            # 全ての書類種別マッピング
            all_types = []
            for code, name in DocumentMetadata.DOC_TYPE_DISPLAY_NAMES.items():
                all_types.append({
                    'code': code,
                    'name': name,
                    'full_name': f"{name} ({code})"
                })
            
            return JsonResponse({
                'categorized_types': categorized_types,
                'all_types': all_types
            })
            
        except Exception as e:
            logger.error(f"書類種別API エラー: {e}")
            return JsonResponse({
                'categorized_types': [],
                'all_types': [],
                'error': str(e)
            })