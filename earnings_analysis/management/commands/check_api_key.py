from django.core.management.base import BaseCommand
from datetime import date, timedelta, datetime
import requests
import json
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'EDINET APIキー診断'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--api-key',
            type=str,
            default=None,
            help='テスト用APIキー（指定しない場合はsettingsから取得）'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='詳細な出力'
        )
    
    def handle(self, *args, **options):
        api_key = options['api_key']
        verbose = options['verbose']
        
        # APIキー取得
        if not api_key:
            from django.conf import settings
            api_key = getattr(settings, 'EDINET_API_SETTINGS', {}).get('API_KEY', '')
        
        if not api_key:
            self.stdout.write(
                self.style.ERROR('❌ APIキーが設定されていません')
            )
            self.stdout.write('解決方法:')
            self.stdout.write('1. https://api.edinet-fsa.go.jp/api/auth/index.aspx でAPIキーを発行')
            self.stdout.write('2. settings.pyのEDINET_API_SETTINGS["API_KEY"]に設定')
            return
        
        self.stdout.write(f'🔑 APIキー診断開始')
        self.stdout.write(f'APIキー: {api_key[:8]}...{api_key[-4:]}')
        
        # 基本的なAPIキー形式チェック
        self._check_api_key_format(api_key)
        
        # APIエンドポイントテスト
        self._test_api_endpoints(api_key, verbose)
        
        # 推奨事項
        self._show_recommendations()
    
    def _check_api_key_format(self, api_key):
        """APIキー形式チェック"""
        self.stdout.write('\n📋 APIキー形式チェック:')
        
        # 長さチェック
        if len(api_key) == 32:
            self.stdout.write('  ✅ 長さ: 32文字（正常）')
        else:
            self.stdout.write(f'  ⚠️ 長さ: {len(api_key)}文字（通常は32文字）')
        
        # 文字種チェック
        if api_key.isalnum():
            self.stdout.write('  ✅ 文字種: 英数字のみ（正常）')
        else:
            self.stdout.write('  ⚠️ 文字種: 英数字以外の文字を含む')
        
        # 空白チェック
        if ' ' not in api_key:
            self.stdout.write('  ✅ 空白: なし（正常）')
        else:
            self.stdout.write('  ❌ 空白: 含まれています（除去してください）')
    
    def _test_api_endpoints(self, api_key, verbose):
        """APIエンドポイントテスト"""
        self.stdout.write('\n🌐 APIエンドポイントテスト:')
        
        # テスト日付（過去の営業日）
        test_date = self._get_last_business_day(days_back=7).isoformat()
        
        # パターン1: パラメータでAPIキー送信
        self.stdout.write('\n  📤 パターン1: パラメータでAPIキー送信')
        self._test_parameter_method(api_key, test_date, verbose)
        
        # パターン2: ヘッダーでAPIキー送信
        self.stdout.write('\n  📤 パターン2: ヘッダーでAPIキー送信')
        self._test_header_method(api_key, test_date, verbose)
        
        # パターン3: v1 API（APIキー不要）
        self.stdout.write('\n  📤 パターン3: v1 API（APIキー不要）')
        self._test_v1_method(test_date, verbose)
    
    def _test_parameter_method(self, api_key, test_date, verbose):
        """パラメータ方式のテスト"""
        url = 'https://api.edinet-fsa.go.jp/api/v2/documents.json'
        params = {
            'date': test_date,
            'type': 2,
            'Subscription-Key': api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            self._analyze_response(response, 'パラメータ方式', verbose)
        except Exception as e:
            self.stdout.write(f'    ❌ エラー: {e}')
    
    def _test_header_method(self, api_key, test_date, verbose):
        """ヘッダー方式のテスト"""
        url = 'https://api.edinet-fsa.go.jp/api/v2/documents.json'
        params = {
            'date': test_date,
            'type': 2,
        }
        headers = {
            'Subscription-Key': api_key
        }
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            self._analyze_response(response, 'ヘッダー方式', verbose)
        except Exception as e:
            self.stdout.write(f'    ❌ エラー: {e}')
    
    def _test_v1_method(self, test_date, verbose):
        """v1 API方式のテスト"""
        url = 'https://disclosure.edinet-fsa.go.jp/api/v1/documents.json'
        params = {
            'date': test_date,
            'type': 2,
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            self._analyze_response(response, 'v1 API', verbose)
        except Exception as e:
            self.stdout.write(f'    ❌ エラー: {e}')
    
    def _analyze_response(self, response, method_name, verbose):
        """レスポンス分析"""
        status = response.status_code
        content_type = response.headers.get('Content-Type', '')
        
        if status == 200:
            if 'application/json' in content_type:
                try:
                    data = response.json()
                    
                    # エラーレスポンスチェック
                    if 'statusCode' in data and data['statusCode'] != 200:
                        self.stdout.write(f'    ❌ {method_name}: APIエラー ({data["statusCode"]}) - {data.get("message", "")}')
                    elif 'results' in data:
                        result_count = len(data['results'])
                        self.stdout.write(f'    ✅ {method_name}: 成功 ({result_count}件のデータ)')
                    else:
                        self.stdout.write(f'    ⚠️ {method_name}: 予期しないレスポンス形式')
                        
                except json.JSONDecodeError:
                    self.stdout.write(f'    ❌ {method_name}: JSONパースエラー')
            else:
                self.stdout.write(f'    ❌ {method_name}: HTMLレスポンス（認証エラーの可能性）')
        elif status == 401:
            self.stdout.write(f'    ❌ {method_name}: 認証エラー (401) - APIキーが無効')
        elif status == 403:
            self.stdout.write(f'    ❌ {method_name}: アクセス拒否 (403)')
        else:
            self.stdout.write(f'    ❌ {method_name}: HTTPエラー ({status})')
        
        if verbose:
            self.stdout.write(f'      レスポンス内容: {response.text[:200]}...')
    
    def _get_last_business_day(self, days_back=1):
        """最新の営業日を取得"""
        target_date = date.today() - timedelta(days=days_back)
        while target_date.weekday() >= 5:  # 土日を避ける
            target_date -= timedelta(days=1)
        return target_date
    
    def _show_recommendations(self):
        """推奨事項表示"""
        self.stdout.write('\n💡 推奨事項:')
        self.stdout.write('1. 有効なAPIキーを取得:')
        self.stdout.write('   https://api.edinet-fsa.go.jp/api/auth/index.aspx')
        self.stdout.write('2. APIキーを設定:')
        self.stdout.write('   settings.py > EDINET_API_SETTINGS["API_KEY"]')
        self.stdout.write('3. v1 APIの使用:')
        self.stdout.write('   python manage.py collect_initial_data --api-version v1')
        self.stdout.write('4. APIキーの確認:')
        self.stdout.write('   python manage.py check_api_key --verbose')