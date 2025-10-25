# stockdiary/services/notification_service.py
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from ..models import DiaryNotification, NotificationLog
from ..api_views import send_push_notification

logger = logging.getLogger(__name__)


class NotificationService:
    """通知送信サービス"""
    
    @classmethod
    def process_all_notifications(cls):
        """すべての通知タイプを処理"""
        results = {
            'reminder': cls.process_reminder_notifications(),
            'price_alert': cls.process_price_alert_notifications(),
            'periodic': cls.process_periodic_notifications(),
        }
        
        total_sent = sum(r['sent'] for r in results.values())
        total_errors = sum(r['errors'] for r in results.values())
        
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
            notification_type='reminder',
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
    def process_price_alert_notifications(cls):
        """価格アラート通知を処理"""
        sent = 0
        errors = 0
        
        # 価格アラートを取得
        alerts = DiaryNotification.objects.filter(
            notification_type='price_alert',
            is_active=True,
            target_price__isnull=False
        ).select_related('diary', 'diary__user')
        
        for alert in alerts:
            try:
                # 過去24時間以内に送信済みかチェック
                if cls._is_recently_sent(alert, hours=24):
                    continue
                
                # 現在価格を取得（APIまたはDB）
                current_price = cls._get_current_stock_price(alert.diary.stock_symbol)
                
                if current_price is None:
                    continue
                
                # 条件チェック
                should_alert = False
                if alert.alert_above and current_price >= alert.target_price:
                    should_alert = True
                    message = f"{alert.diary.stock_name}が目標価格 {alert.target_price}円を上回りました（現在: {current_price}円）"
                elif not alert.alert_above and current_price <= alert.target_price:
                    should_alert = True
                    message = f"{alert.diary.stock_name}が目標価格 {alert.target_price}円を下回りました（現在: {current_price}円）"
                
                if should_alert:
                    success = cls._send_notification(
                        user=alert.diary.user,
                        title=f"💰 {alert.diary.stock_name} 価格アラート",
                        message=alert.message or message,
                        url=f"/stockdiary/{alert.diary.id}/",
                        notification=alert
                    )
                    
                    if success:
                        sent += 1
                        alert.last_sent = timezone.now()
                        alert.save()
                    else:
                        errors += 1
                        
            except Exception as e:
                logger.error(f"価格アラート送信エラー (ID: {alert.id}): {e}")
                errors += 1
        
        return {'sent': sent, 'errors': errors}
    
    @classmethod
    def process_periodic_notifications(cls):
        """定期通知を処理"""
        now = timezone.now()
        sent = 0
        errors = 0
        
        periodics = DiaryNotification.objects.filter(
            notification_type='periodic',
            is_active=True,
            frequency__isnull=False
        ).select_related('diary', 'diary__user')
        
        for periodic in periodics:
            try:
                # 送信すべきかチェック
                if not cls._should_send_periodic(periodic, now):
                    continue
                
                # 過去1時間以内に送信済みかチェック（重複防止）
                if cls._is_recently_sent(periodic, hours=1):
                    continue
                
                # 通知送信
                success = cls._send_notification(
                    user=periodic.diary.user,
                    title=f"🔔 {periodic.diary.stock_name} の定期通知",
                    message=periodic.message or f"{periodic.diary.stock_name}を確認しましょう",
                    url=f"/stockdiary/{periodic.diary.id}/",
                    notification=periodic
                )
                
                if success:
                    sent += 1
                    periodic.last_sent = now
                    periodic.save()
                else:
                    errors += 1
                    
            except Exception as e:
                logger.error(f"定期通知送信エラー (ID: {periodic.id}): {e}")
                errors += 1
        
        return {'sent': sent, 'errors': errors}
    
    @classmethod
    def _should_send_periodic(cls, notification, current_time):
        """定期通知を送信すべきか判定"""
        # 指定時刻がある場合、時刻チェック
        if notification.notify_time:
            target_time = notification.notify_time
            current_time_only = current_time.time()
            
            # 5分の誤差を許容
            time_diff = abs(
                (current_time_only.hour * 60 + current_time_only.minute) - 
                (target_time.hour * 60 + target_time.minute)
            )
            
            if time_diff > 5:  # 5分以上ずれている
                return False
        
        # 最後の送信日時をチェック
        if not notification.last_sent:
            return True  # 初回送信
        
        last_sent = notification.last_sent
        
        # 頻度ごとの判定
        if notification.frequency == 'daily':
            # 24時間以上経過
            return (current_time - last_sent) >= timedelta(hours=23, minutes=55)
        
        elif notification.frequency == 'weekly':
            # 7日以上経過
            return (current_time - last_sent) >= timedelta(days=6, hours=23)
        
        elif notification.frequency == 'monthly':
            # 30日以上経過
            return (current_time - last_sent) >= timedelta(days=29, hours=23)
        
        return False
    
    @classmethod
    def _is_recently_sent(cls, notification, hours=24):
        """最近送信済みかチェック"""
        if not notification.last_sent:
            return False
        
        time_diff = timezone.now() - notification.last_sent
        return time_diff < timedelta(hours=hours)
    
    @classmethod
    def _get_current_stock_price(cls, stock_code):
        """現在の株価を取得（APIまたはDB）"""
        # 実装例: 外部APIから取得
        # ここではダミー実装
        try:
            # TODO: 実際の株価取得APIを実装
            # 例: Yahoo Finance API, Alpha Vantage, etc.
            return None
        except Exception as e:
            logger.error(f"株価取得エラー ({stock_code}): {e}")
            return None

    @classmethod
    def _send_notification(cls, user, title, message, url, notification):
        """プッシュ通知を送信（サブスクリプションがなくてもログには記録）"""
        try:
            logger.info(f"  通知送信開始: ユーザー={user.username}, タイトル={title}")
            
            # 🔧 先に NotificationLog を記録（必ず実行）
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
                # 🔧 ログは記録できたので成功扱い
                return True
            
            # プッシュ通知送信
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
                # 🔧 ログは記録できているので成功扱い
                return True
            
        except Exception as e:
            logger.error(f"  ❌ 通知送信エラー: {str(e)}", exc_info=True)
            return False