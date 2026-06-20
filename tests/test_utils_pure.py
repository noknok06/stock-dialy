"""stockdiary/utils.py の純粋ヘルパー関数の単体テスト（DB非依存）。

既存テストでカバーされていない抽出・検索・抜粋系の純粋関数を対象にする。
find_backlinks など DB を使う関数は test_backlinks.py 等で別途カバー済み。
"""
from stockdiary import utils as u


class TestExtractHashtags:
    def test_basic(self):
        assert u.extract_hashtags('投資理由 @成長株 @配当') == ['成長株', '配当']

    def test_dedup_preserves_order(self):
        assert u.extract_hashtags('@a @b @a') == ['a', 'b']

    def test_ampersand_supported(self):
        assert u.extract_hashtags('注目の @M&A 案件') == ['M&A']

    def test_empty(self):
        assert u.extract_hashtags('') == []
        assert u.extract_hashtags(None) == []

    def test_markdown_heading_not_captured(self):
        # # 見出しは @ ではないのでハッシュタグにならない
        assert u.extract_hashtags('# 見出し\n@成長株') == ['成長株']

    def test_arrow_excluded_from_plain_name(self):
        # @円安↑ は無方向の '円安' として拾う（矢印で名前を割らない）
        assert u.extract_hashtags('輸出 @円安↑ @金利上昇↓') == ['円安', '金利上昇']


class TestExtractHashtagsWithDirection:
    def test_arrows_map_to_direction(self):
        assert u.extract_hashtags_with_direction('@円安↑ @金利上昇↓ @ディフェンシブ→') == [
            ('円安', 'up'), ('金利上昇', 'down'), ('ディフェンシブ', 'neutral'),
        ]

    def test_no_arrow_is_none(self):
        # 矢印なしは direction=None（呼び出し側で手動方向を温存できる）
        assert u.extract_hashtags_with_direction('@AI のみ') == [('AI', None)]

    def test_ampersand_with_arrow(self):
        assert u.extract_hashtags_with_direction('@M&A成長↑') == [('M&A成長', 'up')]

    def test_dedup_first_wins(self):
        # 同一タグが複数回出たら最初の出現（矢印）を採用
        assert u.extract_hashtags_with_direction('@円安↑ … @円安↓') == [('円安', 'up')]

    def test_empty(self):
        assert u.extract_hashtags_with_direction('') == []
        assert u.extract_hashtags_with_direction(None) == []


class TestStockCodeDetection:
    def test_is_japanese_4digit(self):
        assert u.is_japanese_stock('7203') is True

    def test_is_japanese_new_format(self):
        assert u.is_japanese_stock('285A') is True

    def test_is_japanese_us_ticker_false(self):
        assert u.is_japanese_stock('AAPL') is False

    def test_is_japanese_empty(self):
        assert u.is_japanese_stock('') is False

    def test_detect_currency_jpy(self):
        assert u.detect_currency('7203') == 'JPY'

    def test_detect_currency_usd(self):
        assert u.detect_currency('AAPL') == 'USD'


class TestSplitSearchTerms:
    def test_halfwidth_space(self):
        assert u.split_search_terms('トヨタ 半導体') == ['トヨタ', '半導体']

    def test_fullwidth_space(self):
        assert u.split_search_terms('トヨタ　半導体　EV') == ['トヨタ', '半導体', 'EV']

    def test_empty(self):
        assert u.split_search_terms('') == []
        assert u.split_search_terms('   ') == []
        assert u.split_search_terms(None) == []


class TestExtractStockMentions:
    def test_japanese_old_and_new(self):
        assert u.extract_stock_mentions('日本郵船(9101) / キオクシア(285A)') == ['9101', '285A']

    def test_fullwidth_parens(self):
        assert u.extract_stock_mentions('トヨタ（7203）') == ['7203']

    def test_us_ticker(self):
        assert u.extract_stock_mentions('Apple(AAPL)') == ['AAPL']

    def test_dedup(self):
        assert u.extract_stock_mentions('(7203)と(7203)') == ['7203']

    def test_empty(self):
        assert u.extract_stock_mentions('') == []

    def test_no_match(self):
        assert u.extract_stock_mentions('括弧なしのテキスト') == []


class TestMentionExcerpt:
    def test_surrounds_code(self):
        result = u.mention_excerpt('前段の文章(7203)後段の文章', '7203', radius=5)
        assert '(7203)' in result

    def test_truncation_markers(self):
        text = 'あ' * 30 + '(7203)' + 'い' * 30
        result = u.mention_excerpt(text, '7203', radius=5)
        assert result.startswith('…')
        assert result.endswith('…')

    def test_no_match_returns_empty(self):
        assert u.mention_excerpt('テキスト', '9999') == ''

    def test_empty_text(self):
        assert u.mention_excerpt('', '7203') == ''


class TestSearchSnippet:
    def test_centers_on_match(self):
        text = 'あ' * 30 + '検索語' + 'い' * 30
        result = u._make_search_snippet(text, '検索語', radius=5)
        assert '検索語' in result
        assert result.startswith('…')
        assert result.endswith('…')

    def test_no_match_returns_head(self):
        result = u._make_search_snippet('abcdefghij', 'zzz', radius=3)
        assert result == 'abcdef'

    def test_empty(self):
        assert u._make_search_snippet('', 'x') == ''
        assert u._make_search_snippet('text', '') == ''


class TestExtractSection:
    def test_extracts_named_section(self):
        text = '## 要約\n結論はこれ\n## 詳細\n細かい話'
        assert u._extract_section(text, ['要約']) == '結論はこれ'

    def test_missing_section_returns_empty(self):
        text = '## 詳細\n本文'
        assert u._extract_section(text, ['要約']) == ''


class TestExtractLead:
    def test_prefers_summary_section(self):
        text = '## 要約\n- **項目**: 重要な結論\n## 詳細\nノイズ'
        assert u.extract_lead(text) == '重要な結論'

    def test_fallback_skips_markdown_noise(self):
        text = '# 見出し\n> 引用\n本文の最初の文です'
        assert u.extract_lead(text) == '本文の最初の文です'

    def test_empty(self):
        assert u.extract_lead('') == ''

    def test_truncates_to_max_len(self):
        text = 'あ' * 300
        result = u.extract_lead(text, max_len=120)
        assert len(result) <= 121  # 120 + 末尾の「…」
        assert result.endswith('…')
