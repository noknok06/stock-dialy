# AI駆動開発 ケイパビリティマップ

カブログを **AI（Claude Code）で安全に・速く開発するための基盤**を1枚に視覚化したもの。
別システムの「コンテキストレイヤー」図を、*AI 開発者へのコンテキスト供給*として翻案した。

![AI駆動開発 ケイパビリティマップ](assets/ai_driven_development.png)

---

## 中心アイデア

AI駆動開発の設計とは「AI開発者にコンテキストレイヤーを供給する」こと。
到達点（North Star）は3つ：

1. **AI が規約を忘れても壊れない**
2. **指標・概念の定義を取り違えない**
3. **自分の変更を自分で検証できる**

## 3本柱

| 柱 | 意味 | 主な実体 |
|---|------|----------|
| **① コンテキスト供給** | AI に与える「正本」 | オントロジー（`reason＝背景`／`topic＝まとめスレッド`／`note_type＝種類軸`／Thesis→Verdict→Learning）・`stockdiary/services/metrics.py`（指標定義の正本）・`CLAUDE.md`（規約） |
| **② 構造的不変条件** | 規約ではなく構造で守る | `AggregateService.deferred()`（一括操作の唯一の入口）・`Transaction.save()/delete()` の自動再集計・定義の単一正本（DRY）・変更の分離（migration） |
| **③ 検証ループ** | AI が自分で確かめ自己修正 | pytest（全 green）・回帰でオントロジーを固定・`run-app`/`verify` スキル・GitHub Actions |

底の帯は「作業単位・運用レイヤ」（`improvement_plan.md` の論点管理／設計ファースト／意図を残すコミット）。

## 関連ドキュメント

- オントロジー（reason＝背景／topic）の確定: `docs/diary_recording_redesign.md`
- プロダクトの判断軸: `docs/product_context.md`
- 成長OS（Thesis→Verdict→Learning）: `docs/growth_os_redesign.md`
- 指標定義の正本: `stockdiary/services/metrics.py`

---

## 図の再生成

図は `docs/assets/ai_driven_development.html` を正本とし、ヘッドレス Chromium で PNG 化する。

```bash
chromium --headless --no-sandbox --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=2 --window-size=1640,1200 \
  --screenshot=docs/assets/ai_driven_development.png \
  "file://$PWD/docs/assets/ai_driven_development.html"
```

内容を更新するときは HTML を編集してから上記を再実行する（PNG は生成物）。
