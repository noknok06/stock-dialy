# stockdiary/management/commands/send_notifications.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from stockdiary.models import DiaryNotification, NotificationLog
from stockdiary.api_views import send_push_notification
from datetime import timedelta


class Command(BaseCommand):
    help = '定期的に実行して通知を送信'

    def handle(self, *args, **options):
        now = timezone.now()
        
        # リマインダー通知をチェック
        reminder_notifications = DiaryNotification.objects.filter(
            notification_type='reminder',
            is_active=True,
            remind_at__lte=now,
            remind_at__gte=now - timedelta(minutes=5)
        )
        
        for notification in reminder_notifications:
            self.send_reminder(notification)
        
        # 定期通知をチェック
        periodic_notifications = DiaryNotification.objects.filter(
            notification_type='periodic',
            is_active=True
        )
        
        for notification in periodic_notifications:
            self.send_periodic(notification, now)
        
        self.stdout.write(self.style.SUCCESS('通知送信完了'))

    def send_reminder(self, notification):
        diary = notification.diary
        user = diary.user
        
        title = f'{diary.stock_name}のリマインダー'
        message = notification.message or '設定した日時になりました'
        url = f'/stockdiary/{diary.id}/'
        
        # プッシュ通知送信
        send_push_notification(user, title, message, url)
        
        # ログに記録
        NotificationLog.objects.create(
            notification=notification,
            user=user,
            title=title,
            message=message,
            url=url
        )
        
        # 送信済みにマーク
        notification.last_sent = timezone.now()
        notification.is_active = False  # リマインダーは1回のみ
        notification.save()
        
        self.stdout.write(f'リマインダー送信: {title}')

    def send_periodic(self, notification, now):
        # 前回送信から期間が経過しているかチェック
        if notification.last_sent:
            if notification.frequency == 'daily':
                next_send = notification.last_sent + timedelta(days=1)
            elif notification.frequency == 'weekly':
                next_send = notification.last_sent + timedelta(weeks=1)
            elif notification.frequency == 'monthly':
                next_send = notification.last_sent + timedelta(days=30)
            else:
                return
            
            if now < next_send:
                return
        
        # 指定時刻かチェック
        if notification.notify_time:
            if abs((now.time().hour * 60 + now.time().minute) - 
                   (notification.notify_time.hour * 60 + notification.notify_time.minute)) > 5:
                return
        
        diary = notification.diary
        user = diary.user
        
        title = f'{diary.stock_name}の定期通知'
        message = notification.message or '定期確認の時間です'
        url = f'/stockdiary/{diary.id}/'
        
        send_push_notification(user, title, message, url)
        
        NotificationLog.objects.create(
            notification=notification,
            user=user,
            title=title,
            message=message,
            url=url
        )
        
        notification.last_sent = now
        notification.save()
        
        self.stdout.write(f'定期通知送信: {title}')