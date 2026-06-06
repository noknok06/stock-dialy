"""タグ軸ベース関連分析の設定。

軸重み・閾値はここで一元管理する。
運用しながらチューニングすること。
"""

# 軸ごとの関連度重み（FR-1 / FR-6）
# イベント軸は関連度計算から除外（0.0）
AXIS_WEIGHTS: dict[str, float] = {
    'theme':          1.0,
    'business_model': 0.6,
    'risk':           0.5,
    'capital_policy': 0.4,
    'macro':          0.3,
    'event':          0.0,  # 一過性イベントは計算から除外
}

# 関連成立の最小条件（FR-6）
# イベント軸以外の共有タグがこの数以上あれば条件成立
MIN_SHARED_TAGS: int = 2

# テーマ軸の高希少タグ1つだけでも関連成立とみなす IDF 閾値
# idf = log(N/df) >= THRESHOLD → df <= N / e^THRESHOLD
# 2.0 ≒ N の 13.5% 以下の銘柄にしか付かないタグ
HIGH_RARITY_IDF_THRESHOLD: float = 2.0

# 付けすぎタグの除外上限（この数を超える銘柄が共有するタグはノイズとみなす）
RELATED_NOISE_MAX: int = 25

# FR-10: df がこの値未満のタグは「粒度が細かすぎる可能性あり」としてフラグ
DF_MIN_GOVERNANCE: int = 3

# ハブノードの軸ごとの表示色（diary-graph.js と対応）
AXIS_COLORS: dict[str, str] = {
    'theme':          '#7c3aed',  # 紫（テーマ）
    'business_model': '#0891b2',  # シアン（ビジネスモデル）
    'risk':           '#dc2626',  # 赤（リスク）
    'capital_policy': '#16a34a',  # 緑（資本政策）
    'macro':          '#d97706',  # オレンジ（マクロ感応）
    'event':          '#6b7280',  # グレー（イベント）
}

# 軸の日本語ラベル
AXIS_LABELS: dict[str, str] = {
    'theme':          'テーマ',
    'business_model': 'ビジネスモデル',
    'risk':           'リスク',
    'capital_policy': '資本政策',
    'macro':          'マクロ感応',
    'event':          'イベント',
}
