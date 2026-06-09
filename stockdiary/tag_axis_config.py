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
    'custom':         0.0,  # 個人管理ラベルは分析スコアリングから除外
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

# --- 想起（recall）/ 関連スコアのデータサイエンス是正用パラメータ ---
# P1: 小標本での per-user IDF 不安定性への主対策は「加算平滑化」と「高希少の絶対df基準」
#     （下記 HIGH_RARITY_MAX_OTHERS）で行う。テーマ段階自体は N>=2（=他に1銘柄でもあれば）有効。
#     N=1 では others が空のため自然に無効。希少タグは小標本でも意図的に関連させる方針。
MIN_N_FOR_THEMES: int = 2

# P1: 「高希少テーマ」を IDF閾値でなく絶対df基準で判定（ポートフォリオ規模に依存させない）。
#     「focal以外でこの数以下の銘柄にしか付かないテーマ」を高希少とみなす。
HIGH_RARITY_MAX_OTHERS: int = 2

# P2: 推定テーマ（@無しの本文一致）の寄与を割り引く係数（明示タグより常に弱く）。
IMPLICIT_THEME_DISCOUNT: float = 0.4

# ハブノードの軸ごとの表示色（diary-graph.js と対応）
AXIS_COLORS: dict[str, str] = {
    'theme':          '#7c3aed',  # 紫（テーマ）
    'business_model': '#0891b2',  # シアン（ビジネスモデル）
    'risk':           '#dc2626',  # 赤（リスク）
    'capital_policy': '#16a34a',  # 緑（資本政策）
    'macro':          '#d97706',  # オレンジ（マクロ感応）
    'event':          '#6b7280',  # グレー（イベント）
    'custom':         '#9333ea',  # 薄紫（ラベル）
}

# 軸の日本語ラベル
AXIS_LABELS: dict[str, str] = {
    'theme':          'テーマ',
    'business_model': 'ビジネスモデル',
    'risk':           'リスク',
    'capital_policy': '資本政策',
    'macro':          'マクロ感応',
    'event':          'イベント',
    'custom':         'ラベル',
}

# 標準タグ（管理者キュレーション分）の軸マッピング。
#
# 【重要】これは「種データ兼フォールバック」であり、実行時の正は DB（tags.MasterTag）。
#   - 初回マイグレーション（0006）でこの厳選コアが MasterTag に投入される。
#   - 以降は管理画面（Django admin）から追加・編集・無効化できる（デプロイ不要）。
#   - 実行時の軸決定は get_master_axis_map() を使うこと。直接この辞書を参照しない。
#   - この辞書は DB が空・未マイグレーション・例外時のフォールバックとしてのみ使われる。
#
# 方針: 標準タグは「汎用性が高く分析価値のある語」に厳選し、
#       細かい語はユーザーが @タグで自由に追加（既定 custom 軸）する運用とする。
CORE_MASTER_TAGS: dict[str, str] = {
    # テーマ
    'AI': 'theme', '半導体': 'theme', 'データセンター': 'theme',
    'DX': 'theme', 'サイバーセキュリティ': 'theme', '防衛': 'theme',
    'インバウンド': 'theme', 'ヘルスケア': 'theme',
    '脱炭素': 'theme', '再生可能エネルギー': 'theme',
    # マクロ感応
    'インフレ': 'macro', '金利上昇': 'macro', '円安メリット': 'macro',
    '景気敏感': 'macro', 'ディフェンシブ': 'macro',
    # 資本政策
    '高配当': 'capital_policy', '累進配当': 'capital_policy',
    '連続増配': 'capital_policy', '株主還元強化': 'capital_policy',
    '高ROE': 'capital_policy',
    # ビジネスモデル
    'ストック収益': 'business_model', 'プラットフォーム': 'business_model',
    '高シェア': 'business_model', '総合商社': 'business_model',
    # リスク
    '地政学リスク': 'risk', '規制リスク': 'risk',
}

# 後方互換エイリアス（フォールバック用途のみ。新規コードは get_master_axis_map() を使う）
HASHTAG_AXIS_MAP: dict[str, str] = CORE_MASTER_TAGS

# get_master_axis_map() のキャッシュキー（tags.MasterTag.CACHE_KEY と一致させること）
_MASTER_AXIS_CACHE_KEY = 'master_tag_axis_map'


def get_master_axis_map() -> dict[str, str]:
    """標準タグの {タグ名: 軸} を返す。

    実行時の正は DB（tags.MasterTag, is_active=True）。
    DB が空・未マイグレーション・例外時は CORE_MASTER_TAGS にフォールバックする。
    頻繁なクエリを避けるため短時間（5分）キャッシュする。
    MasterTag の保存/削除でキャッシュは即時クリアされる。
    """
    from django.core.cache import cache

    cached = cache.get(_MASTER_AXIS_CACHE_KEY)
    if cached is not None:
        return cached

    mapping = dict(CORE_MASTER_TAGS)
    try:
        from tags.models import MasterTag
        db_map = dict(
            MasterTag.objects.filter(is_active=True).values_list('name', 'axis')
        )
        if db_map:
            mapping = db_map
    except Exception:
        # マイグレーション未適用・DB未接続時などはフォールバックを使う
        pass

    cache.set(_MASTER_AXIS_CACHE_KEY, mapping, 300)
    return mapping
