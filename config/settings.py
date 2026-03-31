"""
Django設定ファイル（config project）- 本番環境用

Django 4.2.13を使用して'django-admin startproject'により生成

このファイルの詳細情報：
https://docs.djangoproject.com/en/4.2/topics/settings/

全設定項目と値の詳細：
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# .envファイルの読み込み
load_dotenv()


# プロジェクト内のパスを構築: BASE_DIR / 'subdir'
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# コア設定
# =============================================================================

# セキュリティ警告: 本番環境用シークレットキー（環境変数から取得）
SECRET_KEY = os.getenv('SECRET_KEY')

# 本番環境用デバッグ設定（無効）。DJANGO_DEBUG=True で開発用に上書き可
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'

# ホストとCSRF設定
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')
CSRF_TRUSTED_ORIGINS = [
    'https://kabu-log.net', 'http://kabu-log.net', 
    'http://localhost:8000', 
]

# 1. セキュリティ向上のための基本設定
if DEBUG:
    # 開発環境の設定
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    # CSP: 開発環境ではインラインスタイル・外部CDNを許可
    CSP_DEFAULT_SRC = ["'self'", "'unsafe-inline'", "cdn.jsdelivr.net", "*.googleapis.com", "*.gstatic.com", "*.bootstrapcdn.com", "*"]
    CSP_STYLE_SRC = ["'self'", "'unsafe-inline'", "cdn.jsdelivr.net", "*.googleapis.com", "https:", "*"]
    CSP_SCRIPT_SRC = ["'self'", "'unsafe-inline'", "'unsafe-eval'", "cdn.jsdelivr.net", "*"]
    CSP_FONT_SRC = ["'self'", "data:", "*.googleapis.com", "*.gstatic.com", "*"]
    CSP_IMG_SRC = ["'self'", "data:", "*"]
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

# CSRF_COOKIE_HTTPONLY = True にするとJavaScriptがCSRFトークンを読めなくなり
# fetchなどのAJAXリクエストでX-CSRFTokenヘッダーが送れず403エラーになるためFalseに設定
CSRF_COOKIE_HTTPONLY = False

# 2. セッション設定の強化
SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 3600  # 1時間でセッション切れ

# ルートURL設定
ROOT_URLCONF = 'config.urls'

# WSGIアプリケーション
WSGI_APPLICATION = 'config.wsgi.application'

# 国際化設定
LANGUAGE_CODE = 'ja'
TIME_ZONE = 'Asia/Tokyo'
USE_I18N = True
USE_TZ = True

# デフォルトのプライマリキーフィールドタイプ
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# データベース設定
# =============================================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', ''),
        'USER': os.getenv('DB_USER', ''),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
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
    'rest_framework',  # ← 追加（API用）
    'django_filters',  # ← 追加（フィルタリング用）
    'corsheaders',     # ← 追加（CORS用、必要に応じて）
    'django_q',
]

# ローカルアプリ
LOCAL_APPS = [
    'users',
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
    'margin_tracking',
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
    'subscriptions.middleware.SubscriptionMiddleware',  # サブスクリプション
    'ads.middleware.AdsMiddleware',  # 広告表示制御
    'axes.middleware.AxesMiddleware',
    'csp.middleware.CSPMiddleware',  # CSPミドルウェアを最後に配置
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
                'ads.context_processors.static_version',
                'users.context_processors.google_oauth_status',  # Google OAuth状態
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
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']  # 必須フィールド
ACCOUNT_UNIQUE_EMAIL = True  # メールアドレスの一意性
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'  # ソーシャルアカウントのメール検証なし
SOCIALACCOUNT_AUTO_SIGNUP = False  # 確認画面を表示してからサインアップ
SOCIALACCOUNT_LOGIN_ON_GET = True  # GETリクエストで直接ログイン
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'  # カスタムアダプター
SOCIALACCOUNT_FORMS = {
    'signup': 'users.forms.CustomSocialSignupForm',  # カスタムサインアップフォーム
}
SOCIALACCOUNT_REDIRECT_URLS = {
    'google': 'https://kabu-log.net/accounts/google/login/callback/'
}

# Google認証設定
# 環境変数からGoogle OAuth認証情報を取得（未設定の場合はGoogleログインボタンを非表示）
GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

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
        'APP': {
            'client_id': GOOGLE_OAUTH_CLIENT_ID,
            'secret': GOOGLE_OAUTH_CLIENT_SECRET,
            'key': '',
        }
    }
}

# Google OAuth が設定済みかどうかのフラグ
GOOGLE_OAUTH_ENABLED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)

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
# メール設定
# =============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # メールサーバー
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'kabulog.information@gmail.com'
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
if not EMAIL_HOST_PASSWORD and not os.getenv('DJANGO_TESTING'):
    raise ValueError("EMAIL_HOST_PASSWORD environment variable is required")
# デフォルトの送信元メールアドレス
DEFAULT_FROM_EMAIL = 'カブログ <kabulog.information@gmail.com>'
# =============================================================================
# ロギング設定
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'level': 'INFO',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'app.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
            'level': 'INFO',
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'error.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
            'level': 'ERROR',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'error_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'stockdiary': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'subscriptions': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'earnings_analysis': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'security': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'analysis_template': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file', 'error_file'],
        'level': 'WARNING',
    },
}

# =============================================================================
# サードパーティアプリ設定
# =============================================================================

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

# =============================================================================
# カスタムアプリ設定
# =============================================================================

# 広告設定
ADS_SETTINGS = {
    'DEFAULT_AD_CLIENT': 'ca-pub-3954701883136363',  # デフォルト広告クライアントID
    'SHOW_ADS_DEFAULT': True,  # デフォルトで広告表示
    'PREMIUM_USERS_NO_ADS': True,  # プレミアムユーザーには広告非表示
    'SHOW_ADS_ON_AUTH_PAGES': False,
}

# メンテナンスモード設定
MAINTENANCE_MODE = False  # メンテナンスモード有効
MAINTENANCE_ALLOWED_IPS = [
    '193.186.4.181',  # 管理者IP
    '192.168.1.100',  # 管理者IP
]
MAINTENANCE_EXEMPT_URLS = [
    r'^/static/.*',  # 静的ファイル
    r'^/media/.*',  # メディアファイル
    r'^/$',        # ランディングページ（ルートURL）
]
MAINTENANCE_END_TIME = '2025年3月23日 10:00 (JST)'  # メンテナンス終了予定時間
MAINTENANCE_CONTACT_EMAIL = 'kabulog.information@gmail.com'  # 問い合わせ用メール

# コンテンツセキュリティポリシー設定（django-csp 4.0 新形式）
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ["'self'", "cdn.jsdelivr.net", "*.googleapis.com", "*.gstatic.com", "*.bootstrapcdn.com", "unpkg.com"],
        'script-src': [
            "'self'",
            "'unsafe-inline'",
            "'unsafe-eval'",
            "unpkg.com",
            "https://unpkg.com",
            "cdn.jsdelivr.net",
            "*.jquery.com",
            "*.googleadservices.com",
            "*.google.com",
            "*.googleapis.com",
            "*.gstatic.com",
            "*.googlesyndication.com",
            "pagead2.googlesyndication.com",
            "*.doubleclick.net",
            "googleads.g.doubleclick.net",
            "*.bootstrapcdn.com",
            "*.googletagmanager.com",
            "www.googletagmanager.com",
            "https://www.googletagmanager.com",
            "https://pagead2.googlesyndication.com",
            "https://www.google-analytics.com",
            "https://ssl.google-analytics.com",
            "*.adtrafficquality.google",
            "https://adtrafficquality.google",
            "https://ep1.adtrafficquality.google",
            "https://ep2.adtrafficquality.google",
        ],
        'style-src': ["'self'", "'unsafe-inline'", "*.googleapis.com", "*.bootstrapcdn.com",
                      "https://cdn.jsdelivr.net", "https:", "data:"],
        'font-src': [
            "'self'",
            "data:",
            "*.googleapis.com",
            "*.gstatic.com",
            "*.bootstrapcdn.com",
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "https://fonts.gstatic.com",
        ],
        'img-src': ["'self'", "data:", "https:", "blob:", "*.google.com", "*.googleapis.com", "*.gstatic.com",
                    "*.doubleclick.net", "pagead2.googlesyndication.com"],
        'connect-src': [
            "'self'",
            "*.google.com",
            "*.doubleclick.net",
            "*.googleapis.com",
            "www.google-analytics.com",
            "stats.g.doubleclick.net",
            "*.googletagmanager.com",
            "https://www.googletagmanager.com",
            "https://adtrafficquality.google",
            "*.adtrafficquality.google",
            "https://ep1.adtrafficquality.google",
            "pagead2.googlesyndication.com",
            "*.googlesyndication.com",
            "https://ep2.adtrafficquality.google",
            "cdn.jsdelivr.net",
            "api.edinet-fsa.go.jp",
            "disclosure.edinet-fsa.go.jp",
        ],
        'frame-src': [
            "'self'",
            "*.google.com",
            "*.doubleclick.net",
            "https://*.doubleclick.net",
            "googleads.g.doubleclick.net",
            "tpc.googlesyndication.com",
            "www.googletagmanager.com",
            "*.googletagmanager.com",
            "*.googlesyndication.com",
            "pagead2.googlesyndication.com",
            "ep2.adtrafficquality.google",
            "*.adtrafficquality.google",
        ],
    }
}
# =============================================================================
# 現在使用していない設定（コメントアウト）
# =============================================================================

# Stripe設定
# STRIPE_PUBLISHABLE_KEY = 'pk_test_your_key_here'
# STRIPE_PUBLIC_KEY = 'pk_test_あなたのStripeパブリックキー'
# STRIPE_SECRET_KEY = 'sk_test_あなたのStripeシークレットキー'
# STRIPE_WEBHOOK_SECRET = 'whsec_あなたのWebhookシークレット'

# 5. レート制限の設定
RATE_LIMIT = {
    'payment_attempts': {
        'limit': 5,  # 試行回数
        'period': 600,  # 期間（秒）
    },
    'login_attempts': {
        'limit': 5,
        'period': 300,
    },
}

# 6. IP制限の設定
# 日本からのアクセスのみを許可（True=有効、False=無効）
JAPAN_ONLY_ACCESS = True

# または特定の高リスク国からのアクセスをブロック (オプション、JAPAN_ONLY_ACCESSがFalseの場合に使用)
HIGH_RISK_COUNTRIES = ['CN', 'RU', 'KP', 'IR']  # 例: 中国、ロシア、北朝鮮、イランなど

# django-axes の設定
AXES_FAILURE_LIMIT = 10  # 10回の失敗でロック
AXES_COOLOFF_TIME = 1  # ロックアウト期間（時間単位）
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address'] 

# 静的ファイルのキャッシュ期間を設定（秒単位）
# STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'


# スパム検出設定
SPAM_DETECTION = {
    # スパム判定の閾値
    'SPAM_THRESHOLD': 3,
    
    # レート制限（同一IPからの送信制限）
    'RATE_LIMIT_ATTEMPTS': 3,  # 1時間あたりの最大試行回数（認証が必要なため厳しく設定）
    'RATE_LIMIT_PERIOD': 3600,  # 期間（秒）
    
    # スパムキーワード（随時更新）
    'SPAM_KEYWORDS': [
        'wkxprysmyph',
        'accordini',
        'gfwljsiqtrr',
        'oyvjwyyrxg',
        'wkxprysmyphgpfwljsiqtrrxfdwdry',
        # 必要に応じて追加
    ],
    
    # 自動削除設定
    'AUTO_DELETE_SPAM_DAYS': 30,  # スパムメッセージの自動削除期間（日）
}

# 管理者への通知設定
ADMIN_NOTIFICATIONS = {
    'SPAM_ALERT_THRESHOLD': 10,  # 1日あたりのスパム件数がこの数を超えたら管理者に通知
    'SPAM_ALERT_EMAIL': 'kabulog.information@gmail.com',
}

# メール認証設定
EMAIL_VERIFICATION = {
    'EXPIRATION_HOURS': 24,  # 認証リンクの有効期限（時間）
    'CLEANUP_EXPIRED_HOURS': 48,  # 期限切れメッセージの削除期間（時間）
}
TEST_ACCOUNT_SETTINGS = {
    'USERNAMES': ['test', 'test1', 'test2', 'test3', 'demo1', 'demo2', 'demo3'],
    'SESSION_TIMEOUT': 7200,  # テストアカウントは2時間
    'CSRF_EXEMPT': True,  # テストアカウントのCSRF例外
}

# CSRFエラー時のカスタムビュー設定
CSRF_FAILURE_VIEW = 'stockdiary.views.csrf_failure_view'


# EDINET API設定
EDINET_API_SETTINGS = {
    'API_KEY': os.getenv('EDINET_API_KEY', ''),  # 環境変数から取得
    'BASE_URL': 'https://api.edinet-fsa.go.jp/api/v2',
    'RATE_LIMIT_DELAY': 2,  # リクエスト間隔（秒）
    'TIMEOUT': 120,         # タイムアウト（秒）
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
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',  # 本番では制限を検討
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# レート制限設定（既存設定に追加）
# 既存のRATE_LIMIT設定を拡張
if 'RATE_LIMIT' not in locals():
    RATE_LIMIT = {}

RATE_LIMIT.update({
    'analysis_requests': {
        'limit': 10,        # 本番環境では厳しく制限
        'period': 3600,     # 制限期間（秒）
    },
    'document_download': {
        'limit': 30,        # 1時間あたり30回のダウンロード
        'period': 3600,
    },
    'api_requests': {
        'limit': 100,       # 1時間あたり100回のAPI呼び出し
        'period': 3600,
    }
})


# 既存のLOGGING設定のhandlersとloggersに追加
LOGGING['handlers']['earnings_file'] = {
    'level': 'INFO',
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': os.path.join(BASE_DIR, 'logs', 'earnings_analysis.log'),
    'maxBytes': 10485760,  # 10MB
    'backupCount': 5,
    'formatter': 'verbose' if 'verbose' in LOGGING.get('formatters', {}) else None,
}

LOGGING['handlers']['sentiment_file'] = {
    'level': 'INFO',
    'class': 'logging.handlers.RotatingFileHandler', 
    'filename': os.path.join(BASE_DIR, 'logs', 'sentiment_analysis.log'),
    'maxBytes': 10485760,  # 10MB
    'backupCount': 5,
    'formatter': 'verbose' if 'verbose' in LOGGING.get('formatters', {}) else None,
}

LOGGING['loggers']['earnings_analysis'] = {
    'handlers': ['earnings_file', 'file'],  # 既存のfileハンドラーも使用
    'level': 'INFO',
    'propagate': True,
}

LOGGING['loggers']['earnings_analysis.services.sentiment_analysis'] = {
    'handlers': ['sentiment_file', 'file'],
    'level': 'INFO',
    'propagate': False,
}

# Celery設定（本番環境では将来的に使用）
# 現在はthreading.Threadを使用するため、CELERY_TASK_ALWAYS_EAGERをTrueに設定
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# 本番環境では当面はeager実行（同期実行）
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Celeryの基本設定（将来的にワーカーを使用する場合の準備）
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Tokyo'

CELERY_TASK_SOFT_TIME_LIMIT = 3600  # 1時間
CELERY_TASK_TIME_LIMIT = 4200  # 70分

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

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

AUTO_GENERATE_SUMMARY = True  # 自動要約生成を有効化

DATA_UPLOAD_MAX_NUMBER_FIELDS = 50000


WEBPUSH_SETTINGS = {
    'VAPID_PUBLIC_KEY': os.getenv('VAPID_PUBLIC_KEY', ''),
    'VAPID_PRIVATE_KEY': os.getenv('VAPID_PRIVATE_KEY', ''),
    'VAPID_ADMIN_EMAIL': os.getenv('VAPID_ADMIN_EMAIL', 'kabulog.information@gmail.com'),
}

# Django-Q設定
Q_CLUSTER = {
    'name': 'kabulog',
    'workers': 2,
    'recycle': 500,
    'timeout': 300,        # タスクのタイムアウト: 5分（PDF処理は60〜150秒かかるため延長）
    'retry': 900,          # リトライ待機時間: 15分（timeoutより大きく）
    'compress': True,
    'save_limit': 100,
    'queue_limit': 300,
    'label': 'Django Q',
    'orm': 'default',      # Redis不要: Django ORM (PostgreSQL) をブローカーとして使用
}

STATIC_VERSION = '1.2.7'
