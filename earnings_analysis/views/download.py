from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import StreamingHttpResponse
from django.utils.encoding import escape_uri_path
import logging

from ..models import DocumentMetadata
from ..services import EdinetDocumentService

logger = logging.getLogger(__name__)


class DocumentDownloadView(APIView):
    """書類表示API（ストリーミング、サーバーバッファリングなし）"""

    # PDF type=2, XBRL type=1, attach type=3, english type=4
    _TYPE_CODE_MAP = {'pdf': 2, 'xbrl': 1, 'attach': 3, 'english': 4}

    def get(self, request, doc_id):
        doc_type = request.query_params.get('type', 'pdf')

        try:
            metadata = DocumentMetadata.objects.get(
                doc_id=doc_id,
                legal_status='1'
            )

            if not self._is_format_available(metadata, doc_type):
                return Response(
                    {'error': f'{doc_type.upper()}形式は利用できません'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # EDINET APIクライアントを取得してストリーミングリクエスト
            doc_service = EdinetDocumentService()
            edinet_client = doc_service.edinet_client
            type_code = self._TYPE_CODE_MAP.get(doc_type, 2)

            url = f"{edinet_client.base_url}/documents/{doc_id}"
            params = {'type': type_code}
            headers = {}
            if edinet_client.api_key:
                params['Subscription-Key'] = edinet_client.api_key
                headers['Subscription-Key'] = edinet_client.api_key

            # stream=True でサーバーにバッファリングせず直接クライアントへ転送
            edinet_resp = edinet_client.session.get(
                url, params=params, headers=headers,
                stream=True, timeout=60
            )
            edinet_resp.raise_for_status()

            content_type = 'application/pdf' if doc_type == 'pdf' else 'application/zip'
            filename = self._generate_filename(metadata, doc_type)
            encoded_filename = escape_uri_path(filename)
            # PDFはブラウザでインライン表示、それ以外はダウンロード
            disposition = 'inline' if doc_type == 'pdf' else 'attachment'

            response = StreamingHttpResponse(
                edinet_resp.iter_content(chunk_size=32768),
                content_type=content_type,
            )
            response['Content-Disposition'] = f'{disposition}; filename="{encoded_filename}"'
            response['X-Document-Description'] = metadata.doc_description[:100]

            logger.info(f"書類ストリーミング開始: {doc_id} ({doc_type}) - {filename}")
            return response

        except DocumentMetadata.DoesNotExist:
            logger.warning(f"書類が見つかりません: {doc_id}")
            return Response(
                {'error': '書類が見つかりません'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"書類取得エラー: {doc_id} - {e}")
            return Response(
                {'error': f'書類取得エラー: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _is_format_available(self, metadata, doc_type):
        format_map = {
            'pdf': metadata.pdf_flag,
            'xbrl': metadata.xbrl_flag,
            'csv': metadata.csv_flag,
            'attach': metadata.attach_doc_flag,
            'english': metadata.english_doc_flag,
        }
        return format_map.get(doc_type, False)

    def _generate_filename(self, metadata, doc_type):
        extension = 'pdf' if doc_type == 'pdf' else 'zip'
        safe_company_name = metadata.company_name
        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            safe_company_name = safe_company_name.replace(char, '_')
        safe_company_name = safe_company_name[:20]
        date_str = metadata.submit_date_time.strftime('%Y%m%d')
        return f"{metadata.doc_id}_{safe_company_name}_{date_str}.{extension}"
