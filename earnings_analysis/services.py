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


# earnings_analysis/services.py（企業情報取得機能追加版）

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
    """EDINET API v2連携サービス（企業情報取得機能付き）"""
    
    def __init__(self):
        # 設定を取得
        self.api_settings = getattr(settings, 'EDINET_API_SETTINGS', {})
        self.api_key = self.api_settings.get('API_KEY')
        
        # 正しいAPI v2のベースURL
        self.base_url = "https://api.edinet-fsa.go.jp"
        
        if not self.api_key:
            raise ValueError("EDINET API キーが設定されていません。settings.py を確認してください。")
        
        # HTTPセッションの設定
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'EarningsAnalysisBot/2.0 (https://kabu-log.net)',
            'Accept': 'application/json',
            'Accept-Language': 'ja',
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

    def get_company_info_by_code(self, company_code: str, days_back: int = 180) -> Optional[Dict]:
        """
        証券コードから企業情報を取得（新機能）
        
        Args:
            company_code: 証券コード（例: "9983"）
            days_back: 何日前まで検索するか
            
        Returns:
            企業情報辞書またはNone
        """
        try:
            logger.info(f"Searching company info for code: {company_code}")
            
            # 過去の書類から企業情報を検索
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            # 週単位でスキップして効率的に検索
            search_dates = []
            current_date = end_date
            while current_date >= start_date:
                if current_date.weekday() < 5:  # 平日のみ
                    search_dates.append(current_date)
                current_date -= timedelta(days=7)  # 1週間ずつ遡る
                
                if len(search_dates) >= 10:  # 最大10日分まで
                    break
            
            # 各日付で検索
            for search_date in search_dates:
                date_str = search_date.strftime('%Y-%m-%d')
                logger.debug(f"Searching documents for {date_str}")
                
                try:
                    documents = self.get_document_list(date_str)
                    
                    # 該当企業の書類を検索
                    for doc in documents:
                        if self._is_target_company_by_code(doc, company_code):
                            company_info = self._extract_company_info_from_document(doc, company_code)
                            if company_info:
                                logger.info(f"Found company info: {company_info['company_name']}")
                                return company_info
                    
                    # レート制限対策
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.warning(f"Error searching date {date_str}: {str(e)}")
                    continue
            
            # 見つからない場合はデフォルト情報を作成
            logger.warning(f"Company {company_code} not found in recent documents, creating default info")
            return self._create_default_company_info(company_code)
            
        except Exception as e:
            logger.error(f"Error getting company info for {company_code}: {str(e)}")
            return self._create_default_company_info(company_code)
    
    def _is_target_company_by_code(self, doc: Dict, target_company_code: str) -> bool:
        """書類が対象企業のものかを証券コードで判定"""
        try:
            # 1. 証券コード（secCode）での直接判定
            sec_code = doc.get('secCode', '') or ''
            if sec_code and sec_code.startswith(target_company_code):
                return True
            
            # 2. 企業名から判定（既知の企業マッピング）
            company_name = doc.get('filerName', '') or ''
            
            # 主要企業のマッピング（拡張版）
            company_mappings = {
                '7203': ['トヨタ', 'TOYOTA', 'トヨタ自動車'],
                '6758': ['ソニー', 'SONY', 'ソニーグループ'],
                '9984': ['ソフトバンク', 'SoftBank', 'ソフトバンクグループ'],
                '6861': ['キーエンス', 'KEYENCE'],
                '8306': ['三菱UFJ', 'MUFG', '三菱ＵＦＪ'],
                '9983': ['ファーストリテイリング', 'Fast Retailing', 'ユニクロ', 'UNIQLO'],  # 追加
                '7974': ['任天堂', 'Nintendo'],
                '6954': ['ファナック', 'FANUC'],
                '4519': ['中外製薬', 'Chugai'],
                '9434': ['ソフトバンク', 'SoftBank'],
                '8035': ['東京エレクトロン', 'Tokyo Electron'],
                '4063': ['信越化学', '信越化学工業'],
                '6981': ['村田製作所', 'Murata'],
                '8058': ['三菱商事'],
                '7741': ['HOYA'],
                '9101': ['日本郵船'],
                '9104': ['商船三井'],
            }
            
            if target_company_code in company_mappings and company_name:
                keywords = company_mappings[target_company_code]
                if any(keyword in company_name for keyword in keywords):
                    logger.debug(f"Found company by name mapping: {company_name}")
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking target company: {str(e)}")
            return False
    
    def _extract_company_info_from_document(self, doc: Dict, company_code: str) -> Optional[Dict]:
        """書類情報から企業情報を抽出"""
        try:
            company_name = doc.get('filerName', '').strip()
            edinet_code = doc.get('edinetCode', '').strip()
            
            if not company_name:
                return None
            
            # 決算月の推定
            fiscal_year_end_month = self._estimate_fiscal_year_end(doc)
            
            company_info = {
                'company_code': company_code,
                'company_name': company_name,
                'edinet_code': edinet_code,
                'fiscal_year_end_month': fiscal_year_end_month,
                'source': 'edinet_api',
                'found_document': {
                    'document_id': doc.get('docID'),
                    'submission_date': doc.get('submitDateTime'),
                    'doc_description': doc.get('docDescription')
                }
            }
            
            return company_info
            
        except Exception as e:
            logger.error(f"Error extracting company info: {str(e)}")
            return None
    
    def _estimate_fiscal_year_end(self, doc: Dict) -> int:
        """書類から決算月を推定"""
        try:
            # period_endから判定
            period_end = doc.get('periodEnd', '')
            if period_end:
                try:
                    period_date = datetime.strptime(period_end, '%Y-%m-%d')
                    return period_date.month
                except ValueError:
                    pass
            
            # 書類説明から判定
            doc_desc = doc.get('docDescription', '') or ''
            
            # 決算月のパターンマッチング
            month_patterns = {
                3: ['3月', '3月期', '第3四半期', 'March'],
                6: ['6月', '6月期', '第2四半期', 'June'],
                9: ['9月', '9月期', '第1四半期', 'September'],
                12: ['12月', '12月期', '第4四半期', 'December']
            }
            
            for month, patterns in month_patterns.items():
                if any(pattern in doc_desc for pattern in patterns):
                    return month
            
            # デフォルトは3月決算
            return 3
            
        except Exception:
            return 3
    
    def _create_default_company_info(self, company_code: str) -> Dict:
        """デフォルトの企業情報を作成"""
        # 既知の企業情報
        known_companies = {
            '9983': {
                'company_name': 'ファーストリテイリング',
                'fiscal_year_end_month': 8,
                'industry': '小売業'
            },
            '7203': {
                'company_name': 'トヨタ自動車',
                'fiscal_year_end_month': 3,
                'industry': '自動車'
            },
            '6758': {
                'company_name': 'ソニーグループ',
                'fiscal_year_end_month': 3,
                'industry': '電機'
            },
            '9984': {
                'company_name': 'ソフトバンクグループ',
                'fiscal_year_end_month': 3,
                'industry': '通信'
            }
        }
        
        if company_code in known_companies:
            known_info = known_companies[company_code]
            return {
                'company_code': company_code,
                'company_name': known_info['company_name'],
                'edinet_code': f'E{company_code.zfill(5)}',  # 仮のEDINETコード
                'fiscal_year_end_month': known_info['fiscal_year_end_month'],
                'source': 'default_mapping',
                'industry': known_info.get('industry', '不明')
            }
        else:
            return {
                'company_code': company_code,
                'company_name': f'企業コード{company_code}',
                'edinet_code': f'E{company_code.zfill(5)}',
                'fiscal_year_end_month': 3,
                'source': 'auto_generated',
                'industry': '不明'
            }

    # 既存のメソッドは変更なし
    def get_document_list(self, date: str, company_code: str = None) -> List[Dict]:
        """指定日の書類一覧を取得（既存メソッド）"""
        try:
            # レート制限対策
            self._wait_for_rate_limit()
            
            # API v2の正しいエンドポイント
            url = f"{self.base_url}/api/v2/documents.json"
            
            # パラメータ設定
            params = {
                'date': date,
                'type': 2,
                'Subscription-Key': self.api_key
            }
            
            logger.info(f"Requesting document list for date: {date}")
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                return []
            
            if 'results' not in data:
                logger.warning(f"Unexpected response structure. Keys: {list(data.keys())}")
                return []
            
            results = data.get('results', [])
            logger.info(f"Found {len(results)} documents for {date}")
            
            # 企業コードでフィルタリング
            if company_code:
                filtered_results = []
                for doc in results:
                    if self._is_target_company_by_code(doc, company_code):
                        filtered_results.append(doc)
                results = filtered_results
                logger.info(f"Filtered to {len(results)} documents for company {company_code}")
            
            # 決算関連書類のみに絞り込み
            earnings_docs = []
            for doc in results:
                doc_type = doc.get('docTypeCode', '')
                doc_description = doc.get('docDescription', '') or ''
                
                if (doc_type in ['120', '130', '140', '350'] or  
                    any(keyword in doc_description.lower() for keyword in   
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

    # その他の既存メソッドはそのまま...
    def get_document_content(self, document_id: str) -> Optional[bytes]:
        """書類の内容を取得（既存メソッド）"""
        try:
            self._wait_for_rate_limit()
            
            url = f"{self.base_url}/api/v2/documents/{document_id}"
            params = {
                'type': 1,
                'Subscription-Key': self.api_key
            }
            
            logger.info(f"Downloading document: {document_id}")
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            content_length = len(response.content)
            logger.info(f"Downloaded {content_length} bytes for document {document_id}")
            
            return response.content
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout downloading document {document_id}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error downloading document {document_id}: {e.response.status_code}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error downloading document {document_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error downloading document {document_id}: {str(e)}")
            return None
    
    def _parse_submission_date(self, submit_datetime: str) -> str:
        """提出日時を日付文字列に変換"""
        try:
            if not submit_datetime:
                return ''
            
            if 'T' in submit_datetime:
                return submit_datetime.split('T')[0]
            elif ' ' in submit_datetime:
                return submit_datetime.split(' ')[0]
            else:
                return submit_datetime
                
        except Exception as e:
            logger.warning(f"Error parsing submission date '{submit_datetime}': {str(e)}")
            return submit_datetime or ''

    # その他の既存メソッドもそのまま残す（省略）
    def search_company_documents(self, company_code: str, days_back: int = 90) -> List[Dict]:
        """特定企業の過去の書類を検索"""
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            all_documents = []
            current_date = start_date
            
            search_dates = []
            while current_date <= end_date:
                if current_date.weekday() < 5:
                    search_dates.append(current_date)
                current_date += timedelta(days=3)
            
            for search_date in search_dates:
                date_str = search_date.strftime('%Y-%m-%d')
                documents = self.get_document_list(date_str, company_code)
                all_documents.extend(documents)
                time.sleep(0.5)
            
            all_documents.sort(
                key=lambda x: x.get('submission_date', ''), 
                reverse=True
            )
            
            logger.info(f"Found {len(all_documents)} documents for company {company_code} in last {days_back} days")
            
            return all_documents[:10]
            
        except Exception as e:
            logger.error(f"Error searching company documents for {company_code}: {str(e)}")
            return []

    def test_api_connection(self) -> bool:
        """API v2接続テスト"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            url = f"{self.base_url}/api/v2/documents.json"
            params = {
                'date': today, 
                'type': 2,
                'Subscription-Key': self.api_key
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            try:
                data = response.json()
            except ValueError:
                logger.error("API returned non-JSON response")
                return False
            
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
            
        except Exception as e:
            logger.error(f"API v2 connection test failed: {str(e)}")
            return False
    
    def get_api_status(self) -> Dict:
        """API v2の状態情報を取得"""
        try:
            if not self.api_key:
                return {
                    'status': 'error',
                    'message': 'APIキーが設定されていません',
                    'api_version': 'v2'
                }
            
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



class CashFlowExtractor:
    """キャッシュフロー計算書からデータを抽出するサービス（改良版）"""
    
    def __init__(self):
        # 実際のXBRL文書に対応したパターンを追加
        self.CF_PATTERNS = {
            'operating_cf': [
                # XBRL特有のタグ名パターン
                r'NetCashProvidedByUsedInOperatingActivities[^>]*>([^<]*)',
                r'CashFlowsFromOperatingActivities[^>]*>([^<]*)',
                r'営業活動によるキャッシュ・フロー[^>]*>([^<]*)',
                
                # 基本的なテキストパターン
                r'営業活動によるキャッシュ・フロー[^\d]*([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'営業CF[^\d]*([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'営業活動による[^\d]*([△▲\-]?\d{1,3}(?:,\d{3})*)',
                
                # 数値のみのパターン（百万円単位）
                r'営業.*?(\d{6,})',  # 6桁以上の数値
                r'Operating.*?(\d{6,})',
                
                # より柔軟なパターン
                r'営業.*キャッシュ.*?([△▲\-]?\d+(?:,\d{3})*)',
                r'cash.*flow.*operating.*?([△▲\-]?\d+(?:,\d{3})*)',
            ],
            'investing_cf': [
                # XBRL特有のタグ名パターン
                r'NetCashProvidedByUsedInInvestmentActivities[^>]*>([^<]*)',
                r'CashFlowsFromInvestingActivities[^>]*>([^<]*)',
                r'投資活動によるキャッシュ・フロー[^>]*>([^<]*)',
                
                # 基本的なテキストパターン
                r'投資活動によるキャッシュ・フロー[^\d]*([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'投資CF[^\d]*([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'投資活動による[^\d]*([△▲\-]?\d{1,3}(?:,\d{3})*)',
                
                # 数値のみのパターン
                r'投資.*?(\d{6,})',
                r'Investing.*?(\d{6,})',
                
                # より柔軟なパターン
                r'投資.*キャッシュ.*?([△▲\-]?\d+(?:,\d{3})*)',
                r'cash.*flow.*investing.*?([△▲\-]?\d+(?:,\d{3})*)',
            ],
            'financing_cf': [
                # XBRL特有のタグ名パターン
                r'NetCashProvidedByUsedInFinancingActivities[^>]*>([^<]*)',
                r'CashFlowsFromFinancingActivities[^>]*>([^<]*)',
                r'財務活動によるキャッシュ・フロー[^>]*>([^<]*)',
                
                # 基本的なテキストパターン
                r'財務活動によるキャッシュ・フロー[^\d]*([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'財務CF[^\d]*([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'財務活動による[^\d]*([△▲\-]?\d{1,3}(?:,\d{3})*)',
                
                # 数値のみのパターン
                r'財務.*?(\d{6,})',
                r'Financing.*?(\d{6,})',
                
                # より柔軟なパターン
                r'財務.*キャッシュ.*?([△▲\-]?\d+(?:,\d{3})*)',
                r'cash.*flow.*financing.*?([△▲\-]?\d+(?:,\d{3})*)',
            ]
        }
    
    def extract_cashflow_data(self, text_content: str) -> Dict[str, Optional[float]]:
        """テキストからキャッシュフローデータを抽出（改良版）"""
        results = {}
        
        logger.info("=== キャッシュフロー抽出デバッグ開始 ===")
        logger.info(f"テキスト長: {len(text_content)}")
        
        # デバッグ用：キーワードの存在確認
        keywords = ['キャッシュ', 'フロー', '営業', '投資', '財務', '活動', 'cash', 'flow']
        for keyword in keywords:
            count = text_content.lower().count(keyword.lower())
            logger.info(f"キーワード '{keyword}': {count}回出現")
        
        # サンプルテキストの表示
        sample_text = text_content[:2000] if len(text_content) > 2000 else text_content
        logger.info(f"サンプルテキスト: {sample_text}")
        
        for cf_type, patterns in self.CF_PATTERNS.items():
            value = None
            matched_pattern = None
            
            logger.info(f"\n--- {cf_type} の抽出開始 ---")
            
            for i, pattern in enumerate(patterns):
                try:
                    matches = re.findall(pattern, text_content, re.IGNORECASE | re.DOTALL)
                    if matches:
                        logger.info(f"パターン {i}: マッチ発見 {matches[:3]}")
                        # 最初にマッチした値を使用
                        value_str = matches[0].strip()
                        if value_str:  # 空文字列でない場合のみ処理
                            value = self._parse_japanese_number(value_str)
                            matched_pattern = pattern
                            logger.info(f"抽出成功: {value_str} -> {value}")
                            break
                except Exception as e:
                    logger.debug(f"パターン {i} でエラー: {str(e)}")
                    continue
            
            if value is None:
                logger.warning(f"{cf_type}: 抽出失敗")
            
            results[cf_type] = value
        
        # フリーキャッシュフローを計算
        if results.get('operating_cf') is not None and results.get('investing_cf') is not None:
            results['free_cf'] = results['operating_cf'] + results['investing_cf']
            logger.info(f"フリーCF計算: {results['free_cf']}")
        
        logger.info(f"=== 最終抽出結果: {results} ===")
        return results
    
    def _parse_japanese_number(self, number_str: str) -> float:
        """日本語の数値表現をfloatに変換（改良版）"""
        try:
            original_str = number_str
            logger.debug(f"数値解析開始: '{original_str}'")
            
            # 空文字やNoneチェック
            if not number_str or number_str.strip() == '':
                raise ValueError("空文字列")
            
            # △や▲マークの処理
            is_negative = any(char in number_str for char in ['△', '▲', '-'])
            
            # XMLタグや特殊文字を除去
            cleaned = re.sub(r'<[^>]*>', '', number_str)  # XMLタグ除去
            cleaned = re.sub(r'[△▲\-,\s百万千万億円¥]', '', cleaned)
            cleaned = re.sub(r'[^\d.]', '', cleaned)  # 数字とピリオド以外除去
            
            logger.debug(f"クリーニング後: '{cleaned}'")
            
            if not cleaned or not re.match(r'^\d+\.?\d*$', cleaned):
                raise ValueError(f"数値として認識できません: {cleaned}")
            
            value = float(cleaned)
            
            # 単位の自動検出と変換
            if '億' in original_str:
                value *= 100  # 億円→百万円に変換
            elif '千万' in original_str:
                value *= 10   # 千万円→百万円に変換
            elif value > 1000000:  # 100万を超える場合は百万円単位と仮定
                pass
            elif value > 1000 and value < 100000:  # 千～10万の場合は百万円に変換
                value = value  # そのまま使用
            
            result = -value if is_negative else value
            logger.debug(f"解析結果: '{original_str}' -> {result}")
            return result
            
        except (ValueError, AttributeError) as e:
            logger.debug(f"数値解析失敗: '{number_str}' - {str(e)}")
            raise ValueError(f"数値解析エラー: {original_str}")

# 5. より詳細なデバッグ用メソッドも追加

    def debug_extract_cashflow_data(self, text_content: str) -> Dict:
        """デバッグ用：すべてのパターンマッチを詳細に確認"""
        debug_results = {
            'text_length': len(text_content),
            'sample_text': text_content[:500],
            'pattern_matches': {},
            'extracted_values': {}
        }
        
        for cf_type, patterns in self.CF_PATTERNS.items():
            debug_results['pattern_matches'][cf_type] = []
            
            for i, pattern in enumerate(patterns):
                matches = re.findall(pattern, text_content, re.IGNORECASE | re.DOTALL)
                if matches:
                    debug_results['pattern_matches'][cf_type].append({
                        'pattern_index': i,
                        'pattern': pattern,
                        'matches': matches[:3]  # 最大3つまで
                    })
        
        # 実際の抽出も実行
        debug_results['extracted_values'] = self.extract_cashflow_data(text_content)
        
        return debug_results


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