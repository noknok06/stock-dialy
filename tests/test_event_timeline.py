"""日記詳細の時系列タブ・振り返りサマリー・取引メモ検索のテスト"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse

from stockdiary.models import StockDiary, DiaryNote, Transaction
from stockdiary.utils import apply_diary_search

pytestmark = pytest.mark.django_db(transaction=True)


class TestTransactionAmount:

    def test_amount_property(self, sample_diary):
        tx = Transaction.objects.create(
            diary=sample_diary, transaction_type='buy',
            transaction_date=date.today(),
            price=Decimal('1500.50'), quantity=Decimal('100'),
        )
        assert tx.amount == Decimal('150050.00')


class TestEventTimeline:
    """時系列タブ（取引・分割・継続記録の統合）"""

    def test_timeline_merges_notes_and_transactions(self, authenticated_client, sample_diary_with_transaction):
        DiaryNote.objects.create(
            diary=sample_diary_with_transaction,
            date=date.today() - timedelta(days=1),
            content='決算前に買い増し検討',
        )
        response = authenticated_client.get(
            reverse('stockdiary:detail', kwargs={'pk': sample_diary_with_transaction.pk})
        )
        timeline = response.context['event_timeline']
        kinds = [e['type'] for e in timeline]
        assert 'transaction' in kinds
        assert 'note' in kinds
        # 日付降順
        dates = [e['date'] for e in timeline]
        assert dates == sorted(dates, reverse=True)

    def test_timeline_tab_rendered(self, authenticated_client, sample_diary):
        response = authenticated_client.get(
            reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk})
        )
        html = response.content.decode()
        assert 'id="events-tab"' in html
        assert '時系列' in html


class TestRetroSummary:
    """振り返りシートの取引サマリー差し込み"""

    def test_summary_for_sold_diary(self, authenticated_client, sample_sold_diary):
        response = authenticated_client.get(
            reverse('stockdiary:detail', kwargs={'pk': sample_sold_diary.pk})
        )
        summary = response.context['retro_summary']
        # fixture: 10日前に5000円×50株買い → 5日前に5500円×50株売り
        assert summary['first_buy'] == date.today() - timedelta(days=10)
        assert summary['last_sell'] == date.today() - timedelta(days=5)
        assert summary['holding_days'] == 5
        assert summary['avg_buy'] == Decimal('5000')
        assert summary['avg_sell'] == Decimal('5500')
        assert 'id="retroSummary"' in response.content.decode()

    def test_no_summary_for_holding_diary(self, authenticated_client, sample_diary_with_transaction):
        response = authenticated_client.get(
            reverse('stockdiary:detail', kwargs={'pk': sample_diary_with_transaction.pk})
        )
        assert 'retro_summary' not in response.context


class TestTransactionMemoSearch:
    """取引メモの全文検索"""

    def test_diary_found_by_transaction_memo(self, user, sample_diary):
        Transaction.objects.create(
            diary=sample_diary, transaction_type='buy',
            transaction_date=date.today(),
            price=Decimal('2000'), quantity=Decimal('100'),
            memo='決算またぎ回避のため一部利確',
        )
        qs = StockDiary.objects.filter(user=user)
        result = apply_diary_search(qs, '決算またぎ')
        assert list(result) == [sample_diary]

    def test_other_users_transaction_memo_not_leaked(self, user, another_user):
        other_diary = StockDiary.objects.create(
            user=another_user, stock_symbol='9984', stock_name='ソフトバンクグループ',
        )
        Transaction.objects.create(
            diary=other_diary, transaction_type='buy',
            transaction_date=date.today(),
            price=Decimal('5000'), quantity=Decimal('10'),
            memo='秘密のメモ',
        )
        qs = StockDiary.objects.filter(user=user)
        assert list(apply_diary_search(qs, '秘密のメモ')) == []
