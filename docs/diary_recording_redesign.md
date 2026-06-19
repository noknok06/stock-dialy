# 記録設計の再検討：入力玄関の統一と「見立て」の時系列化

> North Star（`growth_os_redesign.md` と同じ）: **10年後の自分が、今日の自分の投資判断を正確に理解できる。**

本メモは「日記の記録設計」を 1 論点ずつ検討した結果の **合意（ロック状態）と段階的実装計画**。
プロダクトの判断軸は `docs/product_context.md`、検証ループの全体像は `docs/growth_os_redesign.md` に従う。

---

## 1. 背景・課題

記録設計を再検討した動機は2つ。

1. **入力玄関が2つに割れている（最大の違和感）**
   通常の新規登録（`diary_form` で StockDiary 作成）と、詳細からの継続記録登録（`DiaryNote`）が
   別画面・別アクション。Obsidian の本質は「入力アクションが1つ（書く）で、関連は後から/書きながら emerge する」点であり、
   カブログの“2つの玄関”がつながりにくさ・違和感の核になっている。

2. **多ラウンド取引で単一 `reason` が破綻する**
   同一銘柄を売買で出入りするたびに「検討理由」が生まれるが、`reason` は単一スロットのため
   上書き（履歴喪失）か末尾追記（肥大化）しかできない。

### 譲れない制約

- **銘柄ごとの管理は捨てない**（取引履歴・時系列・EDINET 開示はこの軸でしか成立しない）。
- **他日記との連携は捨てない**（銘柄横断のテーマ・関連付け）。

---

## 2. データ根拠（移行エクスポート `v2` / 208 日記の実測）

検討は admin の実データで裏付けた。

| 観点 | 実測 | 含意 |
|---|---|---|
| 多ラウンド（保有が0に戻り再エントリー）日記 | **57 / 168 取引あり日記（34%）** | 単一 reason 破綻は例外でなく常態 |
| そのうち Thesis を持つ日記 | **1 / 57** | 多ラウンドを捌く構造（Thesis 複数可）はあるが未活用 |
| `topic` の中身 | 決算分析×39・振り返り×15・株価分析×4・決算×3（=note_type 相当）＋ 単発テーマ×1多数 | topic は note_type の代用に流用されている。単発テーマ（ナフサ等）は**これからスレッド化する前提** |
| note_type 分布 | analysis 88 / news 20 / earnings 19 / retrospective 16 / insight 15 / risk 4 | note_type は機能しているが**絞り込み軸が無い** |

結論：構造の不足ではなく **「フロー（入力玄関と軸の使われ方）の設計不足」** が課題。

---

## 3. 確定した設計（ロック状態）

理想は「学び → 記録 → 銘柄」（`growth_os_redesign.md`）。保存は **銘柄起点(StockDiary)を壊さず**、
入力アクションと“見立て”の扱いだけを再設計する。

```
[ 入力アクション ]      ← 玄関は1つ「書く」。銘柄はエントリの属性
        │ routes to
[ 記録の実体 ]          ← 既存: StockDiary(reason=現在の見立て) / DiaryNote(時系列エントリ)
        │
[ 損益の計算 ]          ← 既存: AggregateService（不変）
```

| 層 | 確定内容 |
|---|---|
| **軸** | 銘柄（StockDiary）。取引・損益・EDINET・時系列の土台。**維持**。 |
| **入力** | 玄関を1つ（「書く」）に統一。銘柄はサジェストで選択／無ければその場で軽量作成。実体は既存 `quick_create_diary` / `quick_add_note` に振り分け（§5-C）。 |
| **ナラティブ** | `reason` ＝「**現在の見立て**」スロット（可変・1つ表示・第一の玄関）。**明示ボタン**で旧版を専用 note_type（`stance`）で timeline に退避。reason と継続記録は「エントリ」として**同列・地続き**。 |
| **分類/テーマ** | `note_type` ＝種類スレッド（決算分析・ニュース…／**絞り込み軸へ昇格**）。`topic` ＝銘柄内ストーリーライン（任意・サジェスト付き・**維持**）。`@タグ` ＝銘柄横断テーマ（`DiaryTagDirection` で順連動/逆相関）。 |
| **関係（注釈つきエッジ）** | 銘柄×テーマ＝`DiaryTagDirection`（方向は既存／rationale テキスト追加は段階2）。銘柄×銘柄＝同業は `sector` 自動、手動 `linked_diaries` の種別+note 化は段階2。検証＝`Thesis`/`Verdict` を任意で深掘り。 |
| **関連付け UX** | すべてサジェスト（最初の必須要件）。インライン `(コード)` 言及・`@タグ`。 |

### 「現在の見立て」＋明示退避ボタンの挙動（確定）

- **現在の見立て**（`reason`）：常に1つ表示・編集可。購入検討理由の第一玄関。
- **通常の編集・保存**：その場で更新。**履歴を作らない**（誤字・微修正で timeline を汚さない）。
- **「新しい見立てに更新」ボタン**押下時：
  1. その時点の `reason` 内容を `DiaryNote(note_type='stance')` として **固定退避**（日付つき・前の見立てと同列）。
  2. スロットは内容を保持したまま編集状態へ（＝前回をたたき台に**引き継ぎ**）。
  3. 次に同ボタンを押すまでは「現在の見立て」の更新扱い。
- 再エントリー時は**自動退避しない**。「前回から見立ては動きましたか？」とボタンを**そっと提示するだけ**（採用＝手動トリガー）。

### 純 Obsidian にはしない（意図的）

銘柄は取引・損益・EDINET という構造化データを正当に持つ。統一するのは **“ナラティブの入力アクション”であって、銘柄エンティティの廃止ではない**。「銘柄のまとめ」は入力玄関を増やさない**読み/合成面**（段階2、§5-H）。

---

## 4. 検索・findability（退避先の妥当性確認）

退避先を timeline（DiaryNote）にする根拠：**既存の全文検索がノートを対象に含む**。

- `apply_diary_search`（`stockdiary/utils.py`）は `notes__content` / `notes__topic` を検索対象に含む。
- `annotate_search_matches` がヒットしたノートの抜粋・件数を返す。
- → 「現在の見立て(reason)」も「退避した旧見立て(stance note)」も**両方とも後から検索で辿れる**。

付帯条件（段階1で担保）：
1. 退避は**専用 note_type `stance`**（ニュース等と区別、埋もれさせない）。
2. 「**見立ての変遷**」だけを並べる note_type 絞り込み／ビューを用意。
3. 文字数の不整合を先に解消（§5-N）。

---

## 5. シニアレビューで確定した論点

### 段階1で潰す（順序：N → B → C → E）

**N. 文字数制限の不整合（実害）— 解決方針確定**
`StockDiary.reason` は max 5000 字、`DiaryNote.content` は max 3000 字＋`clean()` で超過例外。
長い見立てを退避すると保存例外になる。→ **退避先 note の上限を 5000 字へ引き上げる**。
- `DiaryNote.content` `max_length=3000 → 5000`（`stockdiary/models.py`）
- `DiaryNote.clean()` の超過チェック `> 3000 → > 5000`（同上）
- クイック記録フォームの `MAX_NOTE_LENGTH = 3000 → 5000`（`detail.html`）＋ `DiaryNoteForm` / `quick_add_note` の長さ検証
- `AlterField` マイグレーション 1 本（本番 PostgreSQL への適用は別途 `migrate`）

**B. note_type 命名の衝突回避**
退避ノートは **専用 note_type `stance`（「見立て」）** を新設し、構造化モデル `Thesis`（claim 200字＋Verdict）とは
明確に分離する。`Thesis.claim` は 200 字で reason 全文は入らない＝両者は別レイヤと確定。
- `DiaryNote.TYPE_CHOICES` に `('stance', '見立て')` を追加。

**C. 統一玄関の振り分けキー**
`StockDiary` に `(user, stock_symbol)` のユニーク制約は**無い**（規約であり DB 保証ではない）。統一玄関の振り分けで仕様化する：
- 既存判定キー＝ `user` × `stock_symbol`（非空）。一致が複数あれば**最新更新日記**に追記、なければ新規作成。
- **symbol 空のメモ日記**は symbol 照合不可 → 明示選択（サジェスト）必須、または常に新規。
- 通貨（USD）・業種は作成時に補完（既存の株式情報 API）。

**E. note_type を「使える軸」にする（前提整備）**
現状 note_type はクイックフォームで hidden 固定 `analysis`、絞り込み UI も無い。段階1の前提として：
- 入力 UI で note_type を選択可能化（`stance` はボタンからは選ばせず、退避アクション専用にする）。
- 継続記録に **note_type 絞り込みチップ**を追加（重要度チップと同方式）。

### 段階2以降（破壊度・コストが高い／未定義）

| 論点 | 内容 | 扱い |
|---|---|---|
| **F** | `DiaryTagDirection` に `rationale`（理由テキスト）追加＋方向トグル UI 拡張＋「まとめ」表示 | 段階2（マイグレーション） |
| **G** | `linked_diaries` を `relation_type`+`note` 付き through モデル化（既存リンク移行・グラフ参照 `linked_diaries.through` 改修） | 段階2（大きめ移行）。同業は `sector` 自動で当面充足 |
| **H** | 「銘柄のまとめ」＝何を合成表示するか（現在の見立て＋タグ方向＋関連銘柄＋Verdict 傾向／編集可否） | 要設計 |
| **K** | 「振り返り」系の役割整理：①退避見立て（前向きの判断履歴）／②retrospective ノート（軽い答え合わせ）／③Verdict（構造化）。重複させない線引きを確定 | 要設計 |

---

## 6. 段階的実装計画

| Phase | 内容 | 依存 |
|---|---|---|
| **9a** | N（文字数）→ B（`stance` 追加）→ C（振り分けキー）→ E（type 選択＋絞り込み） | 新モデルなし・破壊的移行なし |
| **9b** | 統一玄関 UI（「書く」1ボタン → 既存 `quick_create_diary`/`quick_add_note` 振り分け）＋「現在の見立て」スロット＋明示退避ボタン＋「見立ての変遷」ビュー | 9a |
| **9c** | F（タグ方向 rationale）／H（銘柄のまとめ） | 9b |
| **9d** | G（linked_diaries through 化）／K の整理反映 | 9c |

`AggregateService`（FIFO 損益）には一切触れない。統一玄関で取引も作る場合は **作成・更新・削除後に必ず `AggregateService.recalculate(diary)` を呼ぶ**（CLAUDE.md 規約）。

---

## 7. pytest 方針（テスト考慮）

テスト基盤は `pytest-django` + `config.test_settings`（`--nomigrations` / `--reuse-db`）。
**`--nomigrations` のためモデルの `max_length` 変更はテストに自動反映される**が、本番用 `AlterField`
マイグレーションは別途作成・適用が必要（テストの合否だけで「移行済み」と判断しない）。

### 既存テスト（壊さない／回帰確認）

| ファイル | 注意点 |
|---|---|
| `tests/test_diary_note_topic.py` | `topic` UI は**維持**する決定。`name="topic"` / `switchNotesView` / `notes-view-topic` の assert を壊さないこと。 |
| `tests/test_thesis_verdict.py` / `test_demo_verification_loop.py` | `stance` note_type 追加が `Thesis`/`Verdict` に干渉しないこと。 |
| `tests/test_retrospective_topic.py` | `retrospective` の `RETROSPECTIVE_TOPIC` 自動付与ロジックは不変。 |
| `tests/test_migration.py` | エクスポート/インポートの往復で **新 note_type `stance` と 5000 字 content** が保持されること。 |
| `tests/test_backlinks.py` / `test_relation_graph.py` | 退避見立て（= note）内の `(コード)` 言及が関連エッジ・バックリンクに反映されること。 |
| `tests/test_event_timeline.py` / `test_timeline.py` | timeline に `stance` エントリが正しく並ぶこと。 |

### 追加テスト（段階9a–9b）

`@pytest.mark.django_db`、`authenticated_client` / `sample_diary` / `diary_with_notes` / `another_user`
等の既存フィクスチャ（`tests/conftest.py`）を再利用する。

1. **文字数（N）** — `DiaryNote.content` が 5000 字を受理し、5001 字で `ValidationError`。
   `clean()` の境界（5000/5001）を直接検証。
2. **退避アクション（明示退避）** — 「新しい見立てに更新」POST で
   `DiaryNote(note_type='stance')` が当日付で作られ、内容＝退避前 `reason`。
   通常編集（微修正 POST）では stance ノートが**作られない**ことも検証。
3. **`stance` と Thesis の分離（B）** — stance ノート作成が `Thesis` レコードを生成しないこと。
4. **検索 findability（§4）** — 退避した stance ノート内の語が `apply_diary_search` でヒットし、
   `annotate_search_matches` の `match_note` / `match_note_snippet` に出ること。
5. **note_type 絞り込み（E）** — type 指定で対象ノートのみ返ること。
6. **統一玄関の振り分け（C）** — 既存 symbol に「書く」と既存日記へ note 追記、未知 symbol で新規日記＋reason、
   symbol 空（メモ）の経路、他ユーザー資産の 404（`test_diary_note_topic.py::test_edit_note_rejects_other_users_note` に倣う）。

### マーカー / 実行

```bash
pytest tests/test_diary_note_topic.py tests/test_migration.py   # 影響範囲の重点
pytest -m django_db
pytest                                                          # 全体（CI: .github/workflows/django-tests.yml）
```

カバレッジ対象は `stockdiary` / `analysis_template` / `tags`。新規ロジックは `stockdiary` 配下に最小増設し、
再利用可能部分は `services/` / `utils.py` に切り出す（新規アプリは作らない）。

---

## 8. 技術メモ

- Django + Templates + Bootstrap + HTMX。新規アプリは作らず `stockdiary` 内に最小増設。
- サジェスト UI は既存 `static/js/hashtag-autocomplete.js`（CodeMirror 連携）を基底化して再利用する。
- 退避・統一玄関は既存 HTMX パターン（部分テンプレート応答）に合わせる。
- `AggregateService`（FIFO 損益）は不変＝意思決定の質と損益を疎結合に保つ。
