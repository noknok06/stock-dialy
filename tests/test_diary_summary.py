"""銘柄サマリー（diary_summary、旧 stock_list 統合後）のテスト"""
import pytest

from django.urls import reverse

from stockdiary.models import StockDiary

pytestmark = pytest.mark.django_db(transaction=True)


class TestDiarySummaryView:

    def test_page_renders(self, authenticated_client, sample_diary):
        response = authenticated_client.get(reverse('stockdiary:diary_summary'))
        assert response.status_code == 200
        html = response.content.decode()
        assert 'トヨタ自動車' in html
        assert '7203' in html

    def test_sector_shown_and_filterable(self, authenticated_client, user, sample_diary):
        StockDiary.objects.create(
            user=user, stock_symbol='8306', stock_name='三菱UFJ', sector='銀行業',
        )
        response = authenticated_client.get(reverse('stockdiary:diary_summary'))
        summary = {s['symbol']: s for s in response.context['summary_list']}
        assert summary['7203']['sector'] == '輸送用機器'
        assert '銀行業' in response.context['sectors']

        # 業種フィルター
        response = authenticated_client.get(
            reverse('stockdiary:diary_summary'), {'sector': '銀行業'}
        )
        symbols = [s['symbol'] for s in response.context['summary_list']]
        assert symbols == ['8306']

    def test_holding_status_flag(self, authenticated_client, sample_diary_with_transaction, sample_sold_diary):
        response = authenticated_client.get(reverse('stockdiary:diary_summary'))
        summary = {s['symbol']: s for s in response.context['summary_list']}
        assert summary['7203']['is_holding'] is True   # 買い取引あり・保有中
        assert summary['9984']['is_holding'] is False  # 売却完結済み

    def test_search_matches_sector(self, authenticated_client, sample_diary):
        response = authenticated_client.get(
            reverse('stockdiary:diary_summary'), {'q': '輸送用'}
        )
        assert len(response.context['summary_list']) == 1

    def test_old_stock_list_url_redirects(self, authenticated_client):
        response = authenticated_client.get(reverse('stockdiary:stock_list'))
        assert response.status_code == 302
        assert response.url == reverse('stockdiary:diary_summary')

    def test_other_user_not_included(self, authenticated_client, another_user):
        StockDiary.objects.create(
            user=another_user, stock_symbol='9999', stock_name='他人の銘柄',
        )
        response = authenticated_client.get(reverse('stockdiary:diary_summary'))
        symbols = [s['symbol'] for s in response.context['summary_list']]
        assert '9999' not in symbols
