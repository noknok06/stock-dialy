"""
manage.py generate_analysis_key

分析API用のAPIキーを生成して .env に追記する手順を案内する。
"""
import secrets

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = '分析API用 ANALYSIS_API_KEY を生成して表示します'

    def handle(self, *args, **options):
        existing = getattr(settings, 'ANALYSIS_API_KEY', None)

        if existing:
            self.stdout.write(self.style.WARNING('既にキーが設定されています。'))
            self.stdout.write(f'現在のキー: {existing}')
            self.stdout.write('')
            self.stdout.write('再生成する場合は .env の ANALYSIS_API_KEY を削除してから再実行してください。')
            return

        key = secrets.token_urlsafe(32)
        self.stdout.write(self.style.SUCCESS('=== 分析API キー生成 ==='))
        self.stdout.write('')
        self.stdout.write(f'ANALYSIS_API_KEY={key}')
        self.stdout.write('')
        self.stdout.write('↑ この行を .env ファイルに追記してください。')
        self.stdout.write('')
        self.stdout.write('── 使い方（curl）────────────────────────────────────────')
        self.stdout.write(f'curl -H "Authorization: Bearer {key}" https://あなたのサーバー/api/analysis/holdings/')
        self.stdout.write(f'curl -H "Authorization: Bearer {key}" https://あなたのサーバー/api/analysis/diary/7203/')
        self.stdout.write(f'curl -H "Authorization: Bearer {key}" https://あなたのサーバー/api/analysis/portfolio/')
        self.stdout.write('')
        self.stdout.write('── .env に追記する内容（2行）──────────────────────────────')
        self.stdout.write(f'ANALYSIS_API_KEY={key}')
        self.stdout.write('ANALYSIS_API_USER=<あなたのDjangoユーザー名>  # 書き込みAPIの対象ユーザー')
