# stockdiary/tasks.py
from django_q.tasks import schedule
from django_q.models import Schedule
from .services.notification_service import NotificationService
import logging
from datetime import date

logger = logging.getLogger(__name__)


def process_notifications():
    """
    通知を処理するタスク（Django-Qで定期実行）
    """
    try:
        logger.info("📢 通知処理タスク開始")
        result = NotificationService.process_all_notifications()
        logger.info(
            f"✅ 通知処理完了: 送信={result['total_sent']}, "
            f"エラー={result['total_errors']}"
        )
        return result
    except Exception as e:
        logger.error(f"❌ 通知処理エラー: {e}", exc_info=True)
        return {'total_sent': 0, 'total_errors': 1, 'error': str(e)}


def setup_notification_schedule():
    """
    通知スケジュールを設定（初回起動時に実行）
    """
    # 既存のスケジュールを確認
    existing = Schedule.objects.filter(
        func='stockdiary.tasks.process_notifications'
    ).first()
    
    if existing:
        logger.info(f"✅ 通知スケジュール既存: {existing.name}")
        return existing
    
    # 新規スケジュールを作成（1分ごとに実行）
    schedule(
        'stockdiary.tasks.process_notifications',
        name='通知処理タスク',
        schedule_type=Schedule.MINUTES,
        minutes=1,  # 1分ごとに実行
        repeats=-1  # 無限に繰り返し
    )
    
    logger.info("✅ 通知スケジュール作成完了")
    return Schedule.objects.get(func='stockdiary.tasks.process_notifications')


def process_review_notifications():
    """
    定期レビューの期日チェックと通知送信（毎日実行）
    """
    from .models import ReviewSchedule
    try:
        logger.info("🔄 定期レビュー通知処理 開始")
        due_schedules = ReviewSchedule.objects.filter(
            is_active=True,
            next_review_date__lte=date.today()
        ).select_related('diary', 'diary__user')

        sent = 0
        for schedule_obj in due_schedules:
            diary = schedule_obj.diary
            user = diary.user
            try:
                NotificationService.send_push_to_user(
                    user=user,
                    title=f'📋 {diary.stock_name} のレビュー時期です',
                    message=f'投資仮説を振り返りましょう（{schedule_obj.get_interval_days_display()}ごと）',
                    url=f'/stockdiary/{diary.pk}/review/',
                )
                sent += 1
            except Exception as e:
                logger.warning(f"レビュー通知送信失敗 diary={diary.pk}: {e}")

        logger.info(f"✅ 定期レビュー通知完了: 送信={sent}件")
        return {'sent': sent}
    except Exception as e:
        logger.error(f"❌ 定期レビュー通知エラー: {e}", exc_info=True)
        return {'sent': 0, 'error': str(e)}


def setup_review_schedule():
    """
    定期レビュー通知スケジュールを設定（初回起動時に実行）
    """
    func = 'stockdiary.tasks.process_review_notifications'
    if Schedule.objects.filter(func=func).exists():
        logger.info("✅ 定期レビュー通知スケジュール既存")
        return

    schedule(
        func,
        name='定期レビュー通知タスク',
        schedule_type=Schedule.DAILY,
        repeats=-1,
    )
    logger.info("✅ 定期レビュー通知スケジュール作成完了")