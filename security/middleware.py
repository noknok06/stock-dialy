# security/middleware.py
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden
from django.conf import settings
import ipaddress
import requests
from django.utils.deprecation import MiddlewareMixin
import re
import json
from django.urls import resolve

class RateLimitMiddleware:
    """リクエスト制限のミドルウェア"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # 決済関連のパスにのみ適用
        path_info = request.path_info
        
        # 認証されたユーザーからのリクエストのみ処理
        if request.user.is_authenticated:
            # 支払い処理のパスかどうかをチェック
            if path_info.startswith('/subscriptions/checkout/') or 'stripe' in path_info.lower():
                return self._check_payment_rate_limit(request)
            
        # 認証ページのレート制限
        if path_info.startswith('/accounts/login/') or path_info.startswith('/accounts/signup/'):
            return self._check_login_rate_limit(request)
            
        # 通常のレスポンス
        return self.get_response(request)
    
    def _check_payment_rate_limit(self, request):
        """支払い処理のレート制限をチェック"""
        # ユーザーIDとIPアドレスを組み合わせたキーを使用
        key = f"payment_rate_limit_{request.user.id}_{self._get_client_ip(request)}"
        
        # 設定から制限値を取得
        limit = getattr(settings, 'RATE_LIMIT', {}).get('payment_attempts', {}).get('limit', 5)
        period = getattr(settings, 'RATE_LIMIT', {}).get('payment_attempts', {}).get('period', 600)
        
        # 現在の試行回数を取得
        attempts = cache.get(key, 0)
        
        if attempts >= limit:
            return HttpResponse("Too many payment attempts. Please try again later.", status=429)
        
        # 試行回数を増やす
        cache.set(key, attempts + 1, period)
        
        # 通常のレスポンス
        return self.get_response(request)
    
    def _check_login_rate_limit(self, request):
        """ログイン処理のレート制限をチェック"""
        # IPアドレスをキーに使用
        key = f"login_rate_limit_{self._get_client_ip(request)}"
        
        # 設定から制限値を取得
        limit = getattr(settings, 'RATE_LIMIT', {}).get('login_attempts', {}).get('limit', 5)
        period = getattr(settings, 'RATE_LIMIT', {}).get('login_attempts', {}).get('period', 300)
        
        # POSTリクエスト（ログイン試行）の場合のみカウント
        if request.method == 'POST':
            # 現在の試行回数を取得
            attempts = cache.get(key, 0)
            
            if attempts >= limit:
                return HttpResponse("Too many login attempts. Please try again later.", status=429)
            
            # 試行回数を増やす
            cache.set(key, attempts + 1, period)
        
        # 通常のレスポンス
        return self.get_response(request)
    
    def _get_client_ip(self, request):
        """クライアントのIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class IPFilterMiddleware:
    """IPアドレスによるフィルタリングミドルウェア"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        # プライベートIPアドレス範囲
        self.private_ips = [
            ipaddress.ip_network('10.0.0.0/8'),      # RFC1918
            ipaddress.ip_network('172.16.0.0/12'),   # RFC1918
            ipaddress.ip_network('192.168.0.0/16'),  # RFC1918
            ipaddress.ip_network('127.0.0.0/8'),     # ローカルホスト
        ]
        # ブラックリストIPの初期化（空の状態）
        self.blacklist_ips = []
        # 既知の悪意のあるIPやボットIPを動的に追加するための仕組み
        self._initialize_blacklist()
        
    def _initialize_blacklist(self):
        """ブラックリストIPを初期化する"""
        # 設定からブラックリストIPを取得
        blacklist = getattr(settings, 'BLACKLIST_IPS', [])
        for ip in blacklist:
            try:
                if '/' in ip:  # CIDRブロック
                    self.blacklist_ips.append(ipaddress.ip_network(ip))
                else:  # 単一IP
                    self.blacklist_ips.append(ipaddress.ip_address(ip))
            except ValueError:
                continue
    
    def __call__(self, request):
        client_ip = self._get_client_ip(request)
        
        # 特定のパスのみチェック（API、決済、管理画面など）
        if self._should_check_path(request.path):
            # IPがブラックリストに含まれているか確認
            if self._is_blacklisted(client_ip):
                return HttpResponseForbidden('Access Denied')
            
            # 不正なリクエストパターンをチェック
            if self._is_suspicious_request(request):
                # 不審なリクエストを拒否
                return HttpResponseForbidden('Suspicious Request Detected')
            
            # 日本のみアクセス許可の設定が有効な場合
            if hasattr(settings, 'JAPAN_ONLY_ACCESS') and settings.JAPAN_ONLY_ACCESS:
                # 日本からのアクセスかどうかをチェック
                if not self._check_japan_only_access(request):
                    return HttpResponseForbidden('Access is restricted to Japan only for security reasons.')
            
            # 高リスク国からのアクセスをチェック（オプション機能）
            elif hasattr(settings, 'HIGH_RISK_COUNTRIES') and settings.HIGH_RISK_COUNTRIES:
                country_code = self._get_country_code(client_ip)
                if country_code and country_code in settings.HIGH_RISK_COUNTRIES:
                    # ここで全てをブロックするか、追加の認証を要求することができる
                    # 例: 特定の国からのチェックアウトページへのアクセスを制限
                    if request.path.startswith('/subscriptions/checkout/'):
                        return HttpResponseForbidden('Access from your region is restricted for security reasons.')
        
        # 通常のレスポンス
        return self.get_response(request)
    
    def _should_check_path(self, path):
        """チェックすべきパスかどうかを判定"""
        # 管理画面、API、決済関連、ユーザー認証などの重要なパスをチェック
        sensitive_paths = [
            '/admin/',
            '/api/',
            '/subscriptions/checkout/',
            '/accounts/login/',
            '/accounts/signup/',
            '/stripe/',
            '/webhook/'
        ]
        return any(path.startswith(prefix) for prefix in sensitive_paths)
    
    def _is_blacklisted(self, ip):
        """IPアドレスがブラックリストに含まれているかチェック"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            
            # 単一IPの一致をチェック
            if ip_obj in self.blacklist_ips:
                return True
            
            # CIDRブロックとの一致をチェック
            for network in self.blacklist_ips:
                if hasattr(network, 'network_address'):  # ipネットワークオブジェクトの場合
                    if ip_obj in network:
                        return True
            
            return False
        except ValueError:
            return False
    
    def _is_suspicious_request(self, request):
        """不審なリクエストパターンをチェック"""
        # SQLインジェクション、XSS、コマンドインジェクションなどの典型的なパターンをチェック
        suspicious_patterns = [
            r"(\%27)|(\')|(\-\-)|(\%23)|(#)",  # SQLインジェクション
            r"((\%3C)|<)((\%2F)|\/)*[a-z0-9\%]+((\%3E)|>)",  # XSS
            r"((\%3C)|<)((\%69)|i|(\%49))((\%6D)|m|(\%4D))((\%67)|g|(\%47))",  # IMGタグ
            r"((\%3C)|<)[^\n]+((\%3E)|>)",  # その他のタグ
        ]
        
        # URLパラメータとフォームデータをチェック
        for pattern in suspicious_patterns:
            # URLパラメータのチェック
            for key, value in request.GET.items():
                if re.search(pattern, value, re.IGNORECASE):
                    return True
            
            # POSTデータのチェック（JSON含む）
            if request.method == 'POST':
                # 通常のフォームデータ
                for key, value in request.POST.items():
                    if re.search(pattern, value, re.IGNORECASE):
                        return True
                
                # JSON形式のデータ
                if request.content_type == 'application/json':
                    try:
                        data = json.loads(request.body.decode('utf-8'))
                        # 再帰的にJSONデータをチェック
                        if self._check_json_data(data, pattern):
                            return True
                    except:
                        pass
        
        return False
    
    def _check_json_data(self, data, pattern):
        """JSON形式のデータを再帰的にチェック"""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and re.search(pattern, value, re.IGNORECASE):
                    return True
                elif isinstance(value, (dict, list)):
                    if self._check_json_data(value, pattern):
                        return True
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, str) and re.search(pattern, item, re.IGNORECASE):
                    return True
                elif isinstance(item, (dict, list)):
                    if self._check_json_data(item, pattern):
                        return True
        return False
    
    def _get_client_ip(self, request):
        """クライアントのIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _get_country_code(self, ip):
        """IPアドレスから国コードを取得（外部APIを使用）"""
        # ローカルIP/プライベートIPはスキップ
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private:
                return None
                
            # 外部サービスのAPIを使って国コードを取得
            # 注意: この部分は本番環境では実際のGeoIPサービスに置き換えるべきです
            try:
                # 例: IPAPIなどの無料サービスを使用
                response = requests.get(f'https://ipapi.co/{ip}/json/', timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    return data.get('country_code')
            except:
                pass
                
            return None
        except:
            return None
            
    def _check_japan_only_access(self, request):
        """日本からのアクセスのみを許可する"""
        # 決済ページや管理者ページなど、保護すべきパスのみをチェック
        protected_paths = [
            '/subscriptions/checkout/',
            '/admin/',
            '/api/',
            '/stripe/',
            '/webhook/'
        ]
        
        if any(request.path.startswith(path) for path in protected_paths):
            client_ip = self._get_client_ip(request)
            country_code = self._get_country_code(client_ip)
            
            # IPアドレスから国が特定できない場合は許可（ローカル開発環境など）
            if country_code is None:
                return True
                
            # 日本（JP）以外の国からのアクセスをブロック
            if country_code != 'JP':
                return False
                
        # それ以外のパスは制限なし
        return True


class SecurityHeadersMiddleware(MiddlewareMixin):
    """セキュリティヘッダーを追加するミドルウェア (CSP除く)"""
    
    def process_response(self, request, response):
        # CSPはdjango-cspミドルウェアに任せる (この行を削除または無効化)
        # response['Content-Security-Policy'] = "..." 
        
        # XSS Protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Content Type Options
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Feature Policy
        response['Feature-Policy'] = "geolocation 'none'; microphone 'none'; camera 'none'"
        
        # Permission Policy (Feature Policyの後継)
        response['Permissions-Policy'] = "geolocation=(), microphone=(), camera=()"
        
        # Remove Server header if present
        if 'Server' in response:
            del response['Server']
            
        return response