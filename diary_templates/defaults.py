"""既定テンプレート定義。

新規ユーザーには「基本テンプレート」のみ自動配布する（オンボーディングの混乱回避）。
重厚な「サンプルテンプレート」は自動配布せず、テンプレート一覧から任意で追加できる。
"""

BASIC_TEMPLATE_TITLE = '基本テンプレート'

BASIC_TEMPLATE_BODY = """## なぜ投資する？


## 注目しているテーマ
（@ を付けてテーマを書くと、同じテーマの銘柄がつながります。例: @半導体 @高配当）


## 気になるリスク
"""

SAMPLE_TEMPLATE_TITLE = 'サンプルテンプレート'

SAMPLE_TEMPLATE_BODY = """## ひとこと要約

## ビジネスモデル
- **主要事業（セグメント別）**:
- **収益構造**:
- **主要顧客・販売先**:
- **主要製品・サービス**:

## 競合優位性（モート）
- **技術・シェア面の強み**:
- **ブランド・参入障壁**:
- **コスト・規模の優位**:

## 市場環境・成長ドライバー
- **追い風となるトレンド**:
- **主力事業の位置づけ（成熟/成長）**:
- **注力領域・戦略転換**:

## 株価変動ドライバー
- **上昇材料**:
- **下落材料**:
- **市場が注目している指標**:

## 主要リスク
- **事業集中リスク**:
- **市場・競合リスク**:
- **マクロ・地政学リスク**:
- **顧客依存・規制依存**:

## 競合他社・関連企業

- **同業他社**:
- **サプライチェーン上流/下流**:

## 投資家としての注目点（ウォッチリスト）
-

## 投資判断
- **評価**: 強気 / 中立 / 弱気
- **理由**:
- **想定シナリオ**:
- **バリュエーション感**:

## 総合評価

## 関連タグ
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
