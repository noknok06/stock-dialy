"""米ドル（USD）対応のテスト

取引の通貨対応（日記単位の通貨・銘柄コードからの自動判定・表示切替）を検証する。
為替変換は行わず、各日記は元通貨で表示される前提。
"""
import pytest
from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model

from stockdiary.models import StockDiary, Transaction
from stockdiary.forms import StockDiaryForm, TransactionForm
from stockdiary.utils import is_japanese_stock, detect_currency
from stockdiary.templatetags.stockdiary_filters import currency_symbol, currency_unit
from stockdiary.services.aggregate_service import AggregateService

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class TestCurrencyDetection:
    """通貨自動判定ヘルパー"""

    @pytest.mark.parametrize('code', ['7203', '9984', '262A', '1234D', '6758'])
    def test_japanese_codes(self, code):
        assert is_japanese_stock(code) is True
        assert detect_currency(code) == 'JPY'

    @pytest.mark.parametrize('code', ['AAPL', 'GOOG', 'BRK.B', 'TSLA'])
    def test_us_tickers(self, code):
        assert is_japanese_stock(code) is False
        assert detect_currency(code) == 'USD'

    def test_empty_symbol_defaults_jpy(self):
        assert is_japanese_stock('') is False
        # 空コードは日本株判定ではないため USD 扱い
        assert detect_currency('') == 'USD'


class TestStockDiaryCurrency:
    """StockDiary の通貨フィールド・表示プロパティ"""

    def setup_method(self):
        self.user = User.objects.create_user(
            username='cur_user', email='cur@example.com', password='pass12345'
        )

    def test_default_currency_is_jpy(self):
        diary = StockDiary.objects.create(
            user=self.user, stock_symbol='7203', stock_name='トヨタ自動車'
        )
        assert diary.currency == 'JPY'
        assert diary.currency_symbol == '¥'
        assert diary.currency_unit == '円'

    def test_usd_currency_display(self):
        diary = StockDiary.objects.create(
            user=self.user, stock_symbol='AAPL', stock_name='Apple', currency='USD'
        )
        assert diary.currency_symbol == '$'
        assert diary.currency_unit == 'ドル'


class TestCurrencyTemplateFilters:
    """テンプレートフィルタ"""

    def setup_method(self):
        self.user = User.objects.create_user(
            username='filt_user', email='filt@example.com', password='pass12345'
        )

    def test_filters_with_diary(self):
        jpy = StockDiary.objects.create(
            user=self.user, stock_symbol='7203', stock_name='トヨタ', currency='JPY'
        )
        usd = StockDiary.objects.create(
            user=self.user, stock_symbol='AAPL', stock_name='Apple', currency='USD'
        )
        assert currency_symbol(jpy) == '¥'
        assert currency_unit(jpy) == '円'
        assert currency_symbol(usd) == '$'
        assert currency_unit(usd) == 'ドル'

    def test_filters_with_code_string(self):
        assert currency_symbol('USD') == '$'
        assert currency_unit('JPY') == '円'

    def test_filters_with_none(self):
        # None は安全に円扱い
        assert currency_symbol(None) == '¥'
        assert currency_unit(None) == '円'


class TestStockDiaryFormAutoDetect:
    """フォーム作成時の通貨自動判定"""

    def setup_method(self):
        self.user = User.objects.create_user(
            username='form_user', email='form@example.com', password='pass12345'
        )

    def _build(self, symbol):
        form = StockDiaryForm(
            data={
                'stock_symbol': symbol,
                'stock_name': 'テスト銘柄',
                'reason': '',
                'memo': '',
                'sector': '',
                'currency': 'JPY',  # デフォルト送信値（作成時は自動判定が優先される）
            },
            user=self.user,
        )
        assert form.is_valid(), form.errors
        diary = form.save(commit=False)
        diary.user = self.user
        diary.save()
        form.save_m2m()
        return diary

    def test_create_us_stock_detects_usd(self):
        diary = self._build('AAPL')
        assert diary.currency == 'USD'

    def test_create_jp_stock_detects_jpy(self):
        diary = self._build('7203')
        assert diary.currency == 'JPY'

    def test_edit_respects_manual_currency(self):
        # 作成（USD）
        diary = self._build('AAPL')
        assert diary.currency == 'USD'
        # 編集で JPY に手動上書き
        form = StockDiaryForm(
            data={
                'stock_symbol': 'AAPL',
                'stock_name': 'Apple',
                'reason': '',
                'memo': '',
                'sector': '',
                'currency': 'JPY',
            },
            instance=diary,
            user=self.user,
        )
        assert form.is_valid(), form.errors
        updated = form.save()
        assert updated.currency == 'JPY'


class TestTransactionFormLabel:
    """取引フォームの単価ラベルが通貨で切り替わる"""

    def setup_method(self):
        self.user = User.objects.create_user(
            username='txf_user', email='txf@example.com', password='pass12345'
        )

    def test_label_jpy(self):
        diary = StockDiary.objects.create(
            user=self.user, stock_symbol='7203', stock_name='トヨタ', currency='JPY'
        )
        form = TransactionForm(diary=diary)
        assert form.fields['price'].label == '単価（円）'

    def test_label_usd(self):
        diary = StockDiary.objects.create(
            user=self.user, stock_symbol='AAPL', stock_name='Apple', currency='USD'
        )
        form = TransactionForm(diary=diary)
        assert form.fields['price'].label == '単価（ドル）'


class TestAggregateServiceCurrencyAgnostic:
    """USD 日記でも集計ロジックは通貨非依存で正しく計算される"""

    def setup_method(self):
        self.user = User.objects.create_user(
            username='agg_user', email='agg@example.com', password='pass12345'
        )

    def test_usd_buy_sell_profit(self):
        diary = StockDiary.objects.create(
            user=self.user, stock_symbol='AAPL', stock_name='Apple', currency='USD'
        )
        # 100株 @ $150 購入
        Transaction.objects.create(
            diary=diary, transaction_type='buy',
            transaction_date=date.today(), price=Decimal('150.00'),
            quantity=Decimal('100'),
        )
        # 100株 @ $180 売却
        Transaction.objects.create(
            diary=diary, transaction_type='sell',
            transaction_date=date.today(), price=Decimal('180.00'),
            quantity=Decimal('100'),
        )
        diary.refresh_from_db()
        # 実現損益 = (180-150) * 100 = 3000（ドル単位、数値ロジックは円と同一）
        assert diary.realized_profit == Decimal('3000.00')
        assert diary.current_quantity == Decimal('0.00')
        # 通貨は USD のまま保持
        assert diary.currency == 'USD'
