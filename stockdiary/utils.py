"""
stockdiary app utility functions
"""
import re
from typing import List, Set


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
