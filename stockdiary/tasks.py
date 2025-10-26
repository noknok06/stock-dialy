# stockdiary/tasks.py
from django_q.tasks import schedule
from django_q.models import Schedule
from .services.notification_service import NotificationService
import logging

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