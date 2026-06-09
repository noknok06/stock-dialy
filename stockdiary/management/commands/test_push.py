# stockdiary/management/commands/test_push.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings

from stockdiary.models import PushSubscription

User = get_user_model()


class Command(BaseCommand):
    help = (
        'プッシュ通知の疎通を診断する。対象ユーザーの全 PushSubscription に '
        'テストプッシュを送り、購読ごとの成否を表示する。'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            required=True,
            help='対象ユーザー（username または email）'
        )

    def handle(self, *args, **options):
        identifier = options['user']

        # VAPID 鍵の設定状況を先に確認
        public_key = settings.WEBPUSH_SETTINGS.get('VAPID_PUBLIC_KEY')
        private_key = settings.WEBPUSH_SETTINGS.get('VAPID_PRIVATE_KEY')
        if not public_key:
            self.stdout.write(self.style.ERROR('❌ VAPID_PUBLIC_KEY が未設定です（購読が作成できません）'))
        if not private_key:
            self.stdout.write(self.style.ERROR('❌ VAPID_PRIVATE_KEY が未設定です（送信できません）'))
        if public_key and private_key:
            self.stdout.write(self.style.SUCCESS('✅ VAPID 鍵は設定済みです'))

        # ユーザーを解決（username → email の順）
        user = User.objects.filter(username=identifier).first()
        if user is None:
            user = User.objects.filter(email=identifier).first()
        if user is None:
            self.stdout.write(self.style.ERROR(f'❌ ユーザー "{identifier}" が見つかりません'))
            return

        subscriptions = PushSubscription.objects.filter(user=user, is_active=True)
        count = subscriptions.count()
        self.stdout.write(f'対象ユーザー: {user.username} / 有効な購読: {count} 件')

        if count == 0:
            self.stdout.write(self.style.WARNING(
                '⚠️ 有効な PushSubscription がありません。'
                'ブラウザで通知を有効化（subscribe）できているか確認してください。'
            ))
            return

        # 購読ごとに送信して結果を表示
        from pywebpush import webpush, WebPushException
        import json

        payload = json.dumps({
            'title': 'テストプッシュ',
            'message': 'test_push コマンドからの疎通テストです。',
            'url': '/stockdiary/',
            'tag': 'test_push',
            'notification_id': None,
            'icon': '/static/images/icon-192.svg',
            'badge': '/static/images/badge-72.png',
        })

        success = 0
        for sub in subscriptions:
            label = f'sub_id={sub.id} device="{sub.device_name or "?"}"'
            try:
                webpush(
                    subscription_info={
                        'endpoint': sub.endpoint,
                        'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                    },
                    data=payload,
                    vapid_private_key=private_key,
                    vapid_claims={
                        'sub': f'mailto:{settings.WEBPUSH_SETTINGS.get("VAPID_ADMIN_EMAIL")}'
                    },
                )
                success += 1
                self.stdout.write(self.style.SUCCESS(f'  ✅ 送信成功: {label}'))
            except WebPushException as e:
                status = e.response.status_code if e.response is not None else None
                body = e.response.text if e.response is not None else ''
                self.stdout.write(self.style.ERROR(
                    f'  ❌ 送信失敗: {label} status={status} {body or str(e)}'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ 想定外エラー: {label} {e}'))

        self.stdout.write(self.style.SUCCESS(f'完了: 成功 {success}/{count} 件'))
