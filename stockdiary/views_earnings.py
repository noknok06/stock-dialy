# stockdiary/views_earnings.py
"""決算カレンダー（決算予定の表示）

保有銘柄・ウォッチリスト（メモ）の次回決算日と残り日数、日付ごとの決算一覧を
表示する。表示は外部APIを叩かず、ローカルの EarningsSchedule / StockDiary の
事前計算フィールド（next_earnings_date）のみを参照する（API障害・速度に非依存）。

決算予定データの取り込みは earnings_analysis の sync_earnings_calendar コマンド
（日次バッチ）が担う。
"""
from collections import OrderedDict
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from earnings_analysis.models import EarningsSchedule
from .models import StockDiary

# カレンダーの表示期間（当日からの日数）
CALENDAR_WINDOW_DAYS = 90


def _to_ticker(securities_code: str) -> str:
    """証券コードを4桁の銘柄コードへ正規化する。"""
    code = (securities_code or '').strip()
    if len(code) == 5 and code.endswith('0'):
        return code[:4]
    return code


def _candidate_codes(symbols):
    """4桁銘柄コード集合から、EarningsSchedule 照合用の候補コード一覧を作る。"""
    candidates = []
    for s in symbols:
        candidates.append(s)
        candidates.append(s + '0')
    return candidates


@login_required
def earnings_calendar(request):
    """決算カレンダー本体。

    GET パラメータ:
        scope: 'mine'（記録銘柄のみ・既定）/ 'all'（全銘柄）
    """
    scope = request.GET.get('scope', 'mine')
    if scope not in ('mine', 'all'):
        scope = 'mine'

    today = date.today()
    window_end = today + timedelta(days=CALENDAR_WINDOW_DAYS)

    user_diaries = StockDiary.objects.filter(user=request.user, is_excluded=False)

    # 記録銘柄（4桁）の集合 — カレンダーの「自分の銘柄」ハイライト / mine 絞り込みに使う
    user_symbols = set(
        user_diaries
        .filter(stock_symbol__regex=r'^\d{4}$')
        .values_list('stock_symbol', flat=True)
    )

    # 保有銘柄（current_quantity > 0）— 次回決算日が近い順
    holdings = list(
        user_diaries
        .filter(current_quantity__gt=0, next_earnings_date__isnull=False)
        .order_by('next_earnings_date')
    )

    # ウォッチリスト（メモ＝取引なし）— 決算予定日が近い順
    watchlist = list(
        user_diaries
        .filter(transaction_count=0, next_earnings_date__isnull=False)
        .order_by('next_earnings_date')
    )

    # 日付ごとの決算一覧
    schedule_qs = EarningsSchedule.objects.filter(
        earnings_date__gte=today, earnings_date__lte=window_end
    )
    if scope == 'mine':
        if user_symbols:
            schedule_qs = schedule_qs.filter(
                securities_code__in=_candidate_codes(user_symbols)
            )
        else:
            schedule_qs = schedule_qs.none()

    calendar = OrderedDict()
    for schedule in schedule_qs.order_by('earnings_date', 'securities_code'):
        ticker = _to_ticker(schedule.securities_code)
        schedule.ticker_normalized = ticker
        schedule.is_mine = ticker in user_symbols
        schedule.days_until = (schedule.earnings_date - today).days
        calendar.setdefault(schedule.earnings_date, []).append(schedule)

    calendar_days = [
        {'date': d, 'items': items, 'is_today': d == today}
        for d, items in calendar.items()
    ]

    context = {
        'scope': scope,
        'today': today,
        'window_days': CALENDAR_WINDOW_DAYS,
        'holdings': holdings,
        'watchlist': watchlist,
        'calendar_days': calendar_days,
        'calendar_count': sum(len(d['items']) for d in calendar_days),
    }

    is_htmx = (
        request.headers.get('HX-Request') == 'true'
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    )
    if is_htmx:
        return render(
            request, 'stockdiary/partials/earnings_calendar_body.html', context
        )
    return render(request, 'stockdiary/earnings_calendar.html', context)
