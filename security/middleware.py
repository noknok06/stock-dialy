# security/middleware.py の更新
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden
from django.conf import settings
import ipaddress
import requests
from django.utils.deprecation import MiddlewareMixin
import re
import json
from django.urls import resolve
import logging

# ロガーの設定
logger = logging.getLogger(__name__)

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
        key = f"payment_rate_limit_{request.user.id}_{self._get_client_ip(request)}"
        
        limit = getattr(settings, 'RATE_LIMIT', {}).get('payment_attempts', {}).get('limit', 5)
        period = getattr(settings, 'RATE_LIMIT', {}).get('payment_attempts', {}).get('period', 600)
        
        attempts = cache.get(key, 0)
        
        if attempts >= limit:
            return HttpResponse("Too many payment attempts. Please try again later.", status=429)
        
        cache.set(key, attempts + 1, period)
        return self.get_response(request)
    
    def _check_login_rate_limit(self, request):
        """ログイン処理のレート制限をチェック"""
        key = f"login_rate_limit_{self._get_client_ip(request)}"
        
        limit = getattr(settings, 'RATE_LIMIT', {}).get('login_attempts', {}).get('limit', 5)
        period = getattr(settings, 'RATE_LIMIT', {}).get('login_attempts', {}).get('period', 300)
        
        if request.method == 'POST':
            attempts = cache.get(key, 0)
            
            if attempts >= limit:
                return HttpResponse("Too many login attempts. Please try again later.", status=429)
            
            cache.set(key, attempts + 1, period)
        
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
    """IPアドレスによるフィルタリングミドルウェア（ブロックリスト対応）"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.private_ips = [
            ipaddress.ip_network('10.0.0.0/8'),
            ipaddress.ip_network('172.16.0.0/12'),
            ipaddress.ip_network('192.168.0.0/16'),
            ipaddress.ip_network('127.0.0.0/8'),
        ]
        # 静的ブラックリストIP（設定から読み込み）
        self.static_blacklist_ips = []
        self._initialize_static_blacklist()
        
    def _initialize_static_blacklist(self):
        """静的ブラックリストIPを初期化"""
        blacklist = getattr(settings, 'BLACKLIST_IPS', [])
        for ip in blacklist:
            try:
                if '/' in ip:
                    self.static_blacklist_ips.append(ipaddress.ip_network(ip))
                else:
                    self.static_blacklist_ips.append(ipaddress.ip_address(ip))
            except ValueError:
                continue
    
    def __call__(self, request):
        client_ip = self._get_client_ip(request)
        
        # 全てのリクエストでデータベースブロックリストをチェック
        if self._is_blocked_ip(client_ip):
            self._log_block_attempt(request, 'ip', client_ip)
            logger.warning(f"Blocked IP access attempt: {client_ip} to {request.path}")
            return HttpResponseForbidden(
                '<h1>Access Denied</h1>'
                '<p>Your IP address has been blocked due to suspicious activity.</p>'
                '<p>If you believe this is an error, please contact support.</p>'
            )
        
        # 特定のパスのみ追加チェック
        if self._should_check_path(request.path):
            # 静的ブラックリストのチェック
            if self._is_static_blacklisted(client_ip):
                return HttpResponseForbidden('Access Denied')
            
            # 不正なリクエストパターンをチェック
            if self._is_suspicious_request(request):
                return HttpResponseForbidden('Suspicious Request Detected')
            
            # 地理的制限のチェック
            if hasattr(settings, 'JAPAN_ONLY_ACCESS') and settings.JAPAN_ONLY_ACCESS:
                if not self._check_japan_only_access(request):
                    return HttpResponseForbidden('Access is restricted to Japan only for security reasons.')
            elif hasattr(settings, 'HIGH_RISK_COUNTRIES') and settings.HIGH_RISK_COUNTRIES:
                country_code = self._get_country_code(client_ip)
                if country_code and country_code in settings.HIGH_RISK_COUNTRIES:
                    if request.path.startswith('/subscriptions/checkout/'):
                        return HttpResponseForbidden('Access from your region is restricted for security reasons.')
        
        return self.get_response(request)
    
    def _is_blocked_ip(self, ip):
        """データベースのブロックリストをチェック"""
        # キャッシュキーを生成
        cache_key = f"blocked_ip_check_{ip}"
        
        # キャッシュから結果を取得（5分間キャッシュ）
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            from security.models import BlockedIP
            
            # アクティブで期限切れでないブロックをチェック
            blocked_ips = BlockedIP.objects.filter(is_active=True)
            
            for blocked_ip in blocked_ips:
                if blocked_ip.is_blocking_ip(ip):
                    # ブロック対象として結果をキャッシュ
                    cache.set(cache_key, True, 300)  # 5分間キャッシュ
                    return True
            
            # ブロック対象外として結果をキャッシュ
            cache.set(cache_key, False, 300)  # 5分間キャッシュ
            return False
            
        except Exception as e:
            logger.error(f"Error checking blocked IP: {e}")
            return False
    
    def _is_static_blacklisted(self, ip):
        """静的ブラックリストIPのチェック"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            
            if ip_obj in self.static_blacklist_ips:
                return True
            
            for network in self.static_blacklist_ips:
                if hasattr(network, 'network_address'):
                    if ip_obj in network:
                        return True
            
            return False
        except ValueError:
            return False
    
    def _log_block_attempt(self, request, block_type, blocked_value):
        """ブロック試行をログに記録"""
        try:
            from security.models import BlockLog
            
            BlockLog.objects.create(
                block_type=block_type,
                blocked_value=blocked_value,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                request_path=request.path[:255]
            )
        except Exception as e:
            logger.error(f"Error logging block attempt: {e}")
    
    def _should_check_path(self, path):
        """チェックすべきパスかどうかを判定"""
        sensitive_paths = [
            '/admin/',
            '/api/',
            '/subscriptions/checkout/',
            '/accounts/login/',
            '/accounts/signup/',
            '/stripe/',
            '/webhook/'
        ]
        
        excluded_paths = [
            '/admin/financial_reports/',
        ]
        
        for path_prefix in excluded_paths:
            if path.startswith(path_prefix):
                return False
                
        return any(path.startswith(prefix) for prefix in sensitive_paths)
    
    def _is_suspicious_request(self, request):
        """不審なリクエストパターンをチェック"""
        suspicious_patterns = [
            r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
            r"((\%3C)|<)((\%2F)|\/)*[a-z0-9\%]+((\%3E)|>)",
            r"((\%3C)|<)((\%69)|i|(\%49))((\%6D)|m|(\%4D))((\%67)|g|(\%47))",
            r"((\%3C)|<)[^\n]+((\%3E)|>)",
        ]
        
        for pattern in suspicious_patterns:
            for key, value in request.GET.items():
                if re.search(pattern, value, re.IGNORECASE):
                    return True
            
            if request.method == 'POST':
                for key, value in request.POST.items():
                    if re.search(pattern, value, re.IGNORECASE):
                        return True
                
                if request.content_type == 'application/json':
                    try:
                        data = json.loads(request.body.decode('utf-8'))
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
        """IPアドレスから国コードを取得"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private:
                return None
                
            try:
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
        """日本からのアクセスのみを許可"""
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
            
            if country_code is None:
                return True
                
            if country_code != 'JP':
                return False
                
        return True


class SecurityHeadersMiddleware(MiddlewareMixin):
    """セキュリティヘッダーを追加するミドルウェア"""
    
    def process_response(self, request, response):
        response['X-XSS-Protection'] = '1; mode=block'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Feature-Policy'] = "geolocation 'none'; microphone 'none'; camera 'none'"
        response['Permissions-Policy'] = "geolocation=(), microphone=(), camera=()"
        
        if 'Server' in response:
            del response['Server']
            
        return response