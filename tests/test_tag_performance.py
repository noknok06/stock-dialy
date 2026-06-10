"""トレーディングダッシュボードのタグ別成績のテスト"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse

from stockdiary.models import StockDiary, Transaction
from tags.models import Tag

pytestmark = pytest.mark.django_db(transaction=True)


def _sold_diary(user, symbol, name, buy_price, sell_price, tag=None):
    """買い→売り完結の日記を作成"""
    diary = StockDiary.objects.create(user=user, stock_symbol=symbol, stock_name=name)
    Transaction.objects.create(
        diary=diary, transaction_type='buy',
        transaction_date=date.today() - timedelta(days=10),
        price=Decimal(buy_price), quantity=Decimal('100'),
    )
    Transaction.objects.create(
        diary=diary, transaction_type='sell',
        transaction_date=date.today() - timedelta(days=5),
        price=Decimal(sell_price), quantity=Decimal('100'),
    )
    if tag:
        diary.tags.add(tag)
    diary.refresh_from_db()
    return diary


class TestTagPerformance:

    def test_tag_analysis_in_context(self, authenticated_client, user):
        tag = Tag.objects.create(user=user, name='地政学リスク', axis='risk')
        _sold_diary(user, '1605', 'INPEX', '2000', '2200', tag=tag)   # 勝ち
        _sold_diary(user, '7011', '三菱重工', '1000', '900', tag=tag)  # 負け

        response = authenticated_client.get(reverse('stockdiary:dashboard'))
        assert response.status_code == 200
        tag_analysis = response.context['tag_analysis']
        assert len(tag_analysis) == 1
        row = tag_analysis[0]
        assert row['name'] == '地政学リスク'
        assert row['axis_label'] == 'リスク'
        assert row['diary_count'] == 2
        assert row['sold_count'] == 2
        assert row['win_count'] == 1
        assert row['win_rate'] == 50.0
        # 実現損益: +20000 - 10000 = +10000
        assert row['realized_profit'] == 10000

    def test_diary_with_multiple_tags_counted_in_each(self, authenticated_client, user):
        t1 = Tag.objects.create(user=user, name='高配当', axis='capital_policy')
        t2 = Tag.objects.create(user=user, name='円安メリット', axis='macro')
        diary = _sold_diary(user, '7203', 'トヨタ自動車', '2000', '2100', tag=t1)
        diary.tags.add(t2)

        response = authenticated_client.get(reverse('stockdiary:dashboard'))
        names = {row['name'] for row in response.context['tag_analysis']}
        assert names == {'高配当', '円安メリット'}

    def test_untagged_diaries_produce_empty_analysis(self, authenticated_client, user):
        _sold_diary(user, '9984', 'ソフトバンクグループ', '5000', '5500')
        response = authenticated_client.get(reverse('stockdiary:dashboard'))
        assert response.context['tag_analysis'] == []
        html = response.content.decode()
        assert 'タグ別成績' in html
        assert 'タグ付きの取引データがありません' in html

    def test_win_rate_none_for_holding_only(self, authenticated_client, user):
        tag = Tag.objects.create(user=user, name='成長株', axis='theme')
        diary = StockDiary.objects.create(user=user, stock_symbol='4063', stock_name='信越化学')
        Transaction.objects.create(
            diary=diary, transaction_type='buy',
            transaction_date=date.today() - timedelta(days=3),
            price=Decimal('5000'), quantity=Decimal('100'),
        )
        diary.tags.add(tag)

        response = authenticated_client.get(reverse('stockdiary:dashboard'))
        row = response.context['tag_analysis'][0]
        assert row['win_rate'] is None
        assert row['sold_count'] == 0

    def test_transaction_ranking_removed(self, authenticated_client, user):
        _sold_diary(user, '7203', 'トヨタ自動車', '2000', '2100')
        response = authenticated_client.get(reverse('stockdiary:dashboard'))
        assert 'transaction_ranking' not in response.context
        assert '取引回数ランキング' not in response.content.decode()
