from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

class Command(BaseCommand):
    help = 'GoogleのOAuth認証設定を作成します'

    def add_arguments(self, parser):
        parser.add_argument('--client_id', type=str, help='GoogleのクライアントID')
        parser.add_argument('--secret', type=str, help='Googleのクライアントシークレット')
        parser.add_argument('--domain', type=str, default='example.com', help='サイトのドメイン')
        parser.add_argument('--name', type=str, default='localhost:8000', help='サイト名')

    def handle(self, *args, **options):
        client_id = options.get('client_id')
        secret = options.get('secret')
        domain = options.get('domain')
        name = options.get('name')

        if not client_id or not secret:
            self.stdout.write(self.style.ERROR('クライアントIDとシークレットは必須です。'))
            self.stdout.write(self.style.WARNING('使用例: python manage.py setup_google_auth --client_id=YOUR_CLIENT_ID --secret=YOUR_SECRET'))
            return

        # サイト設定の取得または作成
        try:
            site = Site.objects.get(id=1)
            site.domain = domain
            site.name = name
            site.save()
            self.stdout.write(self.style.SUCCESS(f'サイト設定を更新しました: {site.domain}'))
        except Site.DoesNotExist:
            site = Site.objects.create(domain=domain, name=name)
            self.stdout.write(self.style.SUCCESS(f'新しいサイト設定を作成しました: {site.domain}'))

        # Google App設定の取得または作成
        try:
            app = SocialApp.objects.get(provider='google')
            app.name = 'Google'
            app.client_id = client_id
            app.secret = secret
            app.save()
            self.stdout.write(self.style.SUCCESS('既存のGoogle認証設定を更新しました'))
        except SocialApp.DoesNotExist:
            app = SocialApp.objects.create(
                provider='google',
                name='Google',
                client_id=client_id,
                secret=secret
            )
            self.stdout.write(self.style.SUCCESS('新しいGoogle認証設定を作成しました'))

        # サイトとアプリを関連付け
        app.sites.add(site)
        self.stdout.write(self.style.SUCCESS('Google認証の設定が完了しました！'))
        self.stdout.write(self.style.NOTICE(f'クライアントID: {client_id}'))
        self.stdout.write(self.style.NOTICE(f'サイトドメイン: {domain}'))
        self.stdout.write(self.style.NOTICE('Googleログインが利用可能になりました。'))