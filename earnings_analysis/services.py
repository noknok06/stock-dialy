# earnings_analysis/services.py（EDINET API v2修正版）
import requests
import xml.etree.ElementTree as ET
import zipfile
import io
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from django.conf import settings
import time

logger = logging.getLogger(__name__)


class EDINETAPIService:
    """EDINET API v2連携サービス（修正版）"""
    
    def __init__(self):
        # 設定を取得
        self.api_settings = getattr(settings, 'EDINET_API_SETTINGS', {})
        self.api_key = self.api_settings.get('API_KEY')
        
        # 正しいAPI v2のベースURL
        self.base_url = "https://api.edinet-fsa.go.jp"
        
        if not self.api_key:
            raise ValueError("EDINET API キーが設定されていません。settings.py を確認してください。")
        
        # HTTPセッションの設定（APIキーはヘッダーではなくパラメータで渡す）
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'EarningsAnalysisBot/2.0 (https://kabu-log.net)',
            'Accept': 'application/json',
            'Accept-Language': 'ja',
            # 注意: Subscription-Key はヘッダーではなくURLパラメータで渡す
        })
        
        # レート制限対策の設定
        self.rate_limit_delay = self.api_settings.get('RATE_LIMIT_DELAY', 2)
        self.timeout = self.api_settings.get('TIMEOUT', 120)
        self.last_request_time = 0
    
    def _wait_for_rate_limit(self):
        """レート制限対策の待機"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limit wait: {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def get_document_list(self, date: str, company_code: str = None) -> List[Dict]:
        """
        指定日の書類一覧を取得（API v2対応・修正版）
        
        Args:
            date: 検索日（YYYY-MM-DD）
            company_code: 企業コード（任意）
            
        Returns:
            書類情報のリスト
        """
        try:
            # レート制限対策
            self._wait_for_rate_limit()
            
            # API v2の正しいエンドポイント
            url = f"{self.base_url}/api/v2/documents.json"
            
            # パラメータ設定（API v2の正しい仕様に従って Subscription-Key をパラメータに追加）
            params = {
                'date': date,
                'type': 2,  # 2: 提出書類一覧及びメタデータ
                'Subscription-Key': self.api_key  # 仕様書に従いパラメータで渡す
            }
            
            logger.info(f"Requesting document list for date: {date}")
            logger.debug(f"URL: {url}")
            logger.debug(f"Headers: {dict(self.session.headers)}")
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            # レスポンス詳細をログ出力
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            logger.debug(f"Response content: {response.text[:500]}")
            
            response.raise_for_status()
            
            # JSONレスポンスをパース
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response content: {response.text[:1000]}")
                return []
            
            # API v2のレスポンス構造に対応
            if 'results' not in data:
                logger.warning(f"Unexpected response structure. Keys: {list(data.keys())}")
                # metadata フィールドがある場合もチェック
                if 'metadata' in data:
                    logger.info(f"Metadata: {data['metadata']}")
                return []
            
            results = data.get('results', [])
            logger.info(f"Found {len(results)} documents for {date}")
            
            # 企業コードでフィルタリング
            if company_code:
                filtered_results = []
                for doc in results:
                    if self._is_target_company(doc, company_code):
                        filtered_results.append(doc)
                results = filtered_results
                logger.info(f"Filtered to {len(results)} documents for company {company_code}")
            
            # 決算関連書類のみに絞り込み
            earnings_docs = []
            for doc in results:
                doc_type = doc.get('docTypeCode', '')
                doc_description = doc.get('docDescription', '').lower()
                
                # 決算関連書類の判定
                if (doc_type in ['120', '130', '140', '350'] or  # 有報、四半期、半期、決算短信
                    any(keyword in doc_description for keyword in 
                        ['決算', '四半期', '有価証券報告書', '短信'])):
                    
                    earnings_docs.append({
                        'document_id': doc.get('docID'),
                        'edinet_code': doc.get('edinetCode'),
                        'company_name': doc.get('filerName'),
                        'doc_type_code': doc_type,
                        'doc_description': doc.get('docDescription'),
                        'submission_date': self._parse_submission_date(doc.get('submitDateTime')),
                        'period_start': doc.get('periodStart'),
                        'period_end': doc.get('periodEnd')
                    })
            
            logger.info(f"Found {len(earnings_docs)} earnings-related documents")
            return earnings_docs
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("API v2 authentication failed. Please check your API key.")
            elif e.response.status_code == 403:
                logger.error("API v2 access forbidden. Check your subscription and API key.")
            elif e.response.status_code == 404:
                logger.error("API v2 endpoint not found. Check the URL.")
            else:
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error getting document list: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error getting document list: {str(e)}")
            return []
    
    def _is_target_company(self, doc: Dict, target_company_code: str) -> bool:
        """書類が対象企業のものかを判定（secCode対応版）"""
        try:
            # 1. 証券コード（secCode）での直接判定 - これが最も確実
            sec_code = doc.get('secCode', '') or ''
            if sec_code:
                # secCodeは5桁で末尾に業種コードが付く場合があるため、先頭4桁をチェック
                if sec_code.startswith(target_company_code):
                    logger.debug(f"Found company by secCode: {sec_code} matches {target_company_code}")
                    return True
            
            # 2. 企業名から判定（バックアップ）
            company_name = doc.get('filerName', '') or ''
            
            # 既知の企業コードと企業名のマッピング（拡張版）
            company_mappings = {
                '7203': ['トヨタ', 'TOYOTA', 'トヨタ自動車'],
                '6758': ['ソニー', 'SONY', 'ソニーグループ'],
                '9984': ['ソフトバンク', 'SoftBank', 'ソフトバンクグループ'],
                '6861': ['キーエンス', 'KEYENCE'],
                '8306': ['三菱UFJ', 'MUFG', '三菱ＵＦＪ'],
                '7974': ['任天堂', 'Nintendo'],
                '6954': ['ファナック', 'FANUC'],
                '4519': ['中外製薬', 'Chugai'],
                '9434': ['ソフトバンク', 'SoftBank'],
                '8035': ['東京エレクトロン', 'Tokyo Electron'],
                '4063': ['信越化学', '信越化学工業'],
                '6981': ['村田製作所', 'Murata'],
                '8058': ['三菱商事'],
                '7741': ['HOYA'],
                '9983': ['ファーストリテイリング', 'Fast Retailing'],
            }
            
            # マッピングに基づく判定（バックアップ手段）
            if target_company_code in company_mappings and company_name:
                keywords = company_mappings[target_company_code]
                if any(keyword in company_name for keyword in keywords):
                    logger.debug(f"Found company by name mapping: {company_name}")
                    return True
            
            # 3. EDINETコードからの推定（最後の手段）
            edinet_code = doc.get('edinetCode', '') or ''
            if edinet_code and target_company_code in edinet_code:
                logger.debug(f"Found company by edinetCode: {edinet_code}")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking target company: {str(e)}")
            logger.debug(f"Document data: {doc}")
            return False
    
    def get_document_content(self, document_id: str) -> Optional[bytes]:
        """
        書類の内容を取得（ZIP形式、API v2対応・修正版）
        
        Args:
            document_id: 書類管理番号
            
        Returns:
            書類データ（バイト列）
        """
        try:
            # レート制限対策
            self._wait_for_rate_limit()
            
            # API v2の正しい書類取得エンドポイント
            url = f"{self.base_url}/api/v2/documents/{document_id}"
            params = {
                'type': 1,  # 1: 提出書類本体
                'Subscription-Key': self.api_key  # 仕様書に従いパラメータで渡す
            }
            
            logger.info(f"Downloading document: {document_id}")
            logger.debug(f"URL: {url}")
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            content_length = len(response.content)
            logger.info(f"Downloaded {content_length} bytes for document {document_id}")
            
            return response.content
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout downloading document {document_id}")
            return None
    
    def _parse_submission_date(self, submit_datetime: str) -> str:
        """提出日時を日付文字列に変換"""
        try:
            if not submit_datetime:
                return ''
            
            # "2025-06-17 11:00" → "2025-06-17"
            # "2025-06-17T11:00:00" → "2025-06-17"
            if 'T' in submit_datetime:
                return submit_datetime.split('T')[0]
            elif ' ' in submit_datetime:
                return submit_datetime.split(' ')[0]
            else:
                return submit_datetime
                
        except Exception as e:
            logger.warning(f"Error parsing submission date '{submit_datetime}': {str(e)}")
            return submit_datetime or ''
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error downloading document {document_id}: {e.response.status_code}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error downloading document {document_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error downloading document {document_id}: {str(e)}")
            return None
    
    def search_company_documents(self, company_code: str, days_back: int = 90) -> List[Dict]:
        """
        特定企業の過去の書類を検索
        
        Args:
            company_code: 企業コード
            days_back: 何日前まで検索するか
            
        Returns:
            書類リスト
        """
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            all_documents = []
            current_date = start_date
            
            # 日付を遡って検索（効率化のため週単位でスキップ）
            search_dates = []
            while current_date <= end_date:
                # 平日のみ検索（土日は決算書類の提出が少ない）
                if current_date.weekday() < 5:  # 月〜金曜日
                    search_dates.append(current_date)
                current_date += timedelta(days=3)  # 3日ずつスキップして効率化
            
            # 検索実行
            for search_date in search_dates:
                date_str = search_date.strftime('%Y-%m-%d')
                documents = self.get_document_list(date_str, company_code)
                all_documents.extend(documents)
                
                # レート制限対策
                time.sleep(0.5)
            
            # 日付順でソート（新しい順）
            all_documents.sort(
                key=lambda x: x.get('submission_date', ''), 
                reverse=True
            )
            
            logger.info(f"Found {len(all_documents)} documents for company {company_code} in last {days_back} days")
            
            return all_documents[:10]  # 最新10件まで
            
        except Exception as e:
            logger.error(f"Error searching company documents for {company_code}: {str(e)}")
            return []
    
    def test_api_connection(self) -> bool:
        """API v2接続テスト（修正版）"""
        try:
            # 今日の書類一覧を取得してテスト
            today = datetime.now().strftime('%Y-%m-%d')
            url = f"{self.base_url}/api/v2/documents.json"
            params = {
                'date': today, 
                'type': 2,
                'Subscription-Key': self.api_key  # 仕様書に従いパラメータで渡す
            }
            
            logger.info(f"Testing API connection to: {url}")
            
            response = self.session.get(url, params=params, timeout=10)
            
            logger.debug(f"Test response status: {response.status_code}")
            logger.debug(f"Test response content: {response.text[:500]}")
            
            response.raise_for_status()
            
            try:
                data = response.json()
            except ValueError:
                logger.error("API returned non-JSON response")
                return False
            
            # API v2のレスポンス構造を確認
            if 'results' in data:
                result_count = len(data.get('results', []))
                logger.info(f"API v2 connection test successful. Found {result_count} documents for today")
                return True
            elif 'metadata' in data:
                logger.info(f"API v2 connection successful. Metadata: {data['metadata']}")
                return True
            else:
                logger.warning(f"Unexpected API v2 response structure: {list(data.keys())}")
                return False
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("API v2 authentication failed. Please check your API key.")
            elif e.response.status_code == 403:
                logger.error("API v2 access forbidden. Check your subscription.")
            else:
                logger.error(f"API v2 HTTP error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"API v2 connection test failed: {str(e)}")
            return False
    
    def get_api_status(self) -> Dict:
        """API v2の状態情報を取得（修正版）"""
        try:
            # APIキーが設定されているかチェック
            if not self.api_key:
                return {
                    'status': 'error',
                    'message': 'APIキーが設定されていません',
                    'api_version': 'v2'
                }
            
            # 接続テスト
            if self.test_api_connection():
                return {
                    'status': 'ok',
                    'message': 'API v2に正常に接続できます',
                    'api_version': 'v2',
                    'api_key_length': len(self.api_key),
                    'base_url': self.base_url
                }
            else:
                return {
                    'status': 'error',
                    'message': 'API v2への接続に失敗しました',
                    'api_version': 'v2'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'APIステータス取得エラー: {str(e)}',
                'api_version': 'v2'
            }
            
# 以下のクラスは変更なし（既存のまま）
class XBRLTextExtractor:
    """XBRL文書からテキストを抽出するサービス（変更なし）"""
    
    def __init__(self):
        self.namespaces = {
            'xbrli': 'http://www.xbrl.org/2003/instance',
            'ix': 'http://www.xbrl.org/2013/inlineXBRL',
            'xlink': 'http://www.w3.org/1999/xlink'
        }
    
    def extract_text_from_zip(self, zip_data: bytes) -> Dict[str, str]:
        """
        ZIP形式のXBRL文書からテキストを抽出（改良版）
        
        Args:
            zip_data: ZIP形式のバイト列
            
        Returns:
            セクション別のテキスト辞書
        """
        extracted_texts = {}
        
        try:
            logger.info(f"Extracting text from ZIP file ({len(zip_data)} bytes)")
            
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_file:
                # ファイル一覧をログ出力
                file_list = zip_file.filelist
                logger.info(f"ZIP contains {len(file_list)} files")
                
                for file_info in file_list:
                    filename = file_info.filename
                    logger.debug(f"Processing file: {filename}")
                    
                    # 処理対象ファイルの判定
                    if self._should_process_file(filename):
                        try:
                            with zip_file.open(file_info) as file:
                                content = file.read()
                                
                                # エンコーディングを推定して読み込み
                                text_content = self._decode_content(content)
                                if text_content:
                                    # セクションごとにテキストを抽出
                                    section_texts = self._extract_sections_enhanced(text_content, filename)
                                    extracted_texts.update(section_texts)
                                    
                        except Exception as e:
                            logger.warning(f"Error processing file {filename}: {str(e)}")
                            continue
            
            logger.info(f"Extracted {len(extracted_texts)} sections")
            return extracted_texts
            
        except zipfile.BadZipFile:
            logger.error("Invalid ZIP file format")
            return {}
        except Exception as e:
            logger.error(f"Error extracting text from ZIP: {str(e)}")
            return {}
    
    def _should_process_file(self, filename: str) -> bool:
        """処理対象ファイルかを判定"""
        # 処理対象の拡張子
        target_extensions = ['.xbrl', '.xml', '.htm', '.html']
        
        # 除外するファイル
        exclude_patterns = [
            'manifest.xml',
            'metadata.xml',
            '/style/',
            '/css/',
            '/js/',
            '/images/',
            'PublicDoc'  # 公開用文書は除外
        ]
        
        # 拡張子チェック
        if not any(filename.lower().endswith(ext) for ext in target_extensions):
            return False
        
        # 除外パターンチェック
        if any(pattern in filename for pattern in exclude_patterns):
            return False
        
        return True
    
    def _decode_content(self, content: bytes) -> Optional[str]:
        """コンテンツのエンコーディングを推定して文字列に変換"""
        try:
            # UTF-8を最初に試行
            return content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                # Shift_JISを試行
                return content.decode('shift_jis')
            except UnicodeDecodeError:
                try:
                    # EUC-JPを試行
                    return content.decode('euc-jp')
                except UnicodeDecodeError:
                    # エラー無視で強制デコード
                    return content.decode('utf-8', errors='ignore')
    
    def _extract_sections_enhanced(self, content: str, filename: str) -> Dict[str, str]:
        """HTML/XBRL文書からセクション別にテキストを抽出（強化版）"""
        sections = {}
        
        try:
            # HTMLタグを除去してテキストのみ抽出
            clean_text = self._clean_html_enhanced(content)
            
            # ファイル名から書類種別を推定
            doc_type = self._identify_document_type(filename, content)
            
            # 書類種別に応じたセクション抽出
            if doc_type == 'earnings_summary':
                sections.update(self._extract_earnings_summary_sections(clean_text))
            elif doc_type == 'quarterly_report':
                sections.update(self._extract_quarterly_sections(clean_text))
            elif doc_type == 'annual_report':
                sections.update(self._extract_annual_sections(clean_text))
            else:
                # 汎用的なセクション抽出
                sections.update(self._extract_generic_sections(clean_text))
            
            # セクションが見つからない場合は全文を使用
            if not sections:
                sections['full_text'] = clean_text[:10000]  # 最初の10000文字
                logger.warning(f"No sections found, using full text for {filename}")
            
            return sections
            
        except Exception as e:
            logger.error(f"Error extracting sections from {filename}: {str(e)}")
            return {'full_text': content[:5000]}
    
    def _identify_document_type(self, filename: str, content: str) -> str:
        """ファイル名と内容から書類種別を識別"""
        filename_lower = filename.lower()
        content_lower = content.lower()
        
        # 決算短信
        if any(keyword in filename_lower for keyword in ['tanshin', '短信', 'summary']):
            return 'earnings_summary'
        
        # 四半期報告書
        if any(keyword in filename_lower for keyword in ['quarterly', '四半期']):
            return 'quarterly_report'
        
        # 有価証券報告書
        if any(keyword in filename_lower for keyword in ['yuho', '有価証券', 'securities']):
            return 'annual_report'
        
        # 内容からも判定
        if '決算短信' in content_lower:
            return 'earnings_summary'
        elif '四半期' in content_lower:
            return 'quarterly_report'
        elif '有価証券報告書' in content_lower:
            return 'annual_report'
        
        return 'unknown'
    
    def _extract_earnings_summary_sections(self, text: str) -> Dict[str, str]:
        """決算短信特有のセクション抽出"""
        sections = {}
        
        # 決算短信の主要セクション
        patterns = {
            'financial_highlights': [
                r'連結業績.*?(?=\n\s*[１２３４５]|\n\s*\d+\.|$)',
                r'業績概要.*?(?=\n\s*[１２３４５]|\n\s*\d+\.|$)',
            ],
            'management_discussion': [
                r'経営成績.*?(?=\n\s*[１２３４５]|\n\s*\d+\.|$)',
                r'経営者による.*?(?=\n\s*[１２３４５]|\n\s*\d+\.|$)',
            ],
            'cash_flow_statement': [
                r'キャッシュ・フロー.*?(?=\n\s*[１２３４５]|\n\s*\d+\.|$)',
                r'資金の状況.*?(?=\n\s*[１２３４５]|\n\s*\d+\.|$)',
            ],
            'outlook': [
                r'業績予想.*?(?=\n\s*[１２３４５]|\n\s*\d+\.|$)',
                r'今後の見通し.*?(?=\n\s*[１２３４５]|\n\s*\d+\.|$)',
            ]
        }
        
        for section_name, section_patterns in patterns.items():
            for pattern in section_patterns:
                matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                if matches:
                    sections[section_name] = matches[0].strip()
                    break
        
        return sections
    
    def _extract_quarterly_sections(self, text: str) -> Dict[str, str]:
        """四半期報告書特有のセクション抽出"""
        # 基本的には汎用セクション抽出を使用
        return self._extract_generic_sections(text)
    
    def _extract_annual_sections(self, text: str) -> Dict[str, str]:
        """有価証券報告書特有のセクション抽出"""
        # より詳細なセクション抽出を実装可能
        return self._extract_generic_sections(text)
    
    def _extract_generic_sections(self, text: str) -> Dict[str, str]:
        """汎用的なセクション抽出"""
        sections = {}
        
        section_patterns = {
            'business_overview': [
                r'事業の状況.*?(?=\n\s*[１２３４５６７８９]|\n\s*第|$)',
                r'経営方針.*?(?=\n\s*[１２３４５６７８９]|\n\s*第|$)',
            ],
            'management_analysis': [
                r'経営者による財政状態.*?(?=\n\s*[１２３４５６７８９]|\n\s*第|$)',
                r'経営成績.*?(?=\n\s*[１２３４５６７８９]|\n\s*第|$)',
            ],
            'risk_factors': [
                r'事業等のリスク.*?(?=\n\s*[１２３４５６７８９]|\n\s*第|$)',
                r'リスク要因.*?(?=\n\s*[１２３４５６７８９]|\n\s*第|$)',
            ],
            'cashflow_analysis': [
                r'キャッシュ・フロー.*?(?=\n\s*[１２３４５６７８９]|\n\s*第|$)',
                r'資金の状況.*?(?=\n\s*[１２３４５６７８９]|\n\s*第|$)',
            ]
        }
        
        for section_name, patterns in section_patterns.items():
            section_text = ""
            for pattern in patterns:
                matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                if matches:
                    section_text = matches[0]
                    break
            
            if section_text:
                sections[section_name] = section_text.strip()
        
        return sections
    
    def _clean_html_enhanced(self, html_content: str) -> str:
        """HTMLタグを除去してテキストのみ抽出（強化版）"""
        try:
            # HTMLタグを除去
            text = re.sub(r'<[^>]+>', '', html_content)
            
            # XMLの名前空間も除去
            text = re.sub(r'xmlns[^=]*="[^"]*"', '', text)
            
            # 特殊文字をクリーンアップ
            text = re.sub(r'&nbsp;', ' ', text)
            text = re.sub(r'&[a-zA-Z0-9]+;', '', text)
            
            # 複数の空白を単一の空白に
            text = re.sub(r'\s+', ' ', text)
            
            # 不要な改行や空白を整理
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)
            
            return text
            
        except Exception as e:
            logger.error(f"Error cleaning HTML: {str(e)}")
            return html_content


# 以下のクラスも変更なし（既存のまま）
class CashFlowExtractor:
    """キャッシュフロー計算書からデータを抽出（改良版）"""
    
    def __init__(self):
        # より多様なパターンを追加
        self.CF_PATTERNS = {
            'operating_cf': [
                r'営業活動によるキャッシュ・フロー.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'営業CF.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'営業活動による.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'Operating\s+Cash\s+Flow.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'営業キャッシュ・フロー.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
            ],
            'investing_cf': [
                r'投資活動によるキャッシュ・フロー.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'投資CF.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'投資活動による.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'Investing\s+Cash\s+Flow.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'投資キャッシュ・フロー.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
            ],
            'financing_cf': [
                r'財務活動によるキャッシュ・フロー.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'財務CF.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'財務活動による.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'Financing\s+Cash\s+Flow.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'財務キャッシュ・フロー.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
            ]
        }
    
    def extract_cashflow_data(self, text_content: str) -> Dict[str, Optional[float]]:
        """テキストからキャッシュフローデータを抽出（改良版）"""
        results = {}
        
        logger.debug("Extracting cashflow data from text")
        
        for cf_type, patterns in self.CF_PATTERNS.items():
            value = None
            
            for pattern in patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                if matches:
                    try:
                        # 最初にマッチした値を使用
                        value_str = matches[0]
                        value = self._parse_japanese_number(value_str)
                        logger.debug(f"Found {cf_type}: {value_str} -> {value}")
                        break
                    except ValueError as e:
                        logger.debug(f"Failed to parse {cf_type} value '{matches[0]}': {str(e)}")
                        continue
            
            results[cf_type] = value
        
        # フリーキャッシュフローを計算
        if results.get('operating_cf') is not None and results.get('investing_cf') is not None:
            results['free_cf'] = results['operating_cf'] + results['investing_cf']
            logger.debug(f"Calculated free CF: {results['free_cf']}")
        
        # 抽出結果をログ出力
        logger.info(f"Extracted CF data: {results}")
        
        return results
    
    def _parse_japanese_number(self, number_str: str) -> float:
        """日本語の数値表現をfloatに変換（改良版）"""
        try:
            # △や▲マークの処理
            is_negative = number_str.startswith(('△', '▲', '-'))
            
            # 数値部分のみ抽出
            number_str = re.sub(r'[△▲\-,\s百万千万億]', '', number_str)
            
            if not number_str or not number_str.isdigit():
                raise ValueError(f"Cannot extract numeric value from: {number_str}")
            
            value = float(number_str)
            
            # 単位を考慮（百万円単位での表記が多い）
            # ここでは百万円単位として扱う
            
            return -value if is_negative else value
            
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Cannot parse number: {number_str}")


class EarningsNotificationService:
    """決算通知サービス（簡略版）"""
    
    def __init__(self):
        self.edinet_service = EDINETAPIService()
    
    def check_upcoming_earnings(self, days_ahead: int = 7) -> List[Dict]:
        """
        今後N日以内の決算発表予定をチェック（簡略版）
        
        Args:
            days_ahead: 何日先まで確認するか
            
        Returns:
            決算予定のリスト
        """
        from .models import CompanyEarnings, EarningsAlert
        
        upcoming_earnings = []
        
        # アラート設定のある企業を取得
        alerts = EarningsAlert.objects.filter(
            is_enabled=True,
            alert_type='earnings_release'
        ).select_related('company', 'user')
        
        for alert in alerts:
            company = alert.company
            
            # 決算予定日を推定（簡易版）
            estimated_date = self._estimate_earnings_date(company)
            
            if estimated_date:
                days_until = (estimated_date - datetime.now().date()).days
                
                if 0 <= days_until <= alert.days_before_earnings:
                    upcoming_earnings.append({
                        'user': alert.user,
                        'company': company,
                        'estimated_date': estimated_date,
                        'days_until': days_until
                    })
        
        return upcoming_earnings
    
    def _estimate_earnings_date(self, company) -> Optional[datetime]:
        """企業の次回決算発表日を推定（簡易版）"""
        try:
            current_date = datetime.now().date()
            fiscal_month = company.fiscal_year_end_month
            
            # 決算月の翌月15日頃と仮定
            if fiscal_month == 12:
                next_month = 1
                year = current_date.year + 1
            else:
                next_month = fiscal_month + 1
                year = current_date.year
            
            estimated_date = datetime(year, next_month, 15).date()
            
            # 過去の日付の場合は来年に調整
            if estimated_date < current_date:
                estimated_date = datetime(year + 1, next_month, 15).date()
            
            return estimated_date
            
        except ValueError:
            return None