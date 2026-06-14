from django.conf import settings


def google_oauth_status(request):
    """Google OAuth が設定済みかどうかをテンプレートに渡す"""
    return {
        'google_oauth_enabled': getattr(settings, 'GOOGLE_OAUTH_ENABLED', False),
    }


def demo_status(request):
    """デモ体験ボタンを表示してよいかをテンプレートに渡す"""
    return {
        'demo_enabled': getattr(settings, 'DEMO_ENABLED', False),
    }
