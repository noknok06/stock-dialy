"""views_growth.py / views_dashboard.py の基本動作テスト。

これらのビューはカバレッジが8〜18%で、ほぼテストされていなかった。
最もリスクが高い「ログイン必須・正常系・所有者分離」のケースを優先する。
"""
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date

from stockdiary.models import StockDiary, Transaction, Thesis, Verdict

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='growth_test_user', password='pass', email='growth@example.com'
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username='growth_other_user', password='pass', email='growth_other@example.com'
    )


@pytest.fixture
def diary(user):
    return StockDiary.objects.create(
        user=user,
        stock_symbol='7203',
        stock_name='トヨタ自動車',
        reason='長期保有',
        currency='JPY',
    )


@pytest.fixture
def diary_with_transaction(user, diary):
    t = Transaction.objects.create(
        diary=diary,
        transaction_type='buy',
        transaction_date=date(2024, 1, 15),
        price=Decimal('2000'),
        quantity=Decimal('100'),
        is_margin=False,
    )
    return diary


@pytest.fixture
def thesis(diary):
    return Thesis.objects.create(
        diary=diary,
        claim='円安継続で輸出採算が改善する',
        horizon='6m',
    )


@pytest.fixture
def authed_client(client, user):
    client.login(username='growth_test_user', password='pass')
    return client


# ---------------------------------------------------------------------------
# InvestorKarteView
# ---------------------------------------------------------------------------

class TestInvestorKarteView:
    """投資家カルテページの基本動作テスト。"""

    def test_returns_200_for_authenticated_user(self, authed_client):
        """認証済みユーザーは 200 を返す。"""
        resp = authed_client.get(reverse('stockdiary:investor_karte'))
        assert resp.status_code == 200

    def test_requires_login(self, client):
        """未認証は 302 リダイレクト。"""
        resp = client.get(reverse('stockdiary:investor_karte'))
        assert resp.status_code == 302

    def test_karte_in_context(self, authed_client):
        """karte キーがコンテキストに含まれる。"""
        resp = authed_client.get(reverse('stockdiary:investor_karte'))
        assert 'karte' in resp.context


# ---------------------------------------------------------------------------
# karte_block (HTMX FBV)
# ---------------------------------------------------------------------------

class TestKarteBlock:
    """karte_block エンドポイントの基本動作テスト。"""

    def test_returns_200_for_owner(self, authed_client, diary):
        """日記の所有者は 200 を返す。"""
        url = reverse('stockdiary:karte_block', args=[diary.id])
        resp = authed_client.get(url)
        assert resp.status_code == 200

    def test_returns_404_for_other_user(self, authed_client, other_user):
        """他ユーザーの日記は 404 を返す。"""
        other_diary = StockDiary.objects.create(
            user=other_user, stock_symbol='9999', stock_name='他社株'
        )
        url = reverse('stockdiary:karte_block', args=[other_diary.id])
        resp = authed_client.get(url)
        assert resp.status_code == 404

    def test_requires_login(self, client, diary):
        """未認証は 302 リダイレクト。"""
        url = reverse('stockdiary:karte_block', args=[diary.id])
        resp = client.get(url)
        assert resp.status_code == 302

    def test_returns_theses_in_context(self, authed_client, diary, thesis):
        """仮説がコンテキストに含まれる。"""
        url = reverse('stockdiary:karte_block', args=[diary.id])
        resp = authed_client.get(url)
        assert resp.status_code == 200
        theses = list(resp.context['theses'])
        assert any(t.id == thesis.id for t in theses)


# ---------------------------------------------------------------------------
# AnnualReviewView
# ---------------------------------------------------------------------------

class TestAnnualReviewView:
    """年次レビューページの基本動作テスト。"""

    def test_returns_200_for_authenticated_user(self, authed_client):
        resp = authed_client.get(reverse('stockdiary:annual_review'))
        assert resp.status_code == 200

    def test_requires_login(self, client):
        resp = client.get(reverse('stockdiary:annual_review'))
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# LibraryView
# ---------------------------------------------------------------------------

class TestLibraryView:
    """学びライブラリページの基本動作テスト。"""

    def test_returns_200_for_authenticated_user(self, authed_client):
        resp = authed_client.get(reverse('stockdiary:library'))
        assert resp.status_code == 200

    def test_requires_login(self, client):
        resp = client.get(reverse('stockdiary:library'))
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# TradingDashboardView
# ---------------------------------------------------------------------------

class TestTradingDashboardView:
    """取引分析ダッシュボードの基本動作テスト。"""

    def test_returns_200_for_authenticated_user(self, authed_client):
        resp = authed_client.get(reverse('stockdiary:dashboard'))
        assert resp.status_code == 200

    def test_requires_login(self, client):
        resp = client.get(reverse('stockdiary:dashboard'))
        assert resp.status_code == 302

    def test_period_filter_1m(self, authed_client, diary_with_transaction):
        """period=1m でも 200 を返す（クラッシュしない）。"""
        resp = authed_client.get(reverse('stockdiary:dashboard'), {'period': '1m'})
        assert resp.status_code == 200

    def test_period_filter_all(self, authed_client, diary_with_transaction):
        """period=all でも 200 を返す（クラッシュしない）。"""
        resp = authed_client.get(reverse('stockdiary:dashboard'), {'period': 'all'})
        assert resp.status_code == 200

    def test_empty_state_does_not_crash(self, authed_client):
        """取引が1件もない状態でもクラッシュしない。"""
        resp = authed_client.get(reverse('stockdiary:dashboard'))
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# DiaryGraphView
# ---------------------------------------------------------------------------

class TestDiaryGraphView:
    """パフォーマンスグラフページの基本動作テスト。"""

    def test_returns_200_for_authenticated_user(self, authed_client):
        resp = authed_client.get(reverse('stockdiary:diary_graph'))
        assert resp.status_code == 200

    def test_requires_login(self, client):
        resp = client.get(reverse('stockdiary:diary_graph'))
        assert resp.status_code == 302
