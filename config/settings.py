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
import dj_database_url
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

# 本番環境用デバッグ設定（無効）
DEBUG = False

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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'kabulog'),
        'USER': os.getenv('DB_USER', 'naoki'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
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
    'google': 'https://kabu-log.net/accounts/google/login/callback/'
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
# メール設定
# =============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # メールサーバー
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'kabulog.information@gmail.com'
EMAIL_HOST_PASSWORD = 'wfsdxbdxsdusvddw'  # 注意: 環境変数を使用することをお勧めします

# =============================================================================
# ロギング設定
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'django-error.log'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
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

# コンテンツセキュリティポリシー設定
CSP_DEFAULT_SRC = ["'self'", "cdn.jsdelivr.net", "*.googleapis.com", "*.gstatic.com", "*.bootstrapcdn.com"]
CSP_SCRIPT_SRC = ["'self'", "'unsafe-inline'", "'unsafe-eval'", 
                  "cdn.jsdelivr.net", "*.jquery.com", "*.googleadservices.com", 
                  "*.google.com", "*.googleapis.com", "*.gstatic.com",
                  "*.googlesyndication.com", "*.doubleclick.net", "*.bootstrapcdn.com"]
CSP_STYLE_SRC = ["'self'", "'unsafe-inline'", "*.googleapis.com", "*.bootstrapcdn.com", "cdn.jsdelivr.net", "https:", "data:"]
CSP_FONT_SRC = ["'self'", "data:", "*.googleapis.com", "*.gstatic.com", "*.bootstrapcdn.com", "cdn.jsdelivr.net"]
CSP_IMG_SRC = ["'self'", "data:", "blob:", "*.google.com", "*.googleapis.com", "*.gstatic.com", "*.doubleclick.net"]
CSP_CONNECT_SRC = ["'self'", "*.google.com", "*.doubleclick.net", "*.googleapis.com"]
CSP_FRAME_SRC = ["'self'", "*.google.com", "*.doubleclick.net"]

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