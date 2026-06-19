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

    def test_empty_query_returns_recent(self, authenticated_client, sample_diary):
        # [[ 直後（空クエリ）でも最近の日記を候補に出す（@タグ補完と挙動を揃える）
        url = reverse('stockdiary:api_search_my_diaries')
        resp = authenticated_client.get(url, {'q': ''})
        ids = [d['id'] for d in resp.json()['diaries']]
        assert sample_diary.id in ids

    def test_empty_query_no_diaries_is_empty(self, authenticated_client):
        url = reverse('stockdiary:api_search_my_diaries')
        resp = authenticated_client.get(url, {'q': ''})
        assert resp.json()['diaries'] == []
