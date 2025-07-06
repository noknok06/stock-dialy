# earnings_analysis/templatetags/sentiment_filters.py
from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

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
        'positive': 'bg-info',
        'neutral': 'bg-secondary',
        'negative': 'bg-warning',
        'very_negative': 'bg-danger'
    }
    return badge_map.get(sentiment_label, 'bg-secondary')

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
def json_safe(value):
    """Python辞書をJavaScriptで安全に使用できるJSON文字列に変換"""
    try:
        return mark_safe(json.dumps(value))
    except (ValueError, TypeError):
        return mark_safe('{}')

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

@register.filter
def score_percentage(score):
    """スコア（0-1）をパーセンテージに変換"""
    try:
        score = float(score)
        return round(score * 100, 1)
    except (ValueError, TypeError):
        return 0

@register.filter
def highlight_keywords(text, keyword):
    """テキスト内のキーワードをハイライト"""
    try:
        if keyword and keyword in text:
            highlighted = text.replace(
                keyword,
                f'<span class="keyword-highlight">{keyword}</span>'
            )
            return mark_safe(highlighted)
        return text
    except (AttributeError, TypeError):
        return text

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
def round_decimal(value, places=2):
    """小数点以下を指定桁数で四捨五入"""
    try:
        return round(float(value), places)
    except (ValueError, TypeError):
        return value

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

@register.inclusion_tag('earnings_analysis/tags/keyword_cloud.html')
def keyword_cloud(keywords, total_count=None):
    """キーワードクラウドを表示"""
    return {
        'keywords': keywords,
        'total_count': total_count or len(keywords) if keywords else 0
    }

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
    
# earnings_analysis/templatetags/sentiment_filters.py の修正版

@register.filter
def format_japanese_currency(value):
    """日本円を適切な単位で表示（異常値対策強化版）"""
    try:
        value = float(value)
        original_value = value
        abs_value = abs(value)
        
        if abs_value == 0:
            return "0円"
        
        # 異常値の段階的自動調整（より積極的）
        adjustment_made = False
        adjustment_factor = 1
        
        if abs_value > 1_000_000_000_000_000:  # 1000兆円以上は明らかに異常
            # 段階的調整を試行
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
                # どの調整でも現実的にならない場合は、最小の調整を適用
                value = value / 1_000_000
                abs_value = abs(value)
                adjustment_made = True
                adjustment_factor = 1_000_000
        
        # 現実的な範囲での異常値警告（調整後）
        warning_needed = False
        if abs_value > 50_000_000_000_000:  # 50兆円を超える場合は警告
            warning_needed = True
        
        # 通常の表示処理
        formatted_result = format_normal_currency(value)
        
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
        if warning_needed:
            return f"<span class='text-warning'>⚠️</span> {formatted_result} <small class='text-muted'>(要確認)</small>"
        
        return formatted_result
            
    except (ValueError, TypeError):
        return str(value)

def format_normal_currency(value):
    """通常の通貨フォーマット処理（修正版）"""
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    
    # より細かい単位判定
    if abs_value >= 1_000_000_000_000:  # 1兆円以上
        formatted_value = abs_value / 1_000_000_000_000
        if formatted_value >= 10000:  # 1万兆円以上（異常）
            return f"{sign}{formatted_value:,.0f}兆円 <small class='text-danger'>(異常値)</small>"
        elif formatted_value >= 100:
            return f"{sign}{formatted_value:,.0f}兆円"
        else:
            return f"{sign}{formatted_value:.1f}兆円"
    elif abs_value >= 100_000_000:  # 1億円以上
        formatted_value = abs_value / 100_000_000
        if formatted_value >= 10000:  # 1万億円以上
            return f"{sign}{formatted_value:,.0f}億円"
        elif formatted_value >= 100:
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
def format_xbrl_currency_safe(value, context=None):
    """XBRL値の安全な通貨表示（デバッグ情報付き）"""
    try:
        value = float(value)
        abs_value = abs(value)
        
        if abs_value == 0:
            return "0円"
        
        # デバッグ情報の準備
        debug_info = ""
        if context and 'show_debug' in context:
            debug_info = f" <small class='text-muted'>[元値:{value:,.0f}]</small>"
        
        # 異常値の検出と段階的調整
        if abs_value > 100_000_000_000_000:  # 100兆円を超える場合
            # 現実的な値になるまで段階的に調整
            adjustment_steps = []
            original_value = value
            
            test_divisors = [1000, 10000, 100000, 1000000, 10000000, 100000000, 1000000000]
            
            for divisor in test_divisors:
                test_value = abs_value / divisor
                if test_value <= 100_000_000_000_000:  # 100兆円以下になった
                    value = value / divisor
                    adjustment_steps.append(f"÷{divisor}")
                    break
            
            # 調整情報を表示
            adjustment_text = " → ".join(adjustment_steps) if adjustment_steps else "調整失敗"
            debug_info += f" <small class='text-warning'>[{adjustment_text}]</small>"
        
        # 基本的な表示処理
        result = format_normal_currency(value)
        
        return result + debug_info
        
    except (ValueError, TypeError):
        return str(value)

@register.filter  
def format_compact_currency_safe(value):
    """コンパクトな通貨表示（異常値対策版）"""
    try:
        value = float(value)
        abs_value = abs(value)
        
        if abs_value == 0:
            return "0"
        
        # 異常値の簡易調整
        if abs_value > 1_000_000_000_000_000:  # 1000兆円超
            # 適当な調整を適用
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

# デバッグ用フィルター
@register.filter
def debug_financial_value(value):
    """財務値のデバッグ表示"""
    try:
        value = float(value)
        abs_value = abs(value)
        
        # 段階的な表示候補を生成
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
            
            formatted = format_normal_currency(candidate_value)
            debug_html += f"<small class='{css_class}'>{label}: {formatted} {status}</small><br>"
        
        debug_html += "</div>"
        return mark_safe(debug_html)
        
    except (ValueError, TypeError):
        return f"<small class='text-danger'>デバッグ失敗: {value}</small>"
    
@register.filter
def format_compact_currency(value):
    """コンパクトな通貨表示（キャッシュフロー図用）"""
    try:
        value = float(value)
        abs_value = abs(value)
        
        if abs_value == 0:
            return "0"
        
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
def format_xbrl_currency(value, unit_info=None):
    """XBRL単位情報を考慮した通貨表示"""
    try:
        value = float(value)
        abs_value = abs(value)
        sign = "-" if value < 0 else ""
        
        if abs_value == 0:
            return "0円"
        
        # 基本的な日本円表示
        if abs_value >= 1_000_000_000_000:  # 1兆円以上
            formatted_value = abs_value / 1_000_000_000_000
            return f"{sign}{formatted_value:.1f}兆円"
        elif abs_value >= 100_000_000:  # 1億円以上
            formatted_value = abs_value / 100_000_000
            return f"{sign}{formatted_value:.1f}億円"
        elif abs_value >= 1_000_000:  # 100万円以上
            formatted_value = abs_value / 1_000_000
            return f"{sign}{formatted_value:.1f}百万円"
        elif abs_value >= 1_000:  # 1000円以上
            formatted_value = abs_value / 1_000
            return f"{sign}{formatted_value:.1f}千円"
        else:
            return f"{sign}{abs_value:,.0f}円"
            
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
                # 既に百万円単位の場合は、そのまま表示
                return f"{value:,.0f}百万円"
            elif table_unit == 'thousand_yen':
                return f"{value:,.0f}千円"
        
        # デフォルトの表示
        return format_xbrl_currency(value)
        
    except (ValueError, TypeError):
        return str(value)
