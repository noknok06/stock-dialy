# stockdiary/services/notification_service.py
from django.utils import timezone
from datetime import timedelta
import logging

from ..models import DiaryNotification, NotificationLog
from ..api_views import send_push_notification

logger = logging.getLogger(__name__)

# 同一 Thesis への通知を再送するまでの間隔（日）。
# ユーザーが検証を放置しても毎日飛んでうるさくならないように週1ペースにする。
THESIS_NOTIFICATION_COOLDOWN_DAYS = 7
# 検証期日からこの日数以上経過した Thesis は古すぎるため通知しない。
# サーバーが長期停止後に復帰しても過去の全仮説が一斉に飛ばないようにする。
THESIS_GRACE_DAYS = 14


class NotificationService:
    """通知送信サービス（リマインダー・Thesis 期日・月次レビュー）"""

    # 取りこぼしたリマインダーを復帰後に発火させる猶予日数。
    # これより古い期限切れリマインダーは誤発火を避けてスキップする。
    REMINDER_GRACE_DAYS = 3

    @classmethod
    def process_all_notifications(cls):
        """全種別の通知を処理"""
        results = {
            'reminder': cls.process_reminder_notifications(),
            'thesis_due': cls.process_thesis_due_notifications(),
        }

        total_sent = results['reminder']['sent'] + results['thesis_due']['sent']
        total_errors = results['reminder']['errors'] + results['thesis_due']['errors']

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

    @classmethod
    def process_thesis_due_notifications(cls):
        """検証期日到来の仮説（Thesis）を持つユーザーに Push 通知を送る。

        既存の process_notifications タスク（5分ごと）から呼ばれる。新規スケジュール不要。
        同一 Thesis への通知は THESIS_NOTIFICATION_COOLDOWN_DAYS 日に1回に抑える
        （ユーザーが検証を後回しにしても毎日飛んでうるさくならないように）。
        THESIS_GRACE_DAYS 以上前に期日を過ぎた仮説は通知しない（長期停止復帰後の一斉送信防止）。
        """
        from ..models import Thesis, NotificationLog
        from ..api_views import send_push_notification as _send_push

        today = timezone.localdate()
        now = timezone.now()
        sent = 0
        errors = 0
        error_details = []

        due_theses = Thesis.objects.filter(
            status=Thesis.STATUS_OPEN,
            review_due_date__isnull=False,
            review_due_date__lte=today,
            review_due_date__gte=today - timedelta(days=THESIS_GRACE_DAYS),
        ).select_related('diary', 'diary__user')

        logger.info(f"検証期日到来仮説数: {due_theses.count()}")

        for thesis in due_theses:
            try:
                user = thesis.diary.user
                # thesis_verify URL に直リンク（ワンタップで検証フォームへ）
                url = f'/stockdiary/{thesis.diary_id}/thesis/{thesis.id}/verify/'

                # COOLDOWN_DAYS 以内に同じ Thesis の通知を送済みならスキップ。
                # DiaryNotification FK は null 可（disclosure 通知と同パターン）。
                already_sent = NotificationLog.objects.filter(
                    user=user,
                    url=url,
                    sent_at__gte=now - timedelta(days=THESIS_NOTIFICATION_COOLDOWN_DAYS),
                ).exists()
                if already_sent:
                    continue

                title = f'📊 {thesis.diary.stock_name} の仮説を検証しましょう'
                message = thesis.claim[:100]

                # アプリ内通知ログを記録（notification FK は null = リマインダー以外の通知）
                log = NotificationLog.objects.create(
                    user=user,
                    title=title,
                    message=message,
                    url=url,
                    is_read=False,
                )

                # Push 送信（購読がなければアプリ内ログのみで完了）
                from stockdiary.models import PushSubscription
                if PushSubscription.objects.filter(user=user, is_active=True).exists():
                    _send_push(
                        user=user,
                        title=title,
                        message=message,
                        url=url,
                        tag=f'thesis-due-{thesis.id}',
                        notification_id=log.id,
                    )
                    logger.info(f'✅ Thesis Push 送信: thesis_id={thesis.id}, user={user.username}')
                else:
                    logger.info(
                        f'✅ Thesis アプリ内通知記録（Push 購読なし）: '
                        f'thesis_id={thesis.id}, user={user.username}'
                    )

                sent += 1

            except Exception as e:
                error_msg = f'Thesis {thesis.id} 通知エラー: {str(e)}'
                logger.error(error_msg, exc_info=True)
                errors += 1
                error_details.append(error_msg)

        result = {'sent': sent, 'errors': errors, 'error_details': error_details}
        logger.info(f'Thesis 期日通知完了: {result}')
        return result

    @classmethod
    def send_monthly_review(cls):
        """月次レビュー通知を全ユーザーに送る。

        毎月1日の早朝に django-q CRON タスクから呼ばれる（tasks.py 参照）。
        当月中に期日を迎える未検証 Thesis の件数と、すでに期日超過の件数をサマリーして
        1通送る。デイリー通知（process_thesis_due_notifications）が「個別の催促」なのに対し、
        こちらは「今月の全体観」を提供する月1の通知。

        0件のユーザーには送らない。
        """
        import calendar
        from django.contrib.auth import get_user_model
        from ..models import Thesis, NotificationLog

        User = get_user_model()
        today = timezone.localdate()
        # 当月末日を計算
        last_day = calendar.monthrange(today.year, today.month)[1]
        month_end = today.replace(day=last_day)

        sent = 0
        errors = 0
        error_details = []

        # Thesis が1件以上ある全ユーザーを対象にする
        user_ids = Thesis.objects.filter(
            status=Thesis.STATUS_OPEN,
        ).values_list('diary__user_id', flat=True).distinct()

        logger.info(f'月次レビュー通知: 対象ユーザー数={len(list(user_ids))}')

        for user in User.objects.filter(pk__in=user_ids):
            try:
                open_theses = Thesis.objects.filter(
                    diary__user=user,
                    status=Thesis.STATUS_OPEN,
                )
                # 当月末までに期日が来る仮説（超過分も含む）
                due_by_month_end = open_theses.filter(
                    review_due_date__lte=month_end,
                    review_due_date__isnull=False,
                ).count()
                # うち期日超過（今日より前）
                overdue = open_theses.filter(
                    review_due_date__lt=today,
                    review_due_date__isnull=False,
                ).count()

                if due_by_month_end == 0:
                    continue

                # メッセージ組み立て
                if overdue > 0:
                    message = (
                        f'今月{due_by_month_end}件の仮説が答え合わせ時期です'
                        f'（うち{overdue}件は期日超過）'
                    )
                else:
                    message = f'今月{due_by_month_end}件の仮説が答え合わせ時期です'

                title = '📅 今月の仮説レビュー'
                url = '/stockdiary/karte/'

                log = NotificationLog.objects.create(
                    user=user,
                    title=title,
                    message=message,
                    url=url,
                    is_read=False,
                )

                from stockdiary.models import PushSubscription
                if PushSubscription.objects.filter(user=user, is_active=True).exists():
                    from stockdiary.api_views import send_push_notification as _push
                    _push(
                        user=user,
                        title=title,
                        message=message,
                        url=url,
                        tag='monthly-thesis-review',
                        notification_id=log.id,
                    )
                    logger.info(f'✅ 月次レビュー Push 送信: user={user.username}')
                else:
                    logger.info(f'✅ 月次レビュー アプリ内通知（Push 購読なし）: user={user.username}')

                sent += 1

            except Exception as e:
                error_msg = f'月次レビュー通知エラー (user={user.pk}): {str(e)}'
                logger.error(error_msg, exc_info=True)
                errors += 1
                error_details.append(error_msg)

        result = {'sent': sent, 'errors': errors, 'error_details': error_details}
        logger.info(f'月次レビュー通知完了: {result}')
        return result