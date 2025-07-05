# earnings_analysis/views/ui.py （バッチ履歴ビュー追加版）
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

from ..models import Company, DocumentMetadata, BatchExecution

logger = logging.getLogger(__name__)

class IndexView(TemplateView):
    """トップページ - 企業検索"""
    template_name = 'earnings_analysis/simple_index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 統計情報
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


class DocumentListView(TemplateView):
    """書類一覧ページ"""
    template_name = 'earnings_analysis/simple_document_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # クエリパラメータ取得
        company_query = self.request.GET.get('company', '').strip()
        doc_type = self.request.GET.get('doc_type', '')
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
                    # 4桁: 7203 → 72030にもマッチ
                    search_conditions |= Q(securities_code__startswith=company_query)
                    search_conditions |= Q(securities_code__exact=company_query)
                elif len(company_query) == 5:
                    # 5桁: そのまま検索、4桁でも検索
                    search_conditions |= Q(securities_code__exact=company_query)
                    search_conditions |= Q(securities_code__startswith=company_query[:4])
                else:
                    # その他: 部分一致
                    search_conditions |= Q(securities_code__icontains=company_query)
            
            # 3. EDINETコードでの検索
            if len(company_query) == 6:
                search_conditions |= Q(edinet_code__iexact=company_query)
            
            # 4. 英数字混合の場合
            if not company_query.isdigit():
                search_conditions |= Q(securities_code__icontains=company_query)
                search_conditions |= Q(edinet_code__icontains=company_query)
            
            documents = documents.filter(search_conditions)
        
        # その他のフィルタリング
        if doc_type:
            documents = documents.filter(doc_type_code=doc_type)
        
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
        
        # 書類種別の選択肢
        try:
            doc_types = DocumentMetadata.objects.filter(
                legal_status='1'
            ).values('doc_type_code').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
        except Exception:
            doc_types = []
        
        # デバッグ情報
        debug_info = {
            'total_all_documents': total_all_documents,
            'total_active_documents': total_active_documents,
            'filtered_count': paginator.count,
            'search_query': company_query,
            'has_data': total_active_documents > 0,
        }
        
        context.update({
            'documents': documents_page,
            'doc_types': doc_types,
            'search_params': {
                'company': company_query,
                'doc_type': doc_type,
                'from_date': from_date,
                'to_date': to_date,
            },
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
    """企業検索API（AJAX用）"""
    
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        
        if len(query) < 2:
            return JsonResponse({'results': []})
        
        try:
            # より柔軟な企業検索
            search_conditions = Q()
            
            # 企業名での検索
            search_conditions |= Q(company_name__icontains=query)
            
            # 証券コードでの検索（改良版）
            if query.isdigit():
                if len(query) == 4:
                    # 4桁: startswithを使用
                    search_conditions |= Q(securities_code__startswith=query)
                elif len(query) == 5:
                    # 5桁: exact + 4桁での検索
                    search_conditions |= Q(securities_code__exact=query)
                    search_conditions |= Q(securities_code__startswith=query[:4])
                else:
                    search_conditions |= Q(securities_code__icontains=query)
            
            # EDINETコードでの検索
            if len(query) == 6:
                search_conditions |= Q(edinet_code__iexact=query)
            
            companies = Company.objects.filter(
                search_conditions,
                is_active=True
            ).annotate(
                document_count=Count('documentmetadata', filter=Q(documentmetadata__legal_status='1'))
            ).order_by('-document_count', 'company_name')[:10]
            
            results = []
            for company in companies:
                results.append({
                    'edinet_code': company.edinet_code,
                    'securities_code': company.securities_code or '',
                    'company_name': company.company_name,
                    'document_count': company.document_count,
                })
            
            return JsonResponse({'results': results})
            
        except Exception as e:
            logger.error(f"企業検索エラー: {e}")
            return JsonResponse({'results': [], 'error': str(e)})


class SystemStatsView(TemplateView):
    """システム統計ページ"""
    template_name = 'earnings_analysis/simple_stats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # 基本統計
            total_companies = Company.objects.filter(is_active=True).count()
            total_documents = DocumentMetadata.objects.filter(legal_status='1').count()
            
            # 最近のバッチ実行状況
            thirty_days_ago = timezone.now().date() - timedelta(days=30)
            recent_batches = BatchExecution.objects.filter(
                batch_date__gte=thirty_days_ago
            ).order_by('-batch_date')[:10]
            
            # 今月の書類数
            this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            this_month_docs = DocumentMetadata.objects.filter(
                submit_date_time__gte=this_month_start,
                legal_status='1'
            ).count()
            
            # 書類種別統計
            doc_type_stats = DocumentMetadata.objects.filter(
                legal_status='1'
            ).values('doc_type_code').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            # 月別統計（簡略版）
            monthly_stats = []
            for i in range(6):  # 過去6ヶ月
                months_ago = timezone.now() - timedelta(days=30*i)
                month_start = months_ago.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                
                if i == 0:
                    month_end = timezone.now()
                else:
                    month_end = month_start.replace(month=month_start.month+1 if month_start.month < 12 else 1,
                                                  year=month_start.year if month_start.month < 12 else month_start.year+1)
                
                count = DocumentMetadata.objects.filter(
                    submit_date_time__gte=month_start,
                    submit_date_time__lt=month_end,
                    legal_status='1'
                ).count()
                
                monthly_stats.append({
                    'month': month_start.strftime('%Y-%m'),
                    'count': count
                })
            
            monthly_stats.reverse()
            
            context.update({
                'total_companies': total_companies,
                'total_documents': total_documents,
                'this_month_documents': this_month_docs,
                'recent_batches': recent_batches,
                'doc_type_stats': list(doc_type_stats),
                'monthly_stats': json.dumps(monthly_stats),
            })
            
        except Exception as e:
            logger.error(f"統計情報取得エラー: {e}")
            context.update({
                'total_companies': 0,
                'total_documents': 0,
                'this_month_documents': 0,
                'recent_batches': [],
                'doc_type_stats': [],
                'monthly_stats': json.dumps([]),
            })
        
        return context

class BatchHistoryView(TemplateView):
    """バッチ実行履歴ページ"""
    template_name = 'earnings_analysis/batch_history.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # ページネーション
        page = self.request.GET.get('page', 1)
        status_filter = self.request.GET.get('status', '')
        
        # バッチ履歴取得
        batch_history = BatchExecution.objects.all().order_by('-batch_date')
        
        # ステータスフィルタ
        if status_filter:
            batch_history = batch_history.filter(status=status_filter)
        
        # ページネーション
        paginator = Paginator(batch_history, 20)
        try:
            batches = paginator.page(page)
        except PageNotAnInteger:
            batches = paginator.page(1)
        except EmptyPage:
            batches = paginator.page(paginator.num_pages)
        
        # 統計情報
        total_batches = BatchExecution.objects.count()
        success_count = BatchExecution.objects.filter(status='SUCCESS').count()
        failed_count = BatchExecution.objects.filter(status='FAILED').count()
        running_count = BatchExecution.objects.filter(status='RUNNING').count()
        
        # 最近30日の成功率
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        recent_total = BatchExecution.objects.filter(batch_date__gte=thirty_days_ago).count()
        recent_success = BatchExecution.objects.filter(
            batch_date__gte=thirty_days_ago, 
            status='SUCCESS'
        ).count()
        
        success_rate = (recent_success / recent_total * 100) if recent_total > 0 else 0
        
        context.update({
            'batches': batches,
            'status_filter': status_filter,
            'batch_stats': {
                'total_batches': total_batches,
                'success_count': success_count,
                'failed_count': failed_count,
                'running_count': running_count,
                'success_rate': round(success_rate, 1),
            },
            'status_choices': BatchExecution.STATUS_CHOICES,
        })
        
        return context
