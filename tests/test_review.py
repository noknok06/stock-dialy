"""年間/四半期レビュー（AnnualReviewView）の smoke テスト"""
import pytest

from django.urls import reverse

pytestmark = pytest.mark.django_db(transaction=True)


class TestAnnualReview:
    def test_review_year_renders(self, authenticated_client):
        url = reverse('stockdiary:annual_review')
        response = authenticated_client.get(url)
        assert response.status_code == 200
        assert response.context['period'] == 'year'
        # 期間ラベルに年が入る
        assert str(response.context['today'].year) in response.context['period_label']

    def test_review_quarter_renders(self, authenticated_client):
        url = reverse('stockdiary:annual_review')
        response = authenticated_client.get(url, {'period': 'quarter'})
        assert response.status_code == 200
        assert response.context['period'] == 'quarter'
        assert '四半期' in response.context['period_label']

    def test_review_with_data_has_content(self, authenticated_client, diary_with_notes):
        url = reverse('stockdiary:annual_review')
        response = authenticated_client.get(url)
        assert response.status_code == 200
        # 記録・学び・勝ち筋のいずれかがあれば has_content True
        assert 'has_content' in response.context
        assert 'winning_tags' in response.context
        assert 'learnings' in response.context
