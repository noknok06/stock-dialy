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

    def test_table_view_aggregates_volume_and_outcome(
        self, authenticated_client, diary_with_notes, complex_diary_with_multiple_transactions
    ):
        """銘柄別テーブルは「向き合った量×成果」を集計する。

        record_count（日記＋ノート）と txn_count（取引回数）が
        リストでは見えない銘柄単位の累計として context に載ることを保証する。
        """
        response = authenticated_client.get(reverse('stockdiary:diary_summary'))
        table = {s['symbol']: s for s in response.context['table_list']}

        # ノート付き日記: 記録数 = 日記1 + ノート数。集計フィールドが揃っている
        notes_sym = diary_with_notes.stock_symbol
        assert notes_sym in table
        row = table[notes_sym]
        assert row['record_count'] == row['diary_count'] + row['note_count']
        assert row['record_count'] >= 1
        # 量×成果の対比に必要なキーが欠けていない
        for key in ('txn_count', 'realized_profit', 'verdict_hit', 'verdict_total'):
            assert key in row

        # 複数取引の銘柄は取引回数が積み上がる
        multi_sym = complex_diary_with_multiple_transactions.stock_symbol
        assert table[multi_sym]['txn_count'] >= 2

    def test_table_sort_by_record_count(self, authenticated_client, diary_with_notes, sample_memo_diary):
        """tsort=record_desc で記録数の多い銘柄が先頭に並ぶ（デフォルト軸）。"""
        response = authenticated_client.get(
            reverse('stockdiary:diary_summary'), {'tsort': 'record_desc'}
        )
        counts = [s['record_count'] for s in response.context['table_list']]
        assert counts == sorted(counts, reverse=True)
