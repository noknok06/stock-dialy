"""統一玄関「書く」FAB（段階9b）のテスト。

docs/diary_recording_redesign.md 段階9b:
- 全画面共通の FAB → コンポーズシート
- 自分の日記サジェスト(search_my_diaries)で既存追記 or 新規作成を人間が選ぶ
- 実体は既存 quick_create_diary / quick_add_note に振り分け
"""
import pytest
from django.urls import reverse

from stockdiary.models import StockDiary


@pytest.mark.django_db
class TestSearchMyDiaries:
    def test_returns_own_matching_diaries_by_name(self, authenticated_client, sample_diary):
        url = reverse('stockdiary:api_search_my_diaries')
        resp = authenticated_client.get(url, {'q': 'トヨタ'})
        assert resp.status_code == 200
        ids = [d['id'] for d in resp.json()['diaries']]
        assert sample_diary.id in ids

    def test_returns_by_symbol(self, authenticated_client, sample_diary):
        url = reverse('stockdiary:api_search_my_diaries')
        resp = authenticated_client.get(url, {'q': '7203'})
        ids = [d['id'] for d in resp.json()['diaries']]
        assert sample_diary.id in ids

    def test_excludes_other_users(self, authenticated_client, another_user):
        StockDiary.objects.create(user=another_user, stock_symbol='9999', stock_name='他人の銘柄')
        url = reverse('stockdiary:api_search_my_diaries')
        resp = authenticated_client.get(url, {'q': '他人'})
        assert resp.json()['diaries'] == []

    def test_empty_query_returns_empty(self, authenticated_client):
        url = reverse('stockdiary:api_search_my_diaries')
        resp = authenticated_client.get(url, {'q': ''})
        assert resp.json()['diaries'] == []


@pytest.mark.django_db
class TestComposeFabRendered:
    def test_fab_and_modal_present_on_authenticated_page(self, authenticated_client, sample_diary):
        resp = authenticated_client.get(reverse('stockdiary:home'))
        assert resp.status_code == 200
        html = resp.content.decode()
        assert 'composeFab' in html        # FAB ボタン
        assert 'compose-modal' in html      # コンポーズシート
        assert 'composeStock' in html       # 銘柄サジェスト入力

    def test_fab_absent_for_anonymous(self, client):
        # 未ログインのランディング等では FAB を出さない
        resp = client.get(reverse('stockdiary:home'))
        # 未認証は通常ログインへリダイレクト（FAB は描画されない）
        if resp.status_code == 200:
            assert 'composeFab' not in resp.content.decode()
