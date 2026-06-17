"""Phase 8d: 投資家カルテ（自己理解）のテスト"""
import pytest

from django.urls import reverse

from stockdiary.models import StockDiary, Thesis, Verdict
from stockdiary.services.karte_service import build_investor_karte

pytestmark = pytest.mark.django_db(transaction=True)


def _verdict(diary, hyp, pnl, **kw):
    t = Thesis.objects.create(diary=diary, claim='c')
    return Verdict.objects.create(thesis=t, hypothesis_result=hyp, pnl_result=pnl, **kw)


class TestKarteService:
    def test_empty(self, user):
        k = build_investor_karte(user)
        assert k['has_content'] is False
        assert k['total'] == 0

    def test_quadrant_distribution_and_lucky_share(self, user):
        d1 = StockDiary.objects.create(user=user, stock_name='A', stock_symbol='1')
        d2 = StockDiary.objects.create(user=user, stock_name='B', stock_symbol='2')
        # 仮説外れ×利益（偶然の勝ち） + 仮説的中×利益（実力）
        _verdict(d1, Verdict.HYP_MISS, Verdict.PNL_PROFIT)
        _verdict(d2, Verdict.HYP_HIT, Verdict.PNL_PROFIT)
        k = build_investor_karte(user)
        counts = {q['key']: q['count'] for q in k['quadrants']}
        assert counts['lucky'] == 1
        assert counts['skill'] == 1
        assert k['total_wins'] == 2
        assert k['lucky_share'] == 50  # 勝ち2件のうち1件が偶然

    def test_repeated_misses(self, user):
        d1 = StockDiary.objects.create(user=user, stock_name='A', stock_symbol='1')
        d2 = StockDiary.objects.create(user=user, stock_name='B', stock_symbol='2')
        _verdict(d1, Verdict.HYP_MISS, Verdict.PNL_LOSS, missed_factor='入るのが早い')
        _verdict(d2, Verdict.HYP_MISS, Verdict.PNL_LOSS, missed_factor='入るのが早い')
        k = build_investor_karte(user)
        assert k['repeated_misses']
        assert k['repeated_misses'][0]['text'] == '入るのが早い'
        assert k['repeated_misses'][0]['count'] == 2

    def test_philosophy_prefers_repeatable(self, user):
        d1 = StockDiary.objects.create(user=user, stock_name='A', stock_symbol='1')
        _verdict(d1, Verdict.HYP_HIT, Verdict.PNL_PROFIT,
                 learning='テーマで持ち続ける', is_repeatable=True)
        k = build_investor_karte(user)
        assert any(p['text'] == 'テーマで持ち続ける' for p in k['philosophy'])


class TestKarteView:
    def test_karte_renders(self, authenticated_client):
        r = authenticated_client.get(reverse('stockdiary:investor_karte'))
        assert r.status_code == 200
        assert 'karte' in r.context
