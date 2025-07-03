from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from django.utils.encoding import escape_uri_path
import logging

from ..models import DocumentMetadata
from ..services import EdinetDocumentService

logger = logging.getLogger(__name__)

class DocumentDownloadView(APIView):
    """書類ダウンロードAPI"""
    
    def get(self, request, doc_id):
        doc_type = request.query_params.get('type', 'pdf')
        
        try:
            # メタデータ存在確認
            metadata = DocumentMetadata.objects.get(
                doc_id=doc_id, 
                legal_status='1'
            )
            
            # フォーマット利用可能性チェック
            if not self._is_format_available(metadata, doc_type):
                return Response(
                    {'error': f'{doc_type.upper()}形式は利用できません'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # EDINET APIから取得
            document_service = EdinetDocumentService()
            result = document_service.download_document(doc_id, doc_type)
            
            # レスポンス生成
            response = HttpResponse(
                result['data'], 
                content_type=result['content_type']
            )
            
            # ファイル名設定
            filename = self._generate_filename(metadata, doc_type)
            encoded_filename = escape_uri_path(filename)
            response['Content-Disposition'] = f'attachment; filename="{encoded_filename}"'
            response['X-Document-Description'] = metadata.doc_description[:100]
            response['Content-Length'] = len(result['data'])
            
            logger.info(f"書類ダウンロード完了: {doc_id} ({doc_type}) - {filename}")
            return response
            
        except DocumentMetadata.DoesNotExist:
            logger.warning(f"書類が見つかりません: {doc_id}")
            return Response(
                {'error': '書類が見つかりません'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"ダウンロードエラー: {doc_id} - {e}")
            return Response(
                {'error': f'ダウンロードエラー: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _is_format_available(self, metadata, doc_type):
        """フォーマット利用可能性チェック"""
        format_map = {
            'pdf': metadata.pdf_flag,
            'xbrl': metadata.xbrl_flag,
            'csv': metadata.csv_flag,
            'attach': metadata.attach_doc_flag,
            'english': metadata.english_doc_flag,
        }
        return format_map.get(doc_type, False)
    
    def _generate_filename(self, metadata, doc_type):
        """ファイル名生成"""
        extension = 'pdf' if doc_type == 'pdf' else 'zip'
        
        # 安全なファイル名生成
        safe_company_name = metadata.company_name
        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            safe_company_name = safe_company_name.replace(char, '_')
        safe_company_name = safe_company_name[:20]  # 長さ制限
        
        # 日付情報を含める
        date_str = metadata.submit_date_time.strftime('%Y%m%d')
        
        return f"{metadata.doc_id}_{safe_company_name}_{date_str}.{extension}"