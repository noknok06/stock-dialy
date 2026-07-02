"""stockdiary/api.py の主要エンドポイントのテスト。

これらのエンドポイントは従来テストカバレッジがほぼなく、
バグが発生しても検知できない状態だった。
最もリスクの高い3つのエンドポイントを優先的にカバーする。
"""
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date

from stockdiary.models import StockDiary, Transaction, DiaryNote

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='api_test_user', password='pass', email='api@example.com'
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username='api_other_user', password='pass', email='other@example.com'
    )


@pytest.fixture
def diary(user):
    return StockDiary.objects.create(
        user=user,
        stock_symbol='7203',
        stock_name='トヨタ自動車',
        reason='長期保有',
    )


@pytest.fixture
def authed_client(client, user):
    client.login(username='api_test_user', password='pass')
    return client


# ---------------------------------------------------------------------------
# check_diary_duplicate
# ---------------------------------------------------------------------------

class TestCheckDiaryDuplicate:
    """同一銘柄の重複チェック API (/api/check-duplicate/)"""

    def test_returns_existing_diary_by_symbol(self, authed_client, diary):
        """既存銘柄コードを渡すと該当日記が返る。"""
        url = reverse('stockdiary:api_check_duplicate')
        resp = authed_client.get(url, {'symbol': '7203'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['exists'] is True
        assert any(d['id'] == diary.id for d in data['diaries'])

    def test_returns_existing_diary_by_name_when_no_symbol(self, authed_client, user):
        """銘柄コードが空の日記は銘柄名（完全一致・大小無視）で検索できる。

        find_duplicate_diaries は symbol が空の場合のみ name で検索するため、
        銘柄コード未設定の日記を事前に作成してテストする。
        """
        no_symbol_diary = StockDiary.objects.create(
            user=user, stock_symbol='', stock_name='銘柄コードなし株'
        )
        url = reverse('stockdiary:api_check_duplicate')
        resp = authed_client.get(url, {'name': '銘柄コードなし株'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['exists'] is True
        assert any(d['id'] == no_symbol_diary.id for d in data['diaries'])

    def test_returns_empty_for_unknown_symbol(self, authed_client):
        """存在しない銘柄は exists=False を返す。"""
        url = reverse('stockdiary:api_check_duplicate')
        resp = authed_client.get(url, {'symbol': '9999'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['exists'] is False
        assert data['diaries'] == []

    def test_does_not_return_other_users_diary(self, authed_client, other_user):
        """他ユーザーの日記は返さない（所有者分離）。"""
        other_diary = StockDiary.objects.create(
            user=other_user, stock_symbol='7203', stock_name='トヨタ自動車'
        )
        url = reverse('stockdiary:api_check_duplicate')
        resp = authed_client.get(url, {'symbol': '7203'})
        assert resp.status_code == 200
        data = resp.json()
        ids = [d['id'] for d in data['diaries']]
        assert other_diary.id not in ids

    def test_requires_login(self, client):
        """未認証は 302 リダイレクト。"""
        url = reverse('stockdiary:api_check_duplicate')
        resp = client.get(url, {'symbol': '7203'})
        assert resp.status_code == 302

    def test_retrospective_count_is_included(self, authed_client, diary):
        """振り返りノートの件数が返る（再エントリー誘導に使う）。"""
        DiaryNote.objects.create(
            diary=diary, date=date.today(),
            content='振り返り', note_type='retrospective'
        )
        url = reverse('stockdiary:api_check_duplicate')
        resp = authed_client.get(url, {'symbol': '7203'})
        data = resp.json()
        entry = next(d for d in data['diaries'] if d['id'] == diary.id)
        assert entry['retrospective_count'] == 1


# ---------------------------------------------------------------------------
# api_create_diary
# ---------------------------------------------------------------------------

class TestApiCreateDiary:
    """クイック日記作成 API (/api/create-diary/)"""

    URL = 'stockdiary:api_create'

    def test_creates_diary_with_minimum_fields(self, authed_client):
        """銘柄名のみで日記が作成できる。"""
        resp = authed_client.post(
            reverse(self.URL),
            {'stock_name': 'テスト株式'},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert StockDiary.objects.filter(stock_name='テスト株式').exists()

    def test_returns_400_when_stock_name_missing(self, authed_client):
        """銘柄名が空の場合 400 を返す。"""
        resp = authed_client.post(reverse(self.URL), {'stock_name': ''})
        assert resp.status_code == 400
        assert resp.json()['success'] is False

    def test_returns_400_when_stock_name_too_long(self, authed_client):
        """銘柄名が 100 文字超の場合 400 を返す。"""
        resp = authed_client.post(reverse(self.URL), {'stock_name': 'a' * 101})
        assert resp.status_code == 400

    def test_returns_400_when_invalid_price(self, authed_client):
        """purchase_price に数値以外を渡すと 400 を返す。"""
        resp = authed_client.post(
            reverse(self.URL),
            {'stock_name': 'テスト株式', 'purchase_price': 'abc'},
        )
        assert resp.status_code == 400

    def test_requires_login(self, client):
        """未認証は 302 リダイレクト。"""
        resp = client.post(reverse(self.URL), {'stock_name': 'テスト株式'})
        assert resp.status_code == 302

    def test_diary_belongs_to_requesting_user(self, authed_client, user):
        """作成された日記はリクエストユーザーに紐付く。"""
        authed_client.post(reverse(self.URL), {'stock_name': 'ユーザーチェック株'})
        diary = StockDiary.objects.get(stock_name='ユーザーチェック株')
        assert diary.user == user

    def test_only_post_method_allowed(self, authed_client):
        """GET は 405 を返す。"""
        resp = authed_client.get(reverse(self.URL))
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# DiaryTabContentView (XSS 関連は test_views_updated.py でカバー済み)
# ---------------------------------------------------------------------------

class TestDiaryTabContentView:
    """DiaryTabContentView の基本動作テスト。"""

    def test_notes_tab_returns_json_html(self, authed_client, diary):
        """notes タブは JSON{'html': ...} を返す。"""
        url = reverse('stockdiary:api_tab_content', args=[diary.id, 'notes'])
        resp = authed_client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert 'html' in data

    def test_details_tab_returns_json_html(self, authed_client, diary):
        """details タブも JSON を返す。"""
        url = reverse('stockdiary:api_tab_content', args=[diary.id, 'details'])
        resp = authed_client.get(url)
        assert resp.status_code == 200
        assert 'html' in resp.json()

    def test_invalid_tab_returns_400(self, authed_client, diary):
        """不正なタブ名は 400 を返す。"""
        url = reverse('stockdiary:api_tab_content', args=[diary.id, 'nonexistent'])
        resp = authed_client.get(url)
        assert resp.status_code == 400

    def test_other_users_diary_returns_404(self, authed_client, other_user):
        """他ユーザーの日記は 404 を返す（情報漏洩防止）。"""
        other_diary = StockDiary.objects.create(
            user=other_user, stock_symbol='9999', stock_name='他社株'
        )
        url = reverse('stockdiary:api_tab_content', args=[other_diary.id, 'notes'])
        resp = authed_client.get(url)
        assert resp.status_code == 404

    def test_requires_login(self, client, diary):
        """未認証は 302 リダイレクト。"""
        url = reverse('stockdiary:api_tab_content', args=[diary.id, 'notes'])
        resp = client.get(url)
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# search_suggestion — XSS 対策テスト
# ---------------------------------------------------------------------------

class TestSearchSuggestionXSS:
    """search_suggestion ビューの XSS 対策テスト。

    stock_name / stock_symbol / tag.name をエスケープせず f-string で HTML に
    埋め込んでいたため、悪意ある銘柄名でスクリプトが実行できた。
    修正後はDjangoテンプレートエンジンが自動エスケープするため安全。
    """

    def setup_method(self):
        self.user = User.objects.create_user(
            username='xss_suggest_user', password='pass', email='suggest@example.com'
        )

    def test_script_tag_in_stock_name_is_escaped(self, client):
        """<script> を含む銘柄名がエスケープされてレスポンスに含まれる。"""
        StockDiary.objects.create(
            user=self.user,
            stock_symbol='9999',
            stock_name='<script>alert("XSS")</script>',
        )
        client.login(username='xss_suggest_user', password='pass')
        url = reverse('stockdiary:search_suggestion')
        resp = client.get(url, {'query': 'script'})
        assert resp.status_code == 200
        body = resp.content.decode()
        assert '<script>' not in body
        assert '&lt;script&gt;' in body

    def test_html_in_stock_symbol_is_escaped(self, client):
        """銘柄コードに HTML が含まれても <img> タグが実行されない形にエスケープされる。"""
        StockDiary.objects.create(
            user=self.user,
            stock_symbol='"><img src=x onerror=alert(1)>',
            stock_name='テスト株',
        )
        client.login(username='xss_suggest_user', password='pass')
        url = reverse('stockdiary:search_suggestion')
        resp = client.get(url, {'query': 'テスト'})
        assert resp.status_code == 200
        body = resp.content.decode()
        # <img タグが生のまま残っていないこと（< が &lt; に変換されている）
        assert '<img' not in body
        assert '&lt;img' in body

    def test_short_query_returns_empty(self, client):
        """2文字未満のクエリは空レスポンスを返す。"""
        client.login(username='xss_suggest_user', password='pass')
        url = reverse('stockdiary:search_suggestion')
        resp = client.get(url, {'query': 'a'})
        assert resp.status_code == 200
        assert resp.content == b''

    def test_no_match_returns_empty(self, client):
        """一致なしも空レスポンス。"""
        client.login(username='xss_suggest_user', password='pass')
        url = reverse('stockdiary:search_suggestion')
        resp = client.get(url, {'query': 'zzzzzz_nomatch'})
        assert resp.status_code == 200
        assert resp.content == b''

    def test_does_not_return_other_users_stocks(self, client, other_user):
        """他ユーザーの銘柄は提案されない。"""
        StockDiary.objects.create(
            user=other_user, stock_symbol='1234', stock_name='他社の銘柄'
        )
        client.login(username='xss_suggest_user', password='pass')
        url = reverse('stockdiary:search_suggestion')
        resp = client.get(url, {'query': '他社'})
        assert resp.status_code == 200
        assert '他社の銘柄' not in resp.content.decode()
