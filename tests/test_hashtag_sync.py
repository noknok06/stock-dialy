"""
本文（reason）＋継続記録の @タグと StockDiary.tags の完全同期テスト。

`_sync_hashtag_tags()` は保存時に呼ばれ、本文に無くなった @タグの紐付けを解除する。
（バグ修正: 本文から @タグを消してもタグが解除されなかった）
"""
import datetime

import pytest
from django.urls import reverse

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

    def test_tag_stays_while_present_in_other_source(self, user):
        # 本文とノート両方に @成長株 がある状態で本文から消しても、
        # ノートに残っているのでタグは維持される（本文＋ノートが正）
        diary = self._make_diary(user, '本文 @成長株')
        DiaryNote.objects.create(diary=diary, date=datetime.date(2025, 1, 1), content='ノート @成長株')
        _sync_hashtag_tags(diary, user)

        diary.reason = '本文（タグ削除）'
        diary.save(update_fields=['reason'])
        _sync_hashtag_tags(diary, user)

        assert set(diary.tags.values_list('name', flat=True)) == {'成長株'}


@pytest.mark.django_db
class TestHashtagArrowDirection:
    """@タグ直後の矢印(↑/↓/→)を DiaryTagDirection に自動反映する配線。"""

    def _make_diary(self, user, reason):
        return StockDiary.objects.create(
            user=user, stock_symbol='7203', stock_name='トヨタ自動車', reason=reason
        )

    def _dirs(self, diary):
        return {td.tag.name: td.direction for td in diary.tag_directions.all()}

    def test_arrow_sets_direction_and_neutral_tag(self, user):
        diary = self._make_diary(user, '輸出 @円安↑ @金利上昇↓ @AI')
        _sync_hashtag_tags(diary, user)
        # タグ名は無方向（矢印は名前に含めない）
        assert set(diary.tags.values_list('name', flat=True)) == {'円安', '金利上昇', 'AI'}
        # 矢印は方向属性へ。矢印なし(@AI)は方向行を作らない
        assert self._dirs(diary) == {'円安': 'up', '金利上昇': 'down'}

    def test_no_arrow_preserves_manual_direction(self, user):
        diary = self._make_diary(user, '理由 @AI')
        _sync_hashtag_tags(diary, user)
        tag = diary.tags.get(name='AI')
        DiaryTagDirection.objects.create(
            diary=diary, tag=tag, direction=DiaryTagDirection.DIRECTION_UP
        )
        # 矢印なしで再同期しても手動方向は温存される
        _sync_hashtag_tags(diary, user)
        assert self._dirs(diary) == {'AI': 'up'}

    def test_arrow_overwrites_existing_direction(self, user):
        diary = self._make_diary(user, '理由 @円安')
        _sync_hashtag_tags(diary, user)
        tag = diary.tags.get(name='円安')
        DiaryTagDirection.objects.create(
            diary=diary, tag=tag, direction=DiaryTagDirection.DIRECTION_DOWN
        )
        # 本文に矢印が付いたらテキストが権威（down → up へ更新）
        diary.reason = '理由 @円安↑'
        diary.save(update_fields=['reason'])
        _sync_hashtag_tags(diary, user)
        assert self._dirs(diary) == {'円安': 'up'}

    def test_reason_direction_wins_over_note(self, user):
        diary = self._make_diary(user, '本文 @円安↑')
        DiaryNote.objects.create(
            diary=diary, date=datetime.date(2025, 1, 1), content='調整 @円安↓ @規制リスク↓'
        )
        _sync_hashtag_tags(diary, user)
        dirs = self._dirs(diary)
        # reason 優先：@円安 は up。ノート専用の @規制リスク は down が入る
        assert dirs['円安'] == 'up'
        assert dirs['規制リスク'] == 'down'


@pytest.mark.django_db
class TestNoteViewSync:
    """継続記録ビュー経由でタグ同期が走ることを検証（不整合バグ修正）。"""

    def _post_note(self, client, diary, content):
        return client.post(
            reverse('stockdiary:add_note', kwargs={'pk': diary.pk}),
            {'date': '2025-01-01', 'note_type': 'analysis',
             'importance': 'medium', 'topic': '', 'content': content},
        )

    def test_add_note_syncs_tags(self, authenticated_client, sample_diary):
        self._post_note(authenticated_client, sample_diary, 'ノート @決算good')
        assert set(sample_diary.tags.values_list('name', flat=True)) == {'決算good'}

    def test_edit_note_removes_tag(self, authenticated_client, sample_diary):
        # ノート追加でタグが付く
        self._post_note(authenticated_client, sample_diary, 'ノート @決算good')
        note = sample_diary.notes.get()
        assert sample_diary.tags.filter(name='決算good').exists()

        # ノートを編集して @タグを除去 → 日記からタグが解除される
        authenticated_client.post(
            reverse('stockdiary:edit_note', kwargs={'diary_pk': sample_diary.pk, 'pk': note.pk}),
            {'date': '2025-01-01', 'note_type': 'analysis',
             'importance': 'medium', 'topic': '', 'content': 'タグ無しに編集'},
        )
        assert not sample_diary.tags.filter(name='決算good').exists()

    def test_delete_note_removes_tag(self, authenticated_client, sample_diary):
        self._post_note(authenticated_client, sample_diary, 'ノート @決算good')
        note = sample_diary.notes.get()

        authenticated_client.post(
            reverse('stockdiary:delete_note', kwargs={'diary_pk': sample_diary.pk, 'pk': note.pk})
        )
        assert not sample_diary.tags.filter(name='決算good').exists()

    def test_quick_add_note_syncs_tags(self, authenticated_client, sample_diary):
        authenticated_client.post(
            reverse('stockdiary:quick_add_note', kwargs={'diary_id': sample_diary.pk}),
            {'content': 'クイック @急騰', 'importance': 'medium'},
        )
        assert set(sample_diary.tags.values_list('name', flat=True)) == {'急騰'}

    def test_other_diary_tags_untouched(self, authenticated_client, user, sample_diary):
        # 別日記が同名タグを持っていても、片方のノート編集が他方の紐付けに波及しない
        other = StockDiary.objects.create(
            user=user, stock_symbol='6758', stock_name='ソニー', reason='別日記 @決算good'
        )
        _sync_hashtag_tags(other, user)
        assert other.tags.filter(name='決算good').exists()

        # sample_diary 側でノート追加→削除
        self._post_note(authenticated_client, sample_diary, 'ノート @決算good')
        note = sample_diary.notes.get()
        authenticated_client.post(
            reverse('stockdiary:delete_note', kwargs={'diary_pk': sample_diary.pk, 'pk': note.pk})
        )

        # 他日記の紐付けは維持される
        assert other.tags.filter(name='決算good').exists()
