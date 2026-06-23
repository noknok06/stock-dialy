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

    def test_chip_links_to_fulltext_search_not_tag_filter(self, authenticated_client, user, sample_diary):
        """テーマチップのタップ先を、タグ絞り込み(tag-id)ではなく全文検索(query)に張り替えた回帰。

        なぜ: タグ未付与でも reason/継続記録の本文に同じ語が書かれている日記を
        取りこぼさないため、発見の入口を本文横断＋ハイライト付きの全文検索に統一する。
        """
        tag = Tag.objects.create(user=user, name='半導体')
        sample_diary.tags.add(tag)
        resp = authenticated_client.get(reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk}))
        html = resp.content.decode()
        # チップのリンク先がホームの全文検索(query=半導体)になっている
        home = reverse('stockdiary:home')
        assert f'{home}?query=%E5%8D%8A%E5%B0%8E%E4%BD%93' in html  # urlencode('半導体')


@pytest.mark.django_db
class TestFulltextFindsBodyMention:
    """タグ未付与でも本文（reason/継続記録）に記載があれば全文検索でヒットし、
    ハイライトされることを固定する。発見をタグ軸に限定しないための回帰。"""

    def test_body_only_mention_found_and_highlighted(self, authenticated_client, user):
        from stockdiary.models import StockDiary
        # 「半導体」をタグにはせず reason 本文にだけ書く
        d = StockDiary.objects.create(
            user=user, stock_symbol='8035', stock_name='東京エレクトロン',
            reason='半導体製造装置の世界的リーダー。',
        )
        resp = authenticated_client.get(reverse('stockdiary:home') + '?query=半導体')
        assert resp.status_code == 200
        ids = [x.id for x in resp.context['diaries']]
        assert d.id in ids                               # タグ無しでも本文ヒット
        assert 'search-highlight' in resp.content.decode()  # ハイライトが当たる
