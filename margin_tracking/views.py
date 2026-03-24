"""
信用倍率データ APIビュー
"""

import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

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
    for rec in reversed(list(records)):  # 古い順に並べ直す
        data.append({
            'date': rec.record_date.strftime('%Y-%m-%d'),
            'short_balance': rec.short_balance,
            'long_balance': rec.long_balance,
            'margin_ratio': float(rec.margin_ratio) if rec.margin_ratio is not None else None,
        })

    return JsonResponse({
        'stock_code': code,
        'weeks': weeks,
        'count': len(data),
        'data': data,
    })


@login_required
@require_GET
def margin_widget(request, stock_code):
    """
    信用倍率推移ウィジェット（HTMX/部分テンプレート）。

    GET /margin/widget/<stock_code>/
    """
    code = stock_code.strip()
    if len(code) == 5 and code.isdigit():
        code = code[:4]

    records = list(
        MarginData.objects
        .filter(stock_code=code)
        .order_by('-record_date')[:26]
    )
    records.reverse()  # 古い順

    # Chart.js用データ
    labels = [r.record_date.strftime('%m/%d') for r in records]
    margin_ratios = [
        float(r.margin_ratio) if r.margin_ratio is not None else None
        for r in records
    ]
    short_balances = [r.short_balance for r in records]
    long_balances = [r.long_balance for r in records]

    latest = records[-1] if records else None

    context = {
        'stock_code': code,
        'records': records,
        'latest': latest,
        'chart_labels': json.dumps(labels, ensure_ascii=False),
        'chart_margin_ratios': json.dumps(margin_ratios),
        'chart_short_balances': json.dumps(short_balances),
        'chart_long_balances': json.dumps(long_balances),
        'has_data': bool(records),
    }
    return render(request, 'margin_tracking/margin_widget.html', context)
