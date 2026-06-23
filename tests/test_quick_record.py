"""統一玄関（クイック記録）統合のテスト。

docs/diary_recording_redesign.md 段階9b:
- 通貨はコードから自動判定（数字始まり=日本株→JPY／他→USD）
- 既存日記サジェスト(search_my_diaries)はテーマ(topics)も返す
- 既存への追記は quick_add_note にテーマつきで保存できる
- クイック記録シートに追記/テンプレートUIが描画される
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from stockdiary.models import StockDiary, DiaryNote, Transaction


@pytest.mark.django_db
class TestQuickCreateCurrency:
    def test_japanese_code_is_jpy(self, authenticated_client):
        resp = authenticated_client.post(reverse('stockdiary:quick_create'), {
            'stock_name': '7203 トヨタ自動車',
            'reason': 'テスト',
        })
        assert resp.status_code == 200
        d = StockDiary.objects.filter(stock_symbol='7203').latest('id')
        assert d.currency == 'JPY'

    def test_us_code_is_usd(self, authenticated_client):
        resp = authenticated_client.post(reverse('stockdiary:quick_create'), {
            'stock_name': 'AAPL Apple',
            'reason': 'テスト',
        })
        assert resp.status_code == 200
        d = StockDiary.objects.filter(stock_symbol='AAPL').latest('id')
        assert d.currency == 'USD'


@pytest.mark.django_db
class TestSearchMyDiariesTopics:
    def test_returns_topics(self, authenticated_client, sample_diary):
        DiaryNote.objects.create(diary=sample_diary, date=datetime.date.today(),
                                 content='ナフサ高の影響', topic='ナフサ')
        url = reverse('stockdiary:api_search_my_diaries')
        resp = authenticated_client.get(url, {'q': 'トヨタ'})
        data = resp.json()
        hit = next((x for x in data['diaries'] if x['id'] == sample_diary.id), None)
        assert hit is not None
        assert 'ナフサ' in hit['topics']


@pytest.mark.django_db
class TestQuickAppendWithTopic:
    def test_append_saves_topic(self, authenticated_client, sample_diary):
        url = reverse('stockdiary:quick_add_note', kwargs={'diary_id': sample_diary.pk})
        resp = authenticated_client.post(url, {
            'content': '決算は増益。テーマつきで追記。',
            'topic': '決算',
            'note_type': 'analysis',
        })
        assert resp.status_code == 200
        note = DiaryNote.objects.filter(diary=sample_diary, topic='決算').first()
        assert note is not None
        assert note.content.startswith('決算は増益')


@pytest.mark.django_db
class TestQuickRecordSheetRendered:
    def test_sheet_has_append_and_template_ui(self, authenticated_client, sample_diary):
        resp = authenticated_client.get(reverse('stockdiary:home'))
        assert resp.status_code == 200
        html = resp.content.decode()
        assert 'qrMyDiaries' in html       # 既存日記サジェスト（追記候補）
        assert 'qrAppendBanner' in html     # 追記モードのバナー
        assert 'qrTopicSection' in html     # テーマ選択
        assert 'qrTemplate' in html         # テンプレート選択

    def test_hashtag_autocomplete_wired(self, authenticated_client, sample_diary):
        # クイック記録の本文(textarea)で @タグ サジェストが使えるよう配線されている
        resp = authenticated_client.get(reverse('stockdiary:home'))
        html = resp.content.decode()
        assert 'hashtag-autocomplete.js' in html   # スクリプト読み込み
        assert 'data-hashtags-url' in html          # API URL を form に保持


@pytest.mark.django_db
class TestDiaryMentionAutocompleteWired:
    """[[ 日記メンションのサジェストが reason/ノート/クイック記録に配線されている。"""

    def test_quick_record_has_diary_mention(self, authenticated_client, sample_diary):
        html = authenticated_client.get(reverse('stockdiary:home')).content.decode()
        assert 'DiaryMentionAutocomplete' in html

    def test_detail_note_has_diary_mention(self, authenticated_client, sample_diary):
        html = authenticated_client.get(
            reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk})
        ).content.decode()
        assert 'DiaryMentionAutocomplete' in html

    def test_create_form_has_diary_mention(self, authenticated_client):
        html = authenticated_client.get(reverse('stockdiary:create')).content.decode()
        assert 'DiaryMentionAutocomplete' in html


@pytest.mark.django_db
class TestQuickAddTransactionMargin:
    """クイック取引の信用種別バグの回帰テスト。

    なぜこのバグが起きたか:
    quick_add_transaction は 'buy_margin'/'sell_margin' をバリデーションで受理しつつ、
    その文字列を Transaction.transaction_type にそのまま保存していた。しかし
    transaction_type の選択肢は 'buy'/'sell' のみで、信用フラグは別フィールド
    is_margin が持つ。結果、モデルの選択肢に無い不正値が is_margin も立たないまま
    永続化され、表示・集計が壊れる余地があった。種別を正規化し is_margin に
    マッピングする挙動を固定する。
    """

    def _post(self, client, diary, ttype):
        url = reverse('stockdiary:quick_add_transaction', kwargs={'diary_id': diary.pk})
        return client.post(url, {
            'transaction_type': ttype,
            'price': '1000',
            'quantity': '100',
            'transaction_date': datetime.date.today().strftime('%Y-%m-%d'),
        })

    def test_buy_margin_normalizes_to_buy_with_is_margin(self, authenticated_client, sample_diary):
        resp = self._post(authenticated_client, sample_diary, 'buy_margin')
        assert resp.status_code == 200
        tx = Transaction.objects.filter(diary=sample_diary).latest('id')
        assert tx.transaction_type == 'buy'   # 不正値 'buy_margin' を保存しない
        assert tx.is_margin is True
        assert tx.quantity == Decimal('100')

    def test_sell_margin_normalizes_to_sell_with_is_margin(self, authenticated_client, sample_diary):
        resp = self._post(authenticated_client, sample_diary, 'sell_margin')
        assert resp.status_code == 200
        tx = Transaction.objects.filter(diary=sample_diary).latest('id')
        assert tx.transaction_type == 'sell'
        assert tx.is_margin is True

    def test_plain_buy_stays_cash(self, authenticated_client, sample_diary):
        resp = self._post(authenticated_client, sample_diary, 'buy')
        assert resp.status_code == 200
        tx = Transaction.objects.filter(diary=sample_diary).latest('id')
        assert tx.transaction_type == 'buy'
        assert tx.is_margin is False


@pytest.mark.django_db
class TestHomeHorizontalPanLocked:
    """スマホでトップ画面の何もない部分を左右ドラッグするとページ全体が横へ動く
    挙動を抑止する（横方向パンの固定）。CSSが誤って外れていないことを回帰で守る。
    カードの左右スワイプは .diary-header 内の transform で別処理のため影響しない。"""

    def test_home_locks_horizontal_overflow_on_mobile(self, authenticated_client):
        html = authenticated_client.get(reverse('stockdiary:home')).content.decode()
        # モバイル用メディアクエリ内で html, body の横オーバーフローをクリップしている
        assert 'overflow-x: clip;' in html
        assert 'overscroll-behavior-x: none;' in html
