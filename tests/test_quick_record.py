"""統一玄関（クイック記録）統合のテスト。

docs/diary_recording_redesign.md 段階9b:
- 通貨はコードから自動判定（数字始まり=日本株→JPY／他→USD）
- 既存日記サジェスト(search_my_diaries)はテーマ(topics)も返す
- 既存への追記は quick_add_note にテーマつきで保存できる
- クイック記録シートに追記/テンプレートUIが描画される
"""
import datetime

import pytest
from django.urls import reverse

from stockdiary.models import StockDiary, DiaryNote


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
