from django.core.management.base import BaseCommand
from django.utils import timezone
from security.models import BlockedIP, BlockedEmail, BlockLog
import datetime

class Command(BaseCommand):
    help = '期限切れのブロック設定とログを削除します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--log-days',
            type=int,
            default=90,
            help='何日前のブロックログを削除するか（デフォルト: 90日）'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際には削除せず、削除対象を表示するだけ'
        )

    def handle(self, *args, **options):
        log_days = options['log_days']
        dry_run = options['dry_run']
        
        now = timezone.now()
        
        # 期限切れのIPブロックを無効化
        expired_ips = BlockedIP.objects.filter(
            is_active=True,
            expires_at__isnull=False,
            expires_at__lt=now
        )
        ip_count = expired_ips.count()
        
        if not dry_run and ip_count > 0:
            expired_ips.update(is_active=False)
        
        # 期限切れのメールブロックを無効化
        expired_emails = BlockedEmail.objects.filter(
            is_active=True,
            expires_at__isnull=False,
            expires_at__lt=now
        )
        email_count = expired_emails.count()
        
        if not dry_run and email_count > 0:
            expired_emails.update(is_active=False)
        
        # 古いブロックログを削除
        cutoff_date = now - datetime.timedelta(days=log_days)
        old_logs = BlockLog.objects.filter(blocked_at__lt=cutoff_date)
        log_count = old_logs.count()
        
        if not dry_run and log_count > 0:
            old_logs.delete()
        
        # 結果を出力
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'削除対象:\n'
                    f'  - 期限切れIPブロック: {ip_count}件\n'
                    f'  - 期限切れメールブロック: {email_count}件\n'
                    f'  - 古いブロックログ: {log_count}件（{log_days}日より古い）'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'クリーンアップ完了:\n'
                    f'  - 期限切れIPブロック: {ip_count}件を無効化\n'
                    f'  - 期限切れメールブロック: {email_count}件を無効化\n'
                    f'  - 古いブロックログ: {log_count}件を削除'
                )
            )
