# stockdiary/api_analysis.py
"""
Claude Code などの外部ツール向け 読み取り専用分析API。
認証: Authorization: Bearer <ANALYSIS_API_KEY> ヘッダー。
キーは環境変数 ANALYSIS_API_KEY で設定（manage.py generate_analysis_key で生成）。
従量課金なし: ニュースは yfinance.news（無料）を使用。
"""
import logging
from datetime import datetime, timezone as dt_timezone
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import StockDiary
from .utils import is_japanese_stock

logger = logging.getLogger(__name__)


def _require_analysis_key(view_func):
    """ANALYSIS_API_KEY による Bearer 認証デコレータ"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        expected = getattr(settings, 'ANALYSIS_API_KEY', None)
        if not expected:
            return JsonResponse(
                {'error': 'ANALYSIS_API_KEY が未設定です。manage.py generate_analysis_key を実行してください'},
                status=503,
            )
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer ') or auth[7:] != expected:
            return JsonResponse({'error': '認証失敗'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


def _fetch_yfinance_news(stock_symbol: str, limit: int = 10) -> list[dict]:
    """yfinance でニュースを取得（無料）"""
    try:
        import yfinance as yf
        ticker_symbol = f"{stock_symbol}.T" if is_japanese_stock(stock_symbol) else stock_symbol
        ticker = yf.Ticker(ticker_symbol)
        raw_news = ticker.news or []
        results = []
        for item in raw_news[:limit]:
            # yfinance v0.2 以降は content_dict 構造が変わる場合があるため両対応
            content = item.get('content') or item
            title = content.get('title') or item.get('title', '')
            link = (
                (content.get('canonicalUrl') or {}).get('url')
                or content.get('clickThroughUrl', {}).get('url')
                or item.get('link', '')
            )
            publisher = (
                (content.get('provider') or {}).get('displayName')
                or item.get('publisher', '')
            )
            pub_ts = item.get('providerPublishTime') or (content.get('pubDate') and None)
            if pub_ts:
                try:
                    pub_date = datetime.fromtimestamp(pub_ts, tz=dt_timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
                except Exception:
                    pub_date = str(pub_ts)
            else:
                pub_date = content.get('pubDate', '')
            results.append({
                'title': title,
                'publisher': publisher,
                'published_at': pub_date,
                'url': link,
            })
        return results
    except Exception as e:
        logger.warning("yfinance news fetch failed for %s: %s", stock_symbol, e)
        return []


# ------------------------------------------------------------------ #
#  エンドポイント
# ------------------------------------------------------------------ #

@require_GET
@_require_analysis_key
def holdings(request):
    """
    現在保有中の銘柄一覧。

    GET /api/analysis/holdings/
    Authorization: Bearer <key>
    """
    diaries = (
        StockDiary.objects
        .filter(user__isnull=False, current_quantity__gt=0)
        .order_by('-first_purchase_date')
        .values(
            'id', 'stock_symbol', 'stock_name', 'sector',
            'current_quantity', 'average_purchase_price',
            'realized_profit', 'first_purchase_date',
            'user__username',
        )
    )
    return JsonResponse({
        'count': len(list(diaries)),
        'holdings': [
            {
                'id': d['id'],
                'symbol': d['stock_symbol'],
                'name': d['stock_name'],
                'sector': d['sector'],
                'quantity': float(d['current_quantity']),
                'avg_cost': float(d['average_purchase_price']) if d['average_purchase_price'] else None,
                'realized_profit': float(d['realized_profit']),
                'since': d['first_purchase_date'].isoformat() if d['first_purchase_date'] else None,
                'user': d['user__username'],
            }
            for d in diaries
        ],
    })


@require_GET
@_require_analysis_key
def diary_detail(request, symbol: str):
    """
    指定銘柄の日記全データ + 最新ニュース（yfinance 無料）。

    GET /api/analysis/diary/<symbol>/
    Authorization: Bearer <key>

    ?user=<username>  複数ユーザー環境で絞り込む場合に使用
    ?news=0           ニュース取得をスキップ（高速化）
    """
    symbol = symbol.upper().strip()
    qs = StockDiary.objects.filter(stock_symbol__iexact=symbol)

    username = request.GET.get('user', '').strip()
    if username:
        qs = qs.filter(user__username=username)

    diary = qs.prefetch_related('transactions', 'notes', 'tags').first()
    if not diary:
        return JsonResponse({'error': f'{symbol} の日記が見つかりません'}, status=404)

    transactions = [
        {
            'date': t.transaction_date.isoformat(),
            'type': t.transaction_type,
            'price': float(t.price),
            'quantity': float(t.quantity),
            'amount': float(t.amount),
            'is_margin': t.is_margin,
            'memo': t.memo,
        }
        for t in diary.transactions.order_by('transaction_date')
    ]

    notes = [
        {
            'date': n.date.isoformat(),
            'type': n.note_type,
            'topic': n.topic,
            'content': n.content,
        }
        for n in diary.notes.order_by('date')
    ]

    tags = list(diary.tags.values_list('name', flat=True))

    # ステータス判定
    if diary.current_quantity > 0:
        status = '保有中'
    elif diary.transaction_count > 0:
        status = '売却済み'
    else:
        status = 'メモ'

    # ニュース（デフォルトON、?news=0 でスキップ）
    fetch_news = request.GET.get('news', '1') != '0'
    news = _fetch_yfinance_news(symbol) if fetch_news else []

    return JsonResponse({
        'symbol': symbol,
        'name': diary.stock_name,
        'status': status,
        'sector': diary.sector,
        'tags': tags,
        'investment_reason': diary.reason or '',
        'first_purchase_date': diary.first_purchase_date.isoformat() if diary.first_purchase_date else None,
        'current_quantity': float(diary.current_quantity),
        'avg_cost': float(diary.average_purchase_price) if diary.average_purchase_price else None,
        'realized_profit': float(diary.realized_profit),
        'transaction_count': diary.transaction_count,
        'transactions': transactions,
        'notes': notes,
        'latest_news': news,
        'fetched_at': datetime.now(tz=dt_timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
    })


@require_GET
@_require_analysis_key
def portfolio_summary(request):
    """
    ポートフォリオ全体サマリー（業種分布・損益統計）。

    GET /api/analysis/portfolio/
    Authorization: Bearer <key>
    """
    from django.db.models import Sum, Count, Q

    qs = StockDiary.objects.filter(user__isnull=False)

    agg = qs.aggregate(
        total_diaries=Count('id'),
        holding_count=Count('id', filter=Q(current_quantity__gt=0)),
        sold_count=Count('id', filter=Q(transaction_count__gt=0, current_quantity=0)),
        total_realized_profit=Sum('realized_profit'),
    )

    # 業種分布（保有中のみ）
    sector_dist = (
        qs.filter(current_quantity__gt=0)
        .values('sector')
        .annotate(count=Count('id'), realized=Sum('realized_profit'))
        .order_by('-count')
    )

    return JsonResponse({
        'total_diaries': agg['total_diaries'],
        'holding_count': agg['holding_count'],
        'sold_count': agg['sold_count'],
        'total_realized_profit': float(agg['total_realized_profit'] or 0),
        'sector_distribution': [
            {
                'sector': s['sector'] or '未分類',
                'holding_count': s['count'],
                'realized_profit': float(s['realized'] or 0),
            }
            for s in sector_dist
        ],
    })
