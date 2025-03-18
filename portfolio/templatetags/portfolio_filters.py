# portfolio/templatetags/portfolio_filters.py
from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def sub(value, arg):
    """引き算を行うフィルター"""
    try:
        return value - arg
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """割り算を行うフィルター（ゼロ除算対策あり）"""
    try:
        if arg == 0:
            return 0
        return value / arg
    except (ValueError, TypeError):
        return 0

@register.filter
def mul(value, arg):
    """掛け算を行うフィルター"""
    try:
        return value * arg
    except (ValueError, TypeError):
        return 0