from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    """辞書からキーの値を取得"""
    if dictionary and isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter(name='add')
def add_filter(value, arg):
    """文字列連結"""
    return f"{value}{arg}"


@register.filter(name='get_group_label')
def get_group_label(group_code):
    """指標グループコードからラベルを取得"""
    labels = {
        'profitability': '収益性',
        'growth': '成長性',
        'valuation': 'バリュエーション',
        'dividend': '配当',
        'financial_health': '財務健全性',
        'efficiency': '効率性',
        'scale': '規模・実績',
    }
    return labels.get(group_code, group_code)

