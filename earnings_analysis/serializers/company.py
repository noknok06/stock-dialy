from rest_framework import serializers
from django.db.models import Count, Q
from ..models import Company, DocumentMetadata

class CompanySearchSerializer(serializers.ModelSerializer):
    document_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Company
        fields = ['edinet_code', 'securities_code', 'company_name', 'document_count']