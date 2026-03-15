# カブログ バージョンアップ方向性

> 策定日: 2026-03-15
> ブランチ: `claude/explore-upgrade-direction-9dsot`

## 基本方針

**AIコストをかけない方向で、既存インフラを最大活用する。**

機能評価の判断軸:
> 「これは自分の投資思考の記録・蓄積・振り返りに直接貢献するか？」

- ✅ 記録をより豊かにする
- ✅ 蓄積した記録を探しやすくする
- ✅ 振り返りや自己発見を助ける
- ❌ 売買操作や外部データ取得が主目的
- ❌ 証券会社アプリが既にうまくやっていること

---

## 実装済み (このブランチ)

### 方向性B: 投資前思考スキャフォールド

**対象ファイル**: `stockdiary/templates/stockdiary/diary_form.html`

日記作成フォームに **ガイドモード** を追加。Markdownの自由入力に加えて、
4つの構造化フィールドで投資仮説を記録できる。

| フィールド | 目的 |
|-----------|------|
| 投資仮説 | 市場が見落としていることは？ |
| カタリスト | 仮説が証明されるトリガーは？ |
| 反論への回答 | 弱気論とその反論 |
| 損切り条件 | 仮説が外れたら何をきっかけに売るか |

**動作**:
- フリーモード（既存EasyMDE）とガイドモードをトグルで切替
- ガイドモードで入力した4フィールドは、送信時にMarkdown見出し付きで結合し、
  既存の `reason` フィールドにそのまま保存（モデル変更なし）
- リアルタイムの「0/4項目入力済み」バッジ表示

---

### 方向性A: 定期レビューワークフロー

**対象ファイル**:
- `stockdiary/models.py` — `DiaryNote.is_review`, `DiaryNote.review_verdict`, `ReviewSchedule` モデル追加
- `stockdiary/migrations/0001_add_review_workflow.py` — マイグレーション
- `stockdiary/views.py` — `review_page`, `review_schedule_save` ビュー追加
- `stockdiary/urls.py` — `/stockdiary/<id>/review/`, `/stockdiary/<id>/review/schedule/` 追加
- `stockdiary/tasks.py` — `process_review_notifications`, `setup_review_schedule` タスク追加
- `stockdiary/templates/stockdiary/review_page.html` — 新規テンプレート
- `stockdiary/templates/stockdiary/detail.html` — 継続記録タブにスケジュール設定UI追加

**動作**:
1. 日記詳細 → 継続記録タブ → 定期レビューパネルからスケジュール設定（30/60/90/180日）
2. 期日になると Push通知（既存 `notification_service.py` + `PushSubscription` 使用）
3. `/stockdiary/<id>/review/` でレビューページを開き:
   - 元の投資理由を再確認
   - 直近の継続記録タイムラインを参照
   - 「仮説は有効 / 部分的に有効 / 無効」を選択して記録
4. レビュー記録後、次回レビュー日が自動更新される

**新規モデル**:

```python
class ReviewSchedule(models.Model):
    diary           = ForeignKey(StockDiary)
    interval_days   = PositiveIntegerField(choices=[30,60,90,180])
    next_review_date = DateField()
    is_active       = BooleanField(default=True)
```

```python
# DiaryNote に追加
is_review      = BooleanField(default=False)
review_verdict = CharField(choices=['valid', 'partially', 'invalid'], null=True)
```

---

## 今後の検討事項（未実装）

### 方向性C: EDINET連携（コスト不要）

`earnings_analysis` アプリの既存データ（`DocumentMetadata`, `SentimentResult`）を
日記詳細に表示し、ワンクリックで `DiaryNote` を作成できるようにする。

- 新規Gemini API呼び出しは不要（保存済みデータを再利用）
- 実装箇所: `stockdiary/views.py` に HTMXパーシャルビュー追加, `detail.html` に折りたたみセクション

### 方向性D: エクスポートと学習デッキ（コスト不要）

- `@media print` CSS + 専用テンプレートによる銘柄別PDFレポート出力
- 年次投資日誌HTML (`/stockdiary/export/YYYY/`)
- JSON完全エクスポート（管理コマンド + Premium ユーザー向けUIボタン）

### 方向性E: ダッシュボード強化（コスト不要）

既存SQLクエリとChart.jsを使った分析の追加:
- 勝率ヒートマップ（業種×月）
- 平均保有期間 vs ROI 散布図
- タグ別ROIランキング

---

## AI不使用でも「AIらしい体験」を提供する代替手段

| AI機能 | 低コスト代替 |
|--------|------------|
| 意味的類似日記の発見 | TF-IDFベースのテキスト類似度 (scikit-learn) |
| 投資仮説の品質評価 | ルールベース（4セクション入力率・文字数・キーワード確認） |
| 月次ふりかえりレポート | テンプレートベースの自動集計文章生成 |

これらはサーバー処理のみで実現可能（外部APIコストなし）。
