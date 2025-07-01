from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def mul(value, arg):
    """数値の乗算フィルター"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """数値の除算フィルター"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def sub(value, arg):
    """数値の減算フィルター"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0