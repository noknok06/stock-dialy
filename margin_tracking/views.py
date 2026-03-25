"""
信用倍率データ API
分析・計算機能から利用するためのJSONエンドポイント。
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required

from .models import MarginData


@login_required
@require_GET
def margin_data_api(request, stock_code):
    """
    指定銘柄コードの信用倍率推移データをJSON形式で返す。

    GET /margin/api/<stock_code>/
    Query params:
      weeks: 取得週数（デフォルト: 26 = 約半年）
    """
    try:
        weeks = int(request.GET.get('weeks', 26))
        weeks = max(4, min(weeks, 104))  # 4〜104週の範囲に制限
    except (ValueError, TypeError):
        weeks = 26

    # 4桁コードに正規化（5桁の場合は末尾を除く）
    code = stock_code.strip()
    if len(code) == 5 and code.isdigit():
        code = code[:4]

    records = (
        MarginData.objects
        .filter(stock_code=code)
        .order_by('-record_date')[:weeks]
    )

    data = []
    for rec in reversed(list(records)):  # 古い順
        data.append({
            'date': rec.record_date.strftime('%Y-%m-%d'),
            'short_balance': rec.short_balance,
            'long_balance': rec.long_balance,
            'margin_ratio': round(rec.long_balance / rec.short_balance, 2) if rec.short_balance and rec.short_balance > 0 else None,
        })

    return JsonResponse({
        'stock_code': code,
        'weeks': weeks,
        'count': len(data),
        'data': data,
    })
