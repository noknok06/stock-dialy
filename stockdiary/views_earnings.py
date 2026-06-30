# stockdiary/views_earnings.py
"""決算カレンダー（決算予定の表示）

保有銘柄・ウォッチリスト（メモ）の次回決算日と残り日数、月グリッド＋選択日リストの
ハイブリッド型カレンダーを表示する。表示は外部APIを叩かず、ローカルの
EarningsSchedule（証券コードがキーの決算予定マスタ）のみを参照する。

決算日は日記側に持たせない。日記は stock_symbol（銘柄コード）を持つので、
表示時に get_next_earnings_map / attach_next_earnings で都度 join して引く
（マスタと日記の二重管理・日次コピーを避ける）。

決算予定データの取り込みは earnings_analysis の sync_earnings_calendar コマンド
（日次バッチ）が担う。
"""
from calendar import Calendar, monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from earnings_analysis.models import EarningsSchedule
from .models import StockDiary

# カレンダーの表示期間（当日からの日数）
CALENDAR_WINDOW_DAYS = 90

# 決算の近さ区分のしきい値（日数）
PROXIMITY_IMMINENT_DAYS = 3   # 間近
PROXIMITY_SOON_DAYS = 14      # 近日

# 月グリッドの曜日見出し（月曜始まり）
WEEKDAY_HEADERS = ['月', '火', '水', '木', '金', '土', '日']


@dataclass
class NextEarnings:
    """ある銘柄の「次回決算」表示用の値オブジェクト（DBカラムではない）。"""
    date: date
    type: str
    days_until: int
    proximity: str


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


def _classify_proximity(days_until: int) -> str:
    """残り日数を近さ区分へ分類する。"""
    if days_until <= PROXIMITY_IMMINENT_DAYS:
        return 'imminent'
    if days_until <= PROXIMITY_SOON_DAYS:
        return 'soon'
    return 'scheduled'


def get_next_earnings_map(symbols, today=None) -> dict:
    """銘柄コード集合 → {ticker(4桁): NextEarnings} を1クエリで引く。

    各銘柄について「当日以降で最も近い」決算予定を採用する。決算日は日記に
    持たせず、ここで EarningsSchedule（マスタ）から都度参照する。
    """
    if today is None:
        today = date.today()

    # 4桁の日本株コードのみ対象（外国株などは決算予定マスタに無い）
    tickers = {s for s in symbols if s and s.isdigit() and len(s) == 4}
    if not tickers:
        return {}

    rows = (
        EarningsSchedule.objects
        .filter(securities_code__in=_candidate_codes(tickers),
                earnings_date__gte=today)
        .order_by('securities_code', 'earnings_date')
        .values('securities_code', 'earnings_date', 'earnings_type')
    )

    result = {}
    for row in rows:
        ticker = _to_ticker(row['securities_code'])
        if ticker in result:
            continue  # ソート済みなので先頭＝最も近い未来日
        days = (row['earnings_date'] - today).days
        result[ticker] = NextEarnings(
            date=row['earnings_date'],
            type=row['earnings_type'],
            days_until=days,
            proximity=_classify_proximity(days),
        )
    return result


def attach_next_earnings(diaries, today=None):
    """日記群へ `diary.next_earnings`（NextEarnings or None）を付与する。

    一覧表示で使う。渡された全件分の決算予定を1クエリでまとめて引く。
    """
    diaries = list(diaries)
    symbols = {d.stock_symbol for d in diaries if d.stock_symbol}
    mapping = get_next_earnings_map(symbols, today=today)
    for diary in diaries:
        diary.next_earnings = mapping.get(diary.stock_symbol)
    return diaries


def build_month_grid(year, month, today, window_start, window_end,
                     counts, mine_dates, selected_date):
    """月グリッド（週×7セル）を組む。

    各セルは date / in_month / count / has_mine / in_window / is_today /
    is_selected を持つ。`counts` は {date: 件数}、`mine_dates` は記録銘柄を
    含む日付の集合。
    """
    weeks = []
    for week in Calendar(firstweekday=0).monthdatescalendar(year, month):
        cells = []
        for day in week:
            cells.append({
                'date': day,
                'in_month': day.month == month,
                'count': counts.get(day, 0),
                'has_mine': day in mine_dates,
                'in_window': window_start <= day <= window_end,
                'is_today': day == today,
                'is_selected': day == selected_date,
            })
        weeks.append(cells)
    return weeks


def _scope_filter(qs, scope, user_symbols):
    """scope=mine のとき記録銘柄に絞る。記録銘柄が無ければ空。"""
    if scope == 'mine':
        if user_symbols:
            return qs.filter(securities_code__in=_candidate_codes(user_symbols))
        return qs.none()
    return qs


def _parse_month(value, default_first):
    """'YYYY-MM' を当月1日の date に。失敗時は default_first。"""
    if value:
        try:
            return datetime.strptime(value, '%Y-%m').date().replace(day=1)
        except ValueError:
            pass
    return default_first


def _parse_date(value):
    """'YYYY-MM-DD' を date に。失敗時は None。"""
    if value:
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            pass
    return None


@login_required
def earnings_calendar(request):
    """決算カレンダー（ハイブリッド型: 月グリッド＋選択日リスト）。

    GET パラメータ:
        scope: 'mine'（記録銘柄のみ・既定）/ 'all'（全銘柄）
        month: 'YYYY-MM'（表示月。既定=当月。当日〜90日の範囲にクランプ）
        date:  'YYYY-MM-DD'（選択日。既定=今日 or 当月で決算のある最初の日）
        panel=day: 指定時、HTMXで選択日パネルのみ返す
    """
    scope = request.GET.get('scope', 'mine')
    if scope not in ('mine', 'all'):
        scope = 'mine'

    today = date.today()
    window_start = today
    window_end = today + timedelta(days=CALENDAR_WINDOW_DAYS)
    ws_first = window_start.replace(day=1)
    we_first = window_end.replace(day=1)

    # 表示月を決定し、ウィンドウ（月単位）にクランプ
    month_first = _parse_month(request.GET.get('month'), today.replace(day=1))
    if month_first < ws_first:
        month_first = ws_first
    elif month_first > we_first:
        month_first = we_first
    year, month = month_first.year, month_first.month
    month_last = month_first.replace(day=monthrange(year, month)[1])

    # 記録銘柄（4桁）集合
    user_diaries = StockDiary.objects.filter(user=request.user, is_excluded=False)
    user_symbols = set(
        user_diaries
        .filter(stock_symbol__regex=r'^\d{4}$')
        .values_list('stock_symbol', flat=True)
    )

    # --- サマリー: 保有銘柄・ウォッチリスト（月・日に依らず常時表示） ---
    holdings = attach_next_earnings(
        user_diaries.filter(current_quantity__gt=0), today=today)
    holdings = sorted(
        [d for d in holdings if d.next_earnings],
        key=lambda d: d.next_earnings.date)

    watchlist = attach_next_earnings(
        user_diaries.filter(transaction_count=0), today=today)
    watchlist = sorted(
        [d for d in watchlist if d.next_earnings],
        key=lambda d: d.next_earnings.date)

    # --- 月グリッド用の集計（対象月のみ・軽量） ---
    month_qs = _scope_filter(
        EarningsSchedule.objects.filter(
            earnings_date__range=(month_first, month_last)),
        scope, user_symbols)
    counts = {
        row['earnings_date']: row['c']
        for row in month_qs.values('earnings_date').annotate(c=Count('id'))
    }
    # 記録銘柄を含む日（scope に依らずハイライト用に算出）
    if user_symbols:
        mine_dates = set(
            EarningsSchedule.objects
            .filter(earnings_date__range=(month_first, month_last),
                    securities_code__in=_candidate_codes(user_symbols))
            .values_list('earnings_date', flat=True).distinct()
        )
    else:
        mine_dates = set()

    # 選択日: パラメータ優先。なければ今日（当月内）→決算のある最初の日→月初
    selected_date = _parse_date(request.GET.get('date'))
    if not (selected_date and month_first <= selected_date <= month_last):
        if month_first <= today <= month_last:
            selected_date = today
        elif counts:
            selected_date = min(counts)
        else:
            selected_date = month_first

    grid = build_month_grid(
        year, month, today, window_start, window_end,
        counts, mine_dates, selected_date)

    # --- 選択日の決算一覧 ---
    day_qs = _scope_filter(
        EarningsSchedule.objects.filter(earnings_date=selected_date),
        scope, user_symbols).order_by('securities_code')
    day_items = []
    for schedule in day_qs:
        ticker = _to_ticker(schedule.securities_code)
        schedule.ticker_normalized = ticker
        schedule.is_mine = ticker in user_symbols
        day_items.append(schedule)

    # 月送りナビ（ウィンドウ外は None）
    prev_first = (month_first - timedelta(days=1)).replace(day=1)
    next_first = month_last + timedelta(days=1)
    prev_month = prev_first.strftime('%Y-%m') if prev_first >= ws_first else None
    next_month = next_first.strftime('%Y-%m') if next_first <= we_first else None

    context = {
        'scope': scope,
        'today': today,
        'window_days': CALENDAR_WINDOW_DAYS,
        'holdings': holdings,
        'watchlist': watchlist,
        'weekday_headers': WEEKDAY_HEADERS,
        'grid': grid,
        'month_label': f'{year}年{month}月',
        'month_value': month_first.strftime('%Y-%m'),
        'prev_month': prev_month,
        'next_month': next_month,
        'selected_date': selected_date,
        'day_items': day_items,
    }

    is_htmx = (
        request.headers.get('HX-Request') == 'true'
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    )
    if is_htmx and request.GET.get('panel') == 'day':
        return render(
            request, 'stockdiary/partials/earnings_calendar_day.html', context)
    if is_htmx:
        return render(
            request, 'stockdiary/partials/earnings_calendar_month.html', context)
    return render(request, 'stockdiary/earnings_calendar.html', context)
