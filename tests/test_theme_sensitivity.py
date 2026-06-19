"""銘柄のまとめ #3「テーマ × 感応」：付与タグ＋方向(DiaryTagDirection)の表示。

docs/diary_recording_redesign.md 段階H（銘柄のまとめ）の最初のブロック。
"""
import pytest
from django.urls import reverse

from tags.models import Tag
from stockdiary.models import DiaryTagDirection


@pytest.mark.django_db
class TestThemeSensitivity:
    def test_detail_renders_chip_with_direction(self, authenticated_client, user, sample_diary):
        tag = Tag.objects.create(user=user, name='金利上昇')
        sample_diary.tags.add(tag)
        DiaryTagDirection.objects.create(diary=sample_diary, tag=tag, direction='up')

        resp = authenticated_client.get(reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk}))
        assert resp.status_code == 200
        html = resp.content.decode()
        assert 'section-theme-sensitivity' in html   # まとめのテーマ×感応ブロック
        assert '金利上昇' in html                      # 事象タグ名
        assert 'ts-up on' in html                      # 追い風(up)が選択状態

    def test_no_block_when_no_tags(self, authenticated_client, sample_diary):
        sample_diary.tags.clear()
        resp = authenticated_client.get(reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk}))
        assert 'section-theme-sensitivity' not in resp.content.decode()

    def test_unset_direction_shows_no_active(self, authenticated_client, user, sample_diary):
        tag = Tag.objects.create(user=user, name='ナフサ高')
        sample_diary.tags.add(tag)
        # 方向未設定 → どのボタンも on にならない
        resp = authenticated_client.get(reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk}))
        html = resp.content.decode()
        assert 'ナフサ高' in html
        assert 'section-theme-sensitivity' in html
