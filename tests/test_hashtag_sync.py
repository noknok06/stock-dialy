"""
本文（reason）＋継続記録の @タグと StockDiary.tags の完全同期テスト。

`_sync_hashtag_tags()` は保存時に呼ばれ、本文に無くなった @タグの紐付けを解除する。
（バグ修正: 本文から @タグを消してもタグが解除されなかった）
"""
import datetime

import pytest

from stockdiary.models import StockDiary, DiaryNote, DiaryTagDirection
from stockdiary.views import _sync_hashtag_tags
from tags.models import Tag


@pytest.mark.django_db
class TestHashtagSync:
    def _make_diary(self, user, reason):
        return StockDiary.objects.create(
            user=user, stock_symbol='7203', stock_name='トヨタ自動車', reason=reason
        )

    def test_adds_tags_from_reason(self, user):
        diary = self._make_diary(user, '投資理由 @成長株 @配当')
        _sync_hashtag_tags(diary, user)
        assert set(diary.tags.values_list('name', flat=True)) == {'成長株', '配当'}

    def test_removes_tag_deleted_from_reason(self, user):
        diary = self._make_diary(user, '投資理由 @成長株 @配当')
        _sync_hashtag_tags(diary, user)

        # 本文から @配当 を削除して再同期
        diary.reason = '投資理由 @成長株'
        diary.save(update_fields=['reason'])
        _sync_hashtag_tags(diary, user)

        assert set(diary.tags.values_list('name', flat=True)) == {'成長株'}

    def test_clears_all_when_no_hashtags_remain(self, user):
        diary = self._make_diary(user, '投資理由 @成長株 @配当')
        _sync_hashtag_tags(diary, user)

        diary.reason = '＠タグを全部消した本文'
        diary.save(update_fields=['reason'])
        _sync_hashtag_tags(diary, user)

        assert diary.tags.count() == 0

    def test_removes_direction_for_unlinked_tag(self, user):
        diary = self._make_diary(user, '投資理由 @金利上昇')
        _sync_hashtag_tags(diary, user)
        tag = diary.tags.get(name='金利上昇')
        DiaryTagDirection.objects.create(
            diary=diary, tag=tag, direction=DiaryTagDirection.DIRECTION_UP
        )

        # 本文から削除 → 方向属性も消える
        diary.reason = '理由のみ（タグ無し）'
        diary.save(update_fields=['reason'])
        _sync_hashtag_tags(diary, user)

        assert not DiaryTagDirection.objects.filter(diary=diary, tag=tag).exists()

    def test_df_recalculated_after_unlink(self, user):
        diary = self._make_diary(user, '投資理由 @成長株')
        _sync_hashtag_tags(diary, user)
        tag = diary.tags.get(name='成長株')
        assert tag.df == 1

        diary.reason = 'タグ無し'
        diary.save(update_fields=['reason'])
        _sync_hashtag_tags(diary, user)

        tag.refresh_from_db()
        assert tag.df == 0

    def test_extracts_from_continuation_notes(self, user):
        diary = self._make_diary(user, '本文タグ無し')
        DiaryNote.objects.create(diary=diary, date=datetime.date(2025, 1, 1), content='継続記録 @押し目買い')
        _sync_hashtag_tags(diary, user)
        assert set(diary.tags.values_list('name', flat=True)) == {'押し目買い'}
