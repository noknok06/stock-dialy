# edinet_service.py
"""
EDINET API サービスクラス（正式版）

役割:
1. 指定日の全書類取得
2. 特定企業の書類検索  
3. 書類ダウンロード
4. データ形式の統一化
"""

import requests
import time
import json
import zipfile
import io
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EDINETService:
    """EDINET API サービスクラス"""
    
    def __init__(self, api_key: str, rate_limit_delay: float = 2.0):
        """
        EDINET APIサービスの初期化
        
        Args:
            api_key: EDINET APIキー
            rate_limit_delay: API呼び出し間隔（秒）
        """
        self.api_key = api_key
        self.base_url = "https://api.edinet-fsa.go.jp"
        self.rate_limit_delay = rate_limit_delay
        self.timeout = 120
        self.last_request_time = 0
        
        # HTTPセッション設定
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'EDINET-Service/1.0',
            'Accept': 'application/json',
            'Accept-Language': 'ja',
        })
        
        # 企業コードマッピング
        self.company_mappings = {
            '7203': ['トヨタ', 'TOYOTA', 'トヨタ自動車'],
            '6758': ['ソニー', 'SONY', 'ソニーグループ'],
            '9984': ['ソフトバンク', 'SoftBank', 'ソフトバンクグループ'],
            '6861': ['キーエンス', 'KEYENCE'],
            '9983': ['ファーストリテイリング', 'Fast Retailing', 'ユニクロ'],
            '9101': ['日本郵船'],
            '9104': ['商船三井'],
            '4519': ['中外製薬'],
            '9434': ['ソフトバンク'],
        }
        
        logger.info(f"EDINET Service 初期化完了 - APIキー: ***{api_key[-4:]}")
    
    def _wait_for_rate_limit(self):
        """レート制限対策の待機"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f"レート制限待機: {sleep_time:.2f}秒")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def test_connection(self) -> bool:
        """
        API接続テスト
        
        Returns:
            bool: 接続成功の場合True
        """
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
            
            data = response.json()
            
            if 'results' in data:
                count = len(data.get('results', []))
                logger.info(f"API接続成功 - 今日の書類数: {count}件")
                return True
            else:
                logger.warning(f"予期しないレスポンス構造: {list(data.keys())}")
                return False
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("API認証エラー: APIキーを確認してください")
            elif e.response.status_code == 403:
                logger.error("APIアクセス禁止: サブスクリプションとAPIキーを確認してください")
            else:
                logger.error(f"HTTPエラー {e.response.status_code}: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"API接続テストエラー: {str(e)}")
            return False
    
    # ========================================
    # 1. 指定日の全書類取得
    # ========================================
    
    def get_documents_by_date(self, date: str, include_all_types: bool = False) -> List[List[str]]:
        """
        指定日の書類一覧を取得
        
        Args:
            date: 取得日 (YYYY-MM-DD形式)
            include_all_types: 全書類種別を含むか（Falseの場合は決算関連のみ）
            
        Returns:
            List[List[str]]: [書類ID, 企業名, 書類名, 提出日, 書類種別, 証券コード] の配列
        """
        logger.info(f"指定日の書類取得開始: {date}")
        
        try:
            self._wait_for_rate_limit()
            
            url = f"{self.base_url}/api/v2/documents.json"
            params = {
                'date': date,
                'type': 2,
                'Subscription-Key': self.api_key
            }
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            if 'results' not in data:
                logger.error("APIレスポンスに'results'が含まれていません")
                return []
            
            results = data.get('results', [])
            logger.info(f"API取得件数: {len(results)}件")
            
            # 書類情報を二次元配列に変換
            documents = []
            for doc in results:
                doc_info = self._parse_document_info(doc)
                
                # 書類種別でフィルタリング（必要に応じて）
                if not include_all_types and not self._is_earnings_related(doc_info):
                    continue
                
                documents.append(doc_info)
            
            if include_all_types:
                logger.info(f"全書類取得完了: {len(documents)}件")
            else:
                logger.info(f"決算関連書類取得完了: {len(documents)}件")
            
            return documents
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ネットワークエラー: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"書類取得エラー: {str(e)}")
            return []
    
    def get_documents_by_date_range(self, start_date: str, end_date: str, 
                                   include_all_types: bool = False) -> List[List[str]]:
        """
        日付範囲で書類一覧を取得
        
        Args:
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)
            include_all_types: 全書類種別を含むか
            
        Returns:
            List[List[str]]: 書類情報の配列
        """
        logger.info(f"日付範囲での書類取得: {start_date} ～ {end_date}")
        
        all_documents = []
        
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            current_date = start
            while current_date <= end:
                date_str = current_date.strftime('%Y-%m-%d')
                
                # 平日のみ検索（土日は書類が少ないため）
                if current_date.weekday() < 5:
                    daily_docs = self.get_documents_by_date(date_str, include_all_types)
                    all_documents.extend(daily_docs)
                    logger.info(f"{date_str}: {len(daily_docs)}件")
                
                current_date += timedelta(days=1)
            
            logger.info(f"日付範囲取得完了: 合計{len(all_documents)}件")
            return all_documents
            
        except ValueError as e:
            logger.error(f"日付フォーマットエラー: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"日付範囲取得エラー: {str(e)}")
            return []
    
    # ========================================
    # 2. 特定企業の書類検索
    # ========================================
    
    def search_company_documents(self, company_code: str, days_back: int = 30, 
                                max_results: int = 10) -> List[List[str]]:
        """
        特定企業の書類を検索
        
        Args:
            company_code: 企業コード（証券コード）
            days_back: 何日前まで検索するか
            max_results: 最大取得件数
            
        Returns:
            List[List[str]]: 該当企業の書類情報配列
        """
        logger.info(f"企業書類検索開始: {company_code} (過去{days_back}日)")
        
        company_documents = []
        end_date = datetime.now().date()
        
        # 検索日付を生成（平日優先）
        search_dates = self._generate_search_dates(end_date, days_back)
        
        for i, search_date in enumerate(search_dates, 1):
            if len(company_documents) >= max_results:
                logger.info(f"最大件数({max_results})に到達したため検索終了")
                break
            
            date_str = search_date.strftime('%Y-%m-%d')
            logger.debug(f"検索中: {date_str} ({i}/{len(search_dates)})")
            
            try:
                # 指定日の全書類を取得
                daily_docs = self.get_documents_by_date(date_str, include_all_types=True)
                
                # 対象企業の書類をフィルタリング
                for doc in daily_docs:
                    if self._is_target_company(doc, company_code):
                        company_documents.append(doc)
                        logger.info(f"発見: {doc[2][:50]}... ({date_str})")
                
            except Exception as e:
                logger.warning(f"{date_str} の検索でエラー: {str(e)}")
                continue
        
        logger.info(f"企業書類検索完了: {len(company_documents)}件")
        return company_documents[:max_results]
    
    def search_company_by_name(self, company_name: str, days_back: int = 30,
                              max_results: int = 10) -> List[List[str]]:
        """
        企業名で書類を検索
        
        Args:
            company_name: 企業名（部分一致）
            days_back: 検索期間
            max_results: 最大取得件数
            
        Returns:
            List[List[str]]: 該当企業の書類情報配列
        """
        logger.info(f"企業名検索開始: {company_name}")
        
        matching_documents = []
        end_date = datetime.now().date()
        search_dates = self._generate_search_dates(end_date, days_back)
        
        for search_date in search_dates:
            if len(matching_documents) >= max_results:
                break
            
            date_str = search_date.strftime('%Y-%m-%d')
            
            try:
                daily_docs = self.get_documents_by_date(date_str, include_all_types=True)
                
                for doc in daily_docs:
                    if company_name.lower() in doc[1].lower():  # 企業名で部分一致
                        matching_documents.append(doc)
                        
            except Exception as e:
                logger.warning(f"{date_str} の企業名検索でエラー: {str(e)}")
                continue
        
        logger.info(f"企業名検索完了: {len(matching_documents)}件")
        return matching_documents[:max_results]
    
    # ========================================
    # 3. 書類ダウンロード
    # ========================================
    
    def download_document(self, document_id: str, save_to_file: bool = False, 
                         filename: str = None) -> Optional[bytes]:
        """
        書類をダウンロード
        
        Args:
            document_id: 書類ID
            save_to_file: ファイルに保存するか
            filename: 保存ファイル名（未指定時は自動生成）
            
        Returns:
            Optional[bytes]: ダウンロードしたデータ（失敗時はNone）
        """
        logger.info(f"書類ダウンロード開始: {document_id}")
        
        try:
            self._wait_for_rate_limit()
            
            url = f"{self.base_url}/api/v2/documents/{document_id}"
            params = {
                'type': 1,
                'Subscription-Key': self.api_key
            }
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            content = response.content
            size_mb = len(content) / (1024 * 1024)
            logger.info(f"ダウンロード成功: {size_mb:.2f} MB")
            
            # ファイル保存
            if save_to_file:
                if filename is None:
                    filename = f"edinet_{document_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                
                with open(filename, 'wb') as f:
                    f.write(content)
                logger.info(f"ファイル保存: {filename}")
            
            return content
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP エラー {e.response.status_code}: {document_id}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"ネットワークエラー: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"ダウンロードエラー: {str(e)}")
            return None
    
    def download_multiple_documents(self, document_ids: List[str], 
                                   save_to_files: bool = False) -> Dict[str, bytes]:
        """
        複数書類を一括ダウンロード
        
        Args:
            document_ids: 書類IDのリスト
            save_to_files: ファイルに保存するか
            
        Returns:
            Dict[str, bytes]: {書類ID: データ} の辞書
        """
        logger.info(f"複数書類ダウンロード開始: {len(document_ids)}件")
        
        results = {}
        
        for i, doc_id in enumerate(document_ids, 1):
            logger.info(f"ダウンロード中 ({i}/{len(document_ids)}): {doc_id}")
            
            content = self.download_document(doc_id, save_to_files)
            if content:
                results[doc_id] = content
            
            # レート制限対策で待機
            if i < len(document_ids):
                time.sleep(self.rate_limit_delay)
        
        logger.info(f"一括ダウンロード完了: {len(results)}/{len(document_ids)}件成功")
        return results
    
    def analyze_zip_content(self, zip_data: bytes) -> Dict[str, any]:
        """
        ZIPファイルの内容を分析
        
        Args:
            zip_data: ZIPファイルのバイナリデータ
            
        Returns:
            Dict: 分析結果
        """
        try:
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_file:
                file_list = zip_file.filelist
                
                # ファイル種別を分析
                file_types = {}
                total_size = 0
                xbrl_files = []
                
                for file_info in file_list:
                    filename = file_info.filename
                    size = file_info.file_size
                    extension = filename.split('.')[-1].lower() if '.' in filename else 'unknown'
                    
                    file_types[extension] = file_types.get(extension, 0) + 1
                    total_size += size
                    
                    if extension in ['xbrl', 'xml', 'htm', 'html']:
                        xbrl_files.append({
                            'filename': filename,
                            'size': size,
                            'extension': extension
                        })
                
                return {
                    'total_files': len(file_list),
                    'total_size_mb': round(total_size / (1024 * 1024), 2),
                    'file_types': file_types,
                    'xbrl_files': xbrl_files,
                    'has_xbrl': len(xbrl_files) > 0
                }
                
        except Exception as e:
            logger.error(f"ZIP分析エラー: {str(e)}")
            return {}
    
    # ========================================
    # 4. ユーティリティメソッド
    # ========================================
    
    def _parse_document_info(self, doc: Dict) -> List[str]:
        """
        APIレスポンスから書類情報を抽出
        
        Args:
            doc: APIレスポンスの個別書類データ
            
        Returns:
            List[str]: [書類ID, 企業名, 書類名, 提出日, 書類種別, 証券コード]
        """
        return [
            doc.get('docID', ''),
            doc.get('filerName', ''),
            doc.get('docDescription', ''),
            self._parse_submission_date(doc.get('submitDateTime', '')),
            doc.get('docTypeCode', ''),
            doc.get('secCode', ''),
        ]
    
    def _parse_submission_date(self, datetime_str: str) -> str:
        """提出日時から日付部分を抽出"""
        if not datetime_str:
            return ''
        
        if 'T' in datetime_str:
            return datetime_str.split('T')[0]
        elif ' ' in datetime_str:
            return datetime_str.split(' ')[0]
        else:
            return datetime_str
    
    def _is_earnings_related(self, doc_info: List[str]) -> bool:
        """
        決算関連書類かどうかを判定
        
        Args:
            doc_info: 書類情報配列
            
        Returns:
            bool: 決算関連の場合True
        """
        doc_type = doc_info[4]  # 書類種別
        doc_description = doc_info[2].lower()  # 書類名
        
        # 決算関連の書類種別
        earnings_types = ['120', '130', '140', '350']
        
        # 決算関連キーワード
        earnings_keywords = ['決算', '四半期', '有価証券報告書', '短信', 'quarterly', 'annual']
        
        return (doc_type in earnings_types or 
                any(keyword in doc_description for keyword in earnings_keywords))
    
    def _is_target_company(self, doc_info: List[str], company_code: str) -> bool:
        """
        対象企業の書類かどうかを判定
        
        Args:
            doc_info: 書類情報配列
            company_code: 対象企業コード
            
        Returns:
            bool: 対象企業の場合True
        """
        sec_code = doc_info[5]  # 証券コード
        company_name = doc_info[1]  # 企業名
        
        # 1. 証券コードでの直接判定
        if sec_code and sec_code.startswith(company_code):
            return True
        
        # 2. 企業名での判定
        if company_code in self.company_mappings:
            keywords = self.company_mappings[company_code]
            if any(keyword in company_name for keyword in keywords):
                return True
        
        return False
    
    def _generate_search_dates(self, end_date, days_back: int) -> List:
        """検索対象日付を生成（平日優先）"""
        search_dates = []
        
        for i in range(days_back):
            date = end_date - timedelta(days=i)
            search_dates.append(date)
        
        # 平日を優先的にソート
        weekdays = [d for d in search_dates if d.weekday() < 5]
        weekends = [d for d in search_dates if d.weekday() >= 5]
        
        return weekdays + weekends
    
    # ========================================
    # 5. 便利メソッド
    # ========================================
    
    def get_company_latest_documents(self, company_code: str, limit: int = 5) -> List[List[str]]:
        """
        特定企業の最新書類を取得（決算関連のみ）
        
        Args:
            company_code: 企業コード
            limit: 取得件数
            
        Returns:
            List[List[str]]: 最新順の書類情報配列
        """
        all_docs = self.search_company_documents(company_code, days_back=180, max_results=50)
        
        # 決算関連のみフィルタリング
        earnings_docs = [doc for doc in all_docs if self._is_earnings_related(doc)]
        
        # 提出日でソート（新しい順）
        earnings_docs.sort(key=lambda x: x[3], reverse=True)
        
        return earnings_docs[:limit]
    
    def search_documents_by_type(self, doc_type: str, date: str) -> List[List[str]]:
        """
        書類種別で検索
        
        Args:
            doc_type: 書類種別コード（120, 130, 140, 350など）
            date: 検索日
            
        Returns:
            List[List[str]]: 該当書類の配列
        """
        all_docs = self.get_documents_by_date(date, include_all_types=True)
        return [doc for doc in all_docs if doc[4] == doc_type]
    
    def get_statistics(self, date: str) -> Dict[str, int]:
        """
        指定日の書類統計を取得
        
        Args:
            date: 統計取得日
            
        Returns:
            Dict[str, int]: 統計情報
        """
        all_docs = self.get_documents_by_date(date, include_all_types=True)
        
        stats = {
            'total_documents': len(all_docs),
            'earnings_related': len([doc for doc in all_docs if self._is_earnings_related(doc)]),
            'by_type': {}
        }
        
        # 書類種別ごとの統計
        for doc in all_docs:
            doc_type = doc[4]
            stats['by_type'][doc_type] = stats['by_type'].get(doc_type, 0) + 1
        
        return stats


# ========================================
# 使用例とテスト用のメイン関数
# ========================================

def main():
    """使用例とテスト"""
    import os
    # 設定
    API_KEY = os.getenv('EDINET_API_KEY', '')
    if not API_KEY:
        print("Error: EDINET_API_KEY environment variable is not set")
        print("Please set it in your .env file or export it: export EDINET_API_KEY='your_key_here'")
        return
    
    # サービス初期化
    service = EDINETService(API_KEY)
    
    # 接続テスト
    if not service.test_connection():
        print("API接続に失敗しました")
        return
    
    # 1. 指定日の書類取得テスト
    print("\n=== 1. 指定日の書類取得 ===")
    documents = service.get_documents_by_date("2025-06-28")
    print(f"取得件数: {len(documents)}件")
    for doc in documents[:3]:
        print(f"  {doc[0]} | {doc[1][:20]} | {doc[2][:30]}")
    
    # 2. 企業書類検索テスト
    print("\n=== 2. 企業書類検索 ===")
    company_docs = service.search_company_documents("7203", days_back=30)
    print(f"トヨタの書類: {len(company_docs)}件")
    for doc in company_docs[:3]:
        print(f"  {doc[0]} | {doc[2][:40]} | {doc[3]}")
    
    # 3. 書類ダウンロードテスト
    if company_docs:
        print("\n=== 3. 書類ダウンロード ===")
        doc_id = company_docs[0][0]
        content = service.download_document(doc_id, save_to_file=True)
        
        if content:
            # ZIP分析
            analysis = service.analyze_zip_content(content)
            print(f"ZIP分析結果: {analysis}")
    
    print("\n=== テスト完了 ===")


if __name__ == '__main__':
    main()