# stockdiary/services/notification_service.py
from django.utils import timezone
from datetime import timedelta
import logging

from ..models import DiaryNotification, NotificationLog
from ..api_views import send_push_notification

logger = logging.getLogger(__name__)


class NotificationService:
    """通知送信サービス（リマインダーのみ）"""
    
    @classmethod
    def process_all_notifications(cls):
        """リマインダー通知を処理"""
        results = {
            'reminder': cls.process_reminder_notifications(),
        }
        
        total_sent = results['reminder']['sent']
        total_errors = results['reminder']['errors']
        
        logger.info(
            f"通知処理完了: 送信={total_sent}, エラー={total_errors}"
        )
        
        return {
            'total_sent': total_sent,
            'total_errors': total_errors,
            'details': results
        }
    
    @classmethod
    def process_reminder_notifications(cls):
        """リマインダー通知を処理"""
        now = timezone.now()
        sent = 0
        errors = 0
        error_details = []
        
        logger.info(f"リマインダー通知処理開始: {now}")
        
        # 現在時刻を過ぎたリマインダーを取得
        reminders = DiaryNotification.objects.filter(
            is_active=True,
            remind_at__lte=now,
            remind_at__gt=now - timedelta(minutes=5)
        ).select_related('diary', 'diary__user')
        
        logger.info(f"対象リマインダー数: {reminders.count()}")
        
        for reminder in reminders:
            try:
                logger.info(f"リマインダー処理中: ID={reminder.id}, "
                        f"銘柄={reminder.diary.stock_name}, "
                        f"ユーザー={reminder.diary.user.username}")
                
                # 過去24時間以内に送信済みかチェック
                if cls._is_recently_sent(reminder):
                    logger.info(f"  → スキップ: 最近送信済み (last_sent={reminder.last_sent})")
                    continue
                
                # 通知送信
                success = cls._send_notification(
                    user=reminder.diary.user,
                    title=f"📌 {reminder.diary.stock_name} のリマインダー",
                    message=reminder.message or f"{reminder.diary.stock_name}を確認しましょう",
                    url=f"/stockdiary/{reminder.diary.id}/",
                    notification=reminder
                )
                
                if success:
                    sent += 1
                    logger.info(f"  → 送信成功")
                    # リマインダーは1回のみなので無効化
                    reminder.is_active = False
                    reminder.last_sent = now
                    reminder.save()
                else:
                    errors += 1
                    error_msg = f"送信失敗: ID={reminder.id}"
                    logger.error(f"  → {error_msg}")
                    error_details.append(error_msg)
                    
            except Exception as e:
                error_msg = f"リマインダー送信エラー (ID={reminder.id}): {str(e)}"
                logger.error(error_msg, exc_info=True)
                error_details.append(error_msg)
                errors += 1
        
        result = {
            'sent': sent, 
            'errors': errors,
            'error_details': error_details
        }
        
        logger.info(f"リマインダー通知処理完了: {result}")
        
        return result
    
    @classmethod
    def _is_recently_sent(cls, notification, hours=24):
        """最近送信済みかチェック"""
        if not notification.last_sent:
            return False
        
        time_diff = timezone.now() - notification.last_sent
        return time_diff < timedelta(hours=hours)
    
    @classmethod
    def _send_notification(cls, user, title, message, url, notification):
        """プッシュ通知を送信"""
        try:
            logger.info(f"  通知送信開始: ユーザー={user.username}, タイトル={title}")
            
            # NotificationLog を記録
            notification_log = NotificationLog.objects.create(
                notification=notification,
                user=user,
                title=title,
                message=message,
                url=url,
                is_read=False
            )
            logger.info(f"    ✓ NotificationLog記録完了 (ID: {notification_log.id})")
            
            # プッシュサブスクリプションをチェック
            from stockdiary.models import PushSubscription
            subscriptions = PushSubscription.objects.filter(
                user=user,
                is_active=True
            )
            
            logger.info(f"    プッシュサブスクリプション数: {subscriptions.count()}")
            
            if not subscriptions.exists():
                logger.warning(
                    f"    ⚠️ プッシュサブスクリプションなし "
                    f"（アプリ内通知ログのみ記録済み）"
                )
                return True
            
            # プッシュ通知送信
            from stockdiary.api_views import send_push_notification
            
            success_count = send_push_notification(
                user=user,
                title=title,
                message=message,
                url=url,
                tag=f'notification-{notification.id}'
            )
            
            logger.info(f"    プッシュ通知送信結果: {success_count}デバイス")
            
            if success_count > 0:
                logger.info(f"  ✅ プッシュ通知送信成功")
                return True
            else:
                logger.warning(
                    f"  ⚠️ プッシュ通知は送信できなかったが、"
                    f"アプリ内通知ログは記録済み"
                )
                return True
            
        except Exception as e:
            logger.error(f"  ❌ 通知送信エラー: {str(e)}", exc_info=True)
            return False