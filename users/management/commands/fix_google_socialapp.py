"""
Django管理コマンド: 重複したGoogle SocialAppエントリを確認・修正

使用方法:
1. このファイルを users/management/commands/fix_google_socialapp.py に配置
2. python manage.py fix_google_socialapp --check  # 現状確認
3. python manage.py fix_google_socialapp --fix    # 重複を修正
"""

from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = '重複したGoogle SocialAppエントリを確認・修正します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='重複の確認のみ（変更なし）',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='重複を修正する',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Google SocialApp の状態を確認中...'))
        
        # Google SocialAppを全て取得
        google_apps = SocialApp.objects.filter(provider='google')
        count = google_apps.count()
        
        self.stdout.write(f'見つかったGoogle SocialApp: {count}件')
        
        if count == 0:
            self.stdout.write(self.style.WARNING('Google SocialAppが見つかりません'))
            self.stdout.write('以下のコマンドで設定を作成してください:')
            self.stdout.write('python manage.py setup_google_auth --client_id=YOUR_CLIENT_ID --secret=YOUR_SECRET')
            return
        
        # 各SocialAppの詳細を表示
        for i, app in enumerate(google_apps, 1):
            self.stdout.write(f'\n--- Google SocialApp #{i} ---')
            self.stdout.write(f'ID: {app.id}')
            self.stdout.write(f'名前: {app.name}')
            self.stdout.write(f'クライアントID: {app.client_id}')
            self.stdout.write(f'シークレット: {app.secret[:10]}...' if app.secret else 'なし')
            sites = app.sites.all()
            if sites:
                self.stdout.write(f'関連サイト: {", ".join([s.domain for s in sites])}')
            else:
                self.stdout.write('関連サイト: なし')
        
        # 重複がある場合
        if count > 1:
            self.stdout.write(self.style.WARNING(f'\n⚠️ 重複が見つかりました: {count}件のGoogle SocialApp'))
            
            if options['check']:
                self.stdout.write(self.style.NOTICE('\n修正するには --fix オプションを使用してください:'))
                self.stdout.write('python manage.py fix_google_socialapp --fix')
                return
            
            if options['fix']:
                self.stdout.write(self.style.WARNING('\n重複を修正します...'))
                
                # 環境変数から正しい設定を取得
                from django.conf import settings
                correct_client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
                correct_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', '')
                
                if not correct_client_id or not correct_secret:
                    self.stdout.write(self.style.ERROR('環境変数 GOOGLE_CLIENT_ID と GOOGLE_CLIENT_SECRET が設定されていません'))
                    return
                
                # 正しい設定のSocialAppを見つけるか作成
                correct_app = None
                for app in google_apps:
                    if app.client_id == correct_client_id and app.secret == correct_secret:
                        correct_app = app
                        break
                
                if correct_app:
                    self.stdout.write(f'正しい設定が見つかりました: ID {correct_app.id}')
                    # 他のアプリを削除
                    for app in google_apps:
                        if app.id != correct_app.id:
                            self.stdout.write(f'削除中: ID {app.id}')
                            app.delete()
                else:
                    # 最初のアプリを更新して使用
                    first_app = google_apps.first()
                    self.stdout.write(f'ID {first_app.id} を正しい設定で更新中...')
                    first_app.client_id = correct_client_id
                    first_app.secret = correct_secret
                    first_app.name = 'Google'
                    first_app.save()
                    
                    # サイトの関連付けを確認
                    site = Site.objects.get(id=1)
                    if site not in first_app.sites.all():
                        first_app.sites.add(site)
                        self.stdout.write(f'サイト {site.domain} を関連付けました')
                    
                    correct_app = first_app
                    
                    # 他のアプリを削除
                    for app in google_apps:
                        if app.id != correct_app.id:
                            self.stdout.write(f'削除中: ID {app.id}')
                            app.delete()
                
                self.stdout.write(self.style.SUCCESS('\n✓ 修正が完了しました'))
                
                # 最終確認
                final_count = SocialApp.objects.filter(provider='google').count()
                self.stdout.write(f'現在のGoogle SocialApp: {final_count}件')
                
        elif count == 1:
            self.stdout.write(self.style.SUCCESS('\n✓ Google SocialAppは正常です（1件のみ）'))
            
            # 設定の確認
            app = google_apps.first()
            from django.conf import settings
            expected_client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
            expected_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', '')
            
            if app.client_id != expected_client_id or app.secret != expected_secret:
                self.stdout.write(self.style.WARNING('\n⚠️ 環境変数と一致しません'))
                self.stdout.write(f'DB: {app.client_id}')
                self.stdout.write(f'環境変数: {expected_client_id}')
                
                if options['fix']:
                    self.stdout.write('設定を更新中...')
                    app.client_id = expected_client_id
                    app.secret = expected_secret
                    app.save()
                    self.stdout.write(self.style.SUCCESS('✓ 更新完了'))