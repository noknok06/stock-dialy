from django.core.management.base import BaseCommand
from security.models import BlockedIP

class Command(BaseCommand):
    help = '緊急時：すべてのIPブロックを無効化'

    def handle(self, *args, **options):
        # すべてのIPブロックを無効化
        count = BlockedIP.objects.filter(is_active=True).update(is_active=False)
        self.stdout.write(
            self.style.SUCCESS(f'緊急対応: {count}件のIPブロックを無効化しました')
        )