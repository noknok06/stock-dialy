"""振り返りの固定スレッド化・プリフィル・複数ラウンド対応のテスト"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse

from stockdiary.models import StockDiary, DiaryNote, Transaction
from stockdiary.services.recall_service import RecallService

pytestmark = pytest.mark.django_db(transaction=True)


class TestRetrospectiveTopicAutoSet:
    """topic 自動セット（モデル層・全保存経路）"""

    def test_empty_topic_auto_set(self, sample_sold_diary):
        note = DiaryNote.objects.create(
            diary=sample_sold_diary, date=date.today(),
            content='振り返り本文', note_type='retrospective',
        )
        assert note.topic == DiaryNote.RETROSPECTIVE_TOPIC

    def test_explicit_topic_preserved(self, sample_sold_diary):
        note = DiaryNote.objects.create(
            diary=sample_sold_diary, date=date.today(),
            content='2026年前半ラウンドの総括', note_type='retrospective',
            topic='2026前半',
        )
        assert note.topic == '2026前半'

    def test_non_retrospective_topic_stays_empty(self, sample_diary):
        note = DiaryNote.objects.create(
            diary=sample_diary, date=date.today(),
            content='通常の分析', note_type='analysis',
        )
        assert note.topic == ''

    def test_add_note_view_auto_sets_topic(self, authenticated_client, sample_sold_diary):
        response = authenticated_client.post(
            reverse('stockdiary:add_note', kwargs={'pk': sample_sold_diary.pk}),
            {
                'date': date.today().isoformat(),
                'note_type': 'retrospective',
                'importance': 'medium',
                'topic': '',
                'content': 'フォーム経由の振り返り',
            },
        )
        assert response.status_code in (200, 302)
        note = DiaryNote.objects.get(diary=sample_sold_diary)
        assert note.topic == DiaryNote.RETROSPECTIVE_TOPIC

    def test_quick_add_note_auto_sets_topic(self, authenticated_client, sample_sold_diary):
        response = authenticated_client.post(
            reverse('stockdiary:quick_add_note', kwargs={'diary_id': sample_sold_diary.pk}),
            {'content': 'クイック経由の振り返り', 'note_type': 'retrospective'},
        )
        assert response.status_code == 200
        note = DiaryNote.objects.get(diary=sample_sold_diary)
        assert note.topic == DiaryNote.RETROSPECTIVE_TOPIC


class TestRetrospectiveThreadPinned:
    """テーマ別ビューで「振り返り」スレッドが先頭固定"""

    def test_retrospective_thread_first_unclassified_last(self, authenticated_client, sample_sold_diary):
        DiaryNote.objects.create(
            diary=sample_sold_diary, date=date.today() - timedelta(days=3),
            content='ナフサ価格の影響メモ', topic='ナフサの影響',
        )
        DiaryNote.objects.create(
            diary=sample_sold_diary, date=date.today() - timedelta(days=2),
            content='未分類のメモ',
        )
        DiaryNote.objects.create(
            diary=sample_sold_diary, date=date.today(),
            content='総括', note_type='retrospective',
        )
        response = authenticated_client.get(
            reverse('stockdiary:detail', kwargs={'pk': sample_sold_diary.pk})
        )
        topics = list(response.context['notes_by_topic'])
        assert topics[0] == DiaryNote.RETROSPECTIVE_TOPIC
        assert topics[-1] == ''

    def test_detail_page_works_without_retrospective(self, authenticated_client, sample_diary):
        """振り返りノートのない日記で move_to_end が KeyError にならない"""
        DiaryNote.objects.create(diary=sample_diary, date=date.today(), content='通常メモ')
        response = authenticated_client.get(
            reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk})
        )
        assert response.status_code == 200


class TestRetroPrefill:
    """振り返りシートへの取引サマリープリフィル"""

    def test_prefill_contains_summary_and_headings(self, authenticated_client, sample_sold_diary):
        response = authenticated_client.get(
            reverse('stockdiary:detail', kwargs={'pk': sample_sold_diary.pk})
        )
        prefill = response.context['retro_prefill']
        assert '## この投資の記録（通算）' in prefill
        assert '期間:' in prefill
        assert '平均買値' in prefill
        assert '実現損益:' in prefill
        assert '## 結果と要因' in prefill
        assert '## 次に活かす教訓' in prefill
        # None の文字列化が混入していない
        assert 'None' not in prefill


class TestMultiRoundRetrospective:
    """複数売買ラウンドでの振り返り再促進"""

    def _resell(self, diary, sell_date):
        """再買い→再売却で2ラウンド目を作る"""
        Transaction.objects.create(
            diary=diary, transaction_type='buy',
            transaction_date=sell_date - timedelta(days=5),
            price=Decimal('6000'), quantity=Decimal('10'),
        )
        Transaction.objects.create(
            diary=diary, transaction_type='sell',
            transaction_date=sell_date,
            price=Decimal('6500'), quantity=Decimal('10'),
        )
        diary.refresh_from_db()

    def test_banner_reappears_after_second_round(self, authenticated_client, sample_sold_diary):
        url = reverse('stockdiary:detail', kwargs={'pk': sample_sold_diary.pk})

        # 1ラウンド目の振り返りを記入（売り=5日前 < ノート=4日前）
        DiaryNote.objects.create(
            diary=sample_sold_diary, date=date.today() - timedelta(days=4),
            content='1回目の総括', note_type='retrospective',
        )
        assert authenticated_client.get(url).context['needs_retrospective'] is False

        # 2ラウンド目（再買い→今日売却）→ 既存ノートより新しい売りなので再び促す
        self._resell(sample_sold_diary, date.today())
        assert authenticated_client.get(url).context['needs_retrospective'] is True

    def test_recall_unreviewed_reappears_after_second_round(self, user, sample_sold_diary):
        DiaryNote.objects.create(
            diary=sample_sold_diary, date=date.today() - timedelta(days=4),
            content='1回目の総括', note_type='retrospective',
        )
        recall = RecallService.build(user)
        assert sample_sold_diary not in recall['unreviewed']

        self._resell(sample_sold_diary, date.today())
        recall = RecallService.build(user)
        assert sample_sold_diary in recall['unreviewed']


class TestRecallConnections:
    """登録した振り返りが想起面へ正しく接続される"""

    def test_anniversary_shows_content_snippet(self, user, sample_sold_diary):
        """1年前の振り返りは固定topicでなく本文がスニペットに出る"""
        DiaryNote.objects.create(
            diary=sample_sold_diary, date=date.today() - timedelta(days=365),
            content='高値掴みだった。次はエントリー根拠を数値で残す',
            note_type='retrospective',
        )
        recall = RecallService.build(user)
        snippets = [i['snippet'] for i in recall['anniversary']]
        assert any('高値掴み' in s for s in snippets)
        assert DiaryNote.RETROSPECTIVE_TOPIC not in snippets

    def test_duplicate_check_returns_retrospective_count(self, authenticated_client, sample_sold_diary):
        """再エントリー時の重複チェックが過去の振り返り件数を返す"""
        DiaryNote.objects.create(
            diary=sample_sold_diary, date=date.today(),
            content='総括', note_type='retrospective',
        )
        response = authenticated_client.get(
            reverse('stockdiary:api_check_duplicate'), {'symbol': '9984'}
        )
        data = response.json()
        assert data['exists'] is True
        assert data['diaries'][0]['retrospective_count'] == 1
