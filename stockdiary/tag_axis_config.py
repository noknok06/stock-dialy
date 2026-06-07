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

# @ハッシュタグ名 → 軸 の組み込みマッピング
# tags/migrations/0004_auto_assign_tag_axis.py の TAG_AXIS_MAP と同内容。
# ユーザーが Tag M2M で同名タグを作成した場合はそちらが優先される。
HASHTAG_AXIS_MAP: dict[str, str] = {
    # マクロ経済
    'インフレ': 'macro', '金利上昇': 'macro', '金利低下': 'macro',
    '円安メリット': 'macro', '円高メリット': 'macro', '景気敏感': 'macro',
    'ディフェンシブ': 'macro', '資源価格上昇': 'macro',
    '金利感応': 'macro', '都心オフィス': 'macro', '不動産市況': 'macro',
    # AI・デジタル
    'AI': 'theme', 'フィジカルAI': 'theme', 'ドローン': 'theme',
    'DX': 'theme', 'サイバーセキュリティ': 'theme', 'AIセキュリティ': 'theme',
    'データセンター': 'theme', '半導体': 'theme', 'オルタナティブデータ': 'theme',
    '通信インフラ': 'theme',
    # エネルギー
    'エネルギー': 'theme', 'LNG': 'theme',
    # 脱炭素
    '脱炭素': 'theme', '再生可能エネルギー': 'theme', '水素': 'theme',
    '蓄電池': 'theme', 'CCS': 'theme', 'SAF': 'theme',
    # 社会・政策テーマ
    '防衛': 'theme', '国土強靭化': 'theme', 'インフラ老朽化': 'theme',
    '建設補修': 'theme', '少子高齢化': 'theme', 'インバウンド': 'theme',
    'アジア消費': 'theme',
    # ヘルスケア
    'ヘルスケア': 'theme', 'ヘルスケア施設開発': 'theme', '医療DX': 'theme',
    '創薬': 'theme', '医療機器': 'theme',
    # 物流
    '物流': 'theme', 'EC物流': 'theme', 'サプライチェーン': 'theme',
    # 人材
    'HRテック': 'theme', '採用プラットフォーム': 'theme', 'ハイクラス人材': 'theme',
    '人材ビジネス': 'theme', '人材集約型': 'theme',
    # 配当・株主還元
    '高配当': 'capital_policy', '累進配当': 'capital_policy',
    '連続増配': 'capital_policy', '連続増益': 'capital_policy',
    '高ROE': 'capital_policy', '株主還元強化': 'capital_policy',
    # 成長戦略・ビジネスモデル
    'M&A成長': 'business_model', '海外展開': 'business_model',
    'IPビジネス': 'business_model', 'プラットフォーム': 'business_model',
    'ストック収益': 'business_model', '高シェア': 'business_model',
    'ニッチトップ': 'business_model', '総合商社': 'business_model',
    '資源権益': 'business_model', 'バリューチェーン': 'business_model',
    # リスク
    '地政学リスク': 'risk', '規制リスク': 'risk', '需給変化': 'risk',
    # イベント
    '構造改革': 'event', '利益率改善': 'event', '設備投資拡大': 'event',
    '決算注目': 'event', '業績上方修正': 'event', '増配': 'event',
    '減配': 'event', 'MBO・買収': 'event', '決算ミス': 'event',
}
