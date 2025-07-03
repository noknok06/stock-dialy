# earnings_reports/templatetags/custom_filters.py (完全版)

from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def mul(value, arg):
    """数値の乗算フィルター（安全版）"""
    try:
        if value is None or arg is None:
            return 0
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """数値の除算フィルター（安全版）"""
    try:
        if value is None or arg is None or float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def sub(value, arg):
    """数値の減算フィルター（安全版）"""
    try:
        if value is None or arg is None:
            return 0
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add_safe(value, arg):
    """数値の加算フィルター（安全版）"""
    try:
        if value is None or arg is None:
            return 0
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def default_if_none(value, default):
    """None の場合にデフォルト値を返す"""
    return default if value is None else value

@register.filter
def safe_float(value, decimal_places=1):
    """安全な小数点表示"""
    try:
        if value is None:
            return "-"
        return f"{float(value):.{decimal_places}f}"
    except (ValueError, TypeError):
        return "-"