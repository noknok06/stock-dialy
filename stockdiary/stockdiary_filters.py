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