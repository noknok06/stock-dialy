from django.core.management.base import BaseCommand, CommandError
from security.models import BlockedIP, BlockedEmail
from django.contrib.auth import get_user_model
import ipaddress

User = get_user_model()

class Command(BaseCommand):
    help = 'IPアドレスやメールアドレスのブロック管理'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['add-ip', 'add-email', 'remove-ip', 'remove-email', 'list'],
            help='実行するアクション'
        )
        parser.add_argument(
            '--value',
            type=str,
            help='ブロック対象の値（IPアドレスまたはメールアドレス）'
        )
        parser.add_argument(
            '--reason',
            type=str,
            default='manual',
            choices=['spam', 'abuse', 'security', 'manual', 'automated'],
            help='ブロック理由'
        )
        parser.add_argument(
            '--description',
            type=str,
            default='',
            help='ブロック理由の詳細説明'
        )
        parser.add_argument(
            '--email-type',
            type=str,
            default='exact',
            choices=['exact', 'domain', 'pattern'],
            help='メールブロックのタイプ'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'list':
            self._list_blocks()
        elif action in ['add-ip', 'add-email', 'remove-ip', 'remove-email']:
            if not options['value']:
                raise CommandError('--value が必要です')
            
            if action == 'add-ip':
                self._add_ip_block(options)
            elif action == 'add-email':
                self._add_email_block(options)
            elif action == 'remove-ip':
                self._remove_ip_block(options['value'])
            elif action == 'remove-email':
                self._remove_email_block(options['value'])
    
    def _add_ip_block(self, options):
        ip_value = options['value']
        
        # IPアドレスの妥当性チェック
        try:
            ipaddress.ip_address(ip_value)
        except ValueError:
            raise CommandError(f'無効なIPアドレス: {ip_value}')
        
        blocked_ip, created = BlockedIP.objects.get_or_create(
            ip_address=ip_value,
            defaults={
                'reason': options['reason'],
                'description': options['description'],
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'IPアドレス {ip_value} をブロックリストに追加しました')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'IPアドレス {ip_value} は既にブロックリストに存在します')
            )
    
    def _add_email_block(self, options):
        email_value = options['value']
        email_type = options['email_type']
        
        blocked_email, created = BlockedEmail.objects.get_or_create(
            email_pattern=email_value.lower(),
            defaults={
                'block_type': email_type,
                'reason': options['reason'],
                'description': options['description'],
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'メールアドレス {email_value} をブロックリストに追加しました')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'メールアドレス {email_value} は既にブロックリストに存在します')
            )
    
    def _remove_ip_block(self, ip_value):
        try:
            blocked_ip = BlockedIP.objects.get(ip_address=ip_value)
            blocked_ip.is_active = False
            blocked_ip.save()
            self.stdout.write(
                self.style.SUCCESS(f'IPアドレス {ip_value} のブロックを無効化しました')
            )
        except BlockedIP.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'IPアドレス {ip_value} はブロックリストに存在しません')
            )
    
    def _remove_email_block(self, email_value):
        try:
            blocked_email = BlockedEmail.objects.get(email_pattern=email_value.lower())
            blocked_email.is_active = False
            blocked_email.save()
            self.stdout.write(
                self.style.SUCCESS(f'メールアドレス {email_value} のブロックを無効化しました')
            )
        except BlockedEmail.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'メールアドレス {email_value} はブロックリストに存在しません')
            )
    
    def _list_blocks(self):
        self.stdout.write(self.style.WARNING('=== ブロック済みIPアドレス ==='))
        for blocked_ip in BlockedIP.objects.filter(is_active=True)[:20]:
            status = "有効" if not blocked_ip.is_expired() else "期限切れ"
            self.stdout.write(f'{blocked_ip.ip_address} ({blocked_ip.get_reason_display()}) - {status}')
        
        self.stdout.write(self.style.WARNING('\n=== ブロック済みメールアドレス ==='))
        for blocked_email in BlockedEmail.objects.filter(is_active=True)[:20]:
            status = "有効" if not blocked_email.is_expired() else "期限切れ"
            self.stdout.write(f'{blocked_email.email_pattern} ({blocked_email.get_reason_display()}) - {status}')

