# config/test_settings.py を次のように変更
from .settings import *

DEBUG = True
SECRET_KEY = 'test-secret-key'
ALLOWED_HOSTS = ['*']

# subscriptionsアプリを完全に無効化
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'subscriptions']

# テスト用データベース設定 - ファイルベースにして明示的に削除
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'test_db.sqlite3',  # 一時的なファイル名
        'TEST': {
            'NAME': 'test_db.sqlite3',
        }
    }
}

# ROOT_URLCONFも上書き
ROOT_URLCONF = 'config.test_urls'

# パスワードハッシュを高速化
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# ミドルウェアから不要なものを削除
MIDDLEWARE = [m for m in MIDDLEWARE if 'subscription' not in m.lower()]