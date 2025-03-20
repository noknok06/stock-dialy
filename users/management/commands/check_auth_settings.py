from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

class Command(BaseCommand):
    help = 'django-allauthの設定を確認します'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('django-allauthの設定を確認中...'))
        errors = []
        warnings = []

        # INSTALLED_APPSの確認
        required_apps = [
            'django.contrib.sites',
            'allauth',
            'allauth.account',
            'allauth.socialaccount',
            'allauth.socialaccount.providers.google',
        ]

        for app in required_apps:
            if app not in settings.INSTALLED_APPS:
                errors.append(f'INSTALLED_APPSに {app} が含まれていません')

        # MIDDLEWAREの確認
        required_middleware = 'allauth.account.middleware.AccountMiddleware'
        if required_middleware not in settings.MIDDLEWARE:
            errors.append(f'MIDDLEWAREに {required_middleware} が含まれていません')

        # AUTHENTICATION_BACKENDSの確認
        try:
            required_backend = 'allauth.account.auth_backends.AuthenticationBackend'
            if required_backend not in settings.AUTHENTICATION_BACKENDS:
                errors.append(f'AUTHENTICATION_BACKENDSに {required_backend} が含まれていません')
        except AttributeError:
            errors.append('AUTHENTICATION_BACKENDSが設定されていません')

        # SITE_IDの確認
        try:
            site_id = settings.SITE_ID
            if not site_id:
                errors.append('SITE_IDが設定されていません')
        except AttributeError:
            errors.append('SITE_IDが設定されていません')

        # SOCIALACCOUNT_PROVIDERSの確認
        try:
            providers = settings.SOCIALACCOUNT_PROVIDERS
            if 'google' not in providers:
                warnings.append('SOCIALACCOUNTPROVIDERSにgoogleが含まれていません')
            else:
                google_settings = providers['google']
                if 'SCOPE' not in google_settings:
                    warnings.append('google設定にSCOPEが含まれていません')
                elif 'profile' not in google_settings['SCOPE'] or 'email' not in google_settings['SCOPE']:
                    warnings.append('googleのSCOPEにprofileとemailが含まれていません')
        except AttributeError:
            warnings.append('SOCIALACCOUNT_PROVIDERSが設定されていません')

        # リダイレクトURLの確認
        try:
            login_redirect = settings.LOGIN_REDIRECT_URL
            if not login_redirect:
                warnings.append('LOGIN_REDIRECT_URLが設定されていません')
        except AttributeError:
            warnings.append('LOGIN_REDIRECT_URLが設定されていません')

        try:
            logout_redirect = settings.ACCOUNT_LOGOUT_REDIRECT_URL
            if not logout_redirect:
                warnings.append('ACCOUNT_LOGOUT_REDIRECT_URLが設定されていません')
        except AttributeError:
            warnings.append('ACCOUNT_LOGOUT_REDIRECT_URLが設定されていません')

        # 結果の表示
        if errors:
            self.stdout.write(self.style.ERROR('以下の重大な問題が見つかりました:'))
            for error in errors:
                self.stdout.write(self.style.ERROR(f'- {error}'))
            self.stdout.write(self.style.ERROR('これらの問題を解決するまで認証機能は正しく動作しません。'))
        else:
            self.stdout.write(self.style.SUCCESS('必須の設定はすべて正しく行われています。'))

        if warnings:
            self.stdout.write(self.style.WARNING('以下の警告があります:'))
            for warning in warnings:
                self.stdout.write(self.style.WARNING(f'- {warning}'))
            self.stdout.write(self.style.WARNING('これらの警告は修正することをお勧めしますが、基本機能は動作するかもしれません。'))

        # 使用している設定の表示
        self.stdout.write(self.style.NOTICE('\n現在の設定情報:'))
        self.stdout.write(f'SITE_ID: {getattr(settings, "SITE_ID", "未設定")}')
        
        try:
            self.stdout.write(f'LOGIN_REDIRECT_URL: {settings.LOGIN_REDIRECT_URL}')
        except AttributeError:
            self.stdout.write('LOGIN_REDIRECT_URL: 未設定')
            
        try:
            self.stdout.write(f'ACCOUNT_LOGOUT_REDIRECT_URL: {settings.ACCOUNT_LOGOUT_REDIRECT_URL}')
        except AttributeError:
            self.stdout.write('ACCOUNT_LOGOUT_REDIRECT_URL: 未設定')
            
        try:
            self.stdout.write(f'ACCOUNT_EMAIL_VERIFICATION: {settings.ACCOUNT_EMAIL_VERIFICATION}')
        except AttributeError:
            self.stdout.write('ACCOUNT_EMAIL_VERIFICATION: 未設定')
            
        self.stdout.write(self.style.SUCCESS('\n設定確認完了。'))