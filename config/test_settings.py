from .settings import *

DEBUG = True
SECRET_KEY = 'ci-test-secret-key-not-for-production'
ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',
    }
}

ROOT_URLCONF = 'config.test_urls'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
MIDDLEWARE = [m for m in MIDDLEWARE if 'subscription' not in m.lower()]
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# テスト環境では ManifestStaticFilesStorage を使用しない（collectstatic 不要に）。
# 基底 settings は STORAGES dict を定義しているため、レガシーな STATICFILES_STORAGE は
# 併用できない（Django が ImproperlyConfigured を投げる）。STORAGES を上書きする。
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
