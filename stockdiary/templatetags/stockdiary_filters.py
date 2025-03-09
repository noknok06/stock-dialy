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