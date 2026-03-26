# サーバー再構築手順

このドキュメントはサーバーをゼロから再構築する際の手順書です。

---

## 前提条件

| 項目 | バージョン / 備考 |
|------|-----------------|
| OS | Linux (Fedora / RHEL 系) |
| Python | 3.11 |
| DB | PostgreSQL |
| Redis | **不要**（Django-Q は ORM ブローカーを使用） |
| 実行ユーザー | `naoki` |
| デプロイ先 | `/var/www/django/stock-dialy` |

### OS パッケージインストール

```bash
# Fedora / RHEL 系
sudo dnf install -y python3.11 python3.11-devel python3.11-pip \
    postgresql postgresql-server postgresql-devel \
    gcc git

# PostgreSQL 初期化 & 起動
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql
```

---

## 1. リポジトリ取得・配置

```bash
sudo mkdir -p /var/www/django
sudo chown naoki:naoki /var/www/django

cd /var/www/django
git clone <リポジトリURL> stock-dialy
cd stock-dialy
```

---

## 2. Python 仮想環境・依存パッケージ

```bash
cd /var/www/django/stock-dialy

python3.11 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. 環境変数設定

```bash
cp .env.example .env
vim .env   # 各変数を実際の値に書き換える
```

### 必須変数一覧

| 変数名 | 説明 | 取得方法 |
|--------|------|---------|
| `SECRET_KEY` | Django シークレットキー | `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'` |
| `DB_NAME` | DB 名 | 手順 4 で作成するもの |
| `DB_USER` | DB ユーザー | 手順 4 で作成するもの |
| `DB_PASSWORD` | DB パスワード | 手順 4 で設定するもの |
| `DB_HOST` | DB ホスト | `localhost` |
| `DB_PORT` | DB ポート | `5432` |
| `EMAIL_HOST_PASSWORD` | Gmail アプリパスワード | Google アカウント → セキュリティ → アプリパスワード |
| `GEMINI_API_KEY` | Google Gemini API キー | Google AI Studio |
| `EDINET_API_KEY` | EDINET API キー | 金融庁 EDINET |
| `GOOGLE_CLIENT_ID` | Google OAuth クライアント ID | Google Cloud Console → 認証情報 |
| `GOOGLE_CLIENT_SECRET` | Google OAuth クライアントシークレット | 同上 |
| `VAPID_PUBLIC_KEY` | Web Push 公開鍵 | 下記コマンドで生成 |
| `VAPID_PRIVATE_KEY` | Web Push 秘密鍵 | 下記コマンドで生成 |
| `VAPID_ADMIN_EMAIL` | Push 通知管理メール | 任意のメールアドレス |

**VAPID キー生成:**
```bash
python -c "
from py_vapid import Vapid
v = Vapid()
v.generate_keys()
print('VAPID_PUBLIC_KEY=' + v.public_key.decode())
print('VAPID_PRIVATE_KEY=' + v.private_key.decode())
"
```

### オプション変数（必要な場合のみ）

```env
# Stripe 決済
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

---

## 4. データベース作成

```bash
sudo -u postgres psql <<EOF
CREATE USER naoki WITH PASSWORD 'your_password';
CREATE DATABASE stock_dialy OWNER naoki;
GRANT ALL PRIVILEGES ON DATABASE stock_dialy TO naoki;
EOF
```

`.env` の `DB_NAME` / `DB_USER` / `DB_PASSWORD` をここで設定した値に合わせる。

---

## 5. マイグレーション

依存関係の順に `makemigrations` してから `migrate` する。

```bash
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings

# 1. 依存なし（最優先）
python manage.py makemigrations users
python manage.py makemigrations company_master

# 2. users のみに依存
python manage.py makemigrations tags
python manage.py makemigrations ads
python manage.py makemigrations security
python manage.py makemigrations subscriptions

# 3. 複数依存（循環依存あり）
python manage.py makemigrations stockdiary

# 4. その他
python manage.py makemigrations analysis_template
python manage.py makemigrations earnings_analysis
python manage.py makemigrations contact
python manage.py makemigrations maintenance
python manage.py makemigrations margin_tracking

# 5. 実行
python manage.py migrate
```

---

## 6. 初期データ投入

```bash
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings

# スーパーユーザー作成
python manage.py createsuperuser

# サブスクリプションプラン
python manage.py initialize_plans

# 広告ユニット
python manage.py initialize_ad_units

# タグ作成
python manage.py create_tags --username naoki

# Google OAuth 設定（管理画面でも可）
python manage.py setup_google_auth

# EDINET 企業マスタ初期収集（初回のみ・時間がかかる）
python manage.py collect_initial_data --days 365 --api-version v2
python manage.py update_company_master
```

---

## 7. 静的ファイル・メディアディレクトリ

```bash
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings

# 静的ファイル収集（出力先: staticfiles/）
python manage.py collectstatic --noinput

# メディア・ログディレクトリ作成
mkdir -p /var/www/django/stock-dialy/media
mkdir -p /var/www/django/stock-dialy/logs

# ログディレクトリのパーミッション
chmod 755 /var/www/django/stock-dialy/logs
```

---

## 8. systemd サービス設定

プロジェクト内の設定ファイルをシステムにコピーして有効化する。

```bash
# サービス・タイマーファイルをコピー
sudo cp etc/systemd/system/django-qcluster.service /etc/systemd/system/
sudo cp etc/systemd/system/margin-fetch.service    /etc/systemd/system/
sudo cp etc/systemd/system/margin-fetch.timer      /etc/systemd/system/

# 設定リロード
sudo systemctl daemon-reload

# Django-Q クラスター（常駐）
sudo systemctl enable --now django-qcluster.service

# 信用倍率データ日次取得タイマー（毎日 15:00 JST）
sudo systemctl enable --now margin-fetch.timer
```

### 各サービスの役割

| ファイル | 種別 | 説明 |
|---------|------|------|
| `django-qcluster.service` | 常駐サービス | Django-Q ワーカー（通知処理・バックグラウンドタスク） |
| `margin-fetch.service` | oneshot | `fetch_margin_data --days 40` を実行する本体 |
| `margin-fetch.timer` | タイマー | 毎日 15:00 JST に `margin-fetch.service` を起動 |

### 動作確認

```bash
# qcluster が動いているか
sudo systemctl status django-qcluster

# タイマーが登録されているか
sudo systemctl list-timers margin-fetch.timer

# タイマーをすぐ手動実行して確認
sudo systemctl start margin-fetch.service
journalctl -u margin-fetch -f
```

---

## 9. 信用倍率データ 初回取得

バッチタイマーとは別に、過去分を手動で一括取得する。

```bash
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings

# 過去1年分（365日）を取得 ※時間がかかる
python manage.py fetch_margin_data --days 365

# 特定日付を指定する場合
python manage.py fetch_margin_data --date 2026-03-19

# 既存データを強制上書きする場合
python manage.py fetch_margin_data --days 40 --force
```

取得状況はログで確認：
```bash
journalctl -u margin-fetch -f
# または Django ログ
tail -f /var/www/django/stock-dialy/logs/app.log
```

---

## 10. 動作確認チェックリスト

```bash
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings

# [ ] Django の設定チェック
python manage.py check

# [ ] マイグレーション未適用がないか確認
python manage.py showmigrations | grep '\[ \]'

# [ ] 開発サーバーで起動確認
python manage.py runserver 0.0.0.0:8000

# [ ] qcluster の起動確認
sudo systemctl status django-qcluster

# [ ] Django-Q スケジュール登録確認（margin_tracking も含む）
python manage.py shell -c "
from django_q.models import Schedule
for s in Schedule.objects.all():
    print(s.name, s.cron or s.schedule_type, s.next_run)
"

# [ ] タイマー一覧確認
sudo systemctl list-timers
```

---

## 本番環境: Gunicorn 起動

nginx + Gunicorn 構成を使う場合（systemd での管理を推奨）:

```bash
/var/www/django/stock-dialy/venv/bin/gunicorn config.wsgi \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --max-requests 1000 \
    --timeout 60
```

---

## トラブルシューティング

### qcluster が起動しない

```bash
journalctl -u django-qcluster -n 50
# パスが正しいか確認
ls /var/www/django/stock-dialy/venv/bin/python
```

### マイグレーションが失敗する

```bash
# 循環依存エラーの場合は --merge オプション
python manage.py makemigrations --merge
```

### 信用倍率 PDF が取得できない（404 続き）

JPX の公開スケジュールは木曜日が多い（祝日・年末年始は休止）。
404 は正常扱い。取得できた日付を確認：

```bash
python manage.py shell -c "
from margin_tracking.models import MarginFetchLog
for log in MarginFetchLog.objects.filter(status='success').order_by('-record_date')[:5]:
    print(log.record_date, log.total_records)
"
```

### Gmail 送信エラー

- Google アカウントで「2段階認証」を有効にした上でアプリパスワードを取得する
- `EMAIL_HOST_PASSWORD` に通常パスワードではなくアプリパスワードを設定する

---

## ファイル構成（参考）

```
/var/www/django/stock-dialy/
├── venv/                    # Python 仮想環境
├── config/
│   └── settings.py          # Django 設定
├── .env                     # 環境変数（git 管理外）
├── logs/                    # ログ出力先
├── media/                   # アップロードファイル
├── static/                  # collectstatic 出力先
├── etc/systemd/system/      # systemd 設定ファイル（ソース）
│   ├── django-qcluster.service
│   ├── margin-fetch.service
│   └── margin-fetch.timer
├── margin_tracking/         # 信用倍率アプリ
│   └── management/commands/
│       ├── fetch_margin_data.py   # バッチ本体
│       └── debug_margin_pdf.py    # PDF デバッグ用
└── setup/
    ├── setup_data.md         # 初期データ投入コマンド集
    └── 推奨マイグレーション順序.md
```
