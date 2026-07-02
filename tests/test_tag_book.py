"""
背景まとめ（TagBookView / 読み物ビュー）のテスト。

- reason のある銘柄のみが entries に入り、継続記録(notes)と mention_map を持つ
- ?order=asc/desc で並びが変わる
- ページに reason 本文・継続記録セクションが描画される
"""
import datetime
import pytest
from django.urls import reverse

from stockdiary.models import StockDiary
from tags.models import Tag


@pytest.mark.django_db
class TestTagBookReading:
    def test_entries_only_with_reason_and_carry_notes(self, authenticated_client, user, diary_with_notes):
        tag = Tag.objects.create(user=user, name='長期投資', axis='theme')
        diary_with_notes.tags.add(tag)  # reason='長期保有目的' ＋ 継続記録2件
        # reason 空の銘柄は読み物に出さない
        memo = StockDiary.objects.create(user=user, stock_symbol='6758', stock_name='ソニー', reason='')
        memo.tags.add(tag)

        resp = authenticated_client.get(reverse('tags:book', kwargs={'pk': tag.pk}))
        assert resp.status_code == 200
        entries = resp.context['entries']
        symbols = {e['diary'].stock_symbol for e in entries}
        assert '7203' in symbols
        assert '6758' not in symbols  # reason 空は除外

        e = next(e for e in entries if e['diary'].stock_symbol == '7203')
        assert len(e['notes']) == 2
        # 継続記録は時系列（古い→新しい）
        assert e['notes'][0].date <= e['notes'][1].date
        assert 'mention_map' in resp.context

    def test_order_toggle(self, authenticated_client, user):
        tag = Tag.objects.create(user=user, name='テーマ', axis='theme')
        a = StockDiary.objects.create(user=user, stock_symbol='1111', stock_name='A社',
                                      reason='理由A', last_transaction_date=datetime.date(2025, 1, 1))
        b = StockDiary.objects.create(user=user, stock_symbol='2222', stock_name='B社',
                                      reason='理由B', last_transaction_date=datetime.date(2025, 6, 1))
        a.tags.add(tag)
        b.tags.add(tag)
        url = reverse('tags:book', kwargs={'pk': tag.pk})

        desc = authenticated_client.get(url + '?order=desc').context['entries']
        asc = authenticated_client.get(url + '?order=asc').context['entries']
        assert [e['diary'].stock_symbol for e in desc] == ['2222', '1111']
        assert [e['diary'].stock_symbol for e in asc] == ['1111', '2222']

    def test_page_renders_reason_and_notes(self, authenticated_client, user, diary_with_notes):
        tag = Tag.objects.create(user=user, name='長期投資', axis='theme')
        diary_with_notes.tags.add(tag)
        html = authenticated_client.get(reverse('tags:book', kwargs={'pk': tag.pk})).content.decode()
        assert 'readbook' in html
        assert '背景まとめ' in html
        assert 'rb-reason' in html
        assert 'その後の考え' in html          # 継続記録セクション
        assert '長期保有目的' in html           # reason 本文が全文描画される

    def test_jump_nav_shown_only_for_multiple_entries(self, authenticated_client, user):
        tag = Tag.objects.create(user=user, name='テーマ', axis='theme')
        a = StockDiary.objects.create(user=user, stock_symbol='1111', stock_name='A社', reason='理由A')
        a.tags.add(tag)
        url = reverse('tags:book', kwargs={'pk': tag.pk})

        # 1銘柄ではジャンプナビ（マークアップ）を出さない（CSSにrb-nav文字列があるためid属性で判定）
        html1 = authenticated_client.get(url).content.decode()
        assert 'id="rbNav"' not in html1

        # 2銘柄以上で目次（チップ）とアンカーが出る
        b = StockDiary.objects.create(user=user, stock_symbol='2222', stock_name='B社', reason='理由B')
        b.tags.add(tag)
        html2 = authenticated_client.get(url).content.decode()
        assert 'id="rbNav"' in html2
        assert html2.count('class="rb-chip"') == 2
        assert 'id="rb-e0"' in html2 and 'id="rb-e1"' in html2

    def test_empty_state(self, authenticated_client, user):
        tag = Tag.objects.create(user=user, name='空タグ', axis='theme')
        html = authenticated_client.get(reverse('tags:book', kwargs={'pk': tag.pk})).content.decode()
        assert 'まだ背景の記録がありません' in html
