# earnings_analysis/templatetags/sentiment_filters.py
from django import template
from django.utils.safestring import mark_safe
import json
import re
import logging

# 既存のloggingが未定義の場合
logger = logging.getLogger(__name__)
register = template.Library()

# ====================
# 感情分析関連フィルター
# ====================

@register.filter
def sentiment_color(score):
    """感情スコアに応じた色クラスを返す"""
    try:
        score = float(score)
        if score >= 0.6:
            return 'text-success'
        elif score >= 0.2:
            return 'text-info'
        elif score >= -0.2:
            return 'text-secondary'
        elif score >= -0.6:
            return 'text-warning'
        else:
            return 'text-danger'
    except (ValueError, TypeError):
        return 'text-secondary'

@register.filter
def sentiment_badge(sentiment_label):
    """感情ラベルに応じたバッジクラスを返す"""
    badge_map = {
        'very_positive': 'bg-success',
        'positive': 'bg-success',
        'neutral': 'bg-secondary',
        'negative': 'bg-danger',
        'very_negative': 'bg-danger'
    }
    return badge_map.get(sentiment_label, 'bg-secondary')

@register.filter
def sentiment_description(level):
    """感情レベル（数値）を説明文に変換"""
    descriptions = {
        -2: '非常にネガティブ',
        -1: 'ネガティブ',
        0: '中立',
        1: 'ポジティブ',
        2: '非常にポジティブ'
    }
    try:
        level = int(level)
        return descriptions.get(level, '不明')
    except (ValueError, TypeError):
        return '不明'

@register.simple_tag
def sentiment_meter_color(level):
    """5段階レベルに応じたメーター色を返す"""
    colors = {
        -2: '#ef4444',  # 赤
        -1: '#f59e0b',  # オレンジ
        0: '#6b7280',   # グレー
        1: '#84cc16',   # 明るい緑
        2: '#22c55e'    # 濃い緑
    }
    try:
        level = int(level)
        return colors.get(level, '#6b7280')
    except (ValueError, TypeError):
        return '#6b7280'

@register.simple_tag
def sentiment_progress_bar(positive_count, negative_count, total_count):
    """感情分析結果のプログレスバーHTML生成"""
    if total_count == 0:
        return mark_safe('<div class="progress"><div class="progress-bar bg-secondary" style="width: 100%">データなし</div></div>')
    
    positive_percent = (positive_count / total_count) * 100
    negative_percent = (negative_count / total_count) * 100
    neutral_percent = 100 - positive_percent - negative_percent
    
    html = f'''
    <div class="progress">
        <div class="progress-bar bg-success" style="width: {positive_percent:.1f}%" title="ポジティブ: {positive_count}件"></div>
        <div class="progress-bar bg-danger" style="width: {negative_percent:.1f}%" title="ネガティブ: {negative_count}件"></div>
        <div class="progress-bar bg-secondary" style="width: {neutral_percent:.1f}%" title="中立: {total_count - positive_count - negative_count}件"></div>
    </div>
    '''
    return mark_safe(html)

# ====================
# 通貨・財務データ表示フィルター
# ====================

@register.filter
def format_japanese_currency(value, show_debug=False):
    """日本円を適切な単位で表示（異常値対策強化版）"""
    try:
        value = float(value)
        abs_value = abs(value)
        
        if abs_value == 0:
            return "0円"
        
        # 異常値の段階的自動調整
        adjustment_made = False
        adjustment_factor = 1
        
        if abs_value > 1_000_000_000_000_000:  # 1000兆円以上は明らかに異常
            test_divisors = [1_000_000_000, 1_000_000, 1_000, 100, 10]
            
            for divisor in test_divisors:
                test_value = abs_value / divisor
                # 日本企業として現実的な範囲：10億円〜100兆円
                if 1_000_000_000 <= test_value <= 100_000_000_000_000:
                    value = value / divisor
                    abs_value = abs(value)
                    adjustment_made = True
                    adjustment_factor = divisor
                    break
            
            if not adjustment_made:
                value = value / 1_000_000
                abs_value = abs(value)
                adjustment_made = True
                adjustment_factor = 1_000_000
        
        # 通常の表示処理
        formatted_result = _format_currency_base(value)
        
        # 調整が行われた場合の表示
        if adjustment_made:
            if adjustment_factor >= 1_000_000_000:
                factor_text = f"{adjustment_factor // 1_000_000_000}十億分の1"
            elif adjustment_factor >= 1_000_000:
                factor_text = f"{adjustment_factor // 1_000_000}百万分の1"
            elif adjustment_factor >= 1_000:
                factor_text = f"{adjustment_factor // 1_000}千分の1"
            else:
                factor_text = f"{adjustment_factor}分の1"
            
            return f"{formatted_result} <small class='text-warning'>({factor_text}調整)</small>"
        
        # 警告が必要な場合
        if abs_value > 50_000_000_000_000:  # 50兆円を超える場合は警告
            return f"<span class='text-warning'>⚠️</span> {formatted_result} <small class='text-muted'>(要確認)</small>"
        
        return formatted_result
            
    except (ValueError, TypeError):
        return str(value)

@register.filter
def format_compact_currency(value):
    """コンパクトな通貨表示（キャッシュフロー図用）"""
    try:
        value = float(value)
        abs_value = abs(value)
        
        if abs_value == 0:
            return "0"
        
        # 異常値の簡易調整
        if abs_value > 1_000_000_000_000_000:  # 1000兆円超
            while abs_value > 100_000_000_000_000:  # 100兆円以下になるまで
                value = value / 1000
                abs_value = abs(value)
        
        sign = "-" if value < 0 else ""
        
        if abs_value >= 1_000_000_000_000:  # 1兆円以上
            return f"{sign}{abs_value / 1_000_000_000_000:.1f}兆円"
        elif abs_value >= 100_000_000:  # 1億円以上
            return f"{sign}{abs_value / 100_000_000:.1f}億円"
        elif abs_value >= 1_000_000:  # 100万円以上
            return f"{sign}{abs_value / 1_000_000:.1f}百万円"
        else:  # 100万円未満
            return f"{sign}{abs_value / 1_000:.0f}千円"
            
    except (ValueError, TypeError):
        return str(value)

@register.filter
def format_xbrl_currency(value, unit_info=None):
    """XBRL単位情報を考慮した通貨表示"""
    try:
        value = float(value)
        return _format_currency_base(value)
    except (ValueError, TypeError):
        return str(value)

@register.filter
def format_currency_with_unit_context(value, context=None):
    """文脈を考慮した通貨表示"""
    try:
        value = float(value)
        
        # 文脈情報があれば活用
        if context and 'table_unit' in context:
            table_unit = context['table_unit']
            if table_unit == 'million_yen':
                return f"{value:,.0f}百万円"
            elif table_unit == 'thousand_yen':
                return f"{value:,.0f}千円"
        
        return _format_currency_base(value)
        
    except (ValueError, TypeError):
        return str(value)

def _format_currency_base(value):
    """通貨フォーマットの共通処理"""
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    
    if abs_value >= 1_000_000_000_000:  # 1兆円以上
        formatted_value = abs_value / 1_000_000_000_000
        if formatted_value >= 100:
            return f"{sign}{formatted_value:,.0f}兆円"
        else:
            return f"{sign}{formatted_value:.1f}兆円"
    elif abs_value >= 100_000_000:  # 1億円以上
        formatted_value = abs_value / 100_000_000
        if formatted_value >= 100:
            return f"{sign}{formatted_value:,.0f}億円"
        else:
            return f"{sign}{formatted_value:.1f}億円"
    elif abs_value >= 1_000_000:  # 100万円以上
        formatted_value = abs_value / 1_000_000
        if formatted_value >= 100:
            return f"{sign}{formatted_value:,.0f}百万円"
        else:
            return f"{sign}{formatted_value:.1f}百万円"
    elif abs_value >= 10_000:  # 1万円以上
        formatted_value = abs_value / 1_000
        if formatted_value >= 100:
            return f"{sign}{formatted_value:,.0f}千円"
        else:
            return f"{sign}{formatted_value:.1f}千円"
    else:  # 1万円未満
        return f"{sign}{abs_value:,.0f}円"

@register.filter
def format_percentage_safe(value):
    """安全なパーセンテージ表示"""
    try:
        value = float(value)
        if abs(value) >= 1000:  # 既にパーセンテージの場合
            return f"{value:.1f}%"
        else:  # 小数点形式の場合
            return f"{value * 100:.1f}%"
    except (ValueError, TypeError):
        return "--"

# ====================
# デバッグ用フィルター
# ====================

@register.filter
def debug_financial_value(value):
    """財務値のデバッグ表示"""
    try:
        value = float(value)
        candidates = [
            ('原値', value),
            ('÷1,000', value / 1000),
            ('÷100万', value / 1_000_000),
            ('÷10億', value / 1_000_000_000),
        ]
        
        debug_html = "<div class='debug-financial-value'>"
        debug_html += f"<strong>財務値デバッグ:</strong><br>"
        
        for label, candidate_value in candidates:
            abs_candidate = abs(candidate_value)
            if 1_000_000 <= abs_candidate <= 100_000_000_000_000:  # 現実的な範囲
                status = "✓ 現実的"
                css_class = "text-success"
            else:
                status = "✗ 非現実的"
                css_class = "text-danger"
            
            formatted = _format_currency_base(candidate_value)
            debug_html += f"<small class='{css_class}'>{label}: {formatted} {status}</small><br>"
        
        debug_html += "</div>"
        return mark_safe(debug_html)
        
    except (ValueError, TypeError):
        return f"<small class='text-danger'>デバッグ失敗: {value}</small>"

# ====================
# UI表示関連フィルター
# ====================

@register.filter
def confidence_class(percentage):
    """確信度に応じたクラスを返す"""
    try:
        percentage = float(percentage)
        if percentage >= 80:
            return 'text-success'
        elif percentage >= 60:
            return 'text-info'
        elif percentage >= 40:
            return 'text-warning'
        else:
            return 'text-danger'
    except (ValueError, TypeError):
        return 'text-secondary'

@register.filter
def impact_level_icon(impact_level):
    """影響度レベルに応じたアイコンを返す"""
    icon_map = {
        'very_high': 'fas fa-fire',
        'high': 'fas fa-exclamation-triangle',
        'medium': 'fas fa-info-circle',
        'low': 'fas fa-minus-circle'
    }
    return icon_map.get(impact_level, 'fas fa-circle')

@register.filter
def category_icon(category):
    """カテゴリに応じたアイコンを返す"""
    icon_map = {
        'performance': 'fas fa-chart-line',
        'forecast': 'fas fa-crystal-ball',
        'risk': 'fas fa-shield-alt',
        'market': 'fas fa-globe',
        'operation': 'fas fa-cogs',
        'general': 'fas fa-file-text'
    }
    return icon_map.get(category, 'fas fa-circle')

@register.filter
def meter_angle(percentage):
    """メーターの角度を計算（-90度から+90度）"""
    try:
        percentage = float(percentage)
        # 0-100%を-90度から+90度に変換
        angle = (percentage / 100) * 180 - 90
        return max(-90, min(90, angle))
    except (ValueError, TypeError):
        return 0

@register.simple_tag
def progress_bar_width(current, maximum):
    """プログレスバーの幅を計算"""
    try:
        current = float(current)
        maximum = float(maximum)
        if maximum > 0:
            percentage = (current / maximum) * 100
            return min(100, max(0, percentage))
        return 0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

# ====================
# テキスト処理フィルター
# ====================

@register.filter
def highlight_keywords(text, keyword):
    """テキスト内のキーワードをハイライト"""
    if not keyword or not text:
        return text
    
    highlighted = re.sub(
        re.escape(keyword),
        f'<span class="keyword-highlight">{keyword}</span>',
        str(text),
        flags=re.IGNORECASE
    )
    return mark_safe(highlighted)

@register.filter
def truncate_text(text, length):
    """テキストを指定文字数で切り詰める"""
    if not text:
        return ""
    
    text_str = str(text)
    if len(text_str) <= length:
        return text_str
    
    return text_str[:length] + "..."

@register.filter
def clean_text_for_display(text):
    """表示用にテキストをクリーニング"""
    if not text:
        return ""
    
    # HTMLタグを除去（ハイライト以外）
    cleaned = re.sub(r'<(?!/?span[^>]*>)[^>]+>', '', str(text))
    
    # 連続する空白を単一のスペースに
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()

# ====================
# 数値・計算関連フィルター
# ====================

@register.filter
def score_percentage(value):
    """スコアをパーセンテージに変換"""
    try:
        score = float(value)
        if score <= 1:  # 0-1の範囲の場合
            return int(score * 100)
        else:  # 既にパーセンテージの場合
            return int(score)
    except (ValueError, TypeError):
        return 0

@register.filter
def round_decimal(value, places=2):
    """小数点以下を指定桁数で四捨五入"""
    try:
        return round(float(value), places)
    except (ValueError, TypeError):
        return value

@register.filter
def floatformat_safe(value, decimal_places=2):
    """安全な小数点フォーマット"""
    try:
        return f"{float(value):.{decimal_places}f}"
    except (ValueError, TypeError):
        return "0.00"

@register.filter
def multiply(value, multiplier):
    """値に乗数を掛ける"""
    try:
        return float(value) * float(multiplier)
    except (ValueError, TypeError):
        return 0

@register.filter
def abs_value(value):
    """絶対値を返す"""
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return 0

@register.filter
def length_filter(scores_list, threshold):
    """指定した閾値以上のスコアの数をカウント"""
    try:
        threshold_val = float(threshold)
        if isinstance(scores_list, list):
            return len([score for score in scores_list if float(score) >= threshold_val])
        return 0
    except (ValueError, TypeError):
        return 0

@register.filter
def length_filter_range(scores_list, range_str):
    """指定した範囲内のスコアの数をカウント"""
    try:
        min_val, max_val = map(float, range_str.split(','))
        if isinstance(scores_list, list):
            return len([score for score in scores_list 
                       if min_val <= float(score) < max_val])
        return 0
    except (ValueError, TypeError):
        return 0

# ====================
# ユーティリティフィルター
# ====================

@register.filter
def json_safe(value):
    """Python辞書をJavaScriptで安全に使用できるJSON文字列に変換"""
    try:
        return mark_safe(json.dumps(value))
    except (ValueError, TypeError):
        return mark_safe('{}')

@register.filter
def get_item(dictionary, key):
    """辞書から指定キーの値を取得"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.inclusion_tag('earnings_analysis/tags/keyword_cloud.html')
def keyword_cloud(keywords, total_count=None):
    """キーワードクラウドを表示"""
    return {
        'keywords': keywords,
        'total_count': total_count or len(keywords) if keywords else 0
    }
    
@register.filter
def highlight_all_keywords(text, keywords):
    """複数キーワードを一度にハイライト（新規）"""
    if not text or not keywords:
        return text
    
    highlighted_text = str(text)
    
    # キーワードをリストに変換（文字列の場合）
    if isinstance(keywords, str):
        keyword_list = [keywords]
    else:
        keyword_list = list(keywords) if keywords else []
    
    # キーワードを長い順にソートして、部分マッチによる重複を避ける
    sorted_keywords = sorted(set(keyword_list), key=len, reverse=True)
    
    for keyword in sorted_keywords:
        if keyword and keyword in highlighted_text:
            # 既にハイライトされている部分は除外
            if f'<span class="keyword-highlight">{keyword}</span>' not in highlighted_text:
                highlighted_text = highlighted_text.replace(
                    str(keyword),
                    f'<span class="keyword-highlight">{keyword}</span>'
                )
    
    return mark_safe(highlighted_text)

# earnings_analysis/templatetags/sentiment_filters.py の末尾に追加

@register.filter
def prepare_wordcloud_data(keyword_frequency_data, min_count=2):
    """ワードクラウド用データを準備"""
    try:
        wordcloud_words = []
        
        # ポジティブ語彙を処理
        positive_words = keyword_frequency_data.get('positive', [])
        for word_info in positive_words:
            count = word_info.get('count', 1)
            if count >= min_count:
                wordcloud_words.append({
                    'text': word_info.get('word', ''),
                    'size': count,
                    'sentiment': 'positive',
                    'score': word_info.get('score', 0),
                    'color': '#28a745'  # 緑色
                })
        
        # ネガティブ語彙を処理
        negative_words = keyword_frequency_data.get('negative', [])
        for word_info in negative_words:
            count = word_info.get('count', 1)
            if count >= min_count:
                wordcloud_words.append({
                    'text': word_info.get('word', ''),
                    'size': count,
                    'sentiment': 'negative',
                    'score': word_info.get('score', 0),
                    'color': '#dc3545'  # 赤色
                })
        
        # サイズ順でソート（頻出語を優先）
        wordcloud_words.sort(key=lambda x: x['size'], reverse=True)
        
        return json.dumps(wordcloud_words[:300])  # 上位300語まで
        
    except Exception as e:
        logger.error(f"ワードクラウドデータ準備エラー: {e}")
        return json.dumps([])

@register.filter
def prepare_unlimited_wordcloud_data(keyword_frequency_data):
    """制限なしワードクラウド用データを準備"""
    try:
        return prepare_wordcloud_data(keyword_frequency_data, min_count=1)
    except Exception:
        return json.dumps([])

@register.filter
def wordcloud_max_size(keyword_frequency_data):
    """ワードクラウドの最大出現回数を取得"""
    try:
        max_count = 0
        
        positive_words = keyword_frequency_data.get('positive', [])
        for word_info in positive_words:
            max_count = max(max_count, word_info.get('count', 0))
        
        negative_words = keyword_frequency_data.get('negative', [])
        for word_info in negative_words:
            max_count = max(max_count, word_info.get('count', 0))
            
        return max_count
        
    except Exception:
        return 0

@register.filter
def wordcloud_stats(keyword_frequency_data, min_count=2):
    """ワードクラウド統計情報を取得"""
    try:
        total_words = 0
        filtered_words = 0
        total_occurrences = 0
        
        for sentiment_type in ['positive', 'negative']:
            words = keyword_frequency_data.get(sentiment_type, [])
            for word_info in words:
                count = word_info.get('count', 1)
                total_words += 1
                total_occurrences += count
                
                if count >= min_count:
                    filtered_words += 1
        
        return {
            'total_unique_words': total_words,
            'displayed_words': filtered_words,
            'total_occurrences': total_occurrences,
            'filter_rate': (filtered_words / total_words * 100) if total_words > 0 else 0
        }
        
    except Exception:
        return {
            'total_unique_words': 0,
            'displayed_words': 0,
            'total_occurrences': 0,
            'filter_rate': 0
        }