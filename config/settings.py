"""
Django設定ファイル（config project）- 本番環境用（整理版）

Django 4.2.13を使用して'django-admin startproject'により生成
このファイルの詳細情報：
https://docs.djangoproject.com/en/4.2/topics/settings/
"""

from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

import cloudinary
import cloudinary.uploader
import cloudinary.api

import socket

# .envファイルの読み込み
load_dotenv()

# プロジェクト内のパスを構築: BASE_DIR / 'subdir'
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# 基本設定
# =============================================================================

socket.setdefaulttimeout(120)  # 2分
IMPORT_MEMORY_LIMIT_MB = int(os.getenv('IMPORT_MEMORY_LIMIT_MB', '256'))
IMPORT_BATCH_SIZE = int(os.getenv('IMPORT_BATCH_SIZE', '50'))

# セキュリティ設定
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = False
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')
CSRF_TRUSTED_ORIGINS = [
    'https://kabu-log.net', 
    'http://kabu-log.net', 
    'http://localhost:8000', 
]

# セキュリティ向上設定
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1年
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_HTTPONLY = True

# セッション設定
SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 3600  # 1時間でセッション切れ
SESSION_SAVE_EVERY_REQUEST = True

# ルート設定
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

# 国際化設定
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# デフォルトのプライマリキーフィールドタイプ
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CSRF設定
CSRF_FAILURE_VIEW = 'stockdiary.views.csrf_failure_view'

# =============================================================================
# データベース設定
# =============================================================================

DATABASES = {
    'default': {
        'ENGINE': ' .postgresql',
        'NAME': os.getenv('DB_NAME', 'kabulog'),
        'USER': os.getenv('DB_USER', 'naoki'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'CONN_MAX_AGE': 0,  # 接続プールを無効化
        'OPTIONS': {
            'MAX_CONNS': 1,  # 最大接続数を制限
        }
    }
}

# =============================================================================
# アプリケーション設定
# =============================================================================

# Djangoビルトインアプリ
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

# サードパーティアプリ
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
]

# ローカルアプリ
LOCAL_APPS = [
    'users',
    'checklist',
    'tags',
    'ads',
    'security',
    'stockdiary',
    'portfolio',
    'analysis_template',
    'company_master',
    'subscriptions',
    'maintenance',
    'contact',
    'financial_reports',
    'earnings_analysis',
    'margin_trading',
]

# インストール済みアプリ
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
    'csp.middleware.CSPMiddleware',
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

# 認証バックエンド
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'axes.backends.AxesStandaloneBackend',
]

# パスワード検証
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

# 基本設定
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'
SOCIALACCOUNT_FORMS = {'signup': 'users.forms.CustomSocialSignupForm'}
SOCIALACCOUNT_REDIRECT_URLS = {
    'google': 'https://kabu-log.net/accounts/google/login/callback/'
}

# Google認証設定
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
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# 画像圧縮設定
IMAGE_COMPRESSION_SETTINGS = {
    'DIARY': {'MAX_WIDTH': 800, 'MAX_HEIGHT': 600, 'QUALITY': 0.85},
    'NOTE': {'MAX_WIDTH': 600, 'MAX_HEIGHT': 400, 'QUALITY': 0.7}
}

# =============================================================================
# メール設定
# =============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'kabulog.information@gmail.com'
EMAIL_HOST_PASSWORD = 'wfsdxbdxsdusvddw'  # 環境変数使用推奨
DEFAULT_FROM_EMAIL = 'カブログ <kabulog.information@gmail.com>'

# =============================================================================
# ログ設定（統合版）
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} [{name}] {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django-error.log'),
            'formatter': 'verbose',
        },
        'earnings_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'earnings_analysis.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'sentiment_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler', 
            'filename': os.path.join(BASE_DIR, 'logs', 'sentiment_analysis.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'security.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'summary_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'summary.log'),
            'maxBytes': 15728640,  # 15MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
        'earnings_analysis': {
            'handlers': ['earnings_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'earnings_analysis.services.sentiment_analysis': {
            'handlers': ['sentiment_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'earnings_analysis.services.enhanced_document_summarizer': {
            'handlers': ['summary_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'earnings_analysis.services.langextract_processor': {
            'handlers': ['summary_file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'security': {
            'handlers': ['security_file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# =============================================================================
# レート制限設定
# =============================================================================

RATE_LIMIT = {
    'payment_attempts': {'limit': 5, 'period': 600},
    'login_attempts': {'limit': 5, 'period': 300},
    'analysis_requests': {'limit': 10, 'period': 3600},
    'document_download': {'limit': 30, 'period': 3600},
    'api_requests': {'limit': 100, 'period': 3600}
}

# =============================================================================
# セキュリティ設定
# =============================================================================

# IP制限設定
JAPAN_ONLY_ACCESS = True
HIGH_RISK_COUNTRIES = ['CN', 'RU', 'KP', 'IR']

# django-axes設定
AXES_FAILURE_LIMIT = 10
AXES_COOLOFF_TIME = 1
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address'] 

# スパム検出設定
SPAM_DETECTION = {
    'SPAM_THRESHOLD': 3,
    'RATE_LIMIT_ATTEMPTS': 3,
    'RATE_LIMIT_PERIOD': 3600,
    'SPAM_KEYWORDS': ['wkxprysmyph', 'accordini', 'gfwljsiqtrr'],
    'AUTO_DELETE_SPAM_DAYS': 30,
}

# ブロックシステム設定
BLOCK_SYSTEM_SETTINGS = {
    'CACHE_TIMEOUT': 300,
    'AUTO_BLOCK_THRESHOLD': 5,
    'AUTO_BLOCK_ENABLED': True,
    'LOG_RETENTION_DAYS': 90,
    'ENABLE_CIDR_BLOCKING': True,
}

# 管理者通知設定
ADMIN_NOTIFICATIONS = {
    'SPAM_ALERT_THRESHOLD': 10,
    'SPAM_ALERT_EMAIL': 'kabulog.information@gmail.com',
}

# テストアカウント設定
TEST_ACCOUNT_SETTINGS = {
    'USERNAMES': ['test', 'test1', 'test2', 'test3', 'demo1', 'demo2', 'demo3'],
    'SESSION_TIMEOUT': 7200,
    'CSRF_EXEMPT': True,
}

# =============================================================================
# CSP設定
# =============================================================================

CSP_DEFAULT_SRC = ["'self'", "cdn.jsdelivr.net", "*.googleapis.com", "*.gstatic.com", "*.bootstrapcdn.com", "unpkg.com"]
CSP_SCRIPT_SRC = [
    "'self'", "'unsafe-inline'", "'unsafe-eval'", "unpkg.com", "https://unpkg.com",
    "cdn.jsdelivr.net", "*.jquery.com", "*.googleadservices.com", "*.google.com", 
    "*.googleapis.com", "*.gstatic.com", "*.googlesyndication.com", 
    "pagead2.googlesyndication.com", "*.doubleclick.net", "googleads.g.doubleclick.net",
    "*.bootstrapcdn.com", "*.googletagmanager.com", "www.googletagmanager.com",
    "*.adtrafficquality.google", "https://adtrafficquality.google"
]
CSP_STYLE_SRC = ["'self'", "'unsafe-inline'", "*.googleapis.com", "*.bootstrapcdn.com", "https://cdn.jsdelivr.net", "https:", "data:"]
CSP_FONT_SRC = ["'self'", "data:", "*.googleapis.com", "*.gstatic.com", "*.bootstrapcdn.com", "cdn.jsdelivr.net", "cdnjs.cloudflare.com"]
CSP_IMG_SRC = ["'self'", "data:", "https:", "blob:", "*.google.com", "*.googleapis.com", "*.gstatic.com", "*.doubleclick.net", "pagead2.googlesyndication.com"]
CSP_CONNECT_SRC = ["'self'", "*.google.com", "*.doubleclick.net", "*.googleapis.com", "www.google-analytics.com", "*.googletagmanager.com", "*.adtrafficquality.google", "api.edinet-fsa.go.jp", "disclosure.edinet-fsa.go.jp"]
CSP_FRAME_SRC = ["'self'", "*.google.com", "*.doubleclick.net", "https://*.doubleclick.net", "googleads.g.doubleclick.net", "tpc.googlesyndication.com", "*.googletagmanager.com", "*.googlesyndication.com", "pagead2.googlesyndication.com"]

# =============================================================================
# アプリケーション固有設定
# =============================================================================

# 広告設定
ADS_SETTINGS = {
    'DEFAULT_AD_CLIENT': 'ca-pub-3954701883136363',
    'SHOW_ADS_DEFAULT': True,
    'PREMIUM_USERS_NO_ADS': True,
    'SHOW_ADS_ON_AUTH_PAGES': False,
}

# メンテナンスモード設定
MAINTENANCE_MODE = False
MAINTENANCE_ALLOWED_IPS = ['193.186.4.181', '192.168.1.100']
MAINTENANCE_EXEMPT_URLS = [r'^/static/.*', r'^/media/.*', r'^/$']
MAINTENANCE_END_TIME = '2025年3月23日 10:00 (JST)'
MAINTENANCE_CONTACT_EMAIL = 'kabulog.information@gmail.com'

# TinyMCE設定
TINYMCE_DEFAULT_CONFIG = {
    'theme': 'silver',
    'width': '100%',
    'height': 300,
    'menubar': False,
    'plugins': 'link image lists table code',
    'toolbar': 'bold italic | bullist numlist | link image table | code',
    'mobile': {
        'plugins': 'link image lists table',
        'toolbar': 'bold italic | bullist numlist | link image'
    },
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

# =============================================================================
# 決算分析関連設定
# =============================================================================

# API設定
EDINET_API_SETTINGS = {
    'API_KEY': os.getenv('EDINET_API_KEY', ''),
    'BASE_URL': 'https://api.edinet-fsa.go.jp/api/v2',
    'RATE_LIMIT_DELAY': 2,
    'TIMEOUT': 120,
    'USER_AGENT': 'EarningsAnalysisBot/1.0 (https://kabu-log.net)',
}

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# 決算分析機能設定
EARNINGS_ANALYSIS_ENABLED = True
EARNINGS_ANALYSIS_SETTINGS = {
    'ENABLE_CACHE': True,
    'CACHE_TIMEOUT': 86400,
    'MAX_DOCUMENTS_PER_SEARCH': 10,
    'ANALYSIS_TIMEOUT': 300,
    'ON_DEMAND_ANALYSIS': True,
    'ENABLE_AUTO_ANALYSIS': False,
    'ENABLE_BATCH_ANALYSIS': False,
    'MAX_ANALYSIS_HISTORY': 2,
    'ANALYSIS_RETENTION_DAYS': 365,
    'DEBUG_MODE': False,
    'VERBOSE_LOGGING': False,
}

# 感情分析設定
LANGEXTRACT_ENABLED = os.environ.get('LANGEXTRACT_ENABLED', 'True').lower() == 'true'
USE_LANGEXTRACT_SENTIMENT = True
LANGEXTRACT_TIMEOUT_SECONDS = 120
LANGEXTRACT_MAX_TEXT_LENGTH = 50000
LANGEXTRACT_ROLLOUT_PERCENTAGE = 100

SENTIMENT_ANALYSIS_SETTINGS = {
    'MAX_TEXT_LENGTH': int(os.environ.get('SENTIMENT_MAX_TEXT_LENGTH', '50000')),
    'MIN_TEXT_LENGTH': int(os.environ.get('SENTIMENT_MIN_TEXT_LENGTH', '100')),
    'LANGEXTRACT_TIMEOUT': int(os.environ.get('LANGEXTRACT_TIMEOUT', '180')),
    'LANGEXTRACT_MAX_RETRIES': int(os.environ.get('LANGEXTRACT_MAX_RETRIES', '2')),
    'LANGEXTRACT_CHUNK_SIZE': int(os.environ.get('LANGEXTRACT_CHUNK_SIZE', '10000')),
    'ENABLE_TRADITIONAL_FALLBACK': True,
    'ENABLE_GEMINI_FALLBACK': True,
    'MIN_CONFIDENCE_THRESHOLD': float(os.environ.get('SENTIMENT_MIN_CONFIDENCE', '0.3')),
    'HIGH_QUALITY_THRESHOLD': float(os.environ.get('SENTIMENT_HIGH_QUALITY', '0.8')),
    'ENABLE_ANALYSIS_CACHE': True,
    'CACHE_EXPIRE_HOURS': int(os.environ.get('ANALYSIS_CACHE_HOURS', '24')),
}

SENTIMENT_ANALYSIS_MIGRATION = {
    'STAGE': 'hybrid',
    'TEST_COMPANIES': ['E00000', 'E00001'],
    'ENABLE_COMPARISON': True,
}

# LangExtract設定
LANGEXTRACT_CONFIG = {
    'model': 'gemini-2.5-flash',
    'temperature': 0.2,
    'max_tokens': 8192,
    'retry_attempts': 3,
    'retry_delay': 5,
}

LANGEXTRACT_SETTINGS = {
    'ENABLED': True,
    'FALLBACK_TO_TRADITIONAL': True,
    'CONFIDENCE_THRESHOLD': 0.7,
    'TIMEOUT': 30,
    'MAX_TEXT_LENGTH': 10000,
    'CACHE_RESULTS': True,
    'CACHE_TIMEOUT': 3600,
    'DEBUG_LOGGING': False,
    'CHUNK_SIZE': 4000,
    'CHUNK_OVERLAP': 200,
    'LANGUAGE': 'ja',
    'MAX_CHUNKS_PER_DOCUMENT': 20,
}

# 要約機能設定
AUTO_GENERATE_SUMMARY = True
SUMMARY_FEATURE_SETTINGS = {
    'ENABLED': True,
    'AUTO_GENERATE': False,
    'ENHANCED_MODE_DEFAULT': True,
    'DEFAULT_CACHE_TIME': 24 * 60 * 60,
    'LANGEXTRACT_ENABLED': True,
    'LANGEXTRACT_CACHE_DIR': os.path.join(BASE_DIR, 'cache', 'langextract'),
    'TARGET_LENGTHS': {'comprehensive': 600, 'business': 200, 'policy': 180, 'risks': 180},
    'MIN_CONFIDENCE_THRESHOLD': 0.3,
    'MIN_COMPLETENESS_THRESHOLD': 0.5,
    'MAX_CONCURRENT_SUMMARIES': 3,
    'TIMEOUT_SECONDS': 300,
}

SUMMARY_FEATURES = {
    'langextract_enabled': True,
    'gemini_enabled': True,
    'hybrid_mode': True,
    'auto_table_conversion': True,
    'target_lengths': {
        'comprehensive': 1200,
        'business': 800,
        'policy': 800,
        'risks': 800,
    }
}

# Gemini API設定
GEMINI_SETTINGS = {
    'MODEL_NAME': 'gemini-2.5-flash',
    'TEMPERATURE': 0.3,
    'MAX_TOKENS': 2048,
    'TIMEOUT': 30,
}

GEMINI_API_SETTINGS = {
    'MODEL_NAME': 'gemini-2.5-flash',
    'MAX_TOKENS_PER_REQUEST': 8192,
    'TEMPERATURE': 0.3,
    'TOP_P': 0.9,
    'TOP_K': 40,
    'SAFETY_SETTINGS': [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
    ],
    'REQUEST_DELAY': 1.0,
    'MAX_RETRIES': 3,
}

# キャッシュフロー分析設定
CASHFLOW_ANALYSIS_SETTINGS = {
    'CF_THRESHOLD_MILLION': 1000,
    'HEALTH_SCORE_WEIGHTS': {
        'operating_cf': 0.4,
        'pattern_bonus': 0.3,
        'free_cf': 0.2,
        'stability': 0.1,
    },
    'ENABLE_TREND_ANALYSIS': True,
}

# 分析結果キャッシュ設定
ANALYSIS_CACHE_SETTINGS = {
    'ENABLE_CACHE': True,
    'CACHE_KEY_PREFIX': 'earnings_analysis',
    'DEFAULT_TIMEOUT': 3600,
    'COMPANY_ANALYSIS_TIMEOUT': 86400,
    'SEARCH_RESULTS_TIMEOUT': 300,
    'DOCUMENT_LIST_TIMEOUT': 1800,
    'BATCH_HISTORY_TIMEOUT': 3600,
}

# API制限設定
API_RATE_LIMITS = {
    'GEMINI_API': {
        'requests_per_minute': 60,
        'requests_per_day': 1500,
        'tokens_per_minute': 32000,
    },
    'EDINET_API': {
        'requests_per_second': 0.5,
        'max_concurrent': 1,
    }
}

# =============================================================================
# Celery設定
# =============================================================================

CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Tokyo'
CELERY_TASK_SOFT_TIME_LIMIT = 3600
CELERY_TASK_TIME_LIMIT = 4200

# =============================================================================
# パフォーマンス・メモリ設定
# =============================================================================

# Langextract使用時のメモリ設定調整
if LANGEXTRACT_ENABLED:
    DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
    FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# =============================================================================
# 起動メッセージ
# =============================================================================

print(f"🚀 Django本番環境設定（earnings_analysis統合版）を読み込みました")
print(f"📊 決算分析機能: {'有効' if EARNINGS_ANALYSIS_ENABLED else '無効'}")
print(f"📧 メールバックエンド: {EMAIL_BACKEND}")
print(f"🗄️ データベース: PostgreSQL")
print(f"🔍 分析モード: オンデマンド（本番環境）")
print(f"⚡ Celery: 同期実行モード（threading.Thread使用）")