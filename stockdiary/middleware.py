from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

class TestAccountCSRFMiddleware(MiddlewareMixin):
    """テストアカウント用のセッション設定"""

    def process_request(self, request):
        if (hasattr(request, 'user') and
                request.user.is_authenticated and
                request.user.username in getattr(settings, 'TEST_ACCOUNT_SETTINGS', {}).get('USERNAMES', [])):

            # セッションタイムアウトを延長
            request.session.set_expiry(
                settings.TEST_ACCOUNT_SETTINGS.get('SESSION_TIMEOUT', 7200)
            )

        return None
