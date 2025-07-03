from rest_framework import serializers
from ..models import DocumentMetadata

class DocumentMetadataSerializer(serializers.ModelSerializer):
    available_formats = serializers.ReadOnlyField()
    
    class Meta:
        model = DocumentMetadata
        fields = [
            'doc_id', 'company_name', 'doc_description', 
            'submit_date_time', 'period_start', 'period_end',
            'doc_type_code', 'available_formats', 'legal_status'
        ]

class DocumentDetailSerializer(serializers.ModelSerializer):
    available_formats = serializers.ReadOnlyField()
    
    class Meta:
        model = DocumentMetadata
        exclude = ['created_at', 'updated_at']