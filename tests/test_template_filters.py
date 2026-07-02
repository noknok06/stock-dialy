"""テンプレートフィルタ（stockdiary/templatetags/stockdiary_filters.py）の単体テスト。

純粋関数中心のフィルタ群。実装の実際の出力に合わせてアサーションしている
（docstring の例と実装がずれている箇所があるため、実挙動を正とする）。
"""
import pytest
from datetime import date, timedelta

from django.utils import timezone

from stockdiary.templatetags import stockdiary_filters as f


class TestMathFilters:
    def test_add_numbers(self):
        assert f.add_filter(5, 3) == 8

    def test_add_strings_concatenate(self):
        assert f.add_filter('a', 'b') == 'ab'

    def test_add_type_error_returns_value(self):
        assert f.add_filter(5, 'x') == 5

    def test_sub(self):
        assert f.sub_filter(10, 4) == 6

    def test_sub_type_error_returns_value(self):
        assert f.sub_filter(10, 'x') == 10

    def test_mul(self):
        assert f.mul_filter(3, 4) == 12

    def test_div(self):
        assert f.div_filter(10, 2) == 5

    def test_div_by_zero_returns_zero(self):
        assert f.div_filter(10, 0) == 0

    def test_div_type_error_returns_zero(self):
        assert f.div_filter(10, 'x') == 0

    def test_multiply_floats(self):
        assert f.multiply('2.5', '4') == 10.0

    def test_multiply_invalid_returns_zero(self):
        assert f.multiply('x', 2) == 0

    def test_divideby(self):
        assert f.divideby('10', '4') == 2.5

    def test_divideby_zero_returns_zero(self):
        assert f.divideby(10, 0) == 0

    def test_divideby_invalid_returns_zero(self):
        assert f.divideby('x', 2) == 0


class TestPercentage:
    def test_percentage_of(self):
        assert f.percentage_of(1, 4) == 25

    def test_percentage_of_zero_total(self):
        assert f.percentage_of(1, 0) == 0

    def test_percentage_of_invalid(self):
        assert f.percentage_of('x', 4) == 0

    def test_percentage_display_zero(self):
        assert f.percentage_display(0) == '0%'

    def test_percentage_display_tiny(self):
        assert f.percentage_display(0.05) == '<0.1%'

    def test_percentage_display_sub_one(self):
        assert f.percentage_display(0.5) == '0.5%'

    def test_percentage_display_normal(self):
        assert f.percentage_display(42) == '42%'

    def test_percentage_display_with_total(self):
        assert f.percentage_display(1, 4) == '25%'


class TestCurrency:
    def test_symbol_from_code_usd(self):
        assert f.currency_symbol('USD') == '$'

    def test_symbol_from_code_jpy(self):
        assert f.currency_symbol('JPY') == '¥'

    def test_symbol_default_jpy(self):
        assert f.currency_symbol(None) == '¥'
        assert f.currency_symbol('XXX') == '¥'

    def test_symbol_from_dict(self):
        assert f.currency_symbol({'currency': 'USD'}) == '$'

    def test_unit_usd(self):
        assert f.currency_unit('USD') == 'ドル'

    def test_unit_jpy(self):
        assert f.currency_unit('JPY') == '円'

    def test_symbol_from_object(self):
        class Obj:
            currency = 'USD'
        assert f.currency_symbol(Obj()) == '$'


class TestMargin:
    def test_ratio_normal(self):
        assert f.margin_ratio(200, 100) == 2.0

    def test_ratio_zero_sales(self):
        assert f.margin_ratio(200, 0) == 0

    def test_ratio_none_inputs(self):
        assert f.margin_ratio(None, None) == 0

    def test_level_low(self):
        assert f.margin_level(0.5) == 'low'

    def test_level_medium(self):
        assert f.margin_level(1.5) == 'medium'

    def test_level_high(self):
        assert f.margin_level(3.0) == 'high'

    def test_level_unknown(self):
        assert f.margin_level('x') == 'unknown'

    def test_level_class(self):
        assert f.margin_level_class(0.5) == 'text-danger'
        assert f.margin_level_class(1.5) == 'text-primary'
        assert f.margin_level_class(3.0) == 'text-success'
        assert f.margin_level_class('x') == 'text-muted'

    def test_level_text(self):
        assert f.margin_level_text(0.5) == '売り優勢'
        assert f.margin_level_text(1.5) == '均衡'
        assert f.margin_level_text(3.0) == '買い優勢'
        assert f.margin_level_text('x') == '-'

    def test_ratio_color_intensity_bands(self):
        # 売り優勢（<1.0）
        assert f.ratio_color_intensity(0.0) == 1.0
        # 均衡（1.0-2.0）
        assert f.ratio_color_intensity(1.5) == 0.3
        # 買い優勢（>2.0）
        assert f.ratio_color_intensity(4.0) == 1.0
        # 異常値
        assert f.ratio_color_intensity('x') == 0.2


class TestNumberFormatting:
    def test_format_stock_amount_zero(self):
        assert f.format_stock_amount(0) == '0'

    def test_format_stock_amount_thousands(self):
        assert f.format_stock_amount(1500) == '1.5K'

    def test_format_stock_amount_millions(self):
        assert f.format_stock_amount(1234567) == '1.2M'

    def test_format_stock_amount_small(self):
        assert f.format_stock_amount(500) == '500'

    def test_format_stock_amount_invalid(self):
        assert f.format_stock_amount('x') == '0'

    def test_format_change_zero(self):
        assert f.format_change(0) == '±0'

    def test_format_change_positive(self):
        assert f.format_change(1500) == '+1.5K'

    def test_format_change_negative(self):
        assert f.format_change(-2000) == '-2.0K'

    def test_change_direction_class(self):
        assert f.change_direction_class(5) == 'positive-change'
        assert f.change_direction_class(-5) == 'negative-change'
        assert f.change_direction_class(0) == 'neutral-change'
        assert f.change_direction_class('x') == 'neutral-change'

    def test_smart_round_large(self):
        assert f.smart_round(150) == '150'

    def test_smart_round_medium(self):
        assert f.smart_round(15.55) == '15.6'

    def test_smart_round_small(self):
        assert f.smart_round(5.5) == '5.50'

    def test_smart_round_invalid(self):
        assert f.smart_round('x') == '0'

    def test_mobile_number_format_zero(self):
        assert f.mobile_number_format(0) == '0'

    def test_mobile_number_format_billion(self):
        assert f.mobile_number_format(2500000000) == '2.5B'

    def test_mobile_number_format_million(self):
        assert f.mobile_number_format(3000000) == '3.0M'

    def test_mobile_number_format_thousand(self):
        assert f.mobile_number_format(1500) == '1.5K'

    def test_mobile_number_format_small(self):
        assert f.mobile_number_format(0.25) == '0.25'

    def test_intcomma_float_integer(self):
        assert f.intcomma_float(1234567) == '1,234,567'

    def test_intcomma_float_decimals(self):
        assert f.intcomma_float(1234.5, 2) == '1,234.50'

    def test_intcomma_float_invalid(self):
        assert f.intcomma_float('x') == '0'


class TestQualitativeLevels:
    def test_confidence_level(self):
        assert f.confidence_level(0.95) == '高'
        assert f.confidence_level(0.75) == '中'
        assert f.confidence_level(0.55) == '低'
        assert f.confidence_level(0.1) == '不明'
        assert f.confidence_level('x') == '不明'

    def test_risk_level_class(self):
        assert f.risk_level_class(0.9) == 'risk-high'
        assert f.risk_level_class(0.6) == 'risk-medium'
        assert f.risk_level_class(0.3) == 'risk-low'
        assert f.risk_level_class(0.0) == 'risk-minimal'
        assert f.risk_level_class('x') == 'risk-unknown'

    def test_trend_arrow_up(self):
        html = str(f.trend_arrow(1.0))
        assert 'arrow-up' in html

    def test_trend_arrow_down(self):
        html = str(f.trend_arrow(-1.0))
        assert 'arrow-down' in html

    def test_trend_arrow_flat(self):
        html = str(f.trend_arrow(0.0))
        assert 'arrow-right' in html

    def test_trend_arrow_invalid(self):
        html = str(f.trend_arrow('x'))
        assert 'bi-dash' in html


class TestStringHelpers:
    def test_mobile_truncate_short(self):
        assert f.mobile_truncate('abc', 10) == 'abc'

    def test_mobile_truncate_long(self):
        assert f.mobile_truncate('abcdefghijklmn', 10).endswith('...')

    def test_mobile_truncate_empty(self):
        assert f.mobile_truncate('', 10) == ''

    def test_mobile_friendly_title_replacements(self):
        assert f.mobile_friendly_title('トヨタ自動車株式会社') == 'トヨタ自動車(株)'

    def test_mobile_friendly_title_hd(self):
        assert 'HD' in f.mobile_friendly_title('ソフトバンクホールディングス')

    def test_mobile_friendly_title_empty(self):
        assert f.mobile_friendly_title('') == ''

    def test_mobile_friendly_title_truncates(self):
        result = f.mobile_friendly_title('あ' * 30, max_length=15)
        assert result.endswith('…')
        assert len(result) == 15

    def test_touch_friendly_size_min(self):
        assert f.touch_friendly_size(20) == 44

    def test_touch_friendly_size_larger(self):
        assert f.touch_friendly_size(60) == 60

    def test_touch_friendly_size_invalid(self):
        assert f.touch_friendly_size('x') == 44

    def test_get_item(self):
        assert f.get_item({'a': 1}, 'a') == 1
        assert f.get_item({'a': 1}, 'b') is None

    def test_highlight_wraps_term(self):
        result = str(f.highlight('トヨタ自動車', 'トヨタ'))
        assert 'search-highlight' in result
        assert 'トヨタ' in result

    def test_highlight_no_term_returns_text(self):
        assert str(f.highlight('テキスト', '')) == 'テキスト'


class TestDaysAgo:
    def test_today(self):
        assert f.days_ago(timezone.now().date()) == '今日'

    def test_yesterday(self):
        assert f.days_ago(timezone.now().date() - timedelta(days=1)) == '昨日'

    def test_days(self):
        assert f.days_ago(timezone.now().date() - timedelta(days=3)) == '3日前'

    def test_weeks(self):
        assert f.days_ago(timezone.now().date() - timedelta(days=14)) == '2週間前'

    def test_months(self):
        assert f.days_ago(timezone.now().date() - timedelta(days=90)) == '3ヶ月前'

    def test_none(self):
        assert f.days_ago(None) == ''

    def test_string_passthrough(self):
        assert f.days_ago('2020-01-01') == '2020-01-01'


class TestMarkdown:
    def test_bold(self):
        assert '<strong>強調</strong>' in str(f.render_markdown('**強調**'))

    def test_empty(self):
        assert f.render_markdown('') == ''

    def test_xss_script_stripped(self):
        result = str(f.render_markdown('<script>alert(1)</script>本文'))
        assert '<script>' not in result
        assert '本文' in result

    def test_xss_img_stripped(self):
        result = str(f.render_markdown('![x](javascript:alert(1))'))
        assert '<img' not in result

    def test_bare_url_linkified(self):
        result = str(f.render_markdown('参照 https://example.com です'))
        assert '<a href="https://example.com"' in result

    def test_list_rendering(self):
        result = str(f.render_markdown('見出し\n- 項目1\n- 項目2'))
        assert '<li>項目1</li>' in result

    def test_table_rendering(self):
        md = 'A | B\n--- | ---\n1 | 2'
        result = str(f.render_markdown(md))
        assert '<table>' in result

    def test_mentions_linkified(self):
        result = str(f.render_markdown_with_mentions(
            'トヨタ(7203)に注目', {'7203': 42}
        ))
        assert '/stockdiary/42/' in result

    def test_mentions_unknown_code_not_linked(self):
        result = str(f.render_markdown_with_mentions(
            '謎銘柄(9999)', {'7203': 42}
        ))
        assert '/stockdiary/' not in result

    def test_mentions_empty(self):
        assert f.render_markdown_with_mentions('', {'7203': 1}) == ''


def test_markdown_tables_have_mobile_min_width_css():
    """長文ノートの Markdown 表がモバイルで「項目名が1文字ずつ縦折れ」する崩れを
    防ぐCSS（セルの min-width）が components.css に存在することを固定する回帰。
    決算分析など、項目×内容の縦長テーブルの可読性を守るため。"""
    from pathlib import Path
    from django.conf import settings
    css = Path(settings.BASE_DIR) / 'static' / 'css' / '3-components' / 'components.css'
    text = css.read_text(encoding='utf-8')
    # markdown 表のセルに最低幅が設定されている
    assert 'min-width: 6.5em;' in text
    # 表本体は横スクロール可能（潰さず溢れさせる）
    assert '.markdown-content table' in text and 'overflow-x: auto;' in text


class TestCompanyShort:
    """company_short: 表示用に会社種別表記（株式会社等）を除く（マスタ値は不変）。

    決算一覧で可視文字数が限られ「株式会社」で社名本体が読めない問題への対処。
    """

    def test_strips_leading_kabushiki(self):
        assert f.company_short('株式会社アルバイトタイムス') == 'アルバイトタイムス'

    def test_strips_trailing_kabushiki(self):
        assert f.company_short('オーエスジー株式会社') == 'オーエスジー'

    def test_strips_abbreviations(self):
        assert f.company_short('（株）フライヤー') == 'フライヤー'
        assert f.company_short('㈱コックス') == 'コックス'

    def test_keeps_when_only_designation(self):
        # 種別表記のみなら空にせず元を返す
        assert f.company_short('株式会社') == '株式会社'

    def test_noop_without_designation(self):
        assert f.company_short('トヨタ自動車') == 'トヨタ自動車'

    def test_empty(self):
        assert f.company_short('') == ''
