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