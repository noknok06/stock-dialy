# 依存ライブラリ更新 & PostgreSQL 16 移行 手順書

> 実施日: 2026-06-02
> ブランチ: `claude/unsupported-library-check-fzq3I`
> 対象環境: AlmaLinux 9.5 / Python 3.11 / 実行ユーザー `naoki` / `/var/www/django/stock-dialy`

サポート終了（EOL）・非推奨ライブラリの棚卸しと、それに伴う本番アップグレードの記録。
同種の作業を再実施する際の参照用。

---

## 1. 背景：何が EOL だったか

| ライブラリ | 旧 | 状況 | 対応 |
|-----------|----|----|------|
| **Django** | 4.2.27 | LTS が 2026-04-07 に EOL | **5.2 LTS** へ（2028-04 まで） |
| **google-generativeai** | 0.8.6 | 2025-11 非推奨 / 2026-06-24 削除予定 | **google-genai** へ移行 |
| google-ai-generativelanguage | 0.6.15 | 旧SDKの内部依存 | 削除 |
| **django-q** | 1.3.9 | 2021年以降メンテ停止 | 後継 **django-q2** へ |
| プレースホルダ各種 | — | 実体のない/有害なパッケージ | requirements から除去 |

**重要な前提条件**: Django 5.2 は **PostgreSQL 14 以上が必須**。
本番は PostgreSQL 13.20 だったため、Django 5.2 を動かすには **DB を先にアップグレードする必要があった**。

PostgreSQL バージョン要件の対応表:

| Django | 必要な PostgreSQL |
|--------|------------------|
| 4.2 LTS | 12+ |
| 5.1 | 13+ |
| **5.2 LTS** | **14+** |

> AlmaLinux 9 の AppStream には PostgreSQL **14 が無く 13 / 15 / 16** が提供される。
> 14以上を満たす最新の AppStream モジュールとして **PostgreSQL 16** を採用した。

---

## 2. コード/依存の変更内容

`requirements.txt` と Gemini 連携コードを変更（ブランチ `claude/unsupported-library-check-fzq3I`）。

### 2.1 requirements.txt

```diff
-Django==4.2.27
+Django==5.2.3
-django-q==1.3.9
+django-q2==1.8.0
-google-generativeai==0.8.6
-google-ai-generativelanguage==0.6.15
+google-genai==1.21.1
-django-rest-framework==0.1.0   # スタブ。実体は djangorestframework
-django-utils==0.0.2            # 未使用プレースホルダ
-dotenv==0.9.9                  # ダミー。実体は python-dotenv
-frontend==0.0.3                # 未使用プレースホルダ
-pathlib==1.0.1                 # Python3で有害なバックポート
-tools==1.0.16                  # 未使用プレースホルダ
```

> **django-q2** はインポート名・アプリ名ともに `django_q` のままなので、
> `INSTALLED_APPS` やコードの変更は不要。

### 2.2 Gemini SDK 移行（google-generativeai → google-genai）

対象 5 ファイル:
- `earnings_analysis/services/gemini_service.py`
- `earnings_analysis/services/gemini_insights.py`
- `earnings_analysis/services/breakout_detector.py`
- `earnings_analysis/services/ai_expert_analyzer.py`
- `stockdiary/services/gemini_stock_analysis.py`

API の対応:

```python
# 旧 (google-generativeai)
import google.generativeai as genai
genai.configure(api_key=api_key)
self.model = genai.GenerativeModel("gemini-2.5-flash-lite")
response = self.model.generate_content(
    prompt,
    generation_config=genai.types.GenerationConfig(max_output_tokens=..., temperature=...),
)

# 新 (google-genai)
from google import genai
self.client = genai.Client(api_key=api_key)
self.model = "gemini-2.5-flash-lite"   # モデル名は文字列で保持（既存の真偽値チェックを維持）
response = self.client.models.generate_content(
    model=self.model,
    contents=prompt,
    config=genai.types.GenerateContentConfig(max_output_tokens=..., temperature=...),
)
```

`response.text` / `response.prompt_feedback` は新SDKでもそのまま利用可。

### 2.3 検証（ローカル）

```bash
DJANGO_TESTING=1 DJANGO_SETTINGS_MODULE=config.test_settings pytest tests/
# → 71 passed（Django 5.2.3 + django-q2 1.8.0 + google-genai 実環境）
python manage.py check   # → System check identified no issues
```

---

## 3. sudoers 設定（デプロイの自動再起動を許可）

`appleboy/ssh-action` は TTY 無しで実行されるため、`sudo systemctl restart` が
パスワード要求で失敗する。対象コマンド限定で NOPASSWD を付与する。

```bash
sudo visudo -f /etc/sudoers.d/deploy-restart
```

内容（AlmaLinux 9 の systemctl は `/usr/bin/systemctl`）:

```
naoki ALL=(root) NOPASSWD: /usr/bin/systemctl restart gunicorn, /usr/bin/systemctl restart django-qcluster
```

```bash
sudo chmod 0440 /etc/sudoers.d/deploy-restart
sudo visudo -c                                  # 構文チェック
sudo -n systemctl status gunicorn --no-pager    # パスワードを聞かれなければ成功
```

あわせて、デプロイ Workflow（`.github/workflows/django-tests.yml`）の deploy ジョブに
`django-qcluster` の再起動を追加済み（django-q → django-q2 への移行を確実に反映するため）:

```bash
sudo systemctl restart gunicorn
sudo systemctl restart django-qcluster   # 追加
```

---

## 4. PostgreSQL 13 → 16 移行（dump / restore 方式）

RHEL 系の AppStream モジュールは「13 と 16 を同時インストール」できず、
`pg_upgrade`（両バージョン同居が前提）が使いにくい。
DB サイズが小さい（ダンプ約 83MB）ため、**dump → 入替 → restore** を採用した。

### 前提
- 既存: AppStream の `postgresql-13`、サービス名 `postgresql`、データ `/var/lib/pgsql/data`
- SELinux: enforcing（コンテキスト補正に `restorecon` を使う）

### 手順

```bash
# ── STEP 0: 事前確認 ──────────────────────────────
dnf module list postgresql           # 16 が利用可能なこと
sudo -u postgres psql -c "\l+"       # DBサイズ確認

# ── STEP 1: バックアップ（必ず成功確認）──────────────
# 注: sudo -u postgres は postgres が読めるディレクトリで実行する。
#     "could not change directory to /home/naoki" は無害な警告。
sudo -u postgres pg_dumpall > ~/pg13_full_backup_$(date +%F).sql
ls -lh ~/pg13_full_backup_*.sql
grep -c "PostgreSQL database cluster dump complete" ~/pg13_full_backup_*.sql   # → 1

# ── STEP 2: アプリ停止 → 旧データ退避 ─────────────────
sudo systemctl stop gunicorn django-qcluster
sudo systemctl stop postgresql
sudo systemctl disable postgresql
sudo mv /var/lib/pgsql/data /var/lib/pgsql/data.pg13   # 削除せず退避（ロールバック用）

# ── STEP 3: PostgreSQL 16 インストール ────────────────
sudo dnf -y module reset postgresql
sudo dnf -y module enable postgresql:16
sudo dnf -y install postgresql-server postgresql-contrib
psql --version                       # PostgreSQL 16.x

# ── STEP 4: 新クラスタ初期化 ──────────────────────────
sudo postgresql-setup --initdb

# ── STEP 5: 旧設定を退避ディレクトリから復元 ──────────
# pg_hba.conf（認証ルール）はそのままコピー
sudo cp /var/lib/pgsql/data.pg13/pg_hba.conf /var/lib/pgsql/data/pg_hba.conf
sudo chown postgres:postgres /var/lib/pgsql/data/pg_hba.conf
sudo chmod 600 /var/lib/pgsql/data/pg_hba.conf
sudo restorecon -v /var/lib/pgsql/data/pg_hba.conf

# postgresql.conf は「丸ごとコピーしない」。
# PG16で削除/改名されたGUCで起動失敗する恐れがあるため、カスタム行だけ追記する:
#   sudo grep -vE '^[[:space:]]*#|^[[:space:]]*$' /var/lib/pgsql/data.pg13/postgresql.conf
# 本番で実際に追記した内容（listen_addresses / port はデフォルトのままで可）:
sudo tee -a /var/lib/pgsql/data/postgresql.conf > /dev/null <<'EOF'

# --- restored from PG13 (2026-06-02) ---
max_connections = 100
shared_buffers = 128MB
dynamic_shared_memory_type = posix
max_wal_size = 1GB
min_wal_size = 80MB
logging_collector = on
log_filename = 'postgresql-%a.log'
log_truncate_on_rotation = on
log_rotation_age = 1d
log_rotation_size = 0
log_timezone = 'Asia/Tokyo'
datestyle = 'iso, ymd'
timezone = 'Asia/Tokyo'
lc_messages = 'ja_JP.UTF-8'
lc_monetary = 'ja_JP.UTF-8'
lc_numeric = 'ja_JP.UTF-8'
lc_time = 'ja_JP.UTF-8'
default_text_search_config = 'pg_catalog.simple'
EOF

# ── STEP 6: 起動 → クリーン復元 ───────────────────────
sudo systemctl enable --now postgresql
# 復元はリダイレクト方式（postgres は /home/naoki を読めないため）。
# 空クラスタへ流すのでエラーはほぼ出ない（最初の "postgres ロール既存" 程度）。
sudo -u postgres psql < ~/pg13_full_backup_$(date +%F).sql > ~/restore.log 2>&1
grep -iE "ERROR|FATAL" ~/restore.log | grep -v 'ロール"postgres"はすでに' | head

# ── STEP 7: 検証 → アプリ再起動 ───────────────────────
sudo -u postgres psql -c "SELECT version();"                 # 16.x
sudo -u postgres psql -c "\l"                                # kabulog 等が存在
sudo -u postgres psql -d kabulog -c "SELECT count(*) FROM stockdiary_stockdiary;"

cd /var/www/django/stock-dialy && source venv/bin/activate
python manage.py check --database default --settings=config.settings   # 0 issues
sudo systemctl restart gunicorn django-qcluster
sudo systemctl status gunicorn django-qcluster --no-pager | head -8
```

### 起動後の確認ポイント
- 起動ログに `PostgreSQL 14 or later is required` 警告が**出ない**こと
- サイト表示・ログイン
- AI分析 / TDNETレポート（google-genai 動作）
- 通知・タスク（django-q2 / qcluster 動作）

---

## 5. ロールバック（PG16 で問題が出た場合）

```bash
sudo systemctl stop postgresql && sudo systemctl disable postgresql
sudo dnf -y module reset postgresql && sudo dnf -y module enable postgresql:13
sudo dnf -y install postgresql-server
sudo rm -rf /var/lib/pgsql/data
sudo mv /var/lib/pgsql/data.pg13 /var/lib/pgsql/data   # 退避した旧データを戻す
sudo systemctl enable --now postgresql
# この場合 Django は 4.2 に戻す必要あり（requirements.txt を Django==4.2.27 へ）
```

---

## 6. 移行後のクリーンアップ（数日様子見後）

```bash
# 旧データ・バックアップ・ログの削除
sudo rm -rf /var/lib/pgsql/data.pg13
rm -f ~/pg13_full_backup_*.sql ~/restore.log

# venv に残る旧パッケージの除去（任意・残っていても無害）
cd /var/www/django/stock-dialy && source venv/bin/activate
pip uninstall -y google-generativeai google-ai-generativelanguage django-q
```

---

## 7. ハマりどころ（実作業で遭遇）

| 症状 | 原因 | 対処 |
|------|------|------|
| `could not change directory to "/home/naoki"` | `sudo -u postgres` の起動ディレクトリを postgres が読めない | 無害。気になれば postgres が読めるディレクトリで実行 |
| `ls /var/lib/pgsql/pg13_all_*.sql` が「ファイルが無い」 | naoki が `/var/lib/pgsql`(700) を読めず `*` グロブが展開されない | バックアップは `>` でホームに作る（naoki 権限で書ける） |
| restore で大量の「既に存在します」 | **起動中の PG13（データ投入済み）** にダンプを流した | 無害。復元は**空の新クラスタ**に対して行う |
| `sudo systemctl restart` がパスワード要求で失敗 | sudoers に NOPASSWD が無い（TTY無し実行） | §3 の sudoers 設定 |
| 起動時 `PostgreSQL 14 or later is required` | Django 5.2 が PG13 を非サポート | PG14+ へ（本手順で PG16 化） |

---

## 8. 関連ファイル

- `requirements.txt` — 依存定義
- `.github/workflows/django-tests.yml` — CI/CD（push → test → deploy）
- `etc/systemd/system/django-qcluster.service` — タスククラスタ
- `/etc/sudoers.d/deploy-restart` — デプロイ再起動の NOPASSWD（サーバー上のみ）
- `docs/server-reconstruction.md` — サーバーゼロ再構築手順
