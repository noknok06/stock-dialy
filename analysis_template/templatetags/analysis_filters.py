# analysis_template/templatetags/analysis_filters.py
from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """辞書からキーの値を取得するカスタムフィルタ"""
    return dictionary.get(key)

@register.filter
def multiply(value, arg):
    return value * arg    


@register.filter
def index(indexable, i):
    """
    Returns the item at index i from indexable (list/dict).
    Usage: {{ mydict|index:key }} or {{ mylist|index:0 }}
    """
    try:
        return indexable[i]
    except (KeyError, IndexError, TypeError):
        return None