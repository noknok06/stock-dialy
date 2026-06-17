"""Phase 8a: 検証ループ（Thesis / Verdict）のテスト"""
import pytest
from datetime import date

from django.urls import reverse

from stockdiary.models import Thesis, Verdict

pytestmark = pytest.mark.django_db(transaction=True)


class TestVerdictQuadrant:
    """意思決定の質 × 結果 の2×2分類（成長OSの心臓）"""

    def _make(self, diary, hyp, pnl):
        thesis = Thesis.objects.create(diary=diary, claim='テスト主張')
        return Verdict.objects.create(thesis=thesis, hypothesis_result=hyp, pnl_result=pnl)

    def test_hit_profit_is_skill(self, sample_diary):
        v = self._make(sample_diary, Verdict.HYP_HIT, Verdict.PNL_PROFIT)
        assert v.quadrant == 'skill'
        assert v.quadrant_label == '再現すべき勝ち'

    def test_hit_loss_is_unlucky(self, sample_diary):
        # 仮説は正しいが損失 = 一級市民として表現できる
        v = self._make(sample_diary, Verdict.HYP_HIT, Verdict.PNL_LOSS)
        assert v.quadrant == 'unlucky'

    def test_miss_profit_is_lucky(self, sample_diary):
        # 仮説は外れたが利益（偶然・危険）
        v = self._make(sample_diary, Verdict.HYP_MISS, Verdict.PNL_PROFIT)
        assert v.quadrant == 'lucky'

    def test_miss_loss_is_discipline(self, sample_diary):
        v = self._make(sample_diary, Verdict.HYP_MISS, Verdict.PNL_LOSS)
        assert v.quadrant == 'discipline'

    def test_stars(self, sample_diary):
        v = self._make(sample_diary, Verdict.HYP_HIT, Verdict.PNL_PROFIT)
        v.decision_quality = 3
        assert v.stars == '★★★☆☆'


class TestThesisDue:
    def test_is_due_when_past_and_open(self, sample_diary):
        t = Thesis.objects.create(diary=sample_diary, claim='c',
                                  review_due_date=date(2000, 1, 1))
        assert t.is_due is True

    def test_not_due_when_verified(self, sample_diary):
        t = Thesis.objects.create(diary=sample_diary, claim='c',
                                  review_due_date=date(2000, 1, 1),
                                  status=Thesis.STATUS_VERIFIED)
        assert t.is_due is False


class TestThesisVerifyViews:
    def test_create_thesis_via_htmx(self, authenticated_client, sample_diary):
        url = reverse('stockdiary:thesis_edit', args=[sample_diary.id])
        # GET returns the form
        r = authenticated_client.get(url, HTTP_HX_REQUEST='true')
        assert r.status_code == 200
        # POST creates the thesis and returns the karte block
        r = authenticated_client.post(url, {
            'claim': '円安継続で輸出採算が改善する',
            'horizon': '6m',
            'worst_case': '円高反転',
        }, HTTP_HX_REQUEST='true')
        assert r.status_code == 200
        sample_diary.refresh_from_db()
        thesis = Thesis.objects.get(diary=sample_diary)
        assert thesis.claim == '円安継続で輸出採算が改善する'
        # review_due_date は horizon から自動補完される
        assert thesis.review_due_date is not None

    def test_verify_creates_verdict_and_sets_status(self, authenticated_client, sample_diary):
        Thesis.objects.create(diary=sample_diary, claim='主張')
        url = reverse('stockdiary:thesis_verify', args=[sample_diary.id])
        r = authenticated_client.get(url, HTTP_HX_REQUEST='true')
        assert r.status_code == 200
        r = authenticated_client.post(url, {
            'hypothesis_result': Verdict.HYP_MISS,
            'pnl_result': Verdict.PNL_PROFIT,
            'decision_quality': 2,
            'learning': '為替単独を根拠に投資しない',
        }, HTTP_HX_REQUEST='true')
        assert r.status_code == 200
        thesis = Thesis.objects.get(diary=sample_diary)
        assert thesis.status == Thesis.STATUS_VERIFIED
        assert thesis.verdict.quadrant == 'lucky'
        assert thesis.verdict.learning == '為替単独を根拠に投資しない'

    def test_cannot_touch_others_diary(self, authenticated_client, another_user):
        from stockdiary.models import StockDiary
        other = StockDiary.objects.create(user=another_user, stock_name='他人', stock_symbol='9999')
        url = reverse('stockdiary:thesis_edit', args=[other.id])
        r = authenticated_client.post(url, {'claim': 'x', 'horizon': '6m'}, HTTP_HX_REQUEST='true')
        assert r.status_code == 404
