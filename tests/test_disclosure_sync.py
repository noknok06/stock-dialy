"""DisclosureSync（開示インジケーター更新・イベント生成・通知ファンアウト）のテスト"""
import pytest
from datetime import date, datetime, timedelta, timezone as dt_timezone

from stockdiary.models import StockDiary, NotificationLog
from earnings_analysis.models import DocumentMetadata, DisclosureEvent
from earnings_analysis.services.disclosure_sync import (
    update_diary_disclosure_status,
    fan_out_disclosure_notifications,
)

pytestmark = pytest.mark.django_db(transaction=True)


def make_document(securities_code='72030', doc_id='S100TEST', file_date=None,
                  doc_type_code='120', **overrides):
    """DocumentMetadata のテストデータ生成"""
    file_date = file_date or date.today()
    defaults = dict(
        doc_id=doc_id,
        edinet_code='E02144',
        securities_code=securities_code,
        company_name='テスト株式会社',
        ordinance_code='010',
        form_code='030000',
        doc_type_code=doc_type_code,
        submit_date_time=datetime.combine(
            file_date, datetime.min.time(), tzinfo=dt_timezone.utc
        ),
        file_date=file_date,
        doc_description='テスト書類',
        legal_status='1',
        withdrawal_status='0',
    )
    defaults.update(overrides)
    return DocumentMetadata.objects.create(**defaults)


class TestDiaryDisclosureUpdate:
    """Stage 1a: StockDiary の開示フィールド更新"""

    def test_latest_disclosure_updated(self, sample_diary):
        make_document(securities_code='72030', file_date=date.today())
        updated = update_diary_disclosure_status()
        sample_diary.refresh_from_db()
        assert updated == 1
        assert sample_diary.latest_disclosure_date == date.today()
        assert sample_diary.latest_disclosure_doc_type_name == '有価証券報告書'

    def test_no_change_no_update(self, sample_diary):
        make_document(securities_code='72030', file_date=date.today())
        update_diary_disclosure_status()
        # 2回目は変更なし → 更新0件
        assert update_diary_disclosure_status() == 0

    def test_multiple_diaries_same_symbol_all_updated(self, sample_diary, another_user):
        """同一銘柄を複数ユーザーが記録していても全日記が更新される"""
        other = StockDiary.objects.create(
            user=another_user, stock_symbol='7203', stock_name='トヨタ自動車'
        )
        make_document(securities_code='72030', file_date=date.today())
        assert update_diary_disclosure_status() == 2
        other.refresh_from_db()
        assert other.latest_disclosure_date == date.today()

    def test_latest_doc_wins(self, sample_diary):
        """複数書類がある場合は file_date が最新のものを採用"""
        make_document(doc_id='S100OLD1', file_date=date.today() - timedelta(days=3),
                      doc_type_code='120')
        make_document(doc_id='S100NEW1', file_date=date.today(), doc_type_code='160')
        update_diary_disclosure_status()
        sample_diary.refresh_from_db()
        assert sample_diary.latest_disclosure_doc_type_name == '半期報告書'

    def test_unimportant_doc_type_does_not_update(self, sample_diary):
        """有報・半報以外（訂正類・臨報等）は表示フィールドを更新しない"""
        make_document(doc_id='S100AMD1', doc_type_code='130')  # 訂正有価証券報告書
        make_document(doc_id='S100EXT1', doc_type_code='180')  # 臨時報告書
        update_diary_disclosure_status()
        sample_diary.refresh_from_db()
        assert sample_diary.latest_disclosure_date is None

    def test_stale_unimportant_value_reset(self, sample_diary):
        """過去に非重要種別が乗っていた場合、重要開示がなければ None に戻る"""
        sample_diary.latest_disclosure_date = date.today() - timedelta(days=2)
        sample_diary.latest_disclosure_doc_type_name = '臨時報告書'
        sample_diary.save(update_fields=[
            'latest_disclosure_date', 'latest_disclosure_doc_type_name'
        ])
        make_document(doc_type_code='180', file_date=date.today())
        update_diary_disclosure_status()
        sample_diary.refresh_from_db()
        assert sample_diary.latest_disclosure_date is None
        assert sample_diary.latest_disclosure_doc_type_name == ''

    def test_non_japanese_symbol_ignored(self, user):
        diary = StockDiary.objects.create(user=user, stock_symbol='AAPL', stock_name='Apple')
        make_document(securities_code='AAPL0')
        update_diary_disclosure_status()
        diary.refresh_from_db()
        assert diary.latest_disclosure_date is None


class TestDisclosureEvents:
    """Stage 1b: 新規開示のイベント化"""

    def test_event_created_for_notify_type(self, sample_diary):
        make_document(doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()
        event = DisclosureEvent.objects.get()
        assert event.securities_code == '72030'
        assert event.doc_type_name == '有価証券報告書'

    def test_no_event_for_non_notify_type(self, sample_diary):
        """訂正書類など通知対象外の種別はイベント化しない"""
        make_document(doc_type_code='130', file_date=date.today())  # 訂正有価証券報告書
        update_diary_disclosure_status()
        assert DisclosureEvent.objects.count() == 0

    def test_no_event_for_old_disclosure(self, sample_diary):
        """EVENT_MAX_AGE_DAYS より古い開示はイベント化しない（初回実行の過去分流入防止）"""
        make_document(doc_type_code='120', file_date=date.today() - timedelta(days=30))
        update_diary_disclosure_status()
        assert DisclosureEvent.objects.count() == 0
        # 日記の表示フィールドは更新される（イベント化と表示は独立）
        sample_diary.refresh_from_db()
        assert sample_diary.latest_disclosure_date is not None

    def test_rerun_does_not_duplicate_event(self, sample_diary):
        make_document(doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()
        update_diary_disclosure_status()
        assert DisclosureEvent.objects.count() == 1


class TestNotificationFanOut:
    """Stage 2: アプリ内通知のファンアウト"""

    def test_notification_created_per_user(self, sample_diary, another_user):
        StockDiary.objects.create(
            user=another_user, stock_symbol='7203', stock_name='トヨタ自動車'
        )
        make_document(doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()

        assert NotificationLog.objects.count() == 2
        log = NotificationLog.objects.get(user=sample_diary.user)
        assert 'トヨタ自動車' in log.title
        assert '有価証券報告書' in log.message
        assert log.url == f'/stockdiary/{sample_diary.id}/'
        assert log.is_read is False

    def test_one_notification_per_user_with_duplicate_diaries(self, sample_diary):
        """同一銘柄の日記が複数あってもユーザーへの通知は1通"""
        StockDiary.objects.create(
            user=sample_diary.user, stock_symbol='7203', stock_name='トヨタ自動車(2冊目)'
        )
        make_document(doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()
        assert NotificationLog.objects.filter(user=sample_diary.user).count() == 1

    def test_excluded_diary_not_notified(self, sample_diary):
        sample_diary.is_excluded = True
        sample_diary.save(update_fields=['is_excluded'])
        make_document(doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()
        assert NotificationLog.objects.count() == 0

    def test_rerun_does_not_duplicate_notification(self, sample_diary):
        make_document(doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()
        # イベント再ファンアウトでも一意制約 + ignore_conflicts で重複しない
        events = list(DisclosureEvent.objects.all())
        fan_out_disclosure_notifications(events)
        assert NotificationLog.objects.count() == 1

    def test_unrelated_user_not_notified(self, sample_diary, another_user):
        StockDiary.objects.create(
            user=another_user, stock_symbol='9984', stock_name='ソフトバンクグループ'
        )
        make_document(securities_code='72030', doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()
        assert NotificationLog.objects.filter(user=another_user).count() == 0
