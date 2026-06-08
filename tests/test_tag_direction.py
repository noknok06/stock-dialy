"""
タグの方向属性（DiaryTagDirection）に関するテスト。

- get_tag_graph_data: エッジに direction が乗る（グラフのエッジ着色用）
- compute_related_strength: 共有タグの方向から順相関(positive)/逆相関(inverse)を判定
- set_tag_direction ビュー: 方向の保存・同一銘柄への反映・他ユーザー拒否
- TagDetailView: プラス/マイナス件数とヘッジ検出フラグ
"""
import pytest
from django.test import Client
from django.urls import reverse

from stockdiary.models import StockDiary, DiaryTagDirection
from stockdiary.utils import get_tag_graph_data, compute_related_strength
from tags.models import Tag


def _diary(user, symbol, name, **kwargs):
    return StockDiary.objects.create(
        user=user, stock_symbol=symbol, stock_name=name, **kwargs
    )


def _set_dir(diary, tag, direction):
    return DiaryTagDirection.objects.create(diary=diary, tag=tag, direction=direction)


@pytest.mark.django_db
class TestTagGraphDirection:
    def test_edges_carry_direction(self, user):
        tag = Tag.objects.create(user=user, name='金利上昇', axis='macro')
        bank = _diary(user, '8306', '三菱UFJ')
        semi = _diary(user, '8035', '東京エレクトロン')
        bank.tags.add(tag)
        semi.tags.add(tag)
        _set_dir(bank, tag, 'up')
        _set_dir(semi, tag, 'down')

        qs = StockDiary.objects.filter(user=user).prefetch_related('tags')
        res = get_tag_graph_data(qs)

        edge_dir = {e['source']: e['direction'] for e in res['edges']}
        assert edge_dir[bank.id] == 'up'
        assert edge_dir[semi.id] == 'down'

    def test_edge_direction_defaults_neutral(self, user):
        tag = Tag.objects.create(user=user, name='半導体')
        d = _diary(user, '6857', 'アドバンテスト')
        d.tags.add(tag)

        qs = StockDiary.objects.filter(user=user).prefetch_related('tags')
        res = get_tag_graph_data(qs)
        assert res['edges'][0]['direction'] == 'neutral'


@pytest.mark.django_db
class TestRelatedCorrelation:
    def _setup_pair(self, user, focal_dir, other_dir):
        # 2タグ共有で MIN_SHARED_TAGS を満たす。方向は1タグに付与。
        t1 = Tag.objects.create(user=user, name='金利上昇', axis='macro')
        t2 = Tag.objects.create(user=user, name='景気敏感', axis='macro')
        focal = _diary(user, '8306', '三菱UFJ')
        other = _diary(user, '8035', '東京エレクトロン')
        _diary(user, '9999', '無関係')  # N を増やして IDF>0 を確保
        focal.tags.add(t1, t2)
        other.tags.add(t1, t2)
        _set_dir(focal, t1, focal_dir)
        _set_dir(other, t1, other_dir)
        return focal, other

    def test_inverse_correlation(self, user):
        focal, other = self._setup_pair(user, 'up', 'down')
        res = compute_related_strength(focal, user)
        item = next(r for r in res if r['diary'].id == other.id)
        assert any(v.get('correlation') == 'inverse' for v in item['via'])

    def test_positive_correlation(self, user):
        focal, other = self._setup_pair(user, 'up', 'up')
        res = compute_related_strength(focal, user)
        item = next(r for r in res if r['diary'].id == other.id)
        assert any(v.get('correlation') == 'positive' for v in item['via'])

    def test_neutral_has_no_correlation(self, user):
        # 片方が中立（未設定）なら correlation は付かない
        focal, other = self._setup_pair(user, 'up', 'neutral')
        res = compute_related_strength(focal, user)
        item = next(r for r in res if r['diary'].id == other.id)
        assert all('correlation' not in v for v in item['via'])


@pytest.mark.django_db
class TestSetTagDirectionView:
    def test_sets_direction(self, authenticated_client, user):
        tag = Tag.objects.create(user=user, name='金利上昇', axis='macro')
        diary = _diary(user, '8306', '三菱UFJ')
        diary.tags.add(tag)

        url = reverse('tags:set_direction', kwargs={'pk': tag.pk})
        resp = authenticated_client.post(url, {'diary_id': diary.id, 'direction': 'up'})
        assert resp.status_code == 200
        assert DiaryTagDirection.objects.get(diary=diary, tag=tag).direction == 'up'

        # 更新（up -> down）も update_or_create で反映
        authenticated_client.post(url, {'diary_id': diary.id, 'direction': 'down'})
        assert DiaryTagDirection.objects.get(diary=diary, tag=tag).direction == 'down'

    def test_applies_to_same_symbol_diaries(self, authenticated_client, user):
        tag = Tag.objects.create(user=user, name='金利上昇', axis='macro')
        d1 = _diary(user, '8306', '三菱UFJ')
        d2 = _diary(user, '8306', '三菱UFJ（旧メモ）')
        d1.tags.add(tag)
        d2.tags.add(tag)

        url = reverse('tags:set_direction', kwargs={'pk': tag.pk})
        authenticated_client.post(url, {'diary_id': d1.id, 'direction': 'down'})

        assert DiaryTagDirection.objects.get(diary=d1, tag=tag).direction == 'down'
        assert DiaryTagDirection.objects.get(diary=d2, tag=tag).direction == 'down'

    def test_invalid_direction_rejected(self, authenticated_client, user):
        tag = Tag.objects.create(user=user, name='半導体')
        diary = _diary(user, '8035', '東京エレクトロン')
        diary.tags.add(tag)
        url = reverse('tags:set_direction', kwargs={'pk': tag.pk})
        resp = authenticated_client.post(url, {'diary_id': diary.id, 'direction': 'sideways'})
        assert resp.status_code == 400

    def test_csrf_enforced_and_passes_with_header_token(self, user):
        # 本番同様 CSRF を強制し、X-CSRFToken ヘッダ（htmx が付与する）で通ることを確認
        tag = Tag.objects.create(user=user, name='金利上昇', axis='macro')
        diary = _diary(user, '8306', '三菱UFJ')
        diary.tags.add(tag)
        c = Client(enforce_csrf_checks=True)
        c.force_login(user)
        url = reverse('tags:set_direction', kwargs={'pk': tag.pk})

        # トークンなし → 403（再現していた不具合）
        resp = c.post(url, {'diary_id': diary.id, 'direction': 'up'})
        assert resp.status_code == 403

        # タグ詳細を開いて csrftoken クッキーを取得 → ヘッダ付きPOSTは成功
        c.get(reverse('tags:detail', kwargs={'pk': tag.pk}))
        token = c.cookies['csrftoken'].value
        resp2 = c.post(url, {'diary_id': diary.id, 'direction': 'up'}, HTTP_X_CSRFTOKEN=token)
        assert resp2.status_code == 200
        assert DiaryTagDirection.objects.get(diary=diary, tag=tag).direction == 'up'

    def test_other_users_tag_rejected(self, authenticated_client, user, another_user):
        foreign_tag = Tag.objects.create(user=another_user, name='金利上昇', axis='macro')
        foreign_diary = _diary(another_user, '8306', '三菱UFJ')
        foreign_diary.tags.add(foreign_tag)
        url = reverse('tags:set_direction', kwargs={'pk': foreign_tag.pk})
        resp = authenticated_client.post(url, {'diary_id': foreign_diary.id, 'direction': 'up'})
        assert resp.status_code == 404


@pytest.mark.django_db
class TestTagDetailDirectionContext:
    def test_counts_and_hedge_flag(self, authenticated_client, user):
        tag = Tag.objects.create(user=user, name='金利上昇', axis='macro')
        bank = _diary(user, '8306', '三菱UFJ')
        semi = _diary(user, '8035', '東京エレクトロン')
        memo = _diary(user, '6857', 'アドバンテスト')
        for d in (bank, semi, memo):
            d.tags.add(tag)
        _set_dir(bank, tag, 'up')
        _set_dir(semi, tag, 'down')
        # memo は未設定 = neutral

        url = reverse('tags:detail', kwargs={'pk': tag.pk})
        resp = authenticated_client.get(url)
        assert resp.status_code == 200
        stats = resp.context['stats']
        assert stats['plus_count'] == 1
        assert stats['minus_count'] == 1
        assert stats['neutral_count'] == 1
        assert resp.context['has_hedge'] is True

    def test_axis_and_per_stock_card_fields(self, authenticated_client, user):
        tag = Tag.objects.create(user=user, name='金利上昇', axis='macro')
        bank = _diary(user, '8306', '三菱UFJ', sector='銀行業')
        bank.tags.add(tag)
        url = reverse('tags:detail', kwargs={'pk': tag.pk})
        resp = authenticated_client.get(url)
        assert resp.status_code == 200
        # マクロ軸の色がコンテキストに渡る（カードのアクセント・グラフ着色に使用）
        assert resp.context['axis_color']
        # 銘柄カード用の status / records が付与される
        stock = next(s for s in resp.context['stock_list'] if s['symbol'] == '8306')
        assert stock['status'] in ('holding', 'sold', 'memo')
        assert stock['records'] == stock['total_entries']

    def test_redesigned_page_renders_key_blocks(self, authenticated_client, user):
        tag = Tag.objects.create(user=user, name='半導体', axis='theme')
        for sym, name in [('8035', '東京エレクトロン'), ('6857', 'アドバンテスト')]:
            d = _diary(user, sym, name, sector='電機')
            d.tags.add(tag)
        url = reverse('tags:detail', kwargs={'pk': tag.pk})
        html = authenticated_client.get(url).content.decode()
        for marker in ['class="tagdetail"', 'td-tagbadge', 'td-stats', 'td-mgcard',
                       'mini-diary-graph-svg', 'td-grid', 'td-status', 'tag-dir-']:
            assert marker in html, f'missing {marker}'
