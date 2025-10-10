"""
Django設定ファイル（config project）- テスト/開発環境用（簡略化版）

特定企業の個別分析に特化した設定
"""

from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

# .envファイルの読み込み
load_dotenv()

# プロジェクト内のパスを構築: BASE_DIR / 'subdir'
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# コア設定
# =============================================================================

DEBUG = True
SECRET_KEY = 'test-secret-key'
ALLOWED_HOSTS = ['*']

# 1. セキュリティ向上のための基本設定
if DEBUG:
    # 開発環境の設定
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    # その他の開発環境向け設定
else:
    # 本番環境の設定
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = 31536000  # 1年
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# CSRFトークンを常に検証
CSRF_COOKIE_HTTPONLY = True

# 2. セッション設定の強化
SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 3600  # 1時間でセッション切れ

# ルートURL設定
ROOT_URLCONF = 'config.urls'

# WSGIアプリケーション
WSGI_APPLICATION = 'config.wsgi.application'

# 国際化設定
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# デフォルトのプライマリキーフィールドタイプ
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# データベース設定
# =============================================================================

# テスト用データベース設定 - ファイルベースにして明示的に削除
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'test_db.sqlite3',  # 一時的なファイル名
        'TEST': {
            'NAME': 'test_db.sqlite3',
        },
        'CONN_MAX_AGE': 0,  # 接続プールを無効化
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
    # サードパーティ
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
    'earnings_analysis',  # 決算分析アプリ
    'investment_review', 
    'margin_trading', 
]

# インストール済みアプリ
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# =============================================================================
# ミドルウェア設定
# =============================================================================

MIDDLEWARE = [
    'maintenance.middleware.MaintenanceModeMiddleware',  # メンテナンスモード
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'stockdiary.middleware.TestAccountCSRFMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',  # allauth用
    'security.middleware.RateLimitMiddleware',  # レート制限
    'security.middleware.IPFilterMiddleware',   # IP制限
    'security.middleware.SecurityHeadersMiddleware',  # セキュリティヘッダー
    'csp.middleware.CSPMiddleware',  # CSPミドルウェアを最後に配置
    'subscriptions.middleware.SubscriptionMiddleware',  # サブスクリプション
    'ads.middleware.AdsMiddleware',  # 広告表示制御
    'axes.middleware.AxesMiddleware',
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
                'subscriptions.context_processors.subscription_status',  # サブスクリプション状態
                'ads.context_processors.ads_processor',  # 広告表示
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
    'django.contrib.auth.backends.ModelBackend',  # デフォルトのDjango認証
    'allauth.account.auth_backends.AuthenticationBackend',  # allauth認証
    'axes.backends.AxesStandaloneBackend',  # allauth認証
]

# パスワード検証
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# =============================================================================
# Django-allauth設定
# =============================================================================

# Sitesフレームワーク設定
SITE_ID = 1

# Django-allauth基本設定
ACCOUNT_EMAIL_VERIFICATION = 'optional'  # メール検証は任意
ACCOUNT_EMAIL_REQUIRED = True  # メールアドレスは必須
ACCOUNT_UNIQUE_EMAIL = True  # メールアドレスの一意性
ACCOUNT_USERNAME_REQUIRED = True  # ユーザー名は必須
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'  # ソーシャルアカウントのメール検証なし
SOCIALACCOUNT_AUTO_SIGNUP = True  # 自動サインアップを有効化
SOCIALACCOUNT_LOGIN_ON_GET = True  # GETリクエストで直接ログイン
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'  # カスタムアダプター
SOCIALACCOUNT_FORMS = {
    'signup': 'users.forms.CustomSocialSignupForm',  # カスタムサインアップフォーム
}
SOCIALACCOUNT_REDIRECT_URLS = {
    'google': 'http://localhost:8000/accounts/google/login/callback/'  # 開発環境用
}

# Google認証設定
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'VERIFIED_EMAIL': True,  # Googleからのメールを検証済みとして扱う
    }
}

# =============================================================================
# 静的・メディアファイル設定
# =============================================================================

# 静的ファイル
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# メディアファイル
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# =============================================================================
# メール設定（開発環境用）
# =============================================================================

# 開発環境ではコンソールにメールを出力
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'カブログ開発環境 <noreply@localhost>'

# =============================================================================
# ロギング設定
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'earnings_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'earnings-analysis.log'),
            'formatter': 'verbose',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],
    },
    'loggers': {
        'earnings_analysis': {
            'handlers': ['console', 'earnings_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# =============================================================================
# カスタムアプリ設定
# =============================================================================

# 広告設定（開発環境では無効）
ADS_SETTINGS = {
    'DEFAULT_AD_CLIENT': 'ca-pub-test',
    'SHOW_ADS_DEFAULT': False,  # 開発環境では広告非表示
    'PREMIUM_USERS_NO_ADS': True,
    'SHOW_ADS_ON_AUTH_PAGES': False,
}

# CSP設定（開発環境では緩い設定）
CSP_DEFAULT_SRC = ["'self'", "'unsafe-inline'", "'unsafe-eval'", "*"]
CSP_SCRIPT_SRC = ["'self'", "'unsafe-inline'", "'unsafe-eval'", "*"]
CSP_STYLE_SRC = ["'self'", "'unsafe-inline'", "*"]
CSP_FONT_SRC = ["'self'", "data:", "*"]
CSP_IMG_SRC = ["'self'", "data:", "blob:", "*"]
CSP_CONNECT_SRC = ["'self'", "*"]
CSP_FRAME_SRC = ["'self'", "*"]

# =============================================================================
# 決算分析アプリ設定（オンデマンド分析用）
# =============================================================================

# 決算分析機能の有効化
EARNINGS_ANALYSIS_ENABLED = True

# EDINET API設定（v1版・APIキー不要）
EDINET_API_SETTINGS = {
    'BASE_URL': 'https://disclosure.edinet-fsa.go.jp/api/v1',
    'REQUEST_TIMEOUT': 30,
    'RATE_LIMIT_DELAY': 2,  # v1は厳しめのレート制限
    'MAX_RETRIES': 3,
    'API_KEY_REQUIRED': False,  # v1はAPIキー不要
    'USER_AGENT': 'EarningsAnalysisBot/1.0 (https://kabu-log.net)',
}

# 決算分析設定（オンデマンド分析用）
EARNINGS_ANALYSIS_SETTINGS = {
    # 基本設定
    'ENABLE_CACHE': True,
    'CACHE_TIMEOUT': 86400,             # 24時間
    'MAX_DOCUMENTS_PER_SEARCH': 10,     # 検索結果最大件数
    'ANALYSIS_TIMEOUT': 300,            # 5分
    
    # オンデマンド分析設定
    'ON_DEMAND_ANALYSIS': True,
    'ENABLE_AUTO_ANALYSIS': False,      # 自動分析は無効
    'ENABLE_BATCH_ANALYSIS': False,     # バッチ処理無効
    
    # 分析対象期間
    'MAX_ANALYSIS_HISTORY': 2,          # 最新2期分のみ分析
    'ANALYSIS_RETENTION_DAYS': 365,     # 1年間保持
    
    # デバッグ設定
    'DEBUG_MODE': DEBUG,                # DEBUG設定に連動
    'VERBOSE_LOGGING': DEBUG,           # 詳細ログ
}

# 感情分析設定
SENTIMENT_ANALYSIS_SETTINGS = {
    # 感情辞書のパス
    'DICT_PATH': os.path.join(BASE_DIR, 'data', 'sentiment_dict.csv'),
    
    # 分析閾値
    'POSITIVE_THRESHOLD': 0.2,
    'NEGATIVE_THRESHOLD': -0.2,
    
    # テキスト処理設定
    'MIN_SENTENCE_LENGTH': 15,
    'MAX_SAMPLE_SENTENCES': 10,
    'MIN_NUMERIC_VALUE': 5.0,
    
    # キャッシュ設定
    'CACHE_TIMEOUT': 3600,  # 1時間
    'DICTIONARY_CACHE_KEY': 'sentiment_dictionary_v2',
    
    # セッション設定
    'SESSION_EXPIRE_HOURS': 24,
    'MAX_CONCURRENT_SESSIONS': 10,
    
    # パフォーマンス設定
    'BATCH_SIZE': 1000,
    'MAX_TEXT_LENGTH': 100000,  # 10万文字制限
    
    # デバッグ設定
    'ENABLE_DETAILED_LOGGING': DEBUG,
    'LOG_ANALYSIS_METRICS': True,
}

# 感情辞書パスをグローバル設定として追加
SENTIMENT_DICT_PATH = SENTIMENT_ANALYSIS_SETTINGS['DICT_PATH']



# キャッシュフロー分析設定
CASHFLOW_ANALYSIS_SETTINGS = {
    'CF_THRESHOLD_MILLION': 1000,  # 1億円を閾値
    'HEALTH_SCORE_WEIGHTS': {
        'operating_cf': 0.4,
        'pattern_bonus': 0.3,
        'free_cf': 0.2,
        'stability': 0.1,
    },
    'ENABLE_TREND_ANALYSIS': True,  # トレンド分析有効
}

# =============================================================================
# キャッシュ設定（分析結果の高速表示用）
# =============================================================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'earnings-analysis-cache',
        'TIMEOUT': 3600,  # 1時間キャッシュ
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

# 分析結果キャッシュ設定
ANALYSIS_CACHE_SETTINGS = {
    'ENABLE_CACHE': True,
    'CACHE_KEY_PREFIX': 'earnings_analysis',
    'DEFAULT_TIMEOUT': 3600,                # 1時間
    'COMPANY_ANALYSIS_TIMEOUT': 86400,      # 企業分析は24時間
    'SEARCH_RESULTS_TIMEOUT': 300,          # 検索結果は5分
    'DOCUMENT_LIST_TIMEOUT': 1800,          # 書類一覧は30分
    'BATCH_HISTORY_TIMEOUT': 3600,          # バッチ履歴は1時間
}

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# 6. レート制限設定（修正版）
RATE_LIMIT = getattr(globals(), 'RATE_LIMIT', {})
RATE_LIMIT.update({
    'analysis_requests': {
        'limit': 20,        # 1時間あたり20回に増加
        'period': 3600,     # 制限期間（秒）
    },
    'document_download': {
        'limit': 50,        # 1時間あたり50回のダウンロード
        'period': 3600,
    },
    'api_requests': {
        'limit': 200,       # 1時間あたり200回のAPI呼び出し
        'period': 3600,
    }
})

# 7. ログ設定（拡張版）
# ログ設定に感情分析ログを追加
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'earnings_analysis.log'),
            'formatter': 'verbose',
        },
        'sentiment_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'sentiment_analysis.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'earnings_analysis': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'earnings_analysis.services.sentiment_analysis': {
            'handlers': ['sentiment_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ログハンドラに earnings_file が無い場合は追加
if 'earnings_file' not in LOGGING['handlers']:
    LOGGING['handlers']['earnings_file'] = {
        'level': 'DEBUG',
        'class': 'logging.FileHandler',
        'filename': os.path.join(BASE_DIR, 'earnings-analysis.log'),
        'formatter': 'verbose',
    }
    
# =============================================================================
# テスト・開発用設定
# =============================================================================

# レート制限の設定（開発環境では緩め）
RATE_LIMIT = {
    'analysis_requests': {
        'limit': 10,  # 1時間に10回まで分析リクエスト
        'period': 3600,
    },
    'login_attempts': {
        'limit': 100,  # 開発環境では緩く設定
        'period': 300,
    },
}

# テストアカウント設定
TEST_ACCOUNT_SETTINGS = {
    'USERNAMES': ['test', 'test1', 'test2', 'test3', 'demo1', 'demo2', 'demo3'],
    'SESSION_TIMEOUT': 7200,
    'CSRF_EXEMPT': True,
}

# CSRFエラー時のカスタムビュー設定
CSRF_FAILURE_VIEW = 'stockdiary.views.csrf_failure_view'

# =============================================================================
# 削除された設定（不要になったもの）
# =============================================================================

# Celery設定 - 削除（非同期処理不要）
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

if os.environ.get('DJANGO_ENV') != 'production':
    # メモリ内でのタスク実行（開発用）
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    
# Celeryの基本設定
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Tokyo'

CELERY_TASK_SOFT_TIME_LIMIT = 3600  # 1時間
CELERY_TASK_TIME_LIMIT = 4200  # 70分

# バッチ処理設定 - 削除（大量処理不要）
# BATCH_PROCESS_SIZE = 10
# DEFAULT_ANALYSIS_COMPANIES = 100

# 自動分析設定 - 削除（手動分析のみ）
# ENABLE_AUTO_ANALYSIS = True
# NOTIFICATION_DAYS_BEFORE = 7

print(f"🚀 Django 開発環境設定を読み込みました（オンデマンド分析版）")
print(f"📊 決算分析機能: {'有効' if EARNINGS_ANALYSIS_ENABLED else '無効'}")
print(f"📧 メールバックエンド: {EMAIL_BACKEND}")
print(f"🗄️ データベース: {DATABASES['default']['ENGINE']}")
print(f"🔍 分析モード: オンデマンド（ユーザーリクエスト時のみ）")
print(f"💾 キャッシュ: 有効（分析結果を{CACHES['default']['TIMEOUT']}秒間キャッシュ）")

# EDINET API v2設定
EDINET_API_SETTINGS = {
    'API_KEY': '14fb862b5660412d82cc77373cde4170',
    'BASE_URL': 'https://api.edinet-fsa.go.jp/api/v2',
    'RATE_LIMIT_DELAY': 2,  # リクエスト間隔（秒）
    'TIMEOUT': 120,         # タイムアウト（秒）
}

# 決算分析設定
EARNINGS_ANALYSIS_SETTINGS = {
    'ENABLE_CACHE': True,
    'CACHE_TIMEOUT': 86400,  # 24時間
    'MAX_DOCUMENTS_PER_SEARCH': 10,
    'ANALYSIS_TIMEOUT': 300,  # 5分
}

# キャッシュ設定
ANALYSIS_CACHE_SETTINGS = {
    'ENABLE_CACHE': True,
    'CACHE_KEY_PREFIX': 'earnings_analysis',
    'COMPANY_ANALYSIS_TIMEOUT': 86400,  # 24時間
    'SEARCH_RESULTS_TIMEOUT': 300,      # 5分
}

# レート制限設定
RATE_LIMIT = {
    'analysis_requests': {
        'limit': 10,        # 1時間あたりのリクエスト数
        'period': 3600,     # 制限期間（秒）
    }
}

# settings.py に追加
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'earnings-analysis.log',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'earnings_analysis': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}


# 9. セキュリティ設定（EDINET API用）
# CSP設定にEDINET APIドメインを追加
CSP_CONNECT_SRC = getattr(globals(), 'CSP_CONNECT_SRC', ["'self'"])
if 'api.edinet-fsa.go.jp' not in CSP_CONNECT_SRC:
    CSP_CONNECT_SRC.append('api.edinet-fsa.go.jp')

# CORS設定（必要に応じて）
if 'corsheaders' in INSTALLED_APPS:
    CORS_ALLOWED_ORIGINS = getattr(globals(), 'CORS_ALLOWED_ORIGINS', [])
    if 'http://localhost:3000' not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append('http://localhost:3000') 
        
# 11. キャッシュ設定（earnings_analysis専用）
if 'earnings_analysis_cache' not in CACHES:
    CACHES['earnings_analysis_cache'] = {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'earnings-analysis-cache',
        'TIMEOUT': 10800,
        'OPTIONS': {
            'MAX_ENTRIES': 5000,
        }
    }

# 12. 管理画面設定
ADMIN_SITE_HEADER = getattr(globals(), 'ADMIN_SITE_HEADER', 'カブログ管理') + ' - 決算分析'

# 13. 開発環境での追加設定
if DEBUG:
    # 開発環境でのAPI呼び出し制限を緩くする
    EDINET_API_SETTINGS['RATE_LIMIT_DELAY'] = 1  # 1秒間隔
    EARNINGS_ANALYSIS_SETTINGS['MAX_DOCUMENTS_PER_SEARCH'] = 20  # 検索結果を20件に
    
    # 開発環境用のテストデータ設定
    EARNINGS_ANALYSIS_SETTINGS['ENABLE_TEST_DATA'] = True
    EARNINGS_ANALYSIS_SETTINGS['TEST_COMPANIES'] = ['7203', '9984', '6758']  # トヨタ、ソフトバンク、ソニー

# 14. 本番環境での追加設定
else:
    # 本番環境では厳格な制限
    RATE_LIMIT['analysis_requests']['limit'] = 10  # 1時間10回まで
    RATE_LIMIT['document_download']['limit'] = 30  # 1時間30回まで
    
    # 本番環境でのログローテーション
    LOGGING['handlers']['earnings_file'].update({
        'class': 'logging.handlers.RotatingFileHandler',
        'maxBytes': 10485760,  # 10MB
        'backupCount': 5,
    })
    
    
SENTIMENT_ANALYSIS_CONFIG = {
    'enable_financial_context': True,  # 財務文脈分析を有効化
    'financial_context_weight': 1.2,   # 財務文脈の重み（1.0がデフォルト）
}

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyDqCKLsk16O4OVbzXt29T3qezGBQocMNoI')
SENTIMENT_ANALYSIS_DEV_MODE = True

BLOCK_SYSTEM_SETTINGS = {
    # ブロックリストのキャッシュ時間（秒）
    'CACHE_TIMEOUT': 300,  # 5分
    
    # 自動ブロック設定
    'AUTO_BLOCK_THRESHOLD': 5,  # スパムスコアがこの値以上で自動ブロック
    'AUTO_BLOCK_ENABLED': True,
    
    # ブロックログの保持期間（日）
    'LOG_RETENTION_DAYS': 90,
    
    # IP範囲ブロック設定
    'ENABLE_CIDR_BLOCKING': True,
}

# ログ設定にブロックシステム用を追加
LOGGING['handlers']['security_file'] = {
    'level': 'INFO',
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': os.path.join(BASE_DIR, 'logs', 'security.log'),
    'maxBytes': 10485760,  # 10MB
    'backupCount': 5,
}

LOGGING['loggers']['security'] = {
    'handlers': ['security_file', 'file'],
    'level': 'INFO',
    'propagate': True,
}

MAINTENANCE_ALLOWED_IPS = [
    '127.0.0.1',      # ローカル
]


# Langextract設定（新規追加）
LANGEXTRACT_ENABLED = os.environ.get('LANGEXTRACT_ENABLED', 'True').lower() == 'true'

# 感情分析の高度な設定
SENTIMENT_ANALYSIS_SETTINGS = {
    # 基本設定
    'MAX_TEXT_LENGTH': int(os.environ.get('SENTIMENT_MAX_TEXT_LENGTH', '50000')),  # 分析対象テキストの最大長
    'MIN_TEXT_LENGTH': int(os.environ.get('SENTIMENT_MIN_TEXT_LENGTH', '100')),   # 分析対象テキストの最小長
    
    # Langextract設定
    'LANGEXTRACT_TIMEOUT': int(os.environ.get('LANGEXTRACT_TIMEOUT', '180')),     # Langextractタイムアウト（秒）
    'LANGEXTRACT_MAX_RETRIES': int(os.environ.get('LANGEXTRACT_MAX_RETRIES', '2')), # リトライ回数
    'LANGEXTRACT_CHUNK_SIZE': int(os.environ.get('LANGEXTRACT_CHUNK_SIZE', '10000')), # チャンク分割サイズ
    
    # フォールバック設定
    'ENABLE_TRADITIONAL_FALLBACK': os.environ.get('ENABLE_TRADITIONAL_FALLBACK', 'True').lower() == 'true',
    'ENABLE_GEMINI_FALLBACK': os.environ.get('ENABLE_GEMINI_FALLBACK', 'True').lower() == 'true',
    
    # 品質設定
    'MIN_CONFIDENCE_THRESHOLD': float(os.environ.get('SENTIMENT_MIN_CONFIDENCE', '0.3')),
    'HIGH_QUALITY_THRESHOLD': float(os.environ.get('SENTIMENT_HIGH_QUALITY', '0.8')),
    
    # キャッシュ設定
    'ENABLE_ANALYSIS_CACHE': os.environ.get('ENABLE_ANALYSIS_CACHE', 'True').lower() == 'true',
    'CACHE_EXPIRE_HOURS': int(os.environ.get('ANALYSIS_CACHE_HOURS', '24')),
}

# パフォーマンス設定
if LANGEXTRACT_ENABLED:
    # Langextract使用時のメモリ設定調整
    DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
    FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB


SENTIMENT_ANALYSIS_MIGRATION = {
    # 移行段階: 'traditional_only', 'langextract_test', 'hybrid', 'langextract_primary'
    'STAGE': 'hybrid',
    
    # テスト対象の企業コード（段階的移行時）
    'TEST_COMPANIES': ['E00000', 'E00001'],  # 特定企業での先行テスト
    
    # 比較分析の有効化
    'ENABLE_COMPARISON': True,
}


AUTO_GENERATE_SUMMARY = True  # 自動要約生成を有効化

# 要約機能の基本設定
SUMMARY_FEATURE_SETTINGS = {
    'ENABLED': True,  # 要約機能の有効/無効
    'AUTO_GENERATE': False,  # 自動要約生成（通常はFalse）
    'ENHANCED_MODE_DEFAULT': True,  # デフォルトで強化モードを使用
}

# langextract設定
LANGEXTRACT_SETTINGS = {
    'CHUNK_SIZE': 4000,  # Geminiの最大トークン数に合わせて調整
    'CHUNK_OVERLAP': 200,  # チャンク間のオーバーラップ
    'LANGUAGE': 'ja',  # 日本語指定
    'MAX_CHUNKS_PER_DOCUMENT': 20,  # 1文書あたりの最大チャンク数
}

# Gemini API設定
GEMINI_API_SETTINGS = {
    'MODEL_NAME': 'gemini-2.5-flash',  # 要件で指定されたモデル
    'MAX_TOKENS_PER_REQUEST': 8192,  # リクエストあたりの最大トークン数
    'TEMPERATURE': 0.3,  # 創造性 vs 一貫性のバランス（要約なので低め）
    'TOP_P': 0.9,
    'TOP_K': 40,
    'SAFETY_SETTINGS': [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH", 
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        }
    ],
    'REQUEST_DELAY': 1.0,  # API制限対策（秒）
    'MAX_RETRIES': 3,  # リトライ回数
}

# 要約品質設定
SUMMARY_QUALITY_SETTINGS = {
    'TARGET_LENGTHS': {
        'comprehensive': 500,  # 要件: 500文字以内
        'chunk_summary': 300,  # 要件: 300文字以内
        'section_summary': 200,
    },
    'MIN_LENGTHS': {
        'comprehensive': 300,
        'chunk_summary': 150,
        'section_summary': 100,
    },
    'MAX_LENGTHS': {
        'comprehensive': 600,
        'chunk_summary': 400,
        'section_summary': 250,
    },
    'QUALITY_THRESHOLDS': {
        'min_confidence': 0.3,  # 最低信頼度
        'min_completeness': 0.5,  # 最低完全性
        'min_processing_success_rate': 0.7,  # 最低処理成功率
    }
}

# XBRL処理設定
XBRL_PROCESSING_SETTINGS = {
    'MAX_TEXT_LENGTH': 50000,  # 処理対象の最大文字数
    'FINANCIAL_DATA_EXTRACTION': True,  # 財務データ抽出の有効化
    'SECTION_DETECTION': True,  # セクション自動検出
    'NUMERIC_PRESERVATION': True,  # 数値情報の保持
}

# パフォーマンス設定
SUMMARY_PERFORMANCE_SETTINGS = {
    'MAX_PROCESSING_TIME': 300,  # 最大処理時間（秒）
    'BACKGROUND_PROCESSING': True,  # バックグラウンド処理
    'CACHE_RESULTS': True,  # 結果のキャッシュ
    'CLEANUP_INTERVAL': 3600,  # クリーンアップ間隔（秒）
}

# API制限設定
API_RATE_LIMITS = {
    'GEMINI_API': {
        'requests_per_minute': 60,
        'requests_per_day': 1500,
        'tokens_per_minute': 32000,
    },
    'EDINET_API': {
        'requests_per_second': 0.5,  # 2秒に1回
        'max_concurrent': 1,
    }
}

# ログ設定（要約機能用）
LOGGING_SETTINGS_SUMMARY = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'summary_detailed': {
            'format': '{levelname} {asctime} [{name}] {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'summary_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/summary.log',
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 5,
            'formatter': 'summary_detailed',
        },
    },
    'loggers': {
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
    },
}

# メトリクス・監視設定
SUMMARY_MONITORING_SETTINGS = {
    'TRACK_PERFORMANCE': True,  # パフォーマンス追跡
    'COLLECT_METRICS': True,  # メトリクス収集
    'ALERT_ON_ERRORS': True,  # エラー時のアラート
    'QUALITY_MONITORING': True,  # 品質監視
}


SUMMARY_FEATURES = {
    'langextract_enabled': True,
    'gemini_enabled': True,
    'hybrid_mode': True,
    'auto_table_conversion': True,
    'target_lengths': {
        'comprehensive': 1200,  # 600→800に拡張
        'business': 800,       # 200→300に拡張
        'policy': 800,         # 180→250に拡張
        'risks': 800,          # 180→250に拡張
    }
}


# 文書要約設定
DOCUMENT_SUMMARY_CONFIG = {
    'enabled': True,
    'auto_generate': False,  # 自動生成は無効（手動起動）
    'gemini_model': 'gemini-2.5-flash',
    'max_retries': 3,
    'timeout': 300,  # 5分
    'langextract_config': {
        'use_gemini': True,
        'chunk_size': 4000,
        'overlap': 300,
        'min_chunk': 1000,
    }
}
