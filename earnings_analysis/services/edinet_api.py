import requests
import time
from django.conf import settings
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class EdinetAPIClient:
    """EDINET API連携クライアント"""
    
    def __init__(self, api_version='v2'):
        settings_dict = getattr(settings, 'EDINET_API_SETTINGS', {})
        
        if api_version == 'v1':
            self.base_url = 'https://disclosure.edinet-fsa.go.jp/api/v1'
            self.api_key = None  # v1はAPIキー不要
        else:
            # 正しいv2 APIのURL
            self.base_url = 'https://api.edinet-fsa.go.jp/api/v2'
            self.api_key = settings_dict.get('API_KEY', '')
        
        self.api_version = api_version
        self.session = requests.Session()
        self.last_request_time = 0
        self.min_interval = settings_dict.get('RATE_LIMIT_DELAY', 2)
        self.timeout = settings_dict.get('TIMEOUT', 120)
        
        # User-Agentを設定
        user_agent = settings_dict.get('USER_AGENT', 'EarningsAnalysisBot/1.0')
        self.session.headers.update({'User-Agent': user_agent})
        
        logger.info(f"EDINET API {api_version.upper()} クライアント初期化: {self.base_url}")
    
    @classmethod
    def create_v1_client(cls):
        """v1 API用クライアント作成"""
        return cls(api_version='v1')
    
    @classmethod
    def create_v2_client(cls):
        """v2 API用クライアント作成"""
        return cls(api_version='v2')
    
    def _wait_for_rate_limit(self):
        """レート制限対応"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_interval:
            time.sleep(self.min_interval - time_since_last_request)
        
        self.last_request_time = time.time()
    
    def get_document_list(self, date: str, type: int = 2) -> Dict[str, Any]:
        """書類一覧取得"""
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}/documents.json"
        
        # 診断で成功した方法と同じにする
        if self.api_version == 'v2' and self.api_key:
            params = {
                'date': date,
                'type': type,
                'Subscription-Key': self.api_key  # 診断で成功した方法
            }
            headers = {}  # ヘッダーは使わない
        else:
            params = {
                'date': date,
                'type': type,
            }
            headers = {}
        
        try:
            logger.info(f"EDINET API呼び出し: {url} (date={date}, type={type})")
            logger.info(f"使用APIキー: {self.api_key[:8] if self.api_key else 'なし'}...")
            logger.info(f"パラメータ: {params}")
            
            response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            
            # デバッグ情報を追加
            logger.info(f"レスポンスステータス: {response.status_code}")
            logger.info(f"レスポンスヘッダー: {dict(response.headers)}")
            logger.info(f"レスポンス内容の最初の500文字: {response.text[:500]}")
            
            response.raise_for_status()
            
            # 空のレスポンスチェック
            if not response.text.strip():
                logger.warning(f"空のレスポンスを受信: {date}")
                return {'metadata': {'status': '200', 'message': 'No data'}, 'results': []}
            
            # JSONパース前にレスポンス内容をチェック
            if response.text.strip().startswith('<'):
                logger.error(f"HTMLレスポンスを受信（エラーページの可能性）: {response.text[:200]}")
                raise Exception(f"HTMLレスポンスを受信。APIエラーまたは認証問題の可能性があります。")
            
            # JSONレスポンスを解析
            try:
                result = response.json()
            except ValueError as e:
                logger.error(f"JSONパースエラー: {e}")
                logger.error(f"レスポンス内容: {response.text}")
                raise Exception(f"JSONパースエラー: {e}")
            
            # EDINET API v2のエラーレスポンス形式をチェック
            if 'statusCode' in result and result['statusCode'] != 200:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"EDINET APIエラー (statusCode: {result['statusCode']}): {error_msg}")
                
                if result['statusCode'] == 401:
                    raise Exception(f"認証エラー: APIキーが無効または期限切れです。APIキー: {self.api_key[:8] if self.api_key else 'なし'}...")
                else:
                    raise Exception(f"EDINET API Error (Code: {result['statusCode']}): {error_msg}")
            
            # 診断で確認された成功時のレスポンス形式
            if 'metadata' in result:
                # 従来の形式
                if result['metadata'].get('status') != '200':
                    error_msg = result['metadata'].get('message', 'Unknown error')
                    logger.error(f"EDINET APIエラー: {error_msg}")
                    raise Exception(f"EDINET API Error: {error_msg}")
                
                result_count = len(result.get('results', []))
                logger.info(f"EDINET API成功: {result_count}件取得")
                return result
            elif 'results' in result:
                # 新しい形式（診断で確認された形式）
                result_count = len(result.get('results', []))
                logger.info(f"EDINET API成功: {result_count}件取得")
                # 従来の形式に変換
                return {
                    'metadata': {'status': '200', 'message': 'Success'},
                    'results': result['results']
                }
            else:
                # 不明な形式
                logger.warning(f"予期しないレスポンス形式: {result}")
                return {'metadata': {'status': '200', 'message': 'Success'}, 'results': []}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"EDINET API呼び出しエラー: {e}")
            logger.error(f"URL: {url}")
            logger.error(f"パラメータ: {params}")
            logger.error(f"ヘッダー: {headers}")
            raise
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            raise
    
    def get_document(self, doc_id: str, doc_type: int = 2) -> bytes:
        """書類ファイル取得"""
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}/documents/{doc_id}"
        params = {
            'type': doc_type,
        }
        
        # APIキーをパラメータとして追加（v2の推奨方法）
        if self.api_key and self.api_version == 'v2':
            params['Subscription-Key'] = self.api_key
        
        # ヘッダー方式も試す（フォールバック）
        headers = {}
        if self.api_key and self.api_version == 'v2':
            headers['Subscription-Key'] = self.api_key
        
        try:
            logger.info(f"EDINET書類取得: {doc_id} (type={doc_type})")
            response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            logger.info(f"EDINET書類取得成功: {doc_id} ({len(response.content)} bytes)")
            return response.content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"EDINET書類取得エラー: {doc_id} - {e}")
            raise