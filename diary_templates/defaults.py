"""既定テンプレート定義。

新規ユーザーには「基本テンプレート」のみ自動配布する（オンボーディングの混乱回避）。
重厚な「サンプルテンプレート」は自動配布せず、テンプレート一覧から任意で追加できる。
"""

BASIC_TEMPLATE_TITLE = '基本テンプレート'

BASIC_TEMPLATE_BODY = """## ひとこと要約


## なぜ投資する？


## 注目しているテーマ


## 気になるリスク
"""

SAMPLE_TEMPLATE_TITLE = 'サンプルテンプレート'

SAMPLE_TEMPLATE_BODY = """## ひとこと要約
（「○○な企業」形式で1〜2文。関連図にも使われるため、簡潔に本質を突いた一文にする）

## 📌 基本情報
- 分析時点の株価・PER・PBR：
- 確信度：★☆☆☆☆〜★★★★★（この会社への理解・納得感の度合い）

## この会社をどう理解しているか（事実は簡潔に）
- 主力事業と収益構造：
- 稼ぐ力の源泉とその持続性（技術・ブランド・コスト構造のうち該当するもの）：

## 市場環境
- 追い風／向かい風となっているトレンド：
- 主力事業の位置づけ（成熟／成長）と戦略転換の動き：

## 主要リスク（該当するものだけ）
（事業集中／市場・競合／マクロ・地政学／顧客依存・規制の中で、特にこの会社に効いているもの）

## 競合他社・関連企業
> 「(ティッカー)銘柄名」の形式で記載
- 同業他社：
- サプライチェーン上流／下流：

## ウォッチポイント
- 決算で確認する数字・指標：
- 市場が注目しているポイント：

## 投資判断
- 評価：強気／中立／弱気
- バリュエーション感：

## 今の自分への一言
（なぜ今この銘柄に時間を使っているか、心理状態やバイアスの自覚があれば）

## 関連タグ
`@業種` `@テーマ` `@仮説パターン`
"""


def ensure_basic_template(user, template_model=None):
    """指定ユーザーに基本テンプレートが無ければ作成する。

    既存テンプレートは上書きしない（ユーザーの編集を尊重）。
    新規ユーザーへ自動配布する既定テンプレートはこれのみ。
    """
    if template_model is None:
        from .models import DiaryTemplate
        template_model = DiaryTemplate

    template_model.objects.get_or_create(
        user=user,
        title=BASIC_TEMPLATE_TITLE,
        defaults={'body': BASIC_TEMPLATE_BODY},
    )


def ensure_sample_template(user, template_model=None):
    """指定ユーザーにサンプルテンプレート（重厚版）が無ければ作成する。

    既存テンプレートは上書きしない（ユーザーの編集を尊重）。
    自動配布はせず、テンプレート一覧からの任意追加に使う。
    """
    if template_model is None:
        from .models import DiaryTemplate
        template_model = DiaryTemplate

    template_model.objects.get_or_create(
        user=user,
        title=SAMPLE_TEMPLATE_TITLE,
        defaults={'body': SAMPLE_TEMPLATE_BODY},
    )
