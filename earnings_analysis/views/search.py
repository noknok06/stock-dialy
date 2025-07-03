from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as filters
from django.utils import timezone
from datetime import timedelta

from ..models import Company, DocumentMetadata, BatchExecution
from ..serializers import (
    CompanySearchSerializer, 
    DocumentMetadataSerializer, 
    DocumentDetailSerializer
)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

class DocumentMetadataFilter(filters.FilterSet):
    """書類メタデータフィルタ"""
    securities_code = filters.CharFilter(field_name='securities_code', lookup_expr='exact')
    company_name = filters.CharFilter(field_name='company_name', lookup_expr='icontains')
    doc_type_code = filters.CharFilter(field_name='doc_type_code', lookup_expr='exact')
    from_date = filters.DateFilter(field_name='submit_date_time', lookup_expr='gte')
    to_date = filters.DateFilter(field_name='submit_date_time', lookup_expr='lte')
    
    class Meta:
        model = DocumentMetadata
        fields = ['securities_code', 'company_name', 'doc_type_code', 'from_date', 'to_date']

class CompanySearchView(generics.ListAPIView):
    """企業検索API"""
    serializer_class = CompanySearchSerializer
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        query = self.request.query_params.get('q', '').strip()
        
        if len(query) < 2:
            return Company.objects.none()
        
        # 証券コードまたは企業名で検索
        return Company.objects.filter(
            Q(securities_code__icontains=query) |
            Q(company_name__icontains=query),
            is_active=True
        ).annotate(
            document_count=Count('documentmetadata', filter=Q(documentmetadata__legal_status='1'))
        ).order_by('-document_count', 'company_name')

class DocumentListView(generics.ListAPIView):
    """書類一覧API"""
    serializer_class = DocumentMetadataSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DocumentMetadataFilter
    pagination_class = StandardResultsSetPagination
    ordering = ['-submit_date_time']
    
    def get_queryset(self):
        return DocumentMetadata.objects.filter(
            legal_status='1'  # 閲覧可能のみ
        ).select_related()

class DocumentDetailView(generics.RetrieveAPIView):
    """書類詳細API"""
    serializer_class = DocumentDetailSerializer
    lookup_field = 'doc_id'
    
    def get_queryset(self):
        return DocumentMetadata.objects.filter(legal_status='1')

class SystemStatsView(generics.GenericAPIView):
    """システム統計情報API"""
    
    def get(self, request):
        # 基本統計
        total_companies = Company.objects.filter(is_active=True).count()
        total_documents = DocumentMetadata.objects.filter(legal_status='1').count()
        
        # 最近のバッチ実行状況
        recent_batches = BatchExecution.objects.filter(
            batch_date__gte=timezone.now().date() - timedelta(days=30)
        ).order_by('-batch_date')[:10]
        
        # 月間統計
        this_month_docs = DocumentMetadata.objects.filter(
            created_at__gte=timezone.now().replace(day=1),
            legal_status='1'
        ).count()
        
        # 書類種別統計
        doc_type_stats = DocumentMetadata.objects.filter(
            legal_status='1'
        ).values('doc_type_code').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return Response({
            'total_companies': total_companies,
            'total_documents': total_documents,
            'this_month_documents': this_month_docs,
            'recent_batches': [
                {
                    'date': batch.batch_date,
                    'status': batch.status,
                    'processed_count': batch.processed_count,
                    'error_message': batch.error_message[:100] if batch.error_message else None
                }
                for batch in recent_batches
            ],
            'doc_type_stats': list(doc_type_stats),
        })

class BatchHistoryView(generics.ListAPIView):
    """バッチ実行履歴API"""
    queryset = BatchExecution.objects.all().order_by('-batch_date')
    pagination_class = StandardResultsSetPagination
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            data = [
                {
                    'batch_date': batch.batch_date,
                    'status': batch.status,
                    'processed_count': batch.processed_count,
                    'error_message': batch.error_message,
                    'started_at': batch.started_at,
                    'completed_at': batch.completed_at,
                    'duration': str(batch.completed_at - batch.started_at).split('.')[0] 
                                if batch.started_at and batch.completed_at else None
                }
                for batch in page
            ]
            return self.get_paginated_response(data)
        
        data = [
            {
                'batch_date': batch.batch_date,
                'status': batch.status,
                'processed_count': batch.processed_count,
                'error_message': batch.error_message,
                'started_at': batch.started_at,
                'completed_at': batch.completed_at,
                'duration': str(batch.completed_at - batch.started_at).split('.')[0] 
                            if batch.started_at and batch.completed_at else None
            }
            for batch in queryset
        ]
        return Response(data)