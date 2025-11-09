# stockdiary/templatetags/stockdiary_filters.py
import re
import math
from django.utils.safestring import mark_safe
from django import template
from django.template.defaultfilters import stringfilter
import decimal

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """辞書からキーの値を取得するカスタムフィルタ"""
    return dictionary.get(key)

@register.filter(name='add')
def add_filter(value, arg):
    """数値を加算するカスタムフィルタ"""
    try:
        return value + arg
    except (ValueError, TypeError):
        return value

@register.filter(name='sub')
def sub_filter(value, arg):
    """数値を減算するカスタムフィルタ"""
    try:
        return value - arg
    except (ValueError, TypeError):
        return value

@register.filter(name='mul')
def mul_filter(value, arg):
    """数値を乗算するカスタムフィルタ"""
    try:
        return value * arg
    except (ValueError, TypeError):
        return value

@register.filter(name='div')
def div_filter(value, arg):
    """数値を除算するカスタムフィルタ"""
    try:
        return value / arg
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter(name='percentage_of')
def percentage_of(value, total):
    """
    値の合計に対する割合（パーセント）を計算する
    
    例: {{ tag.count|percentage_of:total_tags }}
    """
    try:
        if total == 0:
            return 0
        return int((float(value) / float(total)) * 100)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter(name='highlight')
@stringfilter
def highlight(text, search_term):
    """
    テキスト内の検索キーワードをハイライト表示するフィルタ
    
    例: {{ diary.reason|highlight:request.GET.query }}
    """
    if not search_term or not text:
        return mark_safe(text)
    
    # HTMLタグをエスケープせずに検索するために正規表現を使用
    search_pattern = re.compile(r'({0})'.format(re.escape(search_term)), re.IGNORECASE)
    result = search_pattern.sub(r'<span class="search-highlight">\1</span>', text)
    
    return mark_safe(result)
        

@register.filter(name='multiply')
def multiply(value, arg):
    """2つの値を掛け算するフィルター"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter(name='divideby')
def divideby(value, arg):
    """2つの値を割り算するフィルター"""
    try:
        arg_float = float(arg)
        if arg_float == 0:
            return 0
        return float(value) / arg_float
    except (ValueError, TypeError):
        return 0

@register.filter(name='add_class')
def add_class(field, css_class):
    """フォームフィールドにCSSクラスを追加するフィルター"""
    if hasattr(field, 'as_widget'):
        return field.as_widget(attrs={'class': css_class})
    return field

@register.filter(name='margin_ratio')
def margin_ratio(outstanding_purchases, outstanding_sales):
    """
    正しい信用倍率を計算するフィルター
    
    使用例: {{ margin_data.outstanding_purchases|margin_ratio:margin_data.outstanding_sales }}
    計算式: 買残高 ÷ 売残高
    """
    try:
        outstanding_purchases = float(outstanding_purchases or 0)
        outstanding_sales = float(outstanding_sales or 0)
        
        if outstanding_sales > 0:
            return outstanding_purchases / outstanding_sales
        return 0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter(name='margin_level')
def margin_level(ratio):
    """
    正しい信用倍率のレベルを判定するフィルター
    
    使用例: {{ ratio|margin_level }}
    返り値: 'low', 'medium', 'high', 'unknown'
    """
    try:
        ratio = float(ratio)
        if ratio < 1.0:
            return 'low'      # 低倍率（売り優勢）
        elif ratio < 2.0:
            return 'medium'   # 中倍率（均衡）
        else:
            return 'high'     # 高倍率（買い優勢）
    except (ValueError, TypeError):
        return 'unknown'

@register.filter(name='margin_level_class')
def margin_level_class(ratio):
    """
    正しい信用倍率レベルに対応するCSSクラスを返すフィルター
    
    使用例: <span class="{{ ratio|margin_level_class }}">{{ ratio|floatformat:2 }}倍</span>
    """
    level = margin_level(ratio)
    css_classes = {
        'low': 'text-danger',     # 低倍率（売り優勢）= 赤
        'medium': 'text-primary', # 中倍率（均衡）= 青
        'high': 'text-success',   # 高倍率（買い優勢）= 緑
        'unknown': 'text-muted'
    }
    return css_classes.get(level, 'text-muted')

@register.filter(name='margin_level_text')
def margin_level_text(ratio):
    """
    正しい信用倍率レベルの日本語テキストを返すフィルター
    
    使用例: {{ ratio|margin_level_text }}
    """
    level = margin_level(ratio)
    level_texts = {
        'low': '売り優勢',      # 買残 < 売残
        'medium': '均衡',       # 買残 ≈ 売残
        'high': '買い優勢',     # 買残 > 売残
        'unknown': '-'
    }
    return level_texts.get(level, '-')

@register.filter(name='format_stock_amount')
def format_stock_amount(value):
    """
    株数を読みやすい形式でフォーマット
    
    例：
    1000 -> "1K"
    10000 -> "10K" 
    1000000 -> "1M"
    """
    try:
        value = float(value or 0)
        
        if value == 0:
            return "0"
        
        if value >= 1000000:
            return f"{value/1000000:.1f}M".rstrip('0').rstrip('.')
        elif value >= 1000:
            return f"{value/1000:.1f}K".rstrip('0').rstrip('.')
        else:
            return f"{int(value)}"
            
    except (ValueError, TypeError):
        return "0"

@register.filter(name='format_change')
def format_change(value):
    """
    変動値をフォーマット（+/-付き）
    
    例：
    1500 -> "+1.5K"
    -2000 -> "-2K"
    """
    try:
        value = float(value or 0)
        
        if value == 0:
            return "±0"
            
        sign = "+" if value > 0 else ""
        formatted = format_stock_amount(abs(value))
        
        return f"{sign}{formatted}" if value > 0 else f"-{formatted}"
        
    except (ValueError, TypeError):
        return "±0"

@register.filter(name='change_direction_class')
def change_direction_class(value):
    """
    変動方向に応じたCSSクラスを返す
    """
    try:
        value = float(value or 0)
        
        if value > 0:
            return "positive-change"
        elif value < 0:
            return "negative-change"
        else:
            return "neutral-change"
            
    except (ValueError, TypeError):
        return "neutral-change"

@register.filter(name='smart_round')
def smart_round(value, decimal_places=2):
    """
    スマートな丸め処理
    大きな値は少ない桁数、小さな値は多い桁数
    """
    try:
        value = float(value or 0)
        
        if abs(value) >= 100:
            return f"{value:.0f}"
        elif abs(value) >= 10:
            return f"{value:.1f}"
        else:
            return f"{value:.2f}"
            
    except (ValueError, TypeError):
        return "0"

@register.filter(name='ratio_color_intensity')
def ratio_color_intensity(value):
    """
    信用倍率の値に基づいて色の強度を決定
    0.0-1.0の値を返し、CSS変数として使用
    """
    try:
        value = float(value or 0)
        
        if value < 1.0:
            # 売り優勢：値が小さいほど強い赤
            intensity = max(0.2, min(1.0, (1.0 - value) * 2))
            return intensity
        elif value > 2.0:
            # 買い優勢：値が大きいほど強い緑
            intensity = max(0.2, min(1.0, (value - 2.0) * 0.5))
            return intensity
        else:
            # 均衡：薄い青
            return 0.3
            
    except (ValueError, TypeError):
        return 0.2

@register.filter(name='mobile_truncate')
def mobile_truncate(value, max_length=10):
    """
    モバイル表示用の文字列切り取り
    日本語文字を考慮した切り取り
    """
    if not value:
        return ""
        
    value_str = str(value)
    
    if len(value_str) <= max_length:
        return value_str
    
    # 日本語文字の場合、より短く切る
    japanese_chars = sum(1 for char in value_str if ord(char) > 127)
    if japanese_chars > 0:
        max_length = max(6, max_length - japanese_chars // 2)
    
    return value_str[:max_length] + "..."

@register.filter(name='percentage_display')
def percentage_display(value, total=None):
    """
    パーセント表示の改善
    小さい値でも見やすく表示
    """
    try:
        if total:
            percentage = (float(value or 0) / float(total)) * 100
        else:
            percentage = float(value or 0)
            
        if percentage == 0:
            return "0%"
        elif percentage < 0.1:
            return "<0.1%"
        elif percentage < 1:
            return f"{percentage:.1f}%"
        else:
            return f"{percentage:.0f}%"
            
    except (ValueError, TypeError, ZeroDivisionError):
        return "0%"

@register.filter(name='trend_arrow')
def trend_arrow(value):
    """
    トレンド矢印アイコンを返す
    """
    try:
        value = float(value or 0)
        
        if value > 0.1:
            return mark_safe('<i class="bi bi-arrow-up text-success" title="上昇"></i>')
        elif value < -0.1:
            return mark_safe('<i class="bi bi-arrow-down text-danger" title="下降"></i>')
        else:
            return mark_safe('<i class="bi bi-arrow-right text-muted" title="横ばい"></i>')
            
    except (ValueError, TypeError):
        return mark_safe('<i class="bi bi-dash text-muted"></i>')

@register.filter(name='days_ago')
def days_ago(date):
    """
    日付から経過日数を計算
    モバイルフレンドリーな表示
    """
    if not date:
        return ""
        
    from datetime import date as date_class
    from django.utils import timezone
    
    try:
        if isinstance(date, str):
            return date
            
        today = timezone.now().date()
        diff = (today - date).days
        
        if diff == 0:
            return "今日"
        elif diff == 1:
            return "昨日"
        elif diff < 7:
            return f"{diff}日前"
        elif diff < 30:
            weeks = diff // 7
            return f"{weeks}週間前"
        else:
            months = diff // 30
            return f"{months}ヶ月前"
            
    except (AttributeError, TypeError, ValueError):
        return str(date)

@register.filter(name='confidence_level')
def confidence_level(value):
    """
    信頼度レベルを文字で表現
    分析結果の信頼性を示す
    """
    try:
        value = float(value or 0)
        
        if value >= 0.9:
            return "高"
        elif value >= 0.7:
            return "中"
        elif value >= 0.5:
            return "低"
        else:
            return "不明"
            
    except (ValueError, TypeError):
        return "不明"

@register.filter(name='mobile_number_format')
def mobile_number_format(value):
    """
    モバイル向け数値フォーマット
    スペースを節約しつつ読みやすさを保つ
    """
    try:
        value = float(value or 0)
        
        if value == 0:
            return "0"
        
        # 絶対値で判定
        abs_value = abs(value)
        
        if abs_value >= 1000000000:  # 10億以上
            return f"{value/1000000000:.1f}B"
        elif abs_value >= 1000000:  # 100万以上
            return f"{value/1000000:.1f}M"
        elif abs_value >= 1000:     # 1000以上
            return f"{value/1000:.1f}K"
        elif abs_value >= 1:        # 1以上
            return f"{value:.1f}"
        else:                       # 1未満
            return f"{value:.2f}"
            
    except (ValueError, TypeError):
        return "0"

@register.filter(name='risk_level_class')
def risk_level_class(value):
    """
    リスクレベルに応じたCSSクラス
    """
    try:
        value = float(value or 0)
        
        if value >= 0.8:
            return "risk-high"
        elif value >= 0.5:
            return "risk-medium"
        elif value >= 0.2:
            return "risk-low"
        else:
            return "risk-minimal"
            
    except (ValueError, TypeError):
        return "risk-unknown"

@register.filter(name='mobile_friendly_title')
def mobile_friendly_title(value, max_length=15):
    """
    モバイルフレンドリーなタイトル生成
    長い企業名を適切に短縮
    """
    if not value:
        return ""
        
    value_str = str(value)
    
    # 一般的な省略パターン
    replacements = {
        '株式会社': '(株)',
        'ホールディングス': 'HD',
        'システム': 'Sys',
        'テクノロジー': 'Tech',
        'コーポレーション': 'Corp',
        'インターナショナル': 'Intl',
    }
    
    shortened = value_str
    for full, short in replacements.items():
        shortened = shortened.replace(full, short)
    
    if len(shortened) > max_length:
        shortened = shortened[:max_length-1] + "…"
        
    return shortened

# 条件付きクラス適用フィルター
@register.filter(name='add_class_if')
def add_class_if(field, condition_and_class):
    """
    条件に基づいてクラスを追加
    使用例: {{ field|add_class_if:"True,is-valid" }}
    """
    try:
        condition, css_class = condition_and_class.split(',', 1)
        
        if condition.lower() in ['true', '1', 'yes']:
            return field + f' {css_class}'
        else:
            return field
            
    except (ValueError, AttributeError):
        return field

@register.filter(name='touch_friendly_size')
def touch_friendly_size(base_size):
    """
    タッチフレンドリーなサイズ調整
    最小タッチターゲットサイズ（44px）を保証
    """
    try:
        base = int(base_size)
        return max(44, base)  # 44px minimum for touch targets
    except (ValueError, TypeError):
        return 44
    
@register.filter(name='intcomma_float')
def intcomma_float(value, decimal_places=0):
    """
    float値をカンマ区切りでフォーマットする。
    decimal_places=0 の場合もカンマ付きで整数表示。
    """
    try:
        value = float(value or 0)
        if decimal_places == 0:
            formatted = f"{int(round(value)):,}"
        else:
            formatted = f"{value:,.{decimal_places}f}"
        return formatted
    except (ValueError, TypeError):
        return "0"
    