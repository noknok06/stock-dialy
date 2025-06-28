from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

class TestAccountCSRFMiddleware(MiddlewareMixin):
    """テストアカウント用のCSRF例外処理"""
    
    def process_request(self, request):
        # ユーザーがログインしていて、テストアカウントの場合
        if (hasattr(request, 'user') and 
            request.user.is_authenticated and 
            request.user.username in getattr(settings, 'TEST_ACCOUNT_SETTINGS', {}).get('USERNAMES', [])):
            
            # CSRFチェックをスキップ
            setattr(request, '_dont_enforce_csrf_checks', True)
            
            # セッションタイムアウトを延長
            request.session.set_expiry(
                settings.TEST_ACCOUNT_SETTINGS.get('SESSION_TIMEOUT', 7200)
            )
            
            # デバッグログ
            logger.info(f"CSRF exempted for test account: {request.user.username}")
        
        return None
