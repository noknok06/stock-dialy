from django.core.management.base import BaseCommand
from datetime import date, timedelta, datetime
import requests
import json
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'EDINET API接続テスト'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            default=None,
            help='テスト日付（YYYY-MM-DD形式、デフォルト: 7日前の営業日）'
        )
        parser.add_argument(
            '--api-version',
            type=str,
            choices=['v1', 'v2'],
            default='v2',
            help='APIバージョン（v1またはv2）'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='詳細な出力'
        )
    
    def handle(self, *args, **options):
        test_date = options['date']
        if not test_date:
            # デフォルトで過去の営業日を使用
            test_date = self._get_last_business_day(days_back=7).isoformat()
        
        api_version = options['api_version']
        verbose = options['verbose']
        
        self.stdout.write(f'EDINET API {api_version.upper()} 接続テスト開始')
        self.stdout.write(f'テスト日付: {test_date}')
        
        # 日付の妥当性チェック
        try:
            test_date_obj = datetime.strptime(test_date, '%Y-%m-%d').date()
            today = date.today()
            
            if test_date_obj > today:
                self.stdout.write(
                    self.style.WARNING(f'未来の日付が指定されています: {test_date}')
                )
                test_date = self._get_last_business_day().isoformat()
                self.stdout.write(f'営業日に変更: {test_date}')
            
            if test_date_obj.weekday() >= 5:  # 土日
                self.stdout.write(
                    self.style.WARNING(f'休日が指定されています: {test_date}')
                )
                test_date = self._get_last_business_day().isoformat()
                self.stdout.write(f'営業日に変更: {test_date}')
                
        except ValueError:
            self.stdout.write(
                self.style.ERROR(f'無効な日付形式: {test_date}')
            )
            return
        
        # APIキー確認
        from django.conf import settings
        api_key = getattr(settings, 'EDINET_API_SETTINGS', {}).get('API_KEY', '')
        
        if api_version == 'v2':
            self._test_v2_api(test_date, api_key, verbose)
        else:
            self._test_v1_api(test_date, verbose)
    
    def _get_last_business_day(self, days_back=1):
        """最新の営業日を取得（土日を避ける）"""
        target_date = date.today() - timedelta(days=days_back)
        
        # 土日を避ける
        while target_date.weekday() >= 5:  # 5=土曜, 6=日曜
            target_date -= timedelta(days=1)
        
        return target_date
    
    def _test_v2_api(self, test_date, api_key, verbose):
        """EDINET API v2のテスト"""
        url = 'https://api.edinet-fsa.go.jp/api/v2/documents.json'
        params = {
            'date': test_date,
            'type': 2,
        }
        
        # APIキーをパラメータとして追加（推奨方法）
        if api_key:
            params['Subscription-Key'] = api_key
            self.stdout.write(f'APIキー使用: {api_key[:8]}...')
        else:
            self.stdout.write(self.style.WARNING('⚠️ APIキーが設定されていません'))
            self.stdout.write('settings.pyのEDINET_API_SETTINGS["API_KEY"]を確認してください')
        
        # ヘッダー方式もバックアップとして設定
        headers = {}
        if api_key:
            headers['Subscription-Key'] = api_key
        
        try:
            self.stdout.write(f'リクエスト送信: {url}')
            if verbose:
                self.stdout.write(f'パラメータ: {params}')
                self.stdout.write(f'ヘッダー: {headers}')
            
            response = requests.get(url, params=params, headers=headers, timeout=30)
            
            self.stdout.write(f'レスポンスステータス: {response.status_code}')
            self.stdout.write(f'Content-Type: {response.headers.get("Content-Type", "不明")}')
            self.stdout.write(f'レスポンス長: {len(response.text)} 文字')
            
            if verbose:
                self.stdout.write(f'レスポンスヘッダー: {dict(response.headers)}')
                self.stdout.write(f'レスポンス内容の最初の500文字:')
                self.stdout.write(response.text[:500])
            
            if response.status_code == 200:
                if response.text.strip():
                    if response.text.strip().startswith('<'):
                        self.stdout.write(
                            self.style.ERROR('❌ HTMLエラーページが返されました')
                        )
                        self.stdout.write('認証エラーまたはAPIキーの問題の可能性があります')
                        if verbose:
                            self.stdout.write('HTMLコンテンツ:')
                            self.stdout.write(response.text[:1000])
                    else:
                        try:
                            data = response.json()
                            metadata = data.get('metadata', {})
                            results = data.get('results', [])
                            
                            self.stdout.write(
                                self.style.SUCCESS(f'✅ API v2 成功: {len(results)}件のデータを取得')
                            )
                            self.stdout.write(f'APIステータス: {metadata.get("status", "不明")}')
                            self.stdout.write(f'メッセージ: {metadata.get("message", "なし")}')
                            
                            if verbose and results:
                                self.stdout.write('最初のデータサンプル:')
                                self.stdout.write(json.dumps(results[0], ensure_ascii=False, indent=2))
                            
                        except json.JSONDecodeError as e:
                            self.stdout.write(
                                self.style.ERROR(f'❌ JSONデコードエラー: {e}')
                            )
                            self.stdout.write(f'レスポンス内容: {response.text[:200]}...')
                else:
                    self.stdout.write(
                        self.style.WARNING('⚠️ 空のレスポンス')
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ HTTPエラー: {response.status_code}')
                )
                self.stdout.write(f'エラー内容: {response.text[:500]}')
                
        except requests.exceptions.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'❌ リクエストエラー: {e}')
            )
    
    def _test_v1_api(self, test_date, verbose):
        """EDINET API v1のテスト（APIキー不要）"""
        url = 'https://disclosure.edinet-fsa.go.jp/api/v1/documents.json'
        params = {
            'date': test_date,
            'type': 2,
        }
        
        try:
            self.stdout.write(f'リクエスト送信: {url}')
            if verbose:
                self.stdout.write(f'パラメータ: {params}')
            
            response = requests.get(url, params=params, timeout=30)
            
            self.stdout.write(f'レスポンスステータス: {response.status_code}')
            self.stdout.write(f'Content-Type: {response.headers.get("Content-Type", "不明")}')
            self.stdout.write(f'レスポンス長: {len(response.text)} 文字')
            
            if verbose:
                self.stdout.write(f'レスポンスヘッダー: {dict(response.headers)}')
                self.stdout.write(f'レスポンス内容の最初の500文字:')
                self.stdout.write(response.text[:500])
            
            if response.status_code == 200:
                if response.text.strip():
                    if response.text.strip().startswith('<'):
                        self.stdout.write(
                            self.style.ERROR('❌ HTMLエラーページが返されました')
                        )
                        if verbose:
                            self.stdout.write('HTMLコンテンツ:')
                            self.stdout.write(response.text[:1000])
                    else:
                        try:
                            data = response.json()
                            metadata = data.get('metadata', {})
                            results = data.get('results', [])
                            
                            self.stdout.write(
                                self.style.SUCCESS(f'✅ API v1 成功: {len(results)}件のデータを取得')
                            )
                            self.stdout.write(f'APIステータス: {metadata.get("status", "不明")}')
                            self.stdout.write(f'メッセージ: {metadata.get("message", "なし")}')
                            
                            if verbose and results:
                                self.stdout.write('最初のデータサンプル:')
                                self.stdout.write(json.dumps(results[0], ensure_ascii=False, indent=2))
                            
                        except json.JSONDecodeError as e:
                            self.stdout.write(
                                self.style.ERROR(f'❌ JSONデコードエラー: {e}')
                            )
                            self.stdout.write(f'レスポンス内容: {response.text[:200]}...')
                else:
                    self.stdout.write(
                        self.style.WARNING('⚠️ 空のレスポンス')
                    )
            elif response.status_code == 403:
                self.stdout.write(
                    self.style.ERROR('❌ 403 Forbidden - アクセス拒否')
                )
                self.stdout.write('可能な原因:')
                self.stdout.write('1. IPアドレス制限')
                self.stdout.write('2. User-Agent制限')
                self.stdout.write('3. リクエスト頻度制限')
                self.stdout.write('4. 未来の日付または無効な日付')
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ HTTPエラー: {response.status_code}')
                )
                self.stdout.write(f'エラー内容: {response.text[:500]}')
                
        except requests.exceptions.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'❌ リクエストエラー: {e}')
            )