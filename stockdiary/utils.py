"""
stockdiary app utility functions
"""
import re
from typing import List, Set, Dict, Any, Tuple
from collections import defaultdict


def extract_hashtags(text: str) -> List[str]:
    """
    テキストからハッシュタグを抽出する（@記号を使用）

    Args:
        text: 検索対象のテキスト

    Returns:
        抽出されたハッシュタグのリスト（@を除く、重複なし）

    Examples:
        >>> extract_hashtags("投資理由 @成長株 @配当")
        ['成長株', '配当']
        >>> extract_hashtags("# 見出し\\n@成長株")
        ['成長株']

    ルール:
        - @の後に日本語、英数字、アンダースコアが続く場合にハッシュタグとして扱う
        - マークダウンと競合しない
    """
    if not text:
        return []

    # ハッシュタグのパターン: @の後に日本語、英数字、アンダースコア、& が続く
    # [\u3040-\u309F] - ひらがな
    # [\u30A0-\u30FF] - カタカナ
    # [\u4E00-\u9FFF] - 漢字
    # [a-zA-Z0-9_&] - 英数字・アンダースコア・&（「M&A」のような表記に対応）
    pattern = r'@([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\uFF66-\uFF9Fa-zA-Z0-9_&]+)'

    matches = re.findall(pattern, text)

    # 重複を除去して順序を保持
    seen = set()
    unique_tags = []
    for tag in matches:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)

    return unique_tags


def is_japanese_stock(code: str) -> bool:
    """日本株コードか判定（例: 7203, 262A, 1234D など数字+任意1文字）"""
    if not code:
        return False
    return bool(re.fullmatch(r'\d{3,4}[A-Z]?', code, re.IGNORECASE))


def detect_currency(stock_symbol: str) -> str:
    """銘柄コードから通貨を判定する。

    日本株コード（数字3〜4桁+任意1文字）なら 'JPY'、
    それ以外（米国株ティッカー等）は 'USD' とみなす。

    Args:
        stock_symbol: 銘柄コード（例: '7203', 'AAPL'）

    Returns:
        'JPY' または 'USD'
    """
    return 'JPY' if is_japanese_stock(stock_symbol) else 'USD'


def get_all_hashtags_from_queryset(queryset) -> List[dict]:
    """
    QuerySetから全てのハッシュタグを抽出し、使用回数とともに返す

    Args:
        queryset: StockDiaryのQuerySet

    Returns:
        [{'tag': 'タグ名', 'count': 使用回数}, ...] の形式のリスト
        使用回数の降順でソート
    """
    from collections import Counter

    all_tags = []
    for diary in queryset:
        if diary.reason:
            tags = extract_hashtags(diary.reason)
            all_tags.extend(tags)

    # カウントして辞書形式に変換
    tag_counter = Counter(all_tags)

    result = [
        {'tag': tag, 'count': count}
        for tag, count in tag_counter.most_common()
    ]

    return result


def search_diaries_by_hashtag(queryset, hashtag: str):
    """
    ハッシュタグで日記を絞り込む

    Args:
        queryset: StockDiaryのQuerySet
        hashtag: 検索するハッシュタグ（@あり/なし両方対応）

    Returns:
        絞り込まれたQuerySet
    """
    from django.db.models import Q

    # @を除去
    tag = hashtag.lstrip('@').strip()

    if not tag:
        return queryset

    # 投資理由（reason）と継続記録（DiaryNote.content）の両方から @タグ を検索
    # 前後に空白や改行がある場合も考慮
    return queryset.filter(
        Q(reason__icontains=f'@{tag}') |
        Q(notes__content__icontains=f'@{tag}')
    ).distinct()


def apply_diary_search(queryset, query: str):
    """日記の全文検索を適用する。

    銘柄名・銘柄コード・投資理由・メモ・業種に加え、
    継続記録（DiaryNote.content / topic）も横断して検索する。
    `@タグ` のみが入力された場合は search_diaries_by_hashtag に委譲する。

    Args:
        queryset: StockDiary の QuerySet
        query: 検索文字列

    Returns:
        絞り込まれた QuerySet（notes 結合による重複は distinct で排除）
    """
    from django.db.models import Q

    q = (query or '').strip()
    if not q:
        return queryset

    # 単独の @タグ はハッシュタグ検索（reason + 継続記録）に委譲
    if q.startswith('@') and ' ' not in q and '　' not in q:
        return search_diaries_by_hashtag(queryset, q)

    return queryset.filter(
        Q(stock_name__icontains=q) |
        Q(stock_symbol__icontains=q) |
        Q(reason__icontains=q) |
        Q(memo__icontains=q) |
        Q(sector__icontains=q) |
        Q(notes__content__icontains=q) |
        Q(notes__topic__icontains=q)
    ).distinct()


def _make_search_snippet(text: str, query: str, radius: int = 40) -> str:
    """検索語の周辺を切り出した抜粋テキストを返す（ハイライトは呼び出し側で行う）。"""
    if not text or not query:
        return ''
    lower = text.lower()
    idx = lower.find(query.lower())
    if idx == -1:
        return text[:radius * 2].strip()
    start = max(0, idx - radius)
    end = min(len(text), idx + len(query) + radius)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = '…' + snippet
    if end < len(text):
        snippet = snippet + '…'
    return snippet


def annotate_search_matches(diaries, query: str):
    """表示中の日記リストに、検索語がどこにヒットしたかの情報を付与する。

    各 diary に以下の属性を設定する:
        - match_name:         銘柄名・銘柄コードに一致したか（bool）
        - match_body:         投資理由・メモ・業種に一致したか（bool）
        - match_note:         一致した継続記録（DiaryNote）または None
        - match_note_count:   一致した継続記録の件数（int）
        - match_note_snippet: 一致した継続記録本文の抜粋（str）

    queryset は prefetch_related('notes') 済みであることを前提とし、
    追加クエリを発行しない（表示中のページ分のみを対象に Python で判定）。

    Args:
        diaries: StockDiary の反復可能オブジェクト（ページの object_list 等）
        query: 検索文字列

    Returns:
        diaries（同じオブジェクトを属性付きで返す）
    """
    q = (query or '').strip()
    for diary in diaries:
        if not q:
            diary.match_name = False
            diary.match_body = False
            diary.match_note = None
            diary.match_note_count = 0
            diary.match_note_snippet = ''
            continue

        ql = q.lstrip('@').strip().lower() if q.startswith('@') else q.lower()

        diary.match_name = (
            ql in (diary.stock_name or '').lower()
            or ql in (diary.stock_symbol or '').lower()
        )
        diary.match_body = (
            ql in (diary.reason or '').lower()
            or ql in (diary.memo or '').lower()
            or ql in (diary.sector or '').lower()
        )

        matched_notes = [
            note for note in diary.notes.all()
            if ql in (note.content or '').lower() or ql in (note.topic or '').lower()
        ]
        diary.match_note = matched_notes[0] if matched_notes else None
        diary.match_note_count = len(matched_notes)
        diary.match_note_snippet = (
            _make_search_snippet(matched_notes[0].content or '', ql) if matched_notes else ''
        )

    return diaries


def hub_weight(diary_count: int) -> float:  # noqa: keep for sector/hashtag modes
    """ハブの次数(diary_count)から逆頻度の重みを算出する。

    少数の銘柄しか結ばないハブ（希少な関連）ほど強く、
    全銘柄に付くようなハブ（ノイズ）ほど 0 に近づく。

        N=2  -> 1.0   （2銘柄だけを結ぶ＝最も強い関連）
        N=3  -> 0.5
        N=6  -> 0.2
        N=11 -> 0.1
    """
    return round(1.0 / max(diary_count - 1, 1), 4)


def get_tag_graph_data(diaries_qs) -> Dict[str, Any]:
    """
    タグハブノードと diary→tag エッジを生成する。

    各エッジ・ハブには逆頻度の `weight`（希少な関連ほど大）と、
    他銘柄に繋がらないハブを示す `is_isolated` を付与する。

    Args:
        diaries_qs: prefetch_related('tags') 済みの StockDiary QuerySet

    Returns:
        {
            'tag_nodes': [{'id': 'tag_<pk>', 'node_type': 'tag', 'tag_name': str,
                           'tag_pk': int, 'diary_count': int, 'weight': float, 'is_isolated': bool}],
            'edges':     [{'source': <diary_id>, 'target': 'tag_<pk>', 'edge_type': 'tag', 'weight': float}]
        }
    """
    tag_diary_count: Dict[int, int] = defaultdict(int)
    tag_meta: Dict[int, dict] = {}
    edges: List[dict] = []

    for diary in diaries_qs:
        for tag in diary.tags.all():
            tag_diary_count[tag.pk] += 1
            if tag.pk not in tag_meta:
                tag_meta[tag.pk] = {
                    'name': tag.name,
                    'axis': getattr(tag, 'axis', 'theme'),
                }
            edges.append({
                'source': diary.pk,
                'target': f'tag_{tag.pk}',
                'edge_type': 'tag',
                'axis': getattr(tag, 'axis', 'theme'),
            })

    # 方向属性（DiaryTagDirection）を一括取得してエッジに付与
    # ── マクロ/テーマのハブから「追い風(up)/向かい風(down)」が放射状に分かれて見えるようにする
    from .models import DiaryTagDirection
    dir_map: Dict[tuple, str] = {}
    diary_ids = {e['source'] for e in edges}
    if diary_ids and tag_meta:
        for diary_id, tag_id, direction in DiaryTagDirection.objects.filter(
            diary_id__in=diary_ids, tag_id__in=tag_meta.keys()
        ).values_list('diary_id', 'tag_id', 'direction'):
            dir_map[(diary_id, tag_id)] = direction

    # 全カウント確定後に逆頻度の重みを付与
    for e in edges:
        pk = int(e['target'].split('_', 1)[1])
        e['weight'] = hub_weight(tag_diary_count[pk])
        e['direction'] = dir_map.get((e['source'], pk), 'neutral')

    tag_nodes = [
        {
            'id': f'tag_{pk}',
            'node_type': 'tag',
            'tag_name': meta['name'],
            'tag_pk': pk,
            'axis': meta.get('axis', 'theme'),
            'diary_count': tag_diary_count[pk],
            'weight': hub_weight(tag_diary_count[pk]),
            'is_isolated': tag_diary_count[pk] <= 1,
        }
        for pk, meta in tag_meta.items()
    ]

    return {'tag_nodes': tag_nodes, 'edges': edges}


def get_sector_graph_data(diaries_qs, company_sector_map: Dict[str, str] = None) -> Dict[str, Any]:
    """
    業種ハブノードと diary→sector エッジを生成する。

    Args:
        diaries_qs: StockDiary QuerySet（sector フィールドを含む）
        company_sector_map: stock_symbol -> 業種名 の辞書（sector が空の日記を補完する）

    Returns:
        {
            'sector_nodes': [{'id': 'sec_<name>', 'node_type': 'sector', 'sector_name': str, 'diary_count': int}],
            'edges':        [{'source': <diary_id>, 'target': 'sec_<name>', 'edge_type': 'sector'}]
        }
    """
    sector_diary_count: Dict[str, int] = defaultdict(int)
    edges: List[dict] = []
    UNKNOWN = '未分類'

    for diary in diaries_qs:
        sector_name = (diary.sector or '').strip()
        # sector が未設定の場合は company_sector_map から補完
        if not sector_name and company_sector_map:
            sector_name = company_sector_map.get(diary.stock_symbol or '', '')
        sector_name = sector_name or UNKNOWN
        sector_id = f'sec_{sector_name}'
        sector_diary_count[sector_name] += 1
        edges.append({
            'source': diary.pk,
            'target': sector_id,
            'edge_type': 'sector',
        })

    # 全カウント確定後に逆頻度の重みを付与
    for e in edges:
        name = e['target'].split('_', 1)[1]
        e['weight'] = hub_weight(sector_diary_count[name])

    sector_nodes = [
        {
            'id': f'sec_{name}',
            'node_type': 'sector',
            'sector_name': name,
            'diary_count': count,
            'weight': hub_weight(count),
            'is_isolated': count <= 1,
        }
        for name, count in sector_diary_count.items()
    ]

    return {'sector_nodes': sector_nodes, 'edges': edges}


def get_hashtag_graph_data(
    diaries_qs,
    note_limit: int | None = None,
    user_tag_axis_map: Dict[str, str] | None = None,
    user_tag_dir_map: Dict[tuple, str] | None = None,
) -> Dict[str, Any]:
    """
    @ハッシュタグが共通する日記同士をエッジで繋ぐ。
    ハッシュタグをハブノードとして追加する。
    reason フィールドに加え、継続記録（DiaryNote.content）も対象にする。

    Args:
        diaries_qs: prefetch_related('notes') 済みの StockDiary QuerySet
        note_limit: 各日記の継続記録を直近N件に制限する。None で全件。
        user_tag_axis_map: Tag M2M から取得した {タグ名: 軸} マップ（軸オーバーライド用）
        user_tag_dir_map: {(diary_id, タグ名): 方向} マップ。@ハッシュタグは
            _sync_hashtag_tags で同名の Tag(M2M) に同期されるため、その Tag に
            設定された方向（DiaryTagDirection）をエッジに付与し、タグモードと
            同様に追い風(up)/向かい風(down)で着色できるようにする。

    軸決定の優先順位:
        1. user_tag_axis_map（Tag M2M でユーザーが明示設定）
        2. 標準タグ（MasterTag, get_master_axis_map()）
        3. デフォルト 'theme'

    Returns:
        {
            'hashtag_nodes': [{'id': 'ht_<tag>', 'node_type': 'hashtag', 'tag_name': str,
                               'diary_count': int, 'axis': str, 'is_isolated': bool}],
            'edges':         [{'source': <diary_id>, 'target': 'ht_<tag>',
                               'edge_type': 'hashtag', 'axis': str}]
        }
    """
    from .tag_axis_config import get_master_axis_map
    master_axis_map = get_master_axis_map()

    def _axis(name: str) -> str:
        if user_tag_axis_map and name in user_tag_axis_map:
            return user_tag_axis_map[name]
        return master_axis_map.get(name, 'theme')

    ht_diary_count: Dict[str, int] = defaultdict(int)
    edges: List[dict] = []

    for diary in diaries_qs:
        # 同一日記からの重複エッジを防ぐため、この日記で発見済みのタグを追跡
        seen_tags: Set[str] = set()

        texts = [diary.reason or '']
        try:
            notes = diary.notes.all()
            if note_limit is not None:
                # prefetch済みのデータをPythonでソートして件数制限（直近N件）
                notes = sorted(notes, key=lambda n: n.date, reverse=True)[:note_limit]
            texts.extend(note.content for note in notes if note.content)
        except AttributeError:
            pass

        for text in texts:
            for tag in extract_hashtags(text):
                if tag in seen_tags:
                    continue
                seen_tags.add(tag)
                ht_id = f'ht_{tag}'
                ht_diary_count[tag] += 1
                edges.append({
                    'source': diary.pk,
                    'target': ht_id,
                    'edge_type': 'hashtag',
                    'axis': _axis(tag),
                })

    # 全カウント確定後に逆頻度の重みと方向（追い風/向かい風）を付与
    for e in edges:
        tag = e['target'].split('_', 1)[1]
        e['weight'] = hub_weight(ht_diary_count[tag])
        e['direction'] = (
            user_tag_dir_map.get((e['source'], tag), 'neutral')
            if user_tag_dir_map else 'neutral'
        )

    hashtag_nodes = [
        {
            'id': f'ht_{tag}',
            'node_type': 'hashtag',
            'tag_name': tag,
            'diary_count': count,
            'axis': _axis(tag),
            'weight': hub_weight(count),
            'is_isolated': count <= 1,
        }
        for tag, count in ht_diary_count.items()
    ]

    return {'hashtag_nodes': hashtag_nodes, 'edges': edges}


def extract_stock_mentions(text: str) -> List[str]:
    """
    テキストから証券コードを抽出する（括弧内の数字・英数字）

    対応フォーマット:
        - (9101)  / （9101）  : 日本株・旧形式（4〜6桁数字）
        - (285A)  / （285A）  : 日本株・新形式（3〜4桁数字＋大文字1字）
        - (AAPL)  / （AAPL）  : 米国株・ETF（大文字2〜6字）

    Examples:
        >>> extract_stock_mentions("日本郵船(9101) / キオクシア(285A)")
        ['9101', '285A']
        >>> extract_stock_mentions("参考: AAPL(AAPL) / (USD)")
        ['AAPL', 'USD']
    """
    if not text:
        return []

    # 半角・全角括弧内の証券コードを抽出:
    #   \d{4,6}        : 純数字 4〜6桁（旧形式日本株）
    #   \d{3,4}[A-Z]   : 数字3〜4桁＋大文字1字（新形式 285A 等）
    #   [A-Z]{2,6}     : 大文字のみ 2〜6字（米国株・ETF）
    pattern = r'[（(](\d{4,6}|\d{3,4}[A-Z]|[A-Z]{2,6})[）)]'
    matches = re.findall(pattern, text)

    seen: Set[str] = set()
    unique: List[str] = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique


def get_mention_graph_data(
    primary_diaries,
    symbol_to_diary_id: Dict[str, int],
) -> Dict[str, Any]:
    """
    日記テキスト（reason / memo）内の銘柄コードメンションによるエッジを生成。

    Args:
        primary_diaries: StockDiary のリスト（reason, memo フィールドを含む）
        symbol_to_diary_id: stock_symbol -> diary_pk の辞書（全ユーザー日記）

    Returns:
        {
            'edges':                [{'source': diary_pk, 'target': diary_pk, 'edge_type': 'mention'}],
            'mentioned_diary_ids':  primary 外のメンション先 diary ID の set
        }
    """
    edges: List[dict] = []
    edge_set: Set[Tuple[int, int]] = set()
    mentioned_diary_ids: Set[int] = set()
    primary_id_set = {d.pk for d in primary_diaries}

    for diary in primary_diaries:
        text = (diary.reason or '') + ' ' + (getattr(diary, 'memo', '') or '')
        for symbol in extract_stock_mentions(text):
            target_id = symbol_to_diary_id.get(symbol)
            if not target_id or target_id == diary.pk:
                continue
            key = (min(diary.pk, target_id), max(diary.pk, target_id))
            if key not in edge_set:
                edge_set.add(key)
                edges.append({
                    'source': diary.pk,
                    'target': target_id,
                    'edge_type': 'mention',
                    'weight': 0.9,  # 本文の明示的言及は強い関連
                })
            if target_id not in primary_id_set:
                mentioned_diary_ids.add(target_id)

    return {'edges': edges, 'mentioned_diary_ids': mentioned_diary_ids}


# この数を超える銘柄が共有するタグ／業種／@タグは「付けすぎ＝ノイズ」とみなし、
# 関連サマリーから除外する（関連付けしすぎで見にくくなる問題への対策）。
RELATED_NOISE_MAX = 25


def compute_related_strength(focal, user, limit: int = 12) -> List[dict]:
    """フォーカル日記に対する他日記の「関連の強さ」を軸重み×IDF で算出する。

    [Phase 1+2 更新]
    - 共通タグのスコアを「軸重み × IDF」で計算（希少なテーマタグほど強く）
    - 最小条件: イベント軸以外の共有タグ2つ以上、または高希少テーマタグ1つ
    - イベント軸タグは関連度計算から除外

    Returns:
        score 降順の [{'diary': StockDiary, 'score': float,
                       'via': [{'type': str, 'label': str}]}] （最大 limit 件）
    """
    import math
    from django.db.models import Q
    from .models import StockDiary, DiaryNote
    from .tag_axis_config import (
        AXIS_WEIGHTS, MIN_SHARED_TAGS, RELATED_NOISE_MAX,
        MIN_N_FOR_THEMES, HIGH_RARITY_MAX_OTHERS, IMPLICIT_THEME_DISCOUNT,
    )

    scores: Dict[int, float] = defaultdict(float)
    reasons: Dict[int, List[dict]] = defaultdict(list)
    diary_cache: Dict[int, Any] = {}

    others = StockDiary.objects.filter(user=user).exclude(id=focal.id)
    # IDF 計算用の総銘柄数（ポートフォリオ全体）
    N = StockDiary.objects.filter(user=user, is_excluded=False).count() or 1
    # P1: 小標本では per-user IDF が不安定なため、テーマ段階を無効化する
    themes_enabled = N >= MIN_N_FOR_THEMES

    def _add(did: int, score: float, via: dict) -> None:
        scores[did] += score
        reasons[did].append(via)

    # 1. 同一銘柄コード（同じ会社の別エントリ）= 最も強い
    if focal.stock_symbol:
        for d in others.filter(stock_symbol=focal.stock_symbol):
            diary_cache[d.id] = d
            _add(d.id, 1.0, {'type': 'symbol', 'label': '同一銘柄'})

    # 2. 手動リンク（双方向）= 明示的意図で最強
    manual_ids = (
        set(focal.linked_diaries.values_list('id', flat=True))
        | set(focal.linked_from.values_list('id', flat=True))
    )
    if manual_ids:
        for d in others.filter(id__in=manual_ids):
            diary_cache[d.id] = d
            _add(d.id, 1.0, {'type': 'manual', 'label': '手動リンク'})

    # 3. 共通タグ（軸重み × IDF + 最小条件 + ノイズ除外）
    focal_tags = list(focal.tags.select_related('parent').all())
    # イベント軸・ラベル軸は関連度計算から除外
    effective_focal_tags = [t for t in focal_tags if getattr(t, 'axis', 'theme') not in ('event', 'custom')]

    if effective_focal_tags and themes_enabled:
        # tag_id → 共有している他日記のset（ノイズ上限でフィルタ済み）
        tag_diary_map: Dict[int, set] = {}
        for tag in effective_focal_tags:
            ids = set(others.filter(tags=tag).values_list('id', flat=True))
            if ids and len(ids) <= RELATED_NOISE_MAX:
                tag_diary_map[tag.id] = ids

        # diary_id → 共有タグリスト
        shared_tag_map: Dict[int, List] = defaultdict(list)
        tag_by_id = {t.id: t for t in effective_focal_tags}
        for tag_id, diary_ids in tag_diary_map.items():
            for did in diary_ids:
                shared_tag_map[did].append(tag_by_id[tag_id])

        # 方向属性（DiaryTagDirection）を取得し、共有タグごとに順相関/逆相関を判定する材料にする
        from .models import DiaryTagDirection as _DTD
        focal_dir = dict(
            _DTD.objects.filter(diary=focal, tag_id__in=tag_diary_map.keys())
            .values_list('tag_id', 'direction')
        )
        _other_ids = set()
        for _ids in tag_diary_map.values():
            _other_ids |= _ids
        other_dir: Dict[tuple, str] = {}
        if _other_ids:
            for d_id, t_id, _dir in _DTD.objects.filter(
                diary_id__in=_other_ids, tag_id__in=tag_diary_map.keys()
            ).values_list('diary_id', 'tag_id', 'direction'):
                other_dir[(d_id, t_id)] = _dir

        for did, shared_tags in shared_tag_map.items():
            # 最小条件チェック（FR-6）
            # P1: 高希少は IDF閾値でなく絶対df基準（focal以外で HIGH_RARITY_MAX_OTHERS 銘柄以下）
            theme_tags = [t for t in shared_tags if getattr(t, 'axis', 'theme') == 'theme']
            has_high_rarity_theme = any(
                len(tag_diary_map.get(t.id, set())) <= HIGH_RARITY_MAX_OTHERS
                for t in theme_tags
            )

            if len(shared_tags) < MIN_SHARED_TAGS and not has_high_rarity_theme:
                continue

            # スコア: Σ w_axis(t) × idf(t)   ※ P1: 加算平滑化 ln((N+1)/(df+1))
            for tag in shared_tags:
                axis = getattr(tag, 'axis', 'theme')
                w = AXIS_WEIGHTS.get(axis, 0.5)
                df = max(tag.df, 1) if getattr(tag, 'df', 0) > 0 else len(tag_diary_map.get(tag.id, set())) + 1
                idf = math.log((N + 1) / (df + 1))
                axis_labels = {
                    'theme': 'テーマ', 'business_model': 'BM',
                    'risk': 'リスク', 'capital_policy': '資本政策',
                    'macro': 'マクロ', 'event': 'イベント',
                }
                # 方向が双方とも非中立なら順相関（同方向）/逆相関（逆方向）を判定
                fdir = focal_dir.get(tag.id, 'neutral')
                odir = other_dir.get((did, tag.id), 'neutral')
                correlation = None
                if fdir in ('up', 'down') and odir in ('up', 'down'):
                    correlation = 'positive' if fdir == odir else 'inverse'
                dir_suffix = {'positive': '・順', 'inverse': '・逆'}.get(correlation, '')
                label = f'@{tag.name}（{axis_labels.get(axis, axis)}{dir_suffix}）'
                via = {'type': 'tag', 'label': label, 'key': tag.name, 'axis': axis}
                if correlation:
                    via['correlation'] = correlation
                _add(did, w * idf, via)

    # 4. 同業種（希少なほど強い・付けすぎは除外）
    sector = (focal.sector or '').strip()
    if sector:
        ids = list(others.filter(sector=sector).values_list('id', flat=True))
        if ids and len(ids) <= RELATED_NOISE_MAX:
            w = hub_weight(len(ids) + 1)
            for did in ids:
                _add(did, w, {'type': 'sector', 'label': f'同業種「{sector}」', 'key': f'sector:{sector}'})

    # 5. 共通 @ハッシュタグ（軸重み × IDF でスコアリング）
    from .tag_axis_config import get_master_axis_map, AXIS_LABELS as _AXIS_LABELS
    _master_ht_axis = get_master_axis_map()
    try:
        from tags.models import Tag as _TagModel
        _user_ht_axis = dict(_TagModel.objects.filter(user=user).values_list('name', 'axis'))
    except Exception:
        _user_ht_axis = {}

    def _ht_axis(name: str) -> str:
        if name in _user_ht_axis:
            return _user_ht_axis[name]
        return _master_ht_axis.get(name, 'custom')

    # focal のテキストから @タグ抽出（event軸・ラベル軸除外）
    focal_hashtags = {h for h in extract_hashtags(focal.reason or '') if _ht_axis(h) not in ('event', 'custom')}
    for note in DiaryNote.objects.filter(diary=focal).only('content'):
        focal_hashtags |= {h for h in extract_hashtags(note.content or '') if _ht_axis(h) not in ('event', 'custom')}

    # Phase 3（Tag M2M）で既にスコア済みのタグはダブルカウントを避ける
    m2m_tag_names = {t.name for t in focal.tags.all()}
    focal_hashtags = focal_hashtags - m2m_tag_names

    if focal_hashtags and themes_enabled:
        # 全他日記の reason から @タグを一括取得して ht_df とマップを構築
        ht_df: Dict[str, int] = defaultdict(int)
        other_ht_map: Dict[int, Set[str]] = {}
        for row in others.only('id', 'reason'):
            tags_in = {h for h in extract_hashtags(row.reason or '') if _ht_axis(h) not in ('event', 'custom')}
            other_ht_map[row.id] = tags_in
            for h in tags_in:
                ht_df[h] += 1

        for did, other_tags in other_ht_map.items():
            shared = focal_hashtags & other_tags
            if not shared:
                continue
            # ノイズ除外
            shared = {h for h in shared if ht_df.get(h, 0) <= RELATED_NOISE_MAX}
            if not shared:
                continue
            # 最小条件（2+ 共有 or 高希少テーマ）※ P1: 高希少は絶対df基準
            theme_shared = {h for h in shared if _ht_axis(h) == 'theme'}
            high_rarity = any(
                ht_df.get(h, 0) <= HIGH_RARITY_MAX_OTHERS
                for h in theme_shared
            )
            if len(shared) < MIN_SHARED_TAGS and not high_rarity:
                continue
            # スコア: Σ w_axis × IDF   ※ P1: 加算平滑化 ln((N+1)/(df+1))
            for tag_name in shared:
                axis = _ht_axis(tag_name)
                w = AXIS_WEIGHTS.get(axis, 0.5)
                idf = math.log((N + 1) / (ht_df.get(tag_name, 0) + 1))
                axis_label = _AXIS_LABELS.get(axis, axis)
                _add(did, w * idf, {'type': 'tag', 'label': f'@{tag_name}（{axis_label}）',
                                    'key': tag_name, 'axis': axis})

    # 5b. 推定テーマ: 本文の素のテーマ語（@無し）で関連付ける = 低重み・要裏付け（P2）
    #     - focal側はテーマを明示(@/タグ)していてもよい。相手側が「素の本文で言及」している場合に拾う。
    #       （相手が @テーマ で書いていれば 5. が担当するので二重計上しない＝ n not in other_ht）
    #     - 誤検出抑制: 具体語(3文字以上)のみ／裏付け要件＝2語以上 or 業種一致 or focalが明示済みのテーマ
    if themes_enabled:
        implicit_vocab = {
            name: axis
            for name, axis in {**_master_ht_axis, **_user_ht_axis}.items()
            if axis not in ('event', 'custom') and len(name) >= 3
        }
        focal_text = focal.reason or ''
        for note in DiaryNote.objects.filter(diary=focal).only('content'):
            focal_text += ' ' + (note.content or '')
        # focal が（@/タグ/素の本文 のいずれかで）言及しているテーマ語
        focal_themes = {n for n in implicit_vocab if n in focal_text}
        focal_explicit = m2m_tag_names | focal_hashtags  # focal が意図的に付けたテーマ
        if focal_themes:
            focal_sector = (focal.sector or '').strip()
            impl_df: Dict[str, int] = defaultdict(int)
            other_impl_map: Dict[int, tuple] = {}
            for row in others.only('id', 'reason', 'sector'):
                otext = row.reason or ''
                other_ht = set(extract_hashtags(otext))
                # 相手が素の本文で言及（@で書いていれば 5. が担当）
                shared = {n for n in focal_themes if n in otext and n not in other_ht}
                if shared:
                    other_impl_map[row.id] = (shared, (row.sector or '').strip())
                    for n in shared:
                        impl_df[n] += 1
            for did, (shared, osector) in other_impl_map.items():
                # 裏付け要件: 2語以上 / 業種一致 / focalが明示済みのテーマ（意図的なので単独でも可）
                corroborated = (
                    len(shared) >= 2
                    or (focal_sector and osector == focal_sector)
                    or bool(shared & focal_explicit)
                )
                if not corroborated:
                    continue
                for name in shared:
                    if impl_df.get(name, 0) > RELATED_NOISE_MAX:
                        continue
                    axis = implicit_vocab[name]
                    w = AXIS_WEIGHTS.get(axis, 0.5)
                    idf = math.log((N + 1) / (impl_df.get(name, 0) + 1))
                    _add(did, w * idf * IMPLICIT_THEME_DISCOUNT,
                         {'type': 'tag', 'label': f'{name}（推定）', 'key': name,
                          'axis': axis, 'estimated': True})

    # 6. 銘柄コード言及（双方向）= 明示的参照で強い
    mentioned = extract_stock_mentions((focal.reason or '') + ' ' + (focal.memo or ''))
    if mentioned:
        for d in others.filter(stock_symbol__in=mentioned):
            diary_cache[d.id] = d
            _add(d.id, 0.9, {'type': 'mention', 'label': '本文で言及'})
    if focal.stock_symbol:
        sym = focal.stock_symbol
        token_q = (
            Q(reason__icontains=f'({sym})') | Q(reason__icontains=f'（{sym}）')
            | Q(memo__icontains=f'({sym})') | Q(memo__icontains=f'（{sym}）')
        )
        for d in others.filter(token_q):
            diary_cache[d.id] = d
            _add(d.id, 0.9, {'type': 'mention', 'label': '相手から言及'})

    # まだ取得していない日記オブジェクトをまとめて取得
    missing = [did for did in scores if did not in diary_cache]
    if missing:
        for d in StockDiary.objects.filter(id__in=missing):
            diary_cache[d.id] = d

    # P3: 異種スコアの単純和で順位が逆転しないようティア優先にする。
    #     Tier A(同一銘柄/手動/言及) > Tier B(テーマ) > Tier C(業種)。ティア内のみスコア比較。
    TIER_A_TYPES = {'symbol', 'manual', 'mention'}
    result: List[dict] = []
    for did, score in scores.items():
        d = diary_cache.get(did)
        if not d:
            continue
        vias = reasons[did]
        via_types = {v.get('type') for v in vias}
        if via_types & TIER_A_TYPES:
            tier = 0
        elif 'tag' in via_types:
            tier = 1
        else:
            tier = 2
        result.append({'diary': d, 'score': round(score, 4), 'via': vias, 'tier': tier})
    result.sort(key=lambda x: (x['tier'], -x['score']))
    return result[:limit]


def _extract_section(text: str, headings: List[str]) -> str:
    """Markdown見出し（## など）で区切られた本文から、指定見出しのセクション本文を返す。"""
    out: List[str] = []
    capturing = False
    for raw in text.splitlines():
        s = raw.strip()
        h = re.match(r'^#{1,6}\s*(.+?)\s*$', s)
        if h:
            title = h.group(1)
            if any(k in title for k in headings):
                capturing = True
                continue
            if capturing:
                break  # 次の見出しに到達したら終了
        elif capturing:
            out.append(raw)
    return '\n'.join(out).strip()


def extract_lead(text: str, max_len: int = 120) -> str:
    """投資理由/継続記録から「意味のある先頭1〜2文」を返す。

    Markdownのノイズ（見出し・引用注記・テーブル・空のラベル箇条書き・全角括弧のガイダンス）を
    除去する。テンプレ運用者の場合は `## ひとこと要約` 等の結論セクションを優先する。
    どんな書き方でも何かしらの本文が返るようにし、結論を構造で強制しない（規律ゼロ運用に対応）。
    """
    if not text:
        return ''
    summary = _extract_section(text, ['ひとこと要約', '結論ひとこと', '総合評価'])
    body = summary if summary else text
    lines: List[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('#') or line.startswith('>') or line.startswith('|'):
            continue
        # 箇条書きの先頭記号を外す
        m = re.match(r'^[-*]\s+(.*)$', line)
        if m:
            line = m.group(1).strip()
        # 太字ラベルのみ/値が空の箇条書き（**項目**: ）を除外、値があれば値を採用
        lab = re.match(r'^\*\*[^*]+\*\*\s*[:：]?\s*(.*)$', line)
        if lab is not None:
            val = lab.group(1).strip()
            if not val:
                continue
            line = val
        # 全角/半角の括弧だけで構成されたガイダンス行を除外
        if re.fullmatch(r'[（(].*[)）]', line):
            continue
        line = re.sub(r'^[#>*\-\s]+', '', line).strip()
        line = re.sub(r'\*\*|`', '', line)  # 残った強調記号を除去
        if len(line) < 2:
            continue
        lines.append(line)
        if len(' '.join(lines)) >= max_len:
            break
    result = ' '.join(lines).strip()
    if len(result) > max_len:
        result = result[:max_len].rstrip() + '…'
    return result


def _diary_outcome(d) -> dict:
    """銘柄の損益/状態を「参考」表示用に返す。

    P4(アウトカム・バイアス回避): 主役にせず淡色で添える前提。
    現在株価を保持していないため、保有中の含み損益は出さない（誤った確定感を与えない）。
    """
    if d.is_memo:
        return {'label': 'メモ', 'tone': 'muted'}
    if d.is_short:
        return {'label': '信用売り', 'tone': 'muted'}
    if d.is_sold_out:
        rp = float(d.realized_profit or 0)
        base = float(d.total_buy_amount or 0)
        sign = '+' if rp >= 0 else ''
        tone = 'up' if rp >= 0 else 'down'
        if base > 0:
            return {'label': f'売却済 {sign}{rp / base * 100:.1f}%', 'tone': tone}
        return {'label': f'売却済 {sign}{rp:,.0f}{d.currency_unit}', 'tone': tone}
    return {'label': '保有中', 'tone': 'muted'}


def build_theme_recall(related_unified: List[dict], focal, user) -> dict:
    """関連銘柄リストを「テーマ別の過去判断」に組み替える（想起パネル用）。

    既に算出済みの related_unified を再利用し、再計算しない。
    各メンバーに 冒頭文(主役)・直近ノート・損益(参考)・方向の見立て を添える。
    戻り値: {'primary': [bucket], 'more': [bucket], 'total': int, 'is_empty': bool, 'sector_only': bool}
    （primary=常時表示の主要テーマ、more=折り畳む推定/同業種テーマ）
    """
    from .models import DiaryNote
    from .tag_axis_config import AXIS_COLORS

    THEME_TYPES = {'tag', 'sector'}
    SECTOR_COLOR = '#b45309'

    member_ids = [it['diary'].id for it in related_unified]
    notes_by_diary: Dict[int, list] = defaultdict(list)
    if member_ids:
        for n in (DiaryNote.objects
                  .filter(diary_id__in=member_ids)
                  .order_by('-date', '-id')
                  .only('diary_id', 'content', 'date')):
            notes_by_diary[n.diary_id].append(n)

    themes: Dict[str, dict] = {}
    has_theme_bucket = False

    for it in related_unified:
        d = it['diary']
        lead = extract_lead(d.reason or '')
        latest = None
        for n in notes_by_diary.get(d.id, []):
            txt = extract_lead(n.content or '')
            if txt:
                latest = {'text': txt, 'date': n.date}
                break
        outcome = _diary_outcome(d)

        for v in it['via']:
            vtype = v.get('type')
            if vtype not in THEME_TYPES:
                continue
            key = v.get('key') or v.get('label')
            if not key:
                continue
            estimated = bool(v.get('estimated'))
            if vtype == 'tag':
                has_theme_bucket = True
                display = key
                color = AXIS_COLORS.get(v.get('axis'), '#7c3aed')
            else:  # sector
                display = key.split(':', 1)[-1]
                color = SECTOR_COLOR

            bucket = themes.get(key)
            if bucket is None:
                bucket = {'display': display, 'type': vtype, 'color': color,
                          'estimated': estimated, 'members': [], 'member_ids': set(),
                          'score': 0.0}
                themes[key] = bucket
            # 1件でも非推定経由があればバケットは確定扱い
            bucket['estimated'] = bucket['estimated'] and estimated
            bucket['score'] += it['score']
            if d.id in bucket['member_ids']:
                continue
            bucket['member_ids'].add(d.id)
            bucket['members'].append({
                'diary': d,
                'lead': lead,
                'latest': latest,
                'outcome': outcome,
                'direction': v.get('correlation'),
                'estimated': estimated,
                'score': it['score'],
            })

    # バケットを整列し、規模が増えても膨らまないよう「主要テーマ」と「その他」に分割する。
    # ティア: 0=明示タグ / 1=推定タグ / 2=同業種。明示を常に上、推定・業種は折り畳む。
    MAX_PRIMARY_THEMES = 5
    buckets = list(themes.values())
    for b in buckets:
        b['members'].sort(key=lambda m: -m['score'])
        b['tier'] = 2 if b['type'] == 'sector' else (1 if b['estimated'] else 0)
        b.pop('member_ids', None)
    buckets.sort(key=lambda b: (b['tier'], -b['score']))

    primary = [b for b in buckets if b['tier'] == 0][:MAX_PRIMARY_THEMES]
    if not primary:  # 規律ゼロ（明示タグ皆無）でも何か出す
        primary = buckets[:MAX_PRIMARY_THEMES]
    primary_ids = {id(b) for b in primary}
    more = [b for b in buckets if id(b) not in primary_ids]

    return {
        'primary': primary,
        'more': more,
        'total': len(buckets),
        'is_empty': len(buckets) == 0,
        'sector_only': (not has_theme_bucket) and len(buckets) > 0,
    }
