"""stockdiary/tasks.py のユニットテスト。

django-q タスク関数は django-q ワーカープロセス上で実行されるため
従来テストカバレッジが 20% と低かった。
ImageService を mock してロジックを検証する。
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

from stockdiary.models import StockDiary, DiaryNote

User = get_user_model()

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# compress_diary_image
# ---------------------------------------------------------------------------

class TestCompressDiaryImage:
    """compress_diary_image タスクのテスト。"""

    def test_calls_image_service_when_diary_has_image(self):
        """diary.image が存在するとき ImageService.compress_stored を呼ぶ。"""
        user = User.objects.create_user(username='task_user1', password='pass', email='t1@example.com')
        diary = StockDiary.objects.create(user=user, stock_symbol='7203', stock_name='トヨタ')

        with patch('stockdiary.services.image_service.ImageService.compress_stored') as mock_compress:
            # image を truthy に見せる
            diary.image = MagicMock(spec=['__bool__'])
            diary.image.__bool__ = lambda self: True

            with patch('stockdiary.models.StockDiary.objects') as mock_mgr:
                mock_mgr.get.return_value = diary
                from stockdiary.tasks import compress_diary_image
                compress_diary_image(diary.id)

            mock_compress.assert_called_once()

    def test_does_nothing_when_diary_not_found(self):
        """存在しない diary_id は警告ログを出すだけで例外を投げない。"""
        user = User.objects.create_user(username='task_user2', password='pass', email='t2@example.com')
        # 実在しない ID を使う
        from stockdiary.tasks import compress_diary_image
        compress_diary_image(999999999)  # DoesNotExist を実際に踏む

    def test_does_nothing_when_diary_has_no_image(self):
        """diary.image が falsy のとき compress_stored を呼ばない。"""
        user = User.objects.create_user(username='task_user3', password='pass', email='t3@example.com')
        diary = StockDiary.objects.create(user=user, stock_symbol='7203', stock_name='トヨタ')
        # image は空（デフォルト）

        with patch('stockdiary.services.image_service.ImageService.compress_stored') as mock_compress:
            from stockdiary.tasks import compress_diary_image
            compress_diary_image(diary.id)

        mock_compress.assert_not_called()


# ---------------------------------------------------------------------------
# compress_note_image
# ---------------------------------------------------------------------------

class TestCompressNoteImage:
    """compress_note_image タスクのテスト。"""

    def test_does_nothing_when_note_not_found(self):
        """存在しない note_id は例外を投げない。"""
        from stockdiary.tasks import compress_note_image
        compress_note_image(999999999)

    def test_does_nothing_when_note_has_no_image(self):
        """note.image が falsy のとき compress_stored を呼ばない。"""
        user = User.objects.create_user(username='task_user4', password='pass', email='t4@example.com')
        diary = StockDiary.objects.create(user=user, stock_symbol='7203', stock_name='トヨタ')
        note = DiaryNote.objects.create(diary=diary, date=timezone.now().date(), content='テスト')

        with patch('stockdiary.services.image_service.ImageService.compress_stored') as mock_compress:
            from stockdiary.tasks import compress_note_image
            compress_note_image(note.id)

        mock_compress.assert_not_called()


# ---------------------------------------------------------------------------
# send_monthly_review
# ---------------------------------------------------------------------------

class TestSendMonthlyReview:
    """send_monthly_review タスクのテスト。"""

    def test_returns_result_on_success(self):
        """NotificationService が正常応答するとき送信結果を返す。"""
        expected = {'sent': 3, 'errors': 0}
        with patch('stockdiary.tasks.NotificationService') as MockNS:
            MockNS.send_monthly_review.return_value = expected
            from stockdiary.tasks import send_monthly_review
            result = send_monthly_review()
        assert result == expected

    def test_returns_error_dict_on_exception(self):
        """NotificationService が例外を投げても dict を返す（クラッシュしない）。"""
        with patch('stockdiary.tasks.NotificationService') as MockNS:
            MockNS.send_monthly_review.side_effect = RuntimeError('smtp down')
            from stockdiary.tasks import send_monthly_review
            result = send_monthly_review()
        assert result['sent'] == 0
        assert result['errors'] == 1
        assert 'smtp down' in result['error']


# ---------------------------------------------------------------------------
# process_notifications
# ---------------------------------------------------------------------------

class TestProcessNotifications:
    """process_notifications タスクのテスト。"""

    def test_returns_result_on_success(self):
        expected = {'total_sent': 5, 'total_errors': 0}
        with patch('stockdiary.tasks.NotificationService') as MockNS:
            MockNS.process_all_notifications.return_value = expected
            from stockdiary.tasks import process_notifications
            result = process_notifications()
        assert result == expected

    def test_returns_error_dict_on_exception(self):
        with patch('stockdiary.tasks.NotificationService') as MockNS:
            MockNS.process_all_notifications.side_effect = RuntimeError('db error')
            from stockdiary.tasks import process_notifications
            result = process_notifications()
        assert result['total_sent'] == 0
        assert result['total_errors'] == 1


# ---------------------------------------------------------------------------
# setup_notification_schedule
# ---------------------------------------------------------------------------

class TestSetupNotificationSchedule:
    """setup_notification_schedule のロジックテスト（MINUTES スケジュール）。"""

    def test_creates_new_schedule_when_none_exists(self):
        """スケジュールが存在しない場合は新規作成する。"""
        from django_q.models import Schedule
        Schedule.objects.filter(func='stockdiary.tasks.process_notifications').delete()

        from stockdiary.tasks import setup_notification_schedule
        result = setup_notification_schedule()

        assert result is not None
        assert Schedule.objects.filter(func='stockdiary.tasks.process_notifications').exists()

    def test_returns_existing_valid_schedule_unchanged(self):
        """正常なスケジュールが既存なら上書きしない。"""
        from django_q.models import Schedule
        from stockdiary.tasks import NOTIFICATION_INTERVAL_MINUTES
        Schedule.objects.filter(func='stockdiary.tasks.process_notifications').delete()

        existing = Schedule.objects.create(
            func='stockdiary.tasks.process_notifications',
            name='通知処理タスク',
            schedule_type=Schedule.MINUTES,
            minutes=NOTIFICATION_INTERVAL_MINUTES,
            repeats=-1,
            next_run=timezone.now() + timedelta(minutes=1),
        )

        from stockdiary.tasks import setup_notification_schedule
        result = setup_notification_schedule()

        assert result.id == existing.id

    def test_repairs_stale_schedule(self):
        """next_run が大幅に過去のスケジュールは正規化される。

        過去に next_run が約3ヶ月前で停止した実績があるため、
        自己修復ロジックが正しく動くことを確認する。
        """
        from django_q.models import Schedule
        from stockdiary.tasks import NOTIFICATION_INTERVAL_MINUTES
        Schedule.objects.filter(func='stockdiary.tasks.process_notifications').delete()

        Schedule.objects.create(
            func='stockdiary.tasks.process_notifications',
            name='通知処理タスク',
            schedule_type=Schedule.MINUTES,
            minutes=NOTIFICATION_INTERVAL_MINUTES,
            repeats=-1,
            next_run=timezone.now() - timedelta(days=90),  # 3ヶ月前で凍結
        )

        from stockdiary.tasks import setup_notification_schedule
        setup_notification_schedule()

        stale = Schedule.objects.get(func='stockdiary.tasks.process_notifications')
        # next_run が現在時刻付近に修復されているべき
        assert stale.next_run >= timezone.now() - timedelta(minutes=2)

    def test_repairs_wrong_interval(self):
        """実行間隔が設定値（5分）と異なるスケジュールは正規化される。"""
        from django_q.models import Schedule
        from stockdiary.tasks import NOTIFICATION_INTERVAL_MINUTES
        Schedule.objects.filter(func='stockdiary.tasks.process_notifications').delete()

        # 旧設定: 毎分実行（minutes=1）
        Schedule.objects.create(
            func='stockdiary.tasks.process_notifications',
            name='通知処理タスク',
            schedule_type=Schedule.MINUTES,
            minutes=1,  # 設定値と異なる
            repeats=-1,
            next_run=timezone.now() + timedelta(minutes=1),
        )

        from stockdiary.tasks import setup_notification_schedule
        setup_notification_schedule()

        updated = Schedule.objects.get(func='stockdiary.tasks.process_notifications')
        assert updated.minutes == NOTIFICATION_INTERVAL_MINUTES
