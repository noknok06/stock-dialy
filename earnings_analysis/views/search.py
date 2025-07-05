from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as filters

from ..models import Company, DocumentMetadata
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