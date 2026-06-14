# stockdiary/management/commands/reset_demo.py
"""デモ体験用の共有アカウントを用意し、データを初期状態へリセットする。

ワンクリック「デモを試す」（users.views.demo_login）でログインする共有ユーザーを
provision し、create_realistic_test_data で物語性のあるデモデータを再投入する。

- 初回デプロイ時に1回実行してデモユーザーを作成
- 以降は cron / django-q で定期実行（例: 毎日深夜）して荒れたデータを初期化

デモユーザーはパスワードログイン不可（set_unusable_password）にし、
demo_login の明示的バイパス経由でのみ入れるようにする。staff/superuser は付与しない。

使い方:
    python manage.py reset_demo
    python manage.py reset_demo --username demo
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = 'デモ共有アカウントを作成・維持し、デモデータを初期状態へリセットします'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username', type=str,
            default=getattr(settings, 'DEMO_USERNAME', 'demo'),
            help='デモ用ユーザー名（デフォルト: settings.DEMO_USERNAME）',
        )

    def handle(self, *args, **options):
        username = options['username']

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': f'{username}@kabulog.local', 'is_active': True},
        )

        # 事故防止: デモユーザーは常に一般権限・パスワードログイン不可に保つ
        changed = False
        if user.is_staff or user.is_superuser:
            user.is_staff = False
            user.is_superuser = False
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if user.has_usable_password():
            user.set_unusable_password()
            changed = True
        if created or changed:
            user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f'👤 デモユーザー "{username}" を作成しました'))
        else:
            self.stdout.write(f'👤 デモユーザー "{username}" を確認しました')

        # データを初期状態へ（--clear で既存日記を削除してから再投入）
        call_command('create_realistic_test_data', '--username', username, '--clear')

        self.stdout.write(self.style.SUCCESS('✅ デモのリセットが完了しました'))
