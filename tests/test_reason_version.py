"""見立ての来歴(ReasonVersion)と継続記録の文字数上限(5000)に関するテスト。

docs/diary_recording_redesign.md 段階9a（N: 文字数統一 / ReasonVersion 自動スナップショット）。
- reason 上書き保存時、差分があれば前版を自動スナップショット（明示操作なし）
- 差分なし / 前版が空 / 近接編集(coalesce) では版を増やさない
- 退避した版は全文検索 apply_diary_search で後から辿れる
"""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from stockdiary.models import StockDiary, DiaryNote, ReasonVersion
from stockdiary.utils import apply_diary_search


@pytest.mark.django_db
class TestDiaryNoteContentLength:
    """N: DiaryNote.content の上限を 5000 へ統一。"""

    def test_content_5000_is_accepted(self, sample_diary):
        note = DiaryNote(diary=sample_diary, date=datetime.date.today(), content='あ' * 5000)
        note.full_clean()  # 例外が出なければ合格

    def test_content_over_5000_is_rejected(self, sample_diary):
        note = DiaryNote(diary=sample_diary, date=datetime.date.today(), content='あ' * 5001)
        with pytest.raises(ValidationError):
            note.full_clean()


@pytest.mark.django_db
class TestReasonVersionSnapshot:
    """reason 上書き時の自動スナップショット（来歴）。"""

    def test_change_snapshots_previous_content(self, sample_diary):
        sample_diary.reason = '更新後の見立て'
        sample_diary.save()
        version = ReasonVersion.snapshot_on_change(sample_diary, '初期の見立て')
        assert version is not None
        assert version.content == '初期の見立て'  # 退避されるのは「前版」
        assert sample_diary.reason_versions.count() == 1

    def test_no_diff_creates_no_version(self, sample_diary):
        sample_diary.reason = '同じ見立て'
        sample_diary.save()
        version = ReasonVersion.snapshot_on_change(sample_diary, '同じ見立て')
        assert version is None
        assert sample_diary.reason_versions.count() == 0

    def test_empty_previous_creates_no_version(self, sample_diary):
        # 初めて reason を書いた場合、残すべき前版は無い
        sample_diary.reason = '新しく書いた見立て'
        sample_diary.save()
        version = ReasonVersion.snapshot_on_change(sample_diary, '')
        assert version is None
        assert sample_diary.reason_versions.count() == 0

    def test_coalesce_skips_within_window(self, sample_diary):
        # 1回目の変更で前版'A'を退避
        sample_diary.reason = 'B'
        sample_diary.save()
        first = ReasonVersion.snapshot_on_change(sample_diary, 'A')
        assert first is not None
        # 直後（窓内）の再編集では版を増やさない（途中版の乱造を防ぐ）
        sample_diary.reason = 'C'
        sample_diary.save()
        second = ReasonVersion.snapshot_on_change(sample_diary, 'B')
        assert second is None
        assert sample_diary.reason_versions.count() == 1

    def test_new_version_after_window(self, sample_diary):
        sample_diary.reason = 'B'
        sample_diary.save()
        first = ReasonVersion.snapshot_on_change(sample_diary, 'A')
        # 直近版の作成時刻を窓の外（過去）へずらす
        past = timezone.now() - ReasonVersion.COALESCE_WINDOW - datetime.timedelta(minutes=1)
        ReasonVersion.objects.filter(pk=first.pk).update(created_at=past)
        sample_diary.reason = 'C'
        sample_diary.save()
        second = ReasonVersion.snapshot_on_change(sample_diary, 'B')
        assert second is not None
        assert sample_diary.reason_versions.count() == 2


@pytest.mark.django_db
class TestReasonVersionSearch:
    """退避した版は全文検索で後から辿れる（findability）。"""

    def test_search_finds_archived_version(self, user, sample_diary):
        ReasonVersion.objects.create(diary=sample_diary, content='ナフサ価格高騰の影響を懸念')
        qs = apply_diary_search(StockDiary.objects.filter(user=user), 'ナフサ価格高騰')
        assert sample_diary in list(qs)

    def test_search_miss_when_term_absent(self, user, sample_diary):
        ReasonVersion.objects.create(diary=sample_diary, content='円安メリットの見立て')
        qs = apply_diary_search(StockDiary.objects.filter(user=user), 'まったく無関係な語XYZ')
        assert sample_diary not in list(qs)


@pytest.mark.django_db
class TestUpdateViewAutoSnapshot:
    """更新ビュー経由でも自動スナップショットが行われる（配線確認）。"""

    def test_update_view_snapshots_previous_reason(self, authenticated_client, sample_diary):
        sample_diary.reason = '当初の見立て'
        sample_diary.save()

        url = reverse('stockdiary:update', kwargs={'pk': sample_diary.pk})
        resp = authenticated_client.post(url, {
            'stock_symbol': sample_diary.stock_symbol,
            'stock_name': sample_diary.stock_name,
            'currency': sample_diary.currency,
            'sector': sample_diary.sector or '',
            'reason': '改めた見立て',
        })
        assert resp.status_code == 302  # 成功時は詳細へリダイレクト

        sample_diary.refresh_from_db()
        assert sample_diary.reason == '改めた見立て'
        versions = list(sample_diary.reason_versions.all())
        assert len(versions) == 1
        assert versions[0].content == '当初の見立て'

    def test_update_without_reason_change_creates_no_version(self, authenticated_client, sample_diary):
        sample_diary.reason = '変えない見立て'
        sample_diary.save()

        url = reverse('stockdiary:update', kwargs={'pk': sample_diary.pk})
        resp = authenticated_client.post(url, {
            'stock_symbol': sample_diary.stock_symbol,
            'stock_name': sample_diary.stock_name,
            'currency': sample_diary.currency,
            'sector': '半導体',  # reason 以外を変更
            'reason': '変えない見立て',
        })
        assert resp.status_code == 302
        sample_diary.refresh_from_db()
        assert sample_diary.reason_versions.count() == 0


@pytest.mark.django_db
class TestReasonVersionsDetailView:
    """詳細ページに「見立ての変遷」が表示される（既定は折りたたみ）。"""

    def test_detail_shows_versions_when_present(self, authenticated_client, sample_diary):
        ReasonVersion.objects.create(diary=sample_diary, content='昔の見立て：割安と判断')
        url = reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk})
        resp = authenticated_client.get(url)
        assert resp.status_code == 200
        html = resp.content.decode()
        assert '見立ての変遷' in html
        assert '昔の見立て：割安と判断' in html
        assert 'section-reason-versions' in html

    def test_detail_hides_block_when_no_versions(self, authenticated_client, sample_diary):
        assert sample_diary.reason_versions.count() == 0
        url = reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk})
        resp = authenticated_client.get(url)
        assert resp.status_code == 200
        html = resp.content.decode()
        assert 'section-reason-versions' not in html  # 版が無ければブロックごと出さない
