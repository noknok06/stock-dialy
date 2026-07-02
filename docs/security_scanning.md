# セキュリティ検知スタック（従量課金なし）

「AIの力で脆弱性を検知したいが従量課金は避けたい」という方針に対し、**公開リポジトリ**である利点を
最大活用して、追加課金ゼロ（無料 or 既存サブスクリプション定額）で検知を二層化する。

> 課金の原則：**Gemini/Claude API を CI に直結しない**（per-token 課金になる）。
> AIによる検知は「公開リポジトリ無料の CodeQL/Copilot Autofix」と「Claude Code の定額レビュー」で賄う。

## コスト（GitHub 上の課金）

**公開リポジトリのため、GitHub Actions は標準ランナーで無制限・無料**。コミット/プッシュの
回数は課金に無関係。CodeQL・Dependabot・Secret scanning・Copilot Autofix もすべて
公開リポジトリは無料。課金が出るのは「非公開リポジトリの無料枠超過」か「大型/GPUランナー」
だけで、本リポジトリはどちらも該当しない。

無駄ラン削減（金額ではなく速さ・見やすさのため）も設定済み：

- 全ワークフローは `push:[main,develop]` と `pull_request:[main,develop]` のみで起動。
  **作業ブランチへの普段のコミットでは何も走らない**（走るのは PR と main/develop への push）。
- `concurrency: cancel-in-progress` で連続 push 時は古いランを自動キャンセル。
- `paths-ignore: ['**.md','docs/**']` でドキュメントのみの変更はスキャンしない。

## 導入済みの仕組み

| 仕組み | 種別 | AI性 | 課金 | 何を検知 | 所見の場所 |
|---|---|---|---|---|---|
| **CodeQL**（`.github/workflows/codeql.yml`） | セマンティックSAST | ○ AI-adjacent | 公開リポジトリ無料 | SQLi・XSS・SSRF・path traversal・秘密の流出経路 | Security → Code scanning |
| **Copilot Autofix** | LLM 修正提案 | ◎ LLM | 公開リポジトリ無料 | CodeQL所見への修正パッチ提案 | 各 Code scanning alert |
| **Dependabot**（`.github/dependabot.yml`） | 依存CVE | ✕ | 無料 | 脆弱な依存パッケージ＋更新PR | Security → Dependabot |
| **Secret scanning** | 秘密検知 | ✕ | 公開リポジトリ無料 | コミットされた鍵・トークン | Security → Secret scanning |
| **Bandit**（`security-scan.yml`） | Python SAST | ✕ | 無料 | 危険関数・ハードコード秘密・弱い乱数 | Actions ログ（advisory） |
| **pip-audit**（`security-scan.yml`） | 依存CVE | ✕ | 無料 | requirements.txt の既知脆弱性 | Actions ログ（advisory） |
| **Claude Code `/security-review`** | LLMレビュー | ◎ LLM | 既存サブスク（定額） | 文脈依存の論理欠陥・認可漏れ | 対話／PR時に手動実行 |

二層構造：**AI/セマンティック検知（CodeQL＋Copilot＋Claude）** ＋ **決定的検査（Bandit／依存／秘密）**。

## 有効化の手順（リポジトリ設定・一度だけ）

ワークフロー/設定ファイルはコミット済み。GitHub 側で以下を有効化する（公開リポジトリは無料）：

1. **Settings → Code security and analysis** で次を ON：
   - Dependabot alerts / Dependabot security updates
   - Secret scanning / Push protection
   - Code scanning（CodeQL ワークフローを認識）＋ **Copilot Autofix**
2. CodeQL は push/PR（main・develop）と毎週、`workflow_dispatch` で手動実行可。
   このブランチで今すぐ試すには Actions から CodeQL を手動起動するか、PR を作成する。

## 段階的な厳格化

- 初期は Bandit / pip-audit を **advisory（`continue-on-error`）** で運用し、既存の所見を棚卸し。
- ノイズを潰したら `continue-on-error` を外して**ブロッキング化**、または Bandit を SARIF 出力にして
  Security タブへ集約する（`github/codeql-action/upload-sarif`）。
- Django 固有ルールを増やしたい場合は Semgrep OSS（`p/django`・無料・トークン不要）を追加候補に。

## 運用フロー（AI力の使いどころ）

- **常設（自動・無料）**：CodeQL＋Dependabot＋Secret scanning が push/PR/定期で回る。
- **節目（定額・高文脈）**：認証・フォーム・`migration_import`（ファイルアップロード）・raw クエリを
  変更する PR では Claude Code `/security-review` を手動実行し、論理的欠陥を補う。
