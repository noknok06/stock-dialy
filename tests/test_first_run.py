"""新規ユーザーの初回体験（空状態・オンボーディング・登録後自動ログイン）のテスト"""
import pytest

from django.urls import reverse

from stockdiary.models import StockDiary

pytestmark = pytest.mark.django_db(transaction=True)


class TestEmptyStateHome:
    """日記0件時の home（オンボーディングカード表示・フィルター群非表示）"""

    def test_empty_state_shows_onboarding(self, authenticated_client):
        response = authenticated_client.get(reverse('stockdiary:home'))
        assert response.status_code == 200
        assert response.context['is_empty_state'] is True
        html = response.content.decode()
        assert 'id="onboardingCard"' in html
        assert '最初の一行を書く' in html
        # フィルター群は非表示
        assert 'id="homeSidebar"' not in html
        assert 'id="filterPanel"' not in html

    def test_with_diary_shows_normal_ui(self, authenticated_client, sample_diary):
        response = authenticated_client.get(reverse('stockdiary:home'))
        assert response.context['is_empty_state'] is False
        html = response.content.decode()
        assert 'id="onboardingCard"' not in html
        assert 'id="homeSidebar"' in html
        assert 'id="filterPanel"' in html

    def test_search_with_zero_results_not_empty_state(self, authenticated_client):
        """0件でも検索条件があれば通常UI（検索結果なし表示）を出す"""
        response = authenticated_client.get(reverse('stockdiary:home'), {'query': '存在しない'})
        assert response.context['is_empty_state'] is False
        assert 'id="onboardingCard"' not in response.content.decode()

    def test_no_duplicate_empty_alert(self, authenticated_client):
        """オンボーディングカード表示時は旧空状態アラートを出さない"""
        response = authenticated_client.get(reverse('stockdiary:home'))
        assert '日記がありません。「新規日記作成」' not in response.content.decode()


class TestSignupAutoLogin:
    """登録後の自動ログイン"""

    def test_signup_logs_in_and_redirects_home(self, client):
        response = client.post(reverse('users:signup'), {
            'username': 'firstuser',
            'email': 'first@example.com',
            'password1': 'k4bu-log-Str0ng!',
            'password2': 'k4bu-log-Str0ng!',
        })
        assert response.status_code == 302
        # ホームへ遷移（GA4 の sign_up 計測用に ?signup=1 が付く）
        assert response.url.split('?')[0] == reverse('stockdiary:home')
        assert 'signup=1' in response.url
        # セッションが張られている（ログイン画面に戻されない）
        response = client.get(reverse('stockdiary:home'))
        assert response.status_code == 200
        assert response.context['user'].username == 'firstuser'


class TestEmptyStateLinks:
    """各ページの空状態からの導線"""

    def test_timeline_empty_state_has_create_link(self, authenticated_client):
        response = authenticated_client.get(reverse('stockdiary:timeline'))
        html = response.content.decode()
        assert '最初の日記を作る' in html
        assert reverse('stockdiary:create') in html

    def test_dashboard_empty_state_has_link(self, authenticated_client):
        response = authenticated_client.get(reverse('stockdiary:dashboard'))
        assert '日記に取引を記録する' in response.content.decode()
