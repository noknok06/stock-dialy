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
