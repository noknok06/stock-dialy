# analysis_template/templatetags/analysis_filters.py
from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """辞書からキーの値を取得するカスタムフィルタ"""
    return dictionary.get(key)