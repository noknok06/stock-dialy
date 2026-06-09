# stockdiary/tasks.py
from django_q.tasks import schedule
from django_q.models import Schedule
from .services.notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)

DIARY_IMAGE_MAX_SIZE = (800, 600)
NOTE_IMAGE_MAX_SIZE = (600, 400)


def compress_diary_image(diary_id):
    """StockDiary の保存済み画像を圧縮する（django-q タスク）。"""
    from .models import StockDiary
    from .services.image_service import ImageService

    try:
        diary = StockDiary.objects.get(id=diary_id)
    except StockDiary.DoesNotExist:
        logger.warning("compress_diary_image: diary id=%s not found", diary_id)
        return

    if diary.image:
        ImageService.compress_stored(diary, max_size=DIARY_IMAGE_MAX_SIZE, quality=85)


def compress_note_image(note_id):
    """DiaryNote の保存済み画像を圧縮する（django-q タスク）。"""
    from .models import DiaryNote
    from .services.image_service import ImageService

    try:
        note = DiaryNote.objects.get(id=note_id)
    except DiaryNote.DoesNotExist:
        logger.warning("compress_note_image: note id=%s not found", note_id)
        return

    if note.image:
        ImageService.compress_stored(note, max_size=NOTE_IMAGE_MAX_SIZE, quality=80)


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
    通知スケジュールを設定（初回起動時に実行）。

    既存スケジュールが壊れた状態（next_run が大きく過去にずれて凍結、または repeats が異常値）
    の場合は正常値に自己修復する。これを怠ると、一度凍結したスケジュールが復旧せず
    定期通知が止まり続ける（過去に next_run が約3ヶ月前で停止した実績あり）。
    """
    from django.utils import timezone
    from datetime import timedelta

    existing = Schedule.objects.filter(
        func='stockdiary.tasks.process_notifications'
    ).first()

    if existing:
        # next_run が現在より大幅に過去 = スケジューラが追従できず凍結した壊れた状態。
        # repeats は無限実行を表す -1 を正常とみなし、それ以外（過去に大きく減算された値など）も異常扱い。
        is_stale = (
            existing.next_run is None
            or existing.next_run < timezone.now() - timedelta(minutes=10)
            or existing.repeats != -1
        )
        if not is_stale:
            logger.info(
                f"✅ 通知スケジュール既存: {existing.name} (next_run={existing.next_run})"
            )
            return existing

        logger.warning(
            "⚠️ 通知スケジュールが異常状態のため修復します "
            f"(next_run={existing.next_run}, repeats={existing.repeats})"
        )
        existing.schedule_type = Schedule.MINUTES
        existing.minutes = 1
        existing.repeats = -1
        existing.next_run = timezone.now()
        existing.save()
        logger.info("✅ 通知スケジュール修復完了")
        return existing

    # 新規スケジュールを作成（1分ごとに実行）
    schedule(
        'stockdiary.tasks.process_notifications',
        name='通知処理タスク',
        schedule_type=Schedule.MINUTES,
        minutes=1,  # 1分ごとに実行
        repeats=-1,  # 無限に繰り返し
        next_run=timezone.now(),
    )

    logger.info("✅ 通知スケジュール作成完了")
    return Schedule.objects.get(func='stockdiary.tasks.process_notifications')