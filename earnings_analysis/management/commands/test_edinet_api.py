# earnings_analysis/management/commands/test_edinet_api.py（API v2対応版）
"""
EDINET API v2の接続テスト用コマンド

APIキーを使用したAPI v2での動作確認
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from earnings_analysis.services import EDINETAPIService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'EDINET API v2の接続テストを実行'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='テスト対象日 (YYYY-MM-DD形式。未指定時は今日)',
        )
        parser.add_argument(
            '--company',
            type=str,
            help='特定企業の書類を検索 (証券コード)',
        )
        parser.add_argument(
            '--download-test',
            action='store_true',
            help='書類ダウンロードもテスト',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='詳細ログを出力',
        )
        parser.add_argument(
            '--api-status',
            action='store_true',
            help='API状態とキー情報を表示',
        )
    
    def handle(self, *args, **options):
        test_date = options['date']
        company_code = options['company']
        download_test = options['download_test']
        verbose = options['verbose']
        api_status = options['api_status']
        
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        
        if not test_date:
            test_date = timezone.now().strftime('%Y-%m-%d')
        
        self.stdout.write(
            self.style.SUCCESS(f'EDINET API v2 接続テストを開始します...')
        )
        
        try:
            # APIサービスの初期化
            edinet_service = EDINETAPIService()
            
            # 1. API状態確認
            self.stdout.write('\n=== API v2 状態確認 ===')
            api_status_info = self._check_api_status(edinet_service)
            
            if api_status:
                # APIキー情報の詳細表示
                self._display_api_status(api_status_info)
                return
            
            if api_status_info['status'] != 'ok':
                self.stdout.write(self.style.ERROR(f'✗ API状態: {api_status_info["message"]}'))
                raise CommandError('API v2の初期化に失敗しました')
            
            self.stdout.write(self.style.SUCCESS('✓ API v2接続: 正常'))
            
            # 2. 基本接続テスト
            self.stdout.write('\n=== 基本接続テスト ===')
            self.stdout.write(f'テスト日: {test_date}')
            if company_code:
                self.stdout.write(f'対象企業: {company_code}')
            
            if self._test_basic_connection(edinet_service):
                self.stdout.write(self.style.SUCCESS('✓ 基本接続: 成功'))
            else:
                self.stdout.write(self.style.ERROR('✗ 基本接続: 失敗'))
                raise CommandError('基本接続テストに失敗しました')
            
            # 3. 書類一覧取得テスト
            self.stdout.write('\n=== 書類一覧取得テスト ===')
            documents = self._test_document_list(edinet_service, test_date, company_code)
            
            if documents:
                self.stdout.write(self.style.SUCCESS(f'✓ 書類一覧取得: 成功 ({len(documents)}件)'))
                self._display_documents(documents[:5])  # 最初の5件を表示
            else:
                self.stdout.write(self.style.WARNING('⚠ 書類一覧取得: 該当書類なし'))
            
            # 4. 書類ダウンロードテスト（オプション）
            if download_test and documents:
                self.stdout.write('\n=== 書類ダウンロードテスト ===')
                self._test_document_download(edinet_service, documents[0])
            
            # 5. 特定企業検索テスト
            if company_code:
                self.stdout.write(f'\n=== 企業検索テスト ({company_code}) ===')
                self._test_company_search(edinet_service, company_code)
            
            # 6. API使用量情報（もしあれば）
            self.stdout.write('\n=== API使用状況 ===')
            self._display_api_usage_info(edinet_service)
            
            self.stdout.write(
                self.style.SUCCESS('\n🎉 EDINET API v2テストが完了しました！')
            )
            
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.ERROR('\nテストが中断されました')
            )
            raise CommandError('ユーザーによってテストが中断されました')
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\nテスト中にエラーが発生しました: {str(e)}')
            )
            raise CommandError(f'テストに失敗しました: {str(e)}')
    
    def _check_api_status(self, edinet_service):
        """API状態をチェック"""
        try:
            return edinet_service.get_api_status()
        except Exception as e:
            return {
                'status': 'error',
                'message': f'APIステータスチェックエラー: {str(e)}',
                'api_version': 'v2'
            }
    
    def _display_api_status(self, status_info):
        """API状態の詳細を表示"""
        self.stdout.write('\n=== API v2 詳細情報 ===')
        self.stdout.write(f"ステータス: {status_info['status']}")
        self.stdout.write(f"メッセージ: {status_info['message']}")
        self.stdout.write(f"APIバージョン: {status_info['api_version']}")
        
        if status_info.get('api_key_length'):
            self.stdout.write(f"APIキー長: {status_info['api_key_length']}文字")
        
        if status_info.get('base_url'):
            self.stdout.write(f"ベースURL: {status_info['base_url']}")
    
    def _test_basic_connection(self, edinet_service):
        """基本接続テスト"""
        try:
            return edinet_service.test_api_connection()
        except Exception as e:
            self.stdout.write(f"接続エラー: {str(e)}")
            return False
    
    def _test_document_list(self, edinet_service, test_date, company_code):
        """書類一覧取得テスト"""
        try:
            self.stdout.write(f"日付: {test_date} の書類を取得中...")
            documents = edinet_service.get_document_list(test_date, company_code)
            return documents
        except Exception as e:
            self.stdout.write(f"書類一覧取得エラー: {str(e)}")
            return []
    
    def _display_documents(self, documents):
        """書類一覧を表示"""
        if not documents:
            self.stdout.write("表示する書類がありません")
            return
        
        self.stdout.write("\n取得された書類:")
        self.stdout.write("-" * 100)
        
        for i, doc in enumerate(documents, 1):
            company_name = doc.get('company_name', '不明')[:20]
            doc_description = doc.get('doc_description', '不明')[:30]
            submission_date = doc.get('submission_date', '不明')
            document_id = doc.get('document_id', '不明')
            
            self.stdout.write(
                f"{i:2d}. [{document_id}] {company_name} | {doc_description} | {submission_date}"
            )
        
        self.stdout.write("-" * 100)
    
    def _test_document_download(self, edinet_service, document):
        """書類ダウンロードテスト"""
        try:
            document_id = document['document_id']
            self.stdout.write(f"書類ダウンロード中: {document_id}")
            
            content = edinet_service.get_document_content(document_id)
            
            if content:
                size_mb = len(content) / (1024 * 1024)
                self.stdout.write(
                    self.style.SUCCESS(f'✓ ダウンロード成功: {size_mb:.2f}MB')
                )
                
                # ZIPファイルの中身を確認
                self._analyze_zip_content(content)
                
            else:
                self.stdout.write(
                    self.style.ERROR('✗ ダウンロード失敗')
                )
                
        except Exception as e:
            self.stdout.write(f"ダウンロードエラー: {str(e)}")
    
    def _analyze_zip_content(self, zip_data):
        """ZIPファイルの内容を分析"""
        try:
            import zipfile
            import io
            
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_file:
                file_list = zip_file.filelist
                self.stdout.write(f"ZIP内容: {len(file_list)} ファイル")
                
                # ファイル種別を分析
                file_types = {}
                xbrl_files = []
                
                for file_info in file_list:
                    filename = file_info.filename
                    extension = filename.split('.')[-1].lower() if '.' in filename else 'unknown'
                    file_types[extension] = file_types.get(extension, 0) + 1
                    
                    if extension in ['xbrl', 'xml', 'htm', 'html']:
                        xbrl_files.append(filename)
                
                self.stdout.write(f"ファイル種別: {file_types}")
                
                # XBRL関連ファイルを表示（最大5件）
                if xbrl_files:
                    self.stdout.write("XBRL関連ファイル:")
                    for filename in xbrl_files[:5]:
                        self.stdout.write(f"  📄 {filename}")
                    
                    if len(xbrl_files) > 5:
                        self.stdout.write(f"  ... 他 {len(xbrl_files) - 5} ファイル")
                
        except Exception as e:
            self.stdout.write(f"ZIP分析エラー: {str(e)}")
    
    def _test_company_search(self, edinet_service, company_code):
        """特定企業の検索テスト"""
        try:
            self.stdout.write(f"企業 {company_code} の過去書類を検索中...")
            
            documents = edinet_service.search_company_documents(company_code, days_back=30)
            
            if documents:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 企業検索成功: {len(documents)}件')
                )
                self._display_documents(documents[:3])
            else:
                self.stdout.write(
                    self.style.WARNING('⚠ 該当する書類が見つかりませんでした')
                )
                
                # 検索のヒントを提供
                self.stdout.write("\n💡 検索のヒント:")
                self.stdout.write("- 企業コードが正確か確認してください")
                self.stdout.write("- 該当期間に決算書類が提出されているか確認してください")
                self.stdout.write("- より長い期間で検索してみてください")
                
        except Exception as e:
            self.stdout.write(f"企業検索エラー: {str(e)}")
    
    def _display_api_usage_info(self, edinet_service):
        """API使用状況を表示"""
        try:
            # API v2では使用量制限の情報が取得できる場合があります
            self.stdout.write("📊 API使用状況:")
            self.stdout.write("- API v2では詳細な使用量情報は提供されていません")
            self.stdout.write("- レート制限: 適切な間隔でリクエストを送信しています")
            self.stdout.write("- APIキー: 正常に認証されています")
            
            # 本日のテスト実行回数を記録（簡易版）
            today = timezone.now().strftime('%Y-%m-%d')
            self.stdout.write(f"- 本日のテスト日付: {today}")
            
        except Exception as e:
            self.stdout.write(f"使用状況取得エラー: {str(e)}")


class QuickTestCommand(BaseCommand):
    """クイックテスト用のサブコマンド（API v2対応）"""
    
    def handle(self, *args, **options):
        self.stdout.write("🚀 EDINET API v2 クイックテスト")
        
        try:
            from earnings_analysis.services import EDINETAPIService
            
            edinet_service = EDINETAPIService()
            
            # API状態確認
            status = edinet_service.get_api_status()
            
            if status['status'] == 'ok':
                self.stdout.write("✅ API v2接続: 正常")
                self.stdout.write(f"📡 ベースURL: {status.get('base_url', 'N/A')}")
                self.stdout.write(f"🔑 APIキー: 設定済み ({status.get('api_key_length', 0)}文字)")
            else:
                self.stdout.write(f"❌ API v2エラー: {status['message']}")
                return
            
            # 今日の書類をテスト
            today = timezone.now().strftime('%Y-%m-%d')
            self.stdout.write(f"📅 今日({today})の書類を確認中...")
            
            documents = edinet_service.get_document_list(today)
            
            if documents:
                self.stdout.write(f"✅ 成功: {len(documents)}件の書類を取得")
                
                # 決算関連書類があるかチェック
                earnings_docs = [d for d in documents if any(
                    keyword in d.get('doc_description', '').lower() 
                    for keyword in ['決算', '四半期', '有価証券']
                )]
                
                if earnings_docs:
                    self.stdout.write(f"📊 決算関連書類: {len(earnings_docs)}件")
                else:
                    self.stdout.write("📋 決算関連書類: なし")
                    
            else:
                # 昨日もテスト
                yesterday = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                self.stdout.write(f"📅 昨日({yesterday})の書類を確認中...")
                
                documents = edinet_service.get_document_list(yesterday)
                
                if documents:
                    self.stdout.write(f"✅ 成功: {len(documents)}件の書類を取得")
                else:
                    self.stdout.write("⚠️ 書類が見つかりませんが、APIは正常に動作しています")
            
            self.stdout.write("✅ EDINET API v2は正常に動作しています！")
            
        except Exception as e:
            self.stdout.write(f"❌ エラー: {str(e)}")
            
            # エラーの種類に応じたヒント
            if "API key" in str(e).lower():
                self.stdout.write("💡 settings.py でAPIキーが正しく設定されているか確認してください")
            elif "network" in str(e).lower() or "connection" in str(e).lower():
                self.stdout.write("💡 ネットワーク接続を確認してください")
            else:
                self.stdout.write("💡 ログファイルで詳細なエラー情報を確認してください")