# stockdiary/services/notification_service.py
from django.utils import timezone
from datetime import timedelta
import logging

from ..models import DiaryNotification, NotificationLog
from ..api_views import send_push_notification

logger = logging.getLogger(__name__)


class NotificationService:
    """通知送信サービス（リマインダーのみ）"""

    # 取りこぼしたリマインダーを復帰後に発火させる猶予日数。
    # これより古い期限切れリマインダーは誤発火を避けてスキップする。
    REMINDER_GRACE_DAYS = 3

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

        # 期限が過ぎた未送信の有効リマインダーを取得。
        # qcluster が一時停止しても復帰後に確実に拾えるよう下限 window は設けない。
        # ただし極端に古い取りこぼし（GRACE_DAYS 超）は誤発火防止のためスキップする。
        reminders = DiaryNotification.objects.filter(
            is_active=True,
            last_sent__isnull=True,
            remind_at__lte=now,
            remind_at__gt=now - timedelta(days=cls.REMINDER_GRACE_DAYS)
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
                    f"    ⚠️ プッシュサブスクリプションなし: user={user.username} "
                    f"（アプリ内通知ログのみ記録済み・端末プッシュは未配信）"
                )
                # アプリ内通知は記録済みなので成功扱い（リマインダーは消化する）
                return True

            # プッシュ通知送信
            from stockdiary.api_views import send_push_notification

            success_count = send_push_notification(
                user=user,
                title=title,
                message=message,
                url=url,
                tag=f'notification-{notification.id}',
                notification_id=notification_log.id
            )

            logger.info(f"    プッシュ通知送信結果: {success_count}デバイス")

            if success_count > 0:
                logger.info(f"  ✅ プッシュ通知送信成功")
                return True
            else:
                # 購読はあるのに 0 件成功 = 配信失敗。原因特定のため WARNING で明示。
                # （詳細な失敗理由は send_push_notification 側でログ済み）
                logger.warning(
                    f"  ⚠️ プッシュ通知が1件も配信できなかった: user={user.username} "
                    f"（購読 {subscriptions.count()} 件・アプリ内ログは記録済み）"
                )
                return True
            
        except Exception as e:
            logger.error(f"  ❌ 通知送信エラー: {str(e)}", exc_info=True)
            return False