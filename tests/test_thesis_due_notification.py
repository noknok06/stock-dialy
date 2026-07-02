"""Thesis 検証期日通知・月次レビュー通知の回帰テスト（Phase 8e）。

なぜこのテストを足したか:
継続利用の核は「答え合わせ」という能動トリガー（Readwise の spaced repetition の投資版）。
process_thesis_due_notifications() は、検証期日が到来した未検証 Thesis を持つユーザーに
Push 通知を送り、検証フォームへ直リンクする。

以下の挙動を固定する:
- review_due_date が今日以前・status=open の Thesis → 通知が1件作成される
- review_due_date が未来の Thesis → 通知しない
- status=verified / abandoned の Thesis → 通知しない
- GRACE_DAYS 超の Thesis → 通知しない（長期停止復帰後の一斉送信防止）
- 同一 Thesis への COOLDOWN_DAYS 以内の再通知 → スキップ
"""
import datetime
from unittest.mock import patch

import pytest
from django.utils import timezone

from stockdiary.models import Thesis, NotificationLog, StockDiary
from stockdiary.services.notification_service import (
    NotificationService,
    THESIS_GRACE_DAYS,
    THESIS_NOTIFICATION_COOLDOWN_DAYS,
)


def _make_thesis(diary, claim='円安継続で輸出採算改善', days_offset=0, status=Thesis.STATUS_OPEN):
    """review_due_date = today + days_offset の Thesis を作る。"""
    return Thesis.objects.create(
        diary=diary,
        claim=claim,
        review_due_date=timezone.localdate() + datetime.timedelta(days=days_offset),
        status=status,
    )


@pytest.mark.django_db
class TestThesisDueNotification:

    def _run(self, mock_push=None):
        """Push 送信をモックして process_thesis_due_notifications() を実行する。"""
        if mock_push is None:
            mock_push = patch('stockdiary.services.notification_service.NotificationService'
                              '.process_thesis_due_notifications',
                              wraps=NotificationService.process_thesis_due_notifications)
        with patch('stockdiary.api_views.send_push_notification'):
            return NotificationService.process_thesis_due_notifications()

    def test_due_thesis_creates_notification_log(self, sample_diary):
        """期日到来の未検証 Thesis → NotificationLog が1件作成される。"""
        _make_thesis(sample_diary, days_offset=0)
        with patch('stockdiary.api_views.send_push_notification'):
            result = NotificationService.process_thesis_due_notifications()
        assert result['sent'] == 1
        assert NotificationLog.objects.filter(user=sample_diary.user).count() == 1

    def test_future_thesis_skipped(self, sample_diary):
        """検証期日が未来の Thesis → 通知しない。"""
        _make_thesis(sample_diary, days_offset=1)
        with patch('stockdiary.api_views.send_push_notification'):
            result = NotificationService.process_thesis_due_notifications()
        assert result['sent'] == 0

    def test_verified_thesis_skipped(self, sample_diary):
        """status=verified の Thesis → 通知しない。"""
        _make_thesis(sample_diary, days_offset=0, status=Thesis.STATUS_VERIFIED)
        with patch('stockdiary.api_views.send_push_notification'):
            result = NotificationService.process_thesis_due_notifications()
        assert result['sent'] == 0

    def test_abandoned_thesis_skipped(self, sample_diary):
        """status=abandoned の Thesis → 通知しない。"""
        _make_thesis(sample_diary, days_offset=0, status=Thesis.STATUS_ABANDONED)
        with patch('stockdiary.api_views.send_push_notification'):
            result = NotificationService.process_thesis_due_notifications()
        assert result['sent'] == 0

    def test_too_old_thesis_skipped(self, sample_diary):
        """GRACE_DAYS 超過の Thesis → 通知しない（長期停止後の一斉送信防止）。"""
        _make_thesis(sample_diary, days_offset=-(THESIS_GRACE_DAYS + 1))
        with patch('stockdiary.api_views.send_push_notification'):
            result = NotificationService.process_thesis_due_notifications()
        assert result['sent'] == 0

    def test_cooldown_prevents_resend(self, sample_diary):
        """COOLDOWN_DAYS 以内に送信済みの Thesis → 再送しない。"""
        thesis = _make_thesis(sample_diary, days_offset=0)
        url = f'/stockdiary/{thesis.diary_id}/thesis/{thesis.id}/verify/'
        # 既に通知ログが存在する状態を作る
        NotificationLog.objects.create(
            user=sample_diary.user,
            title='既送信',
            message='test',
            url=url,
            is_read=False,
        )
        with patch('stockdiary.api_views.send_push_notification'):
            result = NotificationService.process_thesis_due_notifications()
        assert result['sent'] == 0

    def test_notification_url_points_to_verify(self, sample_diary):
        """通知 URL が thesis_verify エンドポイントへの直リンクになっている。"""
        thesis = _make_thesis(sample_diary, days_offset=0)
        with patch('stockdiary.api_views.send_push_notification'):
            NotificationService.process_thesis_due_notifications()
        log = NotificationLog.objects.get(user=sample_diary.user)
        assert f'/thesis/{thesis.id}/verify/' in log.url

    def test_process_all_includes_thesis_due(self, sample_diary):
        """process_all_notifications() が Thesis 期日通知を包含する。"""
        _make_thesis(sample_diary, days_offset=0)
        with patch('stockdiary.api_views.send_push_notification'):
            result = NotificationService.process_all_notifications()
        assert 'thesis_due' in result['details']
        assert result['details']['thesis_due']['sent'] == 1


@pytest.mark.django_db
class TestMonthlyReviewNotification:
    """月次レビュー通知の回帰テスト（Phase 8e）。

    なぜこのテストを足したか:
    send_monthly_review() は毎月1日に「今月N件の仮説が答え合わせ時期」を
    サマリー1通送る。デイリー通知（個別催促）と役割が異なる「全体観」の通知。
    0件ユーザーに送らない・超過件数が正しくメッセージに含まれる・
    当月末より後の期日は含まれないことを固定する。
    """

    def test_sends_to_user_with_due_thesis(self, sample_diary):
        """当月内に期日がある Thesis を持つユーザーに1通送る。"""
        _make_thesis(sample_diary, days_offset=0)
        with patch('stockdiary.api_views.send_push_notification'):
            result = NotificationService.send_monthly_review()
        assert result['sent'] == 1
        assert NotificationLog.objects.filter(user=sample_diary.user, title='📅 今月の仮説レビュー').exists()

    def test_no_notification_when_no_due_thesis(self, sample_diary):
        """当月内に期日がない（または Thesis なし）ユーザーには送らない。"""
        # 来月以降の Thesis → 送らない
        _make_thesis(sample_diary, days_offset=40)
        with patch('stockdiary.api_views.send_push_notification'):
            result = NotificationService.send_monthly_review()
        assert result['sent'] == 0

    def test_message_includes_overdue_count(self, sample_diary):
        """期日超過の仮説がある場合、メッセージに超過件数が含まれる。"""
        _make_thesis(sample_diary, days_offset=-3)  # 3日前 = 超過
        with patch('stockdiary.api_views.send_push_notification'):
            NotificationService.send_monthly_review()
        log = NotificationLog.objects.get(user=sample_diary.user, title='📅 今月の仮説レビュー')
        assert '期日超過' in log.message

    def test_future_next_month_excluded(self, sample_diary):
        """当月末より後の期日の Thesis は対象外。"""
        import calendar
        today = timezone.localdate()
        last_day = calendar.monthrange(today.year, today.month)[1]
        # 翌月1日 = 当月末 + 1日
        _make_thesis(sample_diary, days_offset=last_day - today.day + 1)
        with patch('stockdiary.api_views.send_push_notification'):
            result = NotificationService.send_monthly_review()
        assert result['sent'] == 0

    def test_verified_thesis_excluded(self, sample_diary):
        """検証済み（status=verified）の Thesis は件数に含まれない。"""
        _make_thesis(sample_diary, days_offset=0, status=Thesis.STATUS_VERIFIED)
        with patch('stockdiary.api_views.send_push_notification'):
            result = NotificationService.send_monthly_review()
        assert result['sent'] == 0
