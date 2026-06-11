# カブログ UI/UX レビュー（2026-06）

本書は、ドキュメント（`docs/product_context.md` / `docs/improvement_plan.md` / `docs/upgrade_directions.md`）と
実コード（テンプレート・ビュー・CSS/JS）の突き合わせによる UI/UX レビューである。

- 目的1: 利用中の機能と、利用されていない（おまけ・対象外）機能の判定
- 目的2: UI/UX の障害となっている機能の特定と対策提案
- 目的3: レイアウト変更の積極提案と、それにより何が改善されるかの明示

`docs/improvement_plan.md` の既決定（ナビ主要5項目化、CopoMo は「設定・その他」1リンク、
investment_hub は 2026-06 は触らない等）と矛盾しない範囲で提案する。

---

## 1. 機能の利用状況マップ

判断軸はプロダクトのコアバリュー「自分だけの投資知識ベースを育てる
（思考の記録・蓄積・振り返り）」（`docs/product_context.md`）。

| 機能 | 位置づけ | 根拠・現状 |
|------|---------|-----------|
| 投資日記（StockDiary）・継続記録（DiaryNote） | **コア** | プロダクトの中心。home / detail / diary_form |
| ハッシュタグ・関連日記・バックリンク | **コア** | 知識ベースのつながり。improvement_plan 論点7 |
| 日記グラフ（diary_graph） | **コア** | 知識ベースの地図。メインナビ5項目に含まれる |
| タイムライン（timeline） | **コア（新設）** | improvement_plan 論点6 で採用 |
| ダッシュボード（trading_dashboard） | **コア（再構成予定）** | 論点5: 汎用統計→「判断の質」へ再構成予定 |
| 全文検索・フィルタ（home） | **コア** | ただしフィルタ過多（→ 2.4） |
| 取引管理・株式分割・CSVインポート | **補助** | 思考と紐づける基盤。損益計算自体は証券会社アプリに任せる方針 |
| タグ管理・日記テンプレート | **補助** | 「設定・その他」配置で妥当 |
| 通知・EDINET 想起 | **周辺** | 論点2 Stage1-2 実装済み。想起カードはホーム上部 |
| 銘柄サマリー（diary_summary） | **周辺（統合予定）** | home と概念重複。論点10 で統合方針 |
| **investment_hub（投資判断サポート）** | **対象外（凍結）** | improvement_plan バックログ「2026-06 では手を入れない」。AI比較は SuperUser 限定 |
| **analysis_template（分析テンプレート）** | **低使用** | product_context で使用度低と認識。投資思考の記録への直接貢献が薄い |
| **CopoMo（earnings_analysis UI）** | **おまけ** | 論点1: UI改善対象外。ナビは「設定・その他」内1リンクのみ。ただし EDINET データ層（DisclosureSync）は本体基盤 |
| margin_tracking | **補助（API）** | 独立データ提供。専用画面なし |
| subscriptions | **休眠** | 制限は全バイパス中（`subscriptions/mixins.py`）。UI 露出の判断材料にしない |

**要点**: ユーザー向けに露出すべき主要動線は「日記一覧 / タイムライン / 関連グラフ / ダッシュボード / 新規作成」の5つ
（論点10、PCヘッダーは実装済み）。investment_hub・analysis_template・CopoMo は意図的に露出を下げる対象。

---

## 2. UI/UX の障害となる機能と対策

### 2.1 【バグ】「直近の取引」フィルタが取引日でなく登録日時基準

- **課題**: home の `transaction_date_range` フィルタは `Transaction.created_at`（レコード登録日時）で絞り込んでいる
  （`stockdiary/views.py:200-221`）。モデルには取引日 `transaction_date`（`stockdiary/models.py:251`、DateField・索引付き）が
  あるのに未使用。CSV 一括取込（楽天/SBI）で過去取引をまとめて登録すると、数年前の取引が「1週間以内に取引」にヒットする。
  ラベルと挙動が乖離した状態で、フィルタへの信頼を損なう。
- **対策**: `created_at__gte` → `transaction_date__gte`（DateField のため `timezone.now().date()` 基準に変更）。
- **対象**: `stockdiary/views.py:215-219`
- **効果**: フィルタ結果がラベルどおりになる（実質バグ修正）。

### 2.2 【死にコード】comparison.html（1071行）

- **課題**: `StockComparisonView` は investment_hub への恒久リダイレクト化済み（`stockdiary/views_comparison.py:17-20`）で、
  `comparison.html` への参照はゼロ。保守コストと「隠れ機能」の混乱だけが残る。
- **対策**: テンプレートを削除（**本レビューと同時に実施済み**）。
  `urls.py:123` の `stock_comparison` エントリと RedirectView は旧ブックマーク救済のため残す。
- **効果**: 1071 行の死にテンプレートが消え、grep ノイズ・改修時の誤修正リスクがなくなる。

### 2.3 【重複露出】ヘルプ/ポリシー5項目が3箇所に重複

- **課題**: ご利用ガイド・FAQ・利用規約・プライバシー・お問い合わせが
  ①PCユーザードロップダウン（`templates/base.html:936-945`）
  ②スマホフルスクリーンメニュー「設定・その他」（`base.html:1109-1184`、12項目中5項目）
  ③フッター（`base.html:1014-1030`）の3箇所に露出。機能メニューにヘルプが混在し一覧性を損なう。
- **対策**:
  - スマホメニュー「設定・その他」から5項目を削除し 12→7 項目に（残: 通知管理 / 銘柄サマリー / 投資判断サポート /
    タグ管理 / 日記テンプレート / 取引履歴アップロード / CopoMo）。代わりにメニュー下部ユーザーセクションに
    「ガイド ・ FAQ ・ お問い合わせ」の小テキストリンク行を1行追加。
  - PCドロップダウンからプライバシー・規約・FAQ を削除（残: プロフィール / 広告設定 / ご利用ガイド / ログアウト）。
  - 規約・プライバシーはフッターに一本化。
- **効果**: スマホメニューが1画面に収まり、機能とヘルプの混在が解消。リンク更新箇所も削減。

### 2.4 【複雑性】home のフィルタ過多

- **課題**: クエリパラメータが9種（query / hashtag / tag / sector / status / transaction_date_range /
  disclosure / date_range / sort）。特に「直近の取引」（transaction_date_range）と「購入時期」（date_range）の
  使い分けが UI 上判別できない。モバイルはフィルタモーダル・PC は折りたたみ済みで構造自体は妥当。
- **対策**（段階的）:
  1. ラベルのみ変更: 「直近の取引」→「売買があった時期」、「購入時期」→「初回購入の時期」
     （`home.html` のPCサイドバーとモバイルパネル両方。**name/value 属性は変更しない** — フィルタ同期JSが name 直参照のため）。
  2. 2.1 のバグ修正とセットで挙動をラベルに一致させる。
  3. 将来: 利用実態を見て transaction_date_range の統廃合を判断（廃止時は select・リセットJS・views.py を同時修正）。
- **効果**: 期間フィルタ2種の認知負荷低減。誤った絞り込み結果の解消。

### 2.5 【重複ページ】一覧/ダッシュボード系6ページ併存

home / timeline / diary_summary / trading_dashboard / diary_graph / investment_hub の6ページが「全体を見る」系として併存。

- **diary_summary**: home（日記軸）に対し銘柄軸テーブルで完全重複ではないが、論点10 の統合方針どおり
  将来は home の表示切替（カード/銘柄別テーブル）として HTMX partial 化し、ページ自体は削減するのが望ましい。
- **investment_hub / diary_graph / dashboard**: improvement_plan の決定どおり（hub 凍結・dashboard 再構成・graph 維持）。
  本レビューでは構成変更を提案しない。
- **効果**（統合実施時）: 「一覧はどこを見ればいいか」の迷いが解消し、ナビ項目も実質減る。

### 2.6 【異質タブ】detail の通知タブ

- **課題**: detail は7タブ（概要/取引履歴/継続記録/時系列/関連/通知/開示書類）でモバイルは横スクロール必須。
  「通知」だけが閲覧コンテンツでなく設定機能でタブとして異質（improvement_plan バックログ「通知タブの縮退」と一致）。
- **対策**: 通知タブを廃止し、通知設定は既存 `#notificationModal` ＋スピードダイヤルの `modal` 型アクション
  （`templates/speed_dial.html` は `modal_target` 対応済み）へ移設。
- **効果**: タブ 7→6。閲覧系タブへの集中、モバイルのタブ横スクロール緩和。

### 2.7 【保守性】巨大テンプレート・CSS

- **課題**: detail.html 4199行 / diary_form.html 3371行 / home.html 2898行 / base.html 内インラインCSS約740行 /
  diary-detail.css 2982行。UX 改修のたびに影響範囲が読みにくく、改善速度自体の障害になっている。
- **対策**: 機能変更を伴わないリファクタとして、base.html のインライン `<style>` を
  `static/css/3-components/` へ抽出（既存のCSS階層規約に従う）。detail/home の partial 化は
  各機能改修（2.6 等）の際に併せて実施する方針とし、単独の大規模リファクタは行わない。
- **効果**: 以降の UI 改修コストの逓減。STATIC_VERSION によるキャッシュ制御も効くようになる。

---

## 3. レイアウト変更提案

### 3.1 スマホメニューの痩身（小・即効）

2.3 の対策そのもの。変更対象は `templates/base.html` のみ。メニュー開閉JSは ID 直参照のためリンク削除の影響なし。

### 3.2 タイムラインへのスピードダイヤル追加（小・即効）

- **現状**: スピードダイヤル（FAB）は home / detail / diary_form / dashboard / diary_graph / diary_summary /
  notification_list / trade_upload / tags / analysis_template / diary_templates に配置済みで、
  先頭アクション「クイック記録」（`openQuickRecordSheet()`）が記録の最短動線になっている。
  **timeline.html にだけ存在しない**（`views_timeline.py` に page_actions なし）。
- **提案**: `TimelineView` に他ページ同様の `page_actions`（クイック記録＋新規作成）を追加し、
  `timeline.html` 末尾に `{% include 'speed_dial.html' with actions=page_actions %}` を追加。
- **効果**: タイムラインは「想起→追記」が自然な画面であり、振り返り中にそのままクイック記録できるようになる。
  コアバリュー（記録・振り返り）の動線の穴を最小コストで塞ぐ。

### 3.3 モバイルボトムナビゲーション（中期・条件付き推奨）

- **現状評価**: スピードダイヤルを確認した結果、「記録アクション」はほぼ全ページで1タップ確保済み。
  残る課題は**画面間ナビゲーション**で、モバイルは「右上ボタン→フルスクリーンメニュー→項目選択」の3操作。
- **提案**: 画面下固定バー（`d-lg-none`、992px 境界は既存 `pc-only-header` と同一）:
  「日記一覧 / タイムライン / ダッシュボード / メニュー（既存フルスクリーンメニューを開く）」の4項目。
  - 新規: `templates/components/bottom_nav.html`（`quick_record_sheet.html` と同じ components 配置パターン）、
    `static/css/3-components/bottom-nav.css`（z-index 1030 = bottom-sheet/メニュー 1050・speed-dial 1040 より下、
    `env(safe-area-inset-bottom)` 対応）
  - アクティブ表示は `request.resolver_match.url_name` で判定
  - **干渉調整が必須条件**: speed-dial のモバイル `bottom: 16px` にナビ高さ（約56-60px）を加算、
    `.app-footer` のモバイル padding-bottom 調整、右上フローティングナビボタンはモバイルで非表示化
  - クイック記録はスピードダイヤルが既に担っているため、ボトムナビ中央 FAB は**設けない**
    （二重 FAB はかえって混乱する）
- **効果**: 主要画面の遷移が3操作→常時1タップ。日記アプリの主利用シーン（モバイル・スキマ時間）での
  回遊コストが大幅に下がる。規模は新規2ファイル＋base.html/CSS 微修正で2-3日。

### 3.4 期間フィルタのラベル改善（小・即効）

2.4 の対策1。`home.html` のPCサイドバー・モバイルフィルタパネルの文言のみ変更（name/value 不変）。

---

## 4. 実装ロードマップ

| Phase | 内容 | 対象ファイル | 規模 |
|-------|------|-------------|------|
| **1**（0.5-1日） | 2.1 フィルタ基準日修正 / 2.3 メニュー痩身 / 3.2 timeline スピードダイヤル / 3.4 ラベル改善 | `stockdiary/views.py` / `templates/base.html` / `stockdiary/views_timeline.py` / `stockdiary/templates/stockdiary/{timeline,home}.html` | 小 |
| **2**（2-3日） | 3.3 ボトムナビ新設＋FAB/フッター干渉調整 /（任意）base.html インラインCSS抽出 | 新規 `templates/components/bottom_nav.html`・`static/css/3-components/bottom-nav.css` / `templates/base.html` / `static/css/speed-dial.css` | 中 |
| **3**（各1-2日） | 2.6 detail 通知タブ縮退 / 2.5 diary_summary の home 統合 / 2.4 期間フィルタ統廃合判断 | `detail.html` / `views.py` / `home.html` / `diary_summary.html`（統合時は削除を明示） | 中 |

## 5. リスク・注意点

1. **home のフィルタ同期JS**: PCサイドバー⇔モバイルフォーム同期とリセット処理が `name` 属性直参照。
   Phase 1 ではラベル文言のみ変更。フィルタ項目を削除する際は select・hidden input・リセットJS・views.py を必ず同時修正。
2. **HTMX 動線**: home の検索フォームは `hx-get` で `diary_list` partial を差し替える。フォーム構造変更時は
   `#diary-container` とページネーションを実機確認。detail の通知タブ削除時は `tab_content` ビューの分岐も確認。
3. **下部UIの重なり**: ボトムナビ導入時は speed-dial・bottom-sheet・フッター広告・PWA インストールバナーとの
   z-index / 位置干渉を要確認。safe-area 対応必須。
4. **通知導線**: 通知ベルは PC ヘッダーへの JS 注入のみでモバイルには出ない。スマホメニューの「通知管理」は削除しない。
5. **キャッシュ**: CSS/JS 変更時は `STATIC_VERSION` の更新を忘れない。
6. **既決定との整合**: investment_hub は露出含め現状維持。CopoMo は「設定・その他」1リンク維持。
