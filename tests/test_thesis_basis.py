"""仮説(Thesis)UX改善：主張の複数行・長文化＋根拠(basis)の自由文。

docs/diary_recording_redesign.md 仮説UX改善。
"""
import pytest
from django.urls import reverse

from stockdiary.models import Thesis


@pytest.mark.django_db
class TestThesisBasis:
    def test_create_thesis_with_long_claim_and_basis(self, authenticated_client, sample_diary):
        url = reverse('stockdiary:thesis_create', kwargs={'diary_id': sample_diary.pk})
        long_claim = 'あ' * 300   # 旧上限(200)を超える主張
        resp = authenticated_client.post(url, {
            'claim': long_claim,
            'basis': '受注残が積み上がり、来期も二桁増益が見込めるため。',
            'horizon': '6m',
        })
        assert resp.status_code in (200, 302)
        t = Thesis.objects.filter(diary=sample_diary).order_by('-id').first()
        assert t is not None
        assert len(t.claim) == 300
        assert '受注残' in t.basis

    def test_detail_shows_basis(self, authenticated_client, sample_diary):
        Thesis.objects.create(diary=sample_diary, claim='主張テスト', basis='根拠の文章テストです')
        resp = authenticated_client.get(reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk}))
        html = resp.content.decode()
        assert 'karte-basis' in html        # 根拠表示の要素
        assert '根拠の文章テストです' in html
