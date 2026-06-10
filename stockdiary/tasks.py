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


# リマインダー処理の実行間隔（分）。
# リマインダーは分単位の精度を要求しないため、低スペックVPSの常駐負荷を抑える目的で
# 毎分実行から間隔を広げている（docs/improvement_plan.md 論点2 の規約）。
NOTIFICATION_INTERVAL_MINUTES = 5


def setup_notification_schedule():
    """
    通知スケジュールを設定（初回起動時に実行）。

    既存スケジュールが壊れた状態（next_run が大きく過去にずれて凍結、または repeats が異常値）
    の場合は正常値に自己修復する。これを怠ると、一度凍結したスケジュールが復旧せず
    定期通知が止まり続ける（過去に next_run が約3ヶ月前で停止した実績あり）。
    実行間隔が NOTIFICATION_INTERVAL_MINUTES と異なる場合も正規化する。
    """
    from django.utils import timezone
    from datetime import timedelta

    existing = Schedule.objects.filter(
        func='stockdiary.tasks.process_notifications'
    ).first()

    if existing:
        # next_run が現在より大幅に過去 = スケジューラが追従できず凍結した壊れた状態。
        # repeats は無限実行を表す -1 を正常とみなし、それ以外（過去に大きく減算された値など）も異常扱い。
        # 実行間隔が設定値とずれている場合（旧: 毎分実行）も正規化対象。
        is_stale = (
            existing.next_run is None
            or existing.next_run < timezone.now() - timedelta(
                minutes=NOTIFICATION_INTERVAL_MINUTES * 2)
            or existing.repeats != -1
            or existing.minutes != NOTIFICATION_INTERVAL_MINUTES
        )
        if not is_stale:
            logger.info(
                f"✅ 通知スケジュール既存: {existing.name} (next_run={existing.next_run})"
            )
            return existing

        logger.warning(
            "⚠️ 通知スケジュールを正規化します "
            f"(next_run={existing.next_run}, repeats={existing.repeats}, "
            f"minutes={existing.minutes})"
        )
        existing.schedule_type = Schedule.MINUTES
        existing.minutes = NOTIFICATION_INTERVAL_MINUTES
        existing.repeats = -1
        existing.next_run = timezone.now()
        existing.save()
        logger.info("✅ 通知スケジュール修復完了")
        return existing

    # 新規スケジュールを作成
    schedule(
        'stockdiary.tasks.process_notifications',
        name='通知処理タスク',
        schedule_type=Schedule.MINUTES,
        minutes=NOTIFICATION_INTERVAL_MINUTES,
        repeats=-1,  # 無限に繰り返し
        next_run=timezone.now(),
    )

    logger.info("✅ 通知スケジュール作成完了")
    return Schedule.objects.get(func='stockdiary.tasks.process_notifications')