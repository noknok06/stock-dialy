# stockdiary/services/karte_service.py
"""投資家カルテ（自己理解）の集計サービス。

成績評価ではなく「自分はどういう投資家か」を言語化して返すための集計。
Verdict（検証）を母数に、意思決定の質×結果の2×2分布、テーマ別の的中傾向、
繰り返す見落とし、再現したい学び（投資哲学）を組み立てる。

損益計算（AggregateService）には依存せず、意思決定の質の軸で集計する。
"""
from collections import Counter

from ..models import Verdict


# 2×2の象限メタ（テンプレートの並び順とラベル）
QUADRANTS = [
    ('skill', '再現すべき勝ち', '仮説◯ × 利益'),
    ('unlucky', '正しいが報われず', '仮説◯ × 損失'),
    ('lucky', '偶然の勝ち（要注意）', '仮説× × 利益'),
    ('discipline', '想定通りの負け', '仮説× × 損失'),
]


def build_investor_karte(user):
    """ユーザーの全 Verdict から自己理解レポートを構築する。"""
    verdicts = list(
        Verdict.objects
        .filter(thesis__diary__user=user, thesis__diary__is_excluded=False)
        .select_related('thesis', 'thesis__diary')
        .prefetch_related('thesis__basis_tags')
        .order_by('-created_at')
    )
    total = len(verdicts)

    quad_counts = {key: 0 for key, _, _ in QUADRANTS}
    hyp_hit = 0          # 仮説が当たり（的中・部分的中）
    total_wins = 0       # 損益が利益
    lucky_wins = 0       # 利益だが仮説は外れ（偶然の勝ち）
    learnings = []
    missed = []
    tag_stats = {}       # tag_id -> {name, total, hit}

    for v in verdicts:
        quad_counts[v.quadrant] += 1
        if v.hyp_ok:
            hyp_hit += 1
        if v.pnl_ok:
            total_wins += 1
            if not v.hyp_ok:
                lucky_wins += 1
        if v.learning:
            learnings.append({
                'text': v.learning,
                'diary': v.thesis.diary,
                'repeatable': v.is_repeatable,
                'date': v.created_at,
            })
        if v.missed_factor:
            missed.append(v.missed_factor)
        for tag in v.thesis.basis_tags.all():
            st = tag_stats.setdefault(tag.id, {'name': tag.name, 'total': 0, 'hit': 0})
            st['total'] += 1
            if v.hyp_ok:
                st['hit'] += 1

    quadrants = [
        {'key': key, 'label': label, 'axis': axis, 'count': quad_counts[key]}
        for key, label, axis in QUADRANTS
    ]

    hit_rate = round(hyp_hit / total * 100) if total else None
    # 意思決定の質と損益の乖離: 勝ちのうち「偶然（仮説外れ）」が占める割合
    lucky_share = round(lucky_wins / total_wins * 100) if total_wins else None

    # テーマ別の的中傾向（2件以上検証したタグのみ）。得意・苦手に分ける
    theme_rows = []
    for st in tag_stats.values():
        if st['total'] >= 2:
            rate = round(st['hit'] / st['total'] * 100)
            theme_rows.append({'name': st['name'], 'total': st['total'], 'hit': st['hit'], 'rate': rate})
    theme_rows.sort(key=lambda x: (x['rate'], x['total']), reverse=True)
    strong_themes = [t for t in theme_rows if t['rate'] >= 60][:5]
    weak_themes = [t for t in theme_rows if t['rate'] < 40][:5]

    # 繰り返す失敗（同一の見落としが2回以上）
    repeated_misses = [
        {'text': text, 'count': cnt}
        for text, cnt in Counter(missed).most_common(5) if cnt >= 2
    ]

    # 投資哲学＝再現したい学び（なければ全学びの新しい順）
    philosophy = [l for l in learnings if l['repeatable']][:8]
    if not philosophy:
        philosophy = learnings[:8]

    return {
        'total': total,
        'has_content': total > 0,
        'quadrants': quadrants,
        'hit_rate': hit_rate,
        'total_wins': total_wins,
        'lucky_wins': lucky_wins,
        'lucky_share': lucky_share,
        'strong_themes': strong_themes,
        'weak_themes': weak_themes,
        'repeated_misses': repeated_misses,
        'recent_misses': missed[:5],
        'philosophy': philosophy,
    }
