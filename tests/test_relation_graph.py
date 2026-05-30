"""
関連グラフの「関連度で間引く」ロジックのテスト。

- hub_weight: 逆頻度の重み（希少な関連ほど強い）
- get_tag_graph_data: エッジ・ハブへの weight / is_isolated 付与
- compute_related_strength: 希少性で重み付けした関連サマリー＋ノイズ除外
"""
import pytest

from stockdiary.models import StockDiary
from stockdiary.utils import (
    hub_weight,
    get_tag_graph_data,
    compute_related_strength,
)
from tags.models import Tag


def _diary(user, symbol, name, **kwargs):
    return StockDiary.objects.create(
        user=user, stock_symbol=symbol, stock_name=name, **kwargs
    )


class TestHubWeight:
    """逆頻度の重み付け（少数を結ぶハブほど強い）"""

    def test_rare_hub_is_strong(self):
        assert hub_weight(2) == 1.0
        assert hub_weight(3) == 0.5
        assert hub_weight(6) == 0.2

    def test_single_member_hub(self):
        assert hub_weight(1) == 1.0


@pytest.mark.django_db
class TestTagGraphWeights:
    def test_edges_and_nodes_carry_inverse_frequency_weight(self, user):
        tag = Tag.objects.create(user=user, name='半導体')
        d1 = _diary(user, '8035', '東京エレクトロン')
        d2 = _diary(user, '6857', 'アドバンテスト')
        d1.tags.add(tag)
        d2.tags.add(tag)

        qs = StockDiary.objects.filter(user=user).prefetch_related('tags')
        res = get_tag_graph_data(qs)

        node = next(n for n in res['tag_nodes'] if n['tag_name'] == '半導体')
        assert node['diary_count'] == 2
        assert node['weight'] == 1.0
        assert node['is_isolated'] is False
        assert all('weight' in e for e in res['edges'])

    def test_isolated_tag_flagged(self, user):
        tag = Tag.objects.create(user=user, name='単独')
        d = _diary(user, '9999', '単独銘柄')
        d.tags.add(tag)

        qs = StockDiary.objects.filter(user=user).prefetch_related('tags')
        node = get_tag_graph_data(qs)['tag_nodes'][0]
        assert node['diary_count'] == 1
        assert node['is_isolated'] is True


@pytest.mark.django_db
class TestComputeRelatedStrength:
    def test_shared_rare_tag_links_diaries(self, user):
        tag = Tag.objects.create(user=user, name='半導体')
        focal = _diary(user, '8035', '東京エレクトロン')
        other = _diary(user, '6857', 'アドバンテスト')
        focal.tags.add(tag)
        other.tags.add(tag)

        res = compute_related_strength(focal, user)
        item = next(r for r in res if r['diary'].id == other.id)
        assert any(v['type'] == 'tag' for v in item['via'])
        assert item['score'] == 1.0  # 2銘柄だけが共有 -> weight 1.0

    def test_same_symbol_is_strong(self, user):
        focal = _diary(user, '7203', 'トヨタ自動車')
        other = _diary(user, '7203', 'トヨタ（旧メモ）')

        res = compute_related_strength(focal, user)
        item = next(r for r in res if r['diary'].id == other.id)
        assert any(v['type'] == 'symbol' for v in item['via'])

    def test_manual_link(self, user):
        focal = _diary(user, '1111', 'A社')
        other = _diary(user, '2222', 'B社')
        focal.linked_diaries.add(other)

        res = compute_related_strength(focal, user)
        item = next(r for r in res if r['diary'].id == other.id)
        assert any(v['type'] == 'manual' for v in item['via'])

    def test_mention_links_by_code(self, user):
        other = _diary(user, '7203', 'トヨタ自動車')
        focal = _diary(user, '7267', 'ホンダ', reason='競合の (7203) と比較')

        res = compute_related_strength(focal, user)
        item = next(r for r in res if r['diary'].id == other.id)
        assert any(v['type'] == 'mention' for v in item['via'])

    def test_excludes_other_users(self, user, another_user):
        tag = Tag.objects.create(user=user, name='共通テーマ')
        focal = _diary(user, '1', 'F社')
        focal.tags.add(tag)

        foreign_tag = Tag.objects.create(user=another_user, name='共通テーマ')
        foreign = _diary(another_user, '2', '他人の銘柄')
        foreign.tags.add(foreign_tag)

        res = compute_related_strength(focal, user)
        assert all(r['diary'].user_id == user.id for r in res)

    def test_overused_tag_is_filtered_as_noise(self, user, monkeypatch):
        # しきい値を 2 に下げ、3銘柄以上が共有するタグはノイズ扱いになることを確認
        monkeypatch.setattr('stockdiary.utils.RELATED_NOISE_MAX', 2)

        tag = Tag.objects.create(user=user, name='ありふれたタグ')
        focal = _diary(user, '500', 'F社')
        focal.tags.add(tag)

        d0 = _diary(user, '600', 'D0')
        d0.tags.add(tag)
        focal.linked_diaries.add(d0)  # 手動リンクで必ず出現させる
        d1 = _diary(user, '601', 'D1')
        d1.tags.add(tag)
        d2 = _diary(user, '602', 'D2')
        d2.tags.add(tag)

        res = compute_related_strength(focal, user)
        appearing = {r['diary'].id for r in res}

        # 手動リンクの d0 は出現するが、tag 経由ではない（付けすぎタグは除外）
        assert d0.id in appearing
        item = next(r for r in res if r['diary'].id == d0.id)
        assert all(v['type'] != 'tag' for v in item['via'])

        # タグのみで繋がる d1 / d2 はノイズ除外で出現しない
        assert d1.id not in appearing
        assert d2.id not in appearing

    def test_multidimensional_outranks_single(self, user):
        tag = Tag.objects.create(user=user, name='テーマ')
        focal = _diary(user, '9000', 'F社')
        focal.tags.add(tag)

        weak = _diary(user, '9001', 'Weak社')
        weak.tags.add(tag)
        strong = _diary(user, '9002', 'Strong社')
        strong.tags.add(tag)
        focal.linked_diaries.add(strong)  # strong は手動リンクも持つ

        res = compute_related_strength(focal, user)
        order = [r['diary'].id for r in res]
        assert order.index(strong.id) < order.index(weak.id)
