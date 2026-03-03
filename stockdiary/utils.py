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

    # reasonフィールドで @タグ の形式を検索
    # 前後に空白や改行がある場合も考慮
    return queryset.filter(
        Q(reason__icontains=f'@{tag}')
    )


def get_tag_graph_data(diaries_qs) -> Dict[str, Any]:
    """
    タグハブノードと diary→tag エッジを生成する。

    Args:
        diaries_qs: prefetch_related('tags') 済みの StockDiary QuerySet

    Returns:
        {
            'tag_nodes': [{'id': 'tag_<pk>', 'node_type': 'tag', 'tag_name': str, 'tag_pk': int, 'diary_count': int}],
            'edges':     [{'source': <diary_id>, 'target': 'tag_<pk>', 'edge_type': 'tag'}]
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

    tag_nodes = [
        {
            'id': f'tag_{pk}',
            'node_type': 'tag',
            'tag_name': meta['name'],
            'tag_pk': pk,
            'diary_count': tag_diary_count[pk],
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

    sector_nodes = [
        {
            'id': f'sec_{name}',
            'node_type': 'sector',
            'sector_name': name,
            'diary_count': count,
        }
        for name, count in sector_diary_count.items()
    ]

    return {'sector_nodes': sector_nodes, 'edges': edges}


def get_hashtag_graph_data(diaries_qs) -> Dict[str, Any]:
    """
    @ハッシュタグが共通する日記同士をエッジで繋ぐ。
    ハッシュタグをハブノードとして追加する。

    Args:
        diaries_qs: StockDiary QuerySet（reason フィールドを含む）

    Returns:
        {
            'hashtag_nodes': [{'id': 'ht_<tag>', 'node_type': 'hashtag', 'tag_name': str, 'diary_count': int}],
            'edges':         [{'source': <diary_id>, 'target': 'ht_<tag>', 'edge_type': 'hashtag'}]
        }
    """
    ht_diary_count: Dict[str, int] = defaultdict(int)
    edges: List[dict] = []

    for diary in diaries_qs:
        if not diary.reason:
            continue
        for tag in extract_hashtags(diary.reason):
            ht_id = f'ht_{tag}'
            ht_diary_count[tag] += 1
            edges.append({
                'source': diary.pk,
                'target': ht_id,
                'edge_type': 'hashtag',
            })

    hashtag_nodes = [
        {
            'id': f'ht_{tag}',
            'node_type': 'hashtag',
            'tag_name': tag,
            'diary_count': count,
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
                })
            if target_id not in primary_id_set:
                mentioned_diary_ids.add(target_id)

    return {'edges': edges, 'mentioned_diary_ids': mentioned_diary_ids}
