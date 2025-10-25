# stockdiary/management/commands/register_push_device.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from stockdiary.models import PushSubscription
import json

User = get_user_model()


class Command(BaseCommand):
    help = 'プッシュ通知デバイスを手動登録（テスト用）'
    
    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='ユーザー名')
    
    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ ユーザー "{username}" が見つかりません'))
            return
        
        # ダミーのサブスクリプションを作成（テスト用）
        # 注意: これは実際には通知を送信できませんが、動作確認には使えます
        test_subscription = PushSubscription.objects.create(
            user=user,
            endpoint='https://fcm.googleapis.com/fcm/send/test-endpoint-' + user.username,
            p256dh='test-p256dh-key',
            auth='test-auth-key',
            device_name='Test Device',
            user_agent='Test User Agent',
            is_active=True
        )
        
        self.stdout.write(self.style.SUCCESS(f'✅ テストデバイスを登録しました'))
        self.stdout.write(f'User: {user.username}')
        self.stdout.write(f'Device ID: {test_subscription.id}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('⚠️ これはテストデバイスです'))
        self.stdout.write('実際のプッシュ通知を受信するには、ブラウザから登録する必要があります')