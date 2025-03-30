# stockdiary/templatetags/stockdiary_filters.py

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
def highlight_filter(text, search_term):
    """
    テキスト内の検索キーワードをハイライト表示するフィルター
    検索キーワードが大文字小文字を区別せずにハイライトします
    """
    if not text or not search_term or not isinstance(search_term, str) or not search_term.strip():
        return text
    
    try:
        # テキストと検索語を小文字に変換して位置を特定
        text_lower = str(text).lower()
        search_term_lower = search_term.lower()
        
        # 元のテキストから該当部分を抽出して置き換え
        result = text
        start_pos = 0
        
        while True:
            pos = text_lower.find(search_term_lower, start_pos)
            if pos == -1:
                break
                
            original_match = text[pos:pos+len(search_term)]
            highlighted = f'<span class="search-highlight">{original_match}</span>'
            
            # 置換前のテキストの長さ
            before_len = len(result)
            
            # 置換
            result = result[:pos] + highlighted + result[pos+len(search_term):]
            
            # 次の検索位置を計算（ハイライトタグの分だけずれる）
            start_pos = pos + len(highlighted)
            
            # テキストが変わったので、text_lowerも再計算
            text_lower = result.lower()
        
        return mark_safe(result)
    except Exception as e:
        print(f"Highlight error: {e}")
        return text