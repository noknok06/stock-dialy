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

    # ハッシュタグのパターン: @の後に日本語、英数字、アンダースコアが続く
    # [\u3040-\u309F] - ひらがな
    # [\u30A0-\u30FF] - カタカナ
    # [\u4E00-\u9FFF] - 漢字
    # [a-zA-Z0-9_] - 英数字とアンダースコア
    pattern = r'@([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\uFF66-\uFF9Fa-zA-Z0-9_]+)'

    matches = re.findall(pattern, text)

    # 重複を除去して順序を保持
    seen = set()
    unique_tags = []
    for tag in matches:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)

    return unique_tags


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
        - notes_first:        継続記録だけに一致した場合 True（カードの既定タブ制御用）

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
            diary.notes_first = False
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
        # 継続記録だけに一致した場合は、カードの既定タブを「継続」にする
        diary.notes_first = bool(matched_notes) and not diary.match_name and not diary.match_body

    return diaries


def hub_weight(diary_count: int) -> float:
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
                tag_meta[tag.pk] = {'name': tag.name}
            edges.append({
                'source': diary.pk,
                'target': f'tag_{tag.pk}',
                'edge_type': 'tag',
            })

    # 全カウント確定後に逆頻度の重みを付与
    for e in edges:
        pk = int(e['target'].split('_', 1)[1])
        e['weight'] = hub_weight(tag_diary_count[pk])

    tag_nodes = [
        {
            'id': f'tag_{pk}',
            'node_type': 'tag',
            'tag_name': meta['name'],
            'tag_pk': pk,
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


def get_hashtag_graph_data(diaries_qs, note_limit: int | None = None) -> Dict[str, Any]:
    """
    @ハッシュタグが共通する日記同士をエッジで繋ぐ。
    ハッシュタグをハブノードとして追加する。
    reason フィールドに加え、継続記録（DiaryNote.content）も対象にする。

    Args:
        diaries_qs: prefetch_related('notes') 済みの StockDiary QuerySet
        note_limit: 各日記の継続記録を直近N件に制限する。None で全件。

    Returns:
        {
            'hashtag_nodes': [{'id': 'ht_<tag>', 'node_type': 'hashtag', 'tag_name': str, 'diary_count': int}],
            'edges':         [{'source': <diary_id>, 'target': 'ht_<tag>', 'edge_type': 'hashtag'}]
        }
    """
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
                })

    # 全カウント確定後に逆頻度の重みを付与
    for e in edges:
        tag = e['target'].split('_', 1)[1]
        e['weight'] = hub_weight(ht_diary_count[tag])

    hashtag_nodes = [
        {
            'id': f'ht_{tag}',
            'node_type': 'hashtag',
            'tag_name': tag,
            'diary_count': count,
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
    """フォーカル日記に対する他日記の「関連の強さ」を希少性で重み付けして算出する。

    複数の弱い関連より、希少なタグや明示的リンク・言及といった強い関連を上位に出す。
    付けすぎたタグ／業種（多数の銘柄が共有するもの）は RELATED_NOISE_MAX で除外し、
    グラフが密でも「読める」関連発見の導線にする。

    Returns:
        score 降順の [{'diary': StockDiary, 'score': float,
                       'via': [{'type': str, 'label': str}]}] （最大 limit 件）
    """
    from django.db.models import Q
    from .models import StockDiary, DiaryNote

    scores: Dict[int, float] = defaultdict(float)
    reasons: Dict[int, List[dict]] = defaultdict(list)
    diary_cache: Dict[int, Any] = {}

    others = StockDiary.objects.filter(user=user).exclude(id=focal.id)

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

    # 3. 共通タグ（希少なほど強い・付けすぎは除外）
    for tag in focal.tags.all():
        ids = list(others.filter(tags=tag).values_list('id', flat=True))
        if not ids or len(ids) > RELATED_NOISE_MAX:
            continue
        w = hub_weight(len(ids) + 1)
        for did in ids:
            _add(did, w, {'type': 'tag', 'label': f'共通タグ「{tag.name}」'})

    # 4. 同業種（希少なほど強い・付けすぎは除外）
    sector = (focal.sector or '').strip()
    if sector:
        ids = list(others.filter(sector=sector).values_list('id', flat=True))
        if ids and len(ids) <= RELATED_NOISE_MAX:
            w = hub_weight(len(ids) + 1)
            for did in ids:
                _add(did, w, {'type': 'sector', 'label': f'同業種「{sector}」'})

    # 5. 共通 @ハッシュタグ（投資理由 + 継続記録から抽出・付けすぎは除外）
    focal_hashtags: Set[str] = set(extract_hashtags(focal.reason or ''))
    for note in DiaryNote.objects.filter(diary=focal).only('content'):
        focal_hashtags |= set(extract_hashtags(note.content or ''))
    for ht in focal_hashtags:
        ids = list(
            others.filter(
                Q(reason__icontains=f'@{ht}') | Q(notes__content__icontains=f'@{ht}')
            ).distinct().values_list('id', flat=True)
        )
        if not ids or len(ids) > RELATED_NOISE_MAX:
            continue
        w = hub_weight(len(ids) + 1)
        for did in ids:
            _add(did, w, {'type': 'hashtag', 'label': f'共通@{ht}'})

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

    result: List[dict] = []
    for did, score in scores.items():
        d = diary_cache.get(did)
        if not d:
            continue
        result.append({'diary': d, 'score': round(score, 4), 'via': reasons[did]})
    result.sort(key=lambda x: x['score'], reverse=True)
    return result[:limit]
