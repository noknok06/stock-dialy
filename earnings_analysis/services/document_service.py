import requests
from typing import Dict, Any
from .edinet_api import EdinetAPIClient
import logging

logger = logging.getLogger(__name__)

class EdinetDocumentService:
    """書類取得サービス（CSV削除版）"""
    
    def __init__(self, prefer_v1=False):
        # v2で問題がある場合はv1を使用
        if prefer_v1:
            self.edinet_client = EdinetAPIClient.create_v1_client()
            self.fallback_client = EdinetAPIClient.create_v2_client()
        else:
            self.edinet_client = EdinetAPIClient.create_v2_client()
            self.fallback_client = EdinetAPIClient.create_v1_client()
        
        # CSV削除（コメントアウト）
        self.type_code_map = {
            'pdf': 2,      # PDF
            'xbrl': 1,     # XBRL
            # 'csv': 5,      # CSV（無効化）
            'attach': 3,   # 添付文書
            'english': 4,  # 英文ファイル
        }
    
    def get_document_list_with_fallback(self, date: str, type: int = 2):
        """フォールバック機能付き書類一覧取得"""
        try:
            # メインAPIで試行
            result = self.edinet_client.get_document_list(date, type)
            logger.info(f"メインAPI ({self.edinet_client.api_version}) で取得成功")
            return result
        except Exception as e:
            logger.warning(f"メインAPI ({self.edinet_client.api_version}) で失敗: {e}")
            
            # フォールバックAPIで試行
            if self.fallback_client:
                try:
                    logger.info(f"フォールバックAPI ({self.fallback_client.api_version}) で再試行中...")
                    result = self.fallback_client.get_document_list(date, type)
                    logger.info(f"フォールバックAPI ({self.fallback_client.api_version}) で取得成功")
                    return result
                except Exception as fallback_e:
                    logger.error(f"フォールバックAPI ({self.fallback_client.api_version}) でも失敗: {fallback_e}")
                    raise fallback_e
            else:
                raise e
    
    def download_document(self, doc_id: str, doc_type: str) -> Dict[str, Any]:
        """書類ダウンロード実行（CSV削除版）"""
        # CSVダウンロードを明示的に拒否
        if doc_type == 'csv':
            raise Exception('CSV形式のダウンロードは利用できません')
        
        type_code = self.type_code_map.get(doc_type, 2)
        
        try:
            logger.info(f"書類ダウンロード開始: {doc_id} ({doc_type})")
            
            # メインAPIで試行
            try:
                document_data = self.edinet_client.get_document(doc_id, type_code)
                logger.info(f"メインAPI ({self.edinet_client.api_version}) でダウンロード成功")
            except Exception as e:
                logger.warning(f"メインAPI ({self.edinet_client.api_version}) でダウンロード失敗: {e}")
                
                # フォールバックAPIで試行
                if self.fallback_client:
                    logger.info(f"フォールバックAPI ({self.fallback_client.api_version}) でダウンロード再試行中...")
                    document_data = self.fallback_client.get_document(doc_id, type_code)
                    logger.info(f"フォールバックAPI ({self.fallback_client.api_version}) でダウンロード成功")
                else:
                    raise e
            
            content_type = 'application/pdf' if doc_type == 'pdf' else 'application/zip'
            
            result = {
                'data': document_data,
                'content_type': content_type,
                'doc_id': doc_id,
                'doc_type': doc_type,
                'size': len(document_data)
            }
            
            logger.info(f"書類ダウンロード完了: {doc_id} ({result['size']} bytes)")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"EDINET API通信エラー: {doc_id} - {e}")
            raise Exception(f"EDINET API通信エラー: {str(e)}")
        except Exception as e:
            logger.error(f"書類取得エラー: {doc_id} - {e}")
            raise Exception(f"書類取得エラー: {str(e)}")