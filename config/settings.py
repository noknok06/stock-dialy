"""
export DJANGO_SETTINGS_MODULE=config.settings_local
Django設定ファイル（config project）- ローカル開発環境用
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# .envファイルの読み込み
load_dotenv()

# プロジェクト内のパスを構築
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# コア設定
# =============================================================================

# 開発用シークレットキー（本番では絶対に使用しないこと）
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-this-in-production-12345')

# 開発環境ではデバッグを有効化
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# 開発環境ではセキュリティ設定を緩和
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 86400  # 開発環境では24時間

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

LANGUAGE_CODE = 'ja'
TIME_ZONE = 'Asia/Tokyo'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# データベース設定（ローカル用）
# =============================================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'kabulog'),
        'USER': os.getenv('DB_USER', 'naoki'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'ATOMIC_REQUESTS': True,  # ← これを追加
    }
}
DATABASES['default']['ATOMIC_REQUESTS'] = True


# =============================================================================
# アプリケーション設定
# =============================================================================

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',
]

THIRD_PARTY_APPS = [
    'widget_tweaks',
    'tinymce',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'csp',
    'axes',
    'django_htmx',
    'rest_framework',
    'django_filters',
    'corsheaders',
    'django_q',
]

LOCAL_APPS = [
    'users',
    # 'checklist',
    'tags',
    'ads',
    'security',
    'stockdiary',
    'analysis_template',
    'company_master',
    'subscriptions',
    'maintenance',
    'contact',
    'earnings_analysis',
    'financial_reports',
    'margin_trading',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# =============================================================================
# ミドルウェア設定
# =============================================================================

MIDDLEWARE = [
    'maintenance.middleware.MaintenanceModeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'stockdiary.middleware.TestAccountCSRFMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'security.middleware.RateLimitMiddleware',
    'security.middleware.IPFilterMiddleware',
    'security.middleware.SecurityHeadersMiddleware',
    'subscriptions.middleware.SubscriptionMiddleware',
    'ads.middleware.AdsMiddleware',
    'axes.middleware.AxesMiddleware',
    # 'csp.middleware.CSPMiddleware',  # ← コメントアウト（開発環境では無効化）
]

# =============================================================================
# テンプレート設定
# =============================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'company_master', 'templates'),
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'subscriptions.context_processors.subscription_status',
                'ads.context_processors.ads_processor',
                'ads.context_processors.static_version',
            ],
        },
    },
]

# =============================================================================
# 認証設定
# =============================================================================

AUTH_USER_MODEL = 'users.CustomUser'
LOGIN_URL = 'users:login'
LOGIN_REDIRECT_URL = 'stockdiary:home'
LOGOUT_REDIRECT_URL = 'users:login'
ACCOUNT_LOGOUT_REDIRECT_URL = 'users:login'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'axes.backends.AxesStandaloneBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =============================================================================
# Django-allauth設定
# =============================================================================

SITE_ID = 1

ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'
SOCIALACCOUNT_FORMS = {
    'signup': 'users.forms.CustomSocialSignupForm',
}

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'VERIFIED_EMAIL': True,
    }
}

# =============================================================================
# 静的・メディアファイル設定
# =============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# =============================================================================
# メール設定（開発環境ではコンソール出力）
# =============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'カブログ <kabulog.information@gmail.com>'

# =============================================================================
# ロギング設定（開発環境用）
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'django-error.log'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# =============================================================================
# サードパーティアプリ設定
# =============================================================================

TINYMCE_DEFAULT_CONFIG = {
    'theme': 'silver',
    'width': '100%',
    'height': 300,
    'menubar': False,
    'plugins': 'link image lists table code',
    'toolbar': 'bold italic | bullist numlist | link image table | code',
}

# =============================================================================
# カスタムアプリ設定
# =============================================================================

ADS_SETTINGS = {
    'DEFAULT_AD_CLIENT': 'ca-pub-3954701883136363',
    'SHOW_ADS_DEFAULT': False,  # 開発環境では広告非表示
    'PREMIUM_USERS_NO_ADS': True,
    'SHOW_ADS_ON_AUTH_PAGES': False,
}

MAINTENANCE_MODE = False
MAINTENANCE_ALLOWED_IPS = ['127.0.0.1', 'localhost']
MAINTENANCE_EXEMPT_URLS = [r'^/static/.*', r'^/media/.*', r'^/$']

# CSP設定（開発環境用に緩和）
CONTENT_SECURITY_POLICY = {
    'default-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'", "*"],
    'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'", "*"],
    'script-src-elem': ["'self'", "'unsafe-inline'", "'unsafe-eval'", "*", "https://cdn.jsdelivr.net", "https://unpkg.com", "https://www.googletagmanager.com", "https://pagead2.googlesyndication.com"],
    'style-src': ["'self'", "'unsafe-inline'", "*", "https://fonts.googleapis.com", "https://cdn.jsdelivr.net"],
    'style-src-elem': ["'self'", "'unsafe-inline'", "*", "https://fonts.googleapis.com", "https://cdn.jsdelivr.net"],
    'font-src': ["'self'", "data:", "*", "https://fonts.gstatic.com"],
    'img-src': ["'self'", "data:", "blob:", "*"],
    'connect-src': ["'self'", "*"],
    'frame-src': ["'self'", "*"],
}

# レート制限（開発環境では緩和）
RATE_LIMIT = {
    'payment_attempts': {'limit': 100, 'period': 600},
    'login_attempts': {'limit': 100, 'period': 300},
    'analysis_requests': {'limit': 100, 'period': 3600},
    'document_download': {'limit': 100, 'period': 3600},
    'api_requests': {'limit': 1000, 'period': 3600},
}

# 開発環境ではIP制限を無効化
JAPAN_ONLY_ACCESS = False
HIGH_RISK_COUNTRIES = []

# django-axes 設定（開発環境では緩和）
AXES_FAILURE_LIMIT = 100
AXES_COOLOFF_TIME = 0.1
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']

# スパム検出設定
SPAM_DETECTION = {
    'SPAM_THRESHOLD': 3,
    'RATE_LIMIT_ATTEMPTS': 100,
    'RATE_LIMIT_PERIOD': 3600,
    'SPAM_KEYWORDS': [],
    'AUTO_DELETE_SPAM_DAYS': 30,
}

ADMIN_NOTIFICATIONS = {
    'SPAM_ALERT_THRESHOLD': 10,
    'SPAM_ALERT_EMAIL': 'kabulog.information@gmail.com',
}

EMAIL_VERIFICATION = {
    'EXPIRATION_HOURS': 24,
    'CLEANUP_EXPIRED_HOURS': 48,
}

TEST_ACCOUNT_SETTINGS = {
    'USERNAMES': ['test', 'test1', 'test2', 'test3', 'demo1', 'demo2', 'demo3'],
    'SESSION_TIMEOUT': 7200,
    'CSRF_EXEMPT': True,
}

CSRF_FAILURE_VIEW = 'stockdiary.views.csrf_failure_view'

# EDINET API設定
EDINET_API_SETTINGS = {
    'API_KEY': os.getenv('EDINET_API_KEY', ''),
    'BASE_URL': 'https://api.edinet-fsa.go.jp/api/v2',
    'RATE_LIMIT_DELAY': 2,
    'TIMEOUT': 120,
    'USER_AGENT': 'EarningsAnalysisBot/1.0 (https://kabu-log.net)',
}

# REST Framework設定
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# Celery設定（開発環境では同期実行）
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Tokyo'

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
AUTO_GENERATE_SUMMARY = True
DATA_UPLOAD_MAX_NUMBER_FIELDS = 50000

WEBPUSH_SETTINGS = {
    'VAPID_PUBLIC_KEY': os.getenv('VAPID_PUBLIC_KEY', ''),
    'VAPID_PRIVATE_KEY': os.getenv('VAPID_PRIVATE_KEY', ''),
    'VAPID_ADMIN_EMAIL': os.getenv('VAPID_ADMIN_EMAIL', 'kabulog.information@gmail.com'),
}

# Django-Q設定
Q_CLUSTER = {
    'name': 'kabulog_dev',
    'workers': 1,
    'recycle': 500,
    'timeout': 120,
    'retry': 600,
    'compress': True,
    'save_limit': 100,
    'queue_limit': 300,
    'label': 'Django Q Dev',
    'redis': {
        'host': '127.0.0.1',
        'port': 6379,
        'db': 0,
    },
    'orm': 'default',
}


STATIC_VERSION = '1.0.12'
