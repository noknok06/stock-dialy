"""Phase 8c: 知識ライブラリ（学び/テーマ/仮説）のテスト"""
import pytest

from django.urls import reverse

from stockdiary.models import StockDiary, Thesis, Verdict

pytestmark = pytest.mark.django_db(transaction=True)


def _learning(diary, text, hyp=Verdict.HYP_HIT, pnl=Verdict.PNL_PROFIT):
    t = Thesis.objects.create(diary=diary, claim='c')
    return Verdict.objects.create(thesis=t, hypothesis_result=hyp, pnl_result=pnl, learning=text)


class TestLibrary:
    def test_learning_axis_default(self, authenticated_client, user):
        d = StockDiary.objects.create(user=user, stock_name='日本郵船', stock_symbol='9101')
        _learning(d, '海運は運賃サイクルを読む')
        r = authenticated_client.get(reverse('stockdiary:library'))
        assert r.status_code == 200
        assert r.context['axis'] == 'learning'
        assert any(v.learning == '海運は運賃サイクルを読む' for v in r.context['learnings'])

    def test_learning_search_by_keyword(self, authenticated_client, user):
        d1 = StockDiary.objects.create(user=user, stock_name='日本郵船', stock_symbol='9101')
        d2 = StockDiary.objects.create(user=user, stock_name='トヨタ', stock_symbol='7203')
        _learning(d1, '海運は運賃サイクルを読む')
        _learning(d2, '為替単独を根拠にしない')
        r = authenticated_client.get(reverse('stockdiary:library'), {'q': '海運'})
        texts = [v.learning for v in r.context['learnings']]
        assert '海運は運賃サイクルを読む' in texts
        assert '為替単独を根拠にしない' not in texts

    def test_thesis_axis_groups(self, authenticated_client, user):
        d1 = StockDiary.objects.create(user=user, stock_name='A', stock_symbol='1')
        d2 = StockDiary.objects.create(user=user, stock_name='B', stock_symbol='2')
        Thesis.objects.create(diary=d1, claim='未検証の主張')  # open
        _learning(d2, '的中の学び', hyp=Verdict.HYP_HIT)       # hit
        r = authenticated_client.get(reverse('stockdiary:library'), {'axis': 'thesis'})
        assert r.status_code == 200
        assert len(r.context['open_theses']) == 1
        assert len(r.context['hit_verdicts']) == 1

    def test_theme_axis(self, authenticated_client, user, sample_tags):
        d = StockDiary.objects.create(user=user, stock_name='A', stock_symbol='1')
        d.tags.add(sample_tags[0])
        r = authenticated_client.get(reverse('stockdiary:library'), {'axis': 'theme'})
        assert r.status_code == 200
        assert any(t.n >= 1 for t in r.context['theme_rows'])
