# stockdiary/api_analysis.py
"""
Claude Code などの外部ツール向け分析API（読み取り＋書き込み）。

認証: Authorization: Bearer <ANALYSIS_API_KEY> ヘッダー。
書き込み先ユーザー: 環境変数 ANALYSIS_API_USER で固定（サーバー側で決まる）。

セットアップ:
    python manage.py generate_analysis_key
    # .env に ANALYSIS_API_KEY と ANALYSIS_API_USER を追記
    # gunicorn reload

従量課金なし: ニュースは yfinance.news（無料）を使用。
"""
import json
import logging
from datetime import date, datetime, timezone as dt_timezone
from functools import wraps

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .models import DiaryNote, ReasonVersion, StockDiary
from .utils import is_japanese_stock

logger = logging.getLogger(__name__)
User = get_user_model()

# ------------------------------------------------------------------ #
#  共通ヘルパー
# ------------------------------------------------------------------ #

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


def _get_api_user():
    """
    書き込み操作の対象ユーザーを返す。
    ANALYSIS_API_USER 環境変数で固定（呼び出し元からは変更不可）。
    """
    username = getattr(settings, 'ANALYSIS_API_USER', '').strip()
    if not username:
        return None, JsonResponse(
            {'error': 'ANALYSIS_API_USER が未設定です。.env に追記してサーバーを再起動してください'},
            status=503,
        )
    try:
        return User.objects.get(username=username), None
    except User.DoesNotExist:
        return None, JsonResponse(
            {'error': f'ユーザー "{username}" が存在しません。ANALYSIS_API_USER を確認してください'},
            status=503,
        )


def _sync_diary_tags(diary, user) -> list[str]:
    """本文（reason＋全ノート）の @タグを diary.tags へ同期し、結果のタグ名を返す。

    UI の保存フローと同じ正本ロジック（views._sync_hashtag_tags）を使い、
    タグの追加・解除・方向(↑/↓/→)・df 再計算まで行う。分析API経由の書き込みでも
    本文中の `@タグ` がタグ欄へ反映されるように、reason/note の保存後に呼ぶ。
    """
    from .views import _sync_hashtag_tags  # 循環インポート回避のため遅延 import
    _sync_hashtag_tags(diary, user)
    return list(diary.tags.values_list('name', flat=True))


def _fetch_margin_data(symbol: str, weeks: int = 8) -> dict | None:
    """信用取引残高（JPX週次）の最新値＋直近トレンドを返す。

    margin_tracking.MarginData（銘柄コード単位・週次）から取得する。
    信用倍率 = 買い残 / 売り残（1未満は売り長＝取組良好の目安、過大は上値の重し）。
    データが無い銘柄（外国株・未取得）は None を返す。
    """
    try:
        from margin_tracking.models import MarginData
    except Exception:
        return None

    rows = list(
        MarginData.objects
        .filter(stock_code=symbol)
        .order_by('-record_date')[:weeks]
    )
    if not rows:
        return None

    def _row(m):
        return {
            'date': m.record_date.isoformat(),
            'long_balance': m.long_balance,
            'short_balance': m.short_balance,
            'margin_ratio': float(m.margin_ratio) if m.margin_ratio is not None else None,
        }

    latest = rows[0]
    history = [_row(m) for m in reversed(rows)]  # 古い→新しい
    return {
        'latest': _row(latest),
        'history': history,  # 直近 weeks 週（古い順）
        'note': '信用倍率 = 買い残 / 売り残。1倍未満は売り長（取組良好）、'
                '高倍率・買い残増は将来の戻り売り圧力（上値の重し）の目安。',
    }


def _fetch_yfinance_news(stock_symbol: str, limit: int = 10) -> list[dict]:
    """yfinance でニュースを取得（無料）"""
    try:
        import yfinance as yf
        ticker_symbol = f"{stock_symbol}.T" if is_japanese_stock(stock_symbol) else stock_symbol
        ticker = yf.Ticker(ticker_symbol)
        raw_news = ticker.news or []
        results = []
        for item in raw_news[:limit]:
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
            pub_ts = item.get('providerPublishTime') or None
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
#  読み取りエンドポイント
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
    rows = list(diaries)
    return JsonResponse({
        'count': len(rows),
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
            for d in rows
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
            'id': n.id,
            'date': n.date.isoformat(),
            'type': n.note_type,
            'topic': n.topic,
            'content': n.content,
        }
        for n in diary.notes.order_by('date')
    ]

    tags = list(diary.tags.values_list('name', flat=True))

    if diary.current_quantity > 0:
        status = '保有中'
    elif diary.transaction_count > 0:
        status = '売却済み'
    else:
        status = 'メモ'

    fetch_news = request.GET.get('news', '1') != '0'
    news = _fetch_yfinance_news(symbol) if fetch_news else []

    fetch_margin = request.GET.get('margin', '1') != '0'
    margin = _fetch_margin_data(symbol) if fetch_margin else None

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
        'margin': margin,
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
    from django.db.models import Count, Q, Sum

    qs = StockDiary.objects.filter(user__isnull=False)

    agg = qs.aggregate(
        total_diaries=Count('id'),
        holding_count=Count('id', filter=Q(current_quantity__gt=0)),
        sold_count=Count('id', filter=Q(transaction_count__gt=0, current_quantity=0)),
        total_realized_profit=Sum('realized_profit'),
    )

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


def _diary_status(diary) -> str:
    if diary.current_quantity > 0:
        return '保有中'
    if diary.transaction_count > 0:
        return '売却済み'
    return 'メモ'


@require_GET
@_require_analysis_key
def list_diaries(request):
    """
    記録銘柄の一覧（スクリーニング用・保有/売却/メモを横断）。

    GET /api/analysis/diaries/
    Authorization: Bearer <key>

    クエリ:
      ?tags=半導体,AI   いずれかのタグを持つ日記に絞る（OR）
      ?sector=電気       業種の部分一致で絞る
      ?status=holding|sold|memo|all（既定 all）
      ?user=<username>   複数ユーザー環境での絞り込み

    各銘柄に最新の信用倍率（margin_ratio）を付与する（バリュエーションは
    呼び出し側で yfinance 等から補完する想定＝サーバ側で外部APIは叩かない）。
    """
    qs = StockDiary.objects.filter(user__isnull=False).prefetch_related('tags')

    username = request.GET.get('user', '').strip()
    if username:
        qs = qs.filter(user__username=username)

    status = request.GET.get('status', 'all').strip()
    if status == 'holding':
        qs = qs.filter(current_quantity__gt=0)
    elif status == 'sold':
        qs = qs.filter(current_quantity=0, transaction_count__gt=0)
    elif status == 'memo':
        qs = qs.filter(transaction_count=0)

    sector = request.GET.get('sector', '').strip()
    if sector:
        qs = qs.filter(sector__icontains=sector)

    tags_param = request.GET.get('tags', '').strip()
    want_tags = [t.strip().lstrip('@') for t in tags_param.split(',') if t.strip()]
    if want_tags:
        qs = qs.filter(tags__name__in=want_tags).distinct()

    # 最新週の信用倍率をまとめて引く（JPX週次は全銘柄同一 record_date のため1クエリ）
    margin_map = {}
    try:
        from django.db.models import Max
        from margin_tracking.models import MarginData
        latest_date = MarginData.objects.aggregate(d=Max('record_date'))['d']
        if latest_date:
            margin_map = {
                m.stock_code: float(m.margin_ratio) if m.margin_ratio is not None else None
                for m in MarginData.objects.filter(record_date=latest_date)
            }
    except Exception:
        margin_map = {}

    diaries = []
    for d in qs.order_by('stock_symbol'):
        diaries.append({
            'symbol': d.stock_symbol,
            'name': d.stock_name,
            'status': _diary_status(d),
            'sector': d.sector,
            'tags': list(d.tags.values_list('name', flat=True)),
            'current_quantity': float(d.current_quantity),
            'realized_profit': float(d.realized_profit),
            'latest_disclosure_date': (
                d.latest_disclosure_date.isoformat() if d.latest_disclosure_date else None
            ),
            'margin_ratio': margin_map.get(d.stock_symbol),
        })

    return JsonResponse({'count': len(diaries), 'diaries': diaries})


# ------------------------------------------------------------------ #
#  書き込みエンドポイント
# ------------------------------------------------------------------ #

_VALID_NOTE_TYPES = {c[0] for c in DiaryNote.TYPE_CHOICES}


@csrf_exempt
@require_http_methods(['POST'])
@_require_analysis_key
def add_note(request, symbol: str):
    """
    継続記録（DiaryNote）を追加する。

    POST /api/analysis/diary/<symbol>/notes/
    Authorization: Bearer <key>
    Content-Type: application/json

    {
      "content":   "分析内容...",          // 必須
      "note_type": "analysis",             // 省略可（デフォルト: analysis）
                                           //   analysis / news / earnings /
                                           //   insight / risk / retrospective / other
      "topic":     "決算後の見直し",       // 省略可（retrospective 以外は任意）
      "date":      "2024-01-15"            // 省略可（デフォルト: 今日）
    }

    書き込み先ユーザーは ANALYSIS_API_USER 環境変数で固定（呼び出し元からは変更不可）。
    """
    user, err = _get_api_user()
    if err:
        return err

    symbol = symbol.upper().strip()
    diary = StockDiary.objects.filter(
        stock_symbol__iexact=symbol, user=user
    ).first()
    if not diary:
        return JsonResponse(
            {'error': f'{symbol} の日記が見つかりません（ユーザー: {user.username}）'},
            status=404,
        )

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'リクエストボディが不正な JSON です'}, status=400)

    content = (body.get('content') or '').strip()
    if not content:
        return JsonResponse({'error': 'content は必須です'}, status=400)
    if len(content) > 5000:
        return JsonResponse({'error': 'content は 5000 文字以内にしてください'}, status=400)

    note_type = (body.get('note_type') or 'analysis').strip()
    if note_type not in _VALID_NOTE_TYPES:
        return JsonResponse(
            {'error': f'note_type が不正です。使用可能: {sorted(_VALID_NOTE_TYPES)}'},
            status=400,
        )

    topic = (body.get('topic') or '').strip()

    raw_date = body.get('date')
    if raw_date:
        try:
            note_date = date.fromisoformat(raw_date)
        except ValueError:
            return JsonResponse({'error': 'date は YYYY-MM-DD 形式で指定してください'}, status=400)
    else:
        note_date = date.today()

    note = DiaryNote(
        diary=diary,
        content=content,
        note_type=note_type,
        topic=topic,
        date=note_date,
    )
    try:
        note.full_clean()
        note.save()
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)

    synced_tags = _sync_diary_tags(diary, user)

    return JsonResponse({
        'success': True,
        'note_id': note.id,
        'symbol': symbol,
        'diary_name': diary.stock_name,
        'note_type': note.note_type,
        'topic': note.topic,
        'date': note.date.isoformat(),
        'content_length': len(note.content),
        'tags': synced_tags,
    }, status=201)


@csrf_exempt
@require_http_methods(['DELETE'])
@_require_analysis_key
def delete_note(request, symbol: str, note_id: int):
    """
    継続記録（DiaryNote）を1件削除する。

    DELETE /api/analysis/diary/<symbol>/notes/<note_id>/
    Authorization: Bearer <key>

    削除後は reason＋残りノートの和集合でタグを再同期する
    （削除したノートにしか無かった @タグはタグ欄からも解除される）。
    書き込み先ユーザーは ANALYSIS_API_USER 環境変数で固定。
    """
    user, err = _get_api_user()
    if err:
        return err

    symbol = symbol.upper().strip()
    diary = StockDiary.objects.filter(
        stock_symbol__iexact=symbol, user=user
    ).first()
    if not diary:
        return JsonResponse(
            {'error': f'{symbol} の日記が見つかりません（ユーザー: {user.username}）'},
            status=404,
        )

    note = diary.notes.filter(id=note_id).first()
    if not note:
        return JsonResponse(
            {'error': f'ノート(id={note_id}) が {symbol} の日記に見つかりません'},
            status=404,
        )

    note.delete()
    synced_tags = _sync_diary_tags(diary, user)

    return JsonResponse({
        'success': True,
        'symbol': symbol,
        'diary_name': diary.stock_name,
        'deleted_note_id': note_id,
        'tags': synced_tags,
    })


@csrf_exempt
@require_http_methods(['PATCH'])
@_require_analysis_key
def update_reason(request, symbol: str):
    """
    投資理由（reason）を更新する。上書き前の内容は ReasonVersion に自動退避される。

    PATCH /api/analysis/diary/<symbol>/
    Authorization: Bearer <key>
    Content-Type: application/json

    {
      "reason": "更新後の投資理由テキスト..."  // 必須
    }

    書き込み先ユーザーは ANALYSIS_API_USER 環境変数で固定（呼び出し元からは変更不可）。
    """
    user, err = _get_api_user()
    if err:
        return err

    symbol = symbol.upper().strip()
    diary = StockDiary.objects.filter(
        stock_symbol__iexact=symbol, user=user
    ).first()
    if not diary:
        return JsonResponse(
            {'error': f'{symbol} の日記が見つかりません（ユーザー: {user.username}）'},
            status=404,
        )

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'リクエストボディが不正な JSON です'}, status=400)

    new_reason = (body.get('reason') or '').strip()
    if not new_reason:
        return JsonResponse({'error': 'reason は必須です'}, status=400)

    old_reason = diary.reason or ''
    diary.reason = new_reason

    try:
        diary.full_clean(exclude=['user', 'stock_name'])
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)

    diary.save(update_fields=['reason', 'updated_at'])
    snapshot = ReasonVersion.snapshot_on_change(diary, old_reason)

    synced_tags = _sync_diary_tags(diary, user)

    return JsonResponse({
        'success': True,
        'symbol': symbol,
        'diary_name': diary.stock_name,
        'reason_updated': True,
        'snapshot_created': snapshot is not None,
        'reason_length': len(new_reason),
        'tags': synced_tags,
    })
