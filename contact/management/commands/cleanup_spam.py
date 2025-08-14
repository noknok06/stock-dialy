from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from contact.models import ContactMessage
import datetime

class Command(BaseCommand):
    help = 'スパムメッセージを自動削除します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=getattr(settings, 'SPAM_DETECTION', {}).get('AUTO_DELETE_SPAM_DAYS', 30),
            help='何日前のスパムメッセージを削除するか（デフォルト: 30日）'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際には削除せず、削除対象を表示するだけ'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        # 指定日数より古いスパムメッセージを取得
        cutoff_date = timezone.now() - datetime.timedelta(days=days)
        spam_messages = ContactMessage.objects.filter(
            is_spam=True,
            created_at__lt=cutoff_date
        )
        
        count = spam_messages.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(f'{days}日より古いスパムメッセージはありません。')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'削除対象: {count}件のスパムメッセージ（{days}日より古い）')
            )
            for msg in spam_messages[:10]:  # 最初の10件を表示
                self.stdout.write(f'  - {msg.created_at}: {msg.name} ({msg.email})')
            if count > 10:
                self.stdout.write(f'  ... その他 {count - 10}件')
        else:
            spam_messages.delete()
            self.stdout.write(
                self.style.SUCCESS(f'{count}件のスパムメッセージを削除しました。')
            )
            
            # ログ出力
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'スパムメッセージ自動削除: {count}件削除（{days}日より古い）')

