# AWS デプロイ手順（ConoHa VPS → AWS 案B）

ConoHa VPS（全部入り単一サーバー）から **EC2 + RDS + S3** へ移行する手順書。
インフラは Terraform（`infra/terraform/`）で構築し、**無料利用枠**（最初の12ヶ月）で学ぶ。

**構成の全体像**

| 層 | ConoHa VPS | AWS（移行後） |
|----|------------|--------------|
| アプリ | nginx + gunicorn + django-q | EC2 t3.micro（同じ構成を踏襲） |
| DB | VPS 内 PostgreSQL | RDS PostgreSQL 16（db.t3.micro） |
| メディア/静的ファイル | ローカルディスク | S3（static/ + media/） |
| メール | Gmail SMTP | SES（後の章で移行。当面 Gmail のまま） |
| HTTPS | Let's Encrypt | Let's Encrypt（ALB は使わない） |

**コスト方針**: NAT Gateway・ALB なし、Single-AZ。使わない期間は `terraform destroy` で課金停止。

---

## フェーズ概要

| フェーズ | 内容 | 影響 |
|---------|------|------|
| 1 | アプリ側コード変更（USE_S3 / HTTP_ONLY フラグ） | VPS に影響なし |
| 2 | Terraform でインフラ構築（VPC / EC2 / RDS / S3） | AWS 環境のみ |
| 2.5 | ドメインなし検証（EIP で HTTP 動作確認） | 一時的 |
| 3 | データ移行（DB / メディア）→ ConoHa 廃止 | 本番切替 |
| 4 | ドメイン取得 → HTTPS → SES → DNS カットオーバー | 本番 |

---

## フェーズ 1: アプリ側コード変更

> すでに完了済み（PR #377 にて main マージ）。VPS への影響はない。

### 変更内容

**`requirements.txt`** に追加:
- `django-storages[s3]`（S3 ストレージバックエンド + boto3）
- `django-ses`（SES メールバックエンド）

**`config/settings.py`** の変更点:
- `USE_S3` フラグ: `True` にすると静的・メディアファイルを S3 へ配信
- `USE_SES` フラグ: `True` にするとメール送信を SES 経由に切替
- `HTTP_ONLY` フラグ: ドメインなし検証時に一時的に `True`（HTTPS 強制を無効化）
- `EXTRA_CSRF_ORIGINS`: EIP を `CSRF_TRUSTED_ORIGINS` に追加する環境変数
- S3 の CSP ディレクティブ: `USE_S3=True` 時にバケット固有の3形式ドメインを CSP に追加
  - `bucket.s3.amazonaws.com`（global）
  - `bucket.s3.ap-northeast-1.amazonaws.com`（regional dot）
  - `bucket.s3-ap-northeast-1.amazonaws.com`（regional dash、boto3 レガシー形式）

**`.env.example`** に AWS 系変数を追加済み。

---

## フェーズ 2: Terraform でインフラ構築

### 2-1. 前提

| 項目 | 内容 |
|------|------|
| AWS CLI | `aws configure` 済み（管理用 IAM ユーザー） |
| Terraform | >= 1.6 |
| SSH キーペア | EC2 用に事前作成（AWS コンソール or CLI） |
| S3 バケット名 | グローバル一意な名前を決める |

**キーペア作成**（コンソールで作るか、CLI で）:
```bash
aws ec2 create-key-pair --key-name stock-dialy-key \
  --query 'KeyMaterial' --output text > ~/.ssh/stock-dialy-key.pem
chmod 600 ~/.ssh/stock-dialy-key.pem
```

### 2-2. terraform.tfvars の作成

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` を以下を参考に編集:
```hcl
key_pair_name      = "stock-dialy-key"          # 作成したキーペア名
media_bucket_name  = "your-unique-bucket-name"  # グローバル一意
ssh_ingress_cidr   = "203.0.113.10/32"          # 自分の固定 IP（curl ifconfig.me で確認）
db_password        = "StrongPass123!"           # 記号・大小英数字を含む12文字以上
                                                 # 使用不可文字: / @ " スペース
```

> `terraform.tfvars` は `.gitignore` 済み。コミットしない。
> `db_password` は `.env` の `DB_PASSWORD` と同じ値にする。

### 2-3. terraform コマンド

```bash
terraform init      # プロバイダのダウンロード（初回のみ）
terraform plan      # 作成されるリソースの確認（無料枠外のものが含まれないか）
terraform apply     # 実際に作成（確認プロンプトに yes）
terraform output    # EIP・RDS エンドポイント・S3 バケット名を確認
```

**`terraform output` の例:**
```
cloudfront_domain = ""
ec2_public_ip     = "35.76.97.160"
rds_endpoint      = "stock-dialy-db.xxxxxxxxxx.ap-northeast-1.rds.amazonaws.com:5432"
s3_bucket_name    = "your-unique-bucket-name"
```

### 2-4. ハマりポイント（実際に起きたエラー）

| エラー | 原因 | 対処 |
|--------|------|------|
| `FreeTierRestrictionError: backup_retention_period` | 無料枠では `backup_retention_period = 0` 必須 | `rds.tf` の値を `0` に変更 |
| `InvalidParameterValue: Invalid master password` | パスワードに `/` `@` `"` が含まれている | パスワードを記号なしか `!` `_` のみに変更 |
| SSH タイムアウト | `ssh_ingress_cidr` が古い IP になっている | `terraform.tfvars` の CIDR を更新して再 apply |
| EC2 にキーペアが紐づかない | `terraform.tfvars` を example のままにした | 正しい値で tfvars を作り直し、EC2 を再作成 |

---

## フェーズ 2.5: ドメインなし検証（EIP アクセス確認）

ドメイン取得前に EIP（`http://<EIP>`）で一通りの機能を確認する手順。

### 2.5-1. EC2 へ SSH してアプリをデプロイ

```bash
ssh -i ~/.ssh/stock-dialy-key.pem ec2-user@<EIP>

# リポジトリ取得
cd ~
git clone <リポジトリURL> stock-dialy
cd stock-dialy
git checkout main    # または feature ブランチ

# 仮想環境
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# ホームディレクトリを nginx が読めるようにしておく
chmod 755 /home/ec2-user
```

### 2.5-2. .env 作成

```bash
cp .env.example .env
vim .env
```

```env
SECRET_KEY=<python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' で生成>
DEBUG=False
ALLOWED_HOSTS=<EIP>

DB_HOST=<terraform output rds_endpoint のホスト部分（:5432 を除く）>
DB_PORT=5432
DB_NAME=stock_dialy
DB_USER=naoki
DB_PASSWORD=<terraform.tfvars の db_password と同じ>

USE_S3=True
AWS_STORAGE_BUCKET_NAME=<terraform output s3_bucket_name>
AWS_S3_REGION_NAME=ap-northeast-1
AWS_S3_CUSTOM_DOMAIN=

USE_SES=False
EMAIL_HOST_PASSWORD=<Gmail アプリパスワード>

# ドメインなし検証用（確認が終わったら False に戻す）
HTTP_ONLY=True
EXTRA_CSRF_ORIGINS=http://<EIP>

GEMINI_API_KEY=...
EDINET_API_KEY=...
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_ADMIN_EMAIL=...
```

> **注意**: `HTTP_ONLY=True` は HTTPS 強制・HSTS を無効化する。ドメイン取得 → HTTPS 設定後は必ず `False` に戻す。

### 2.5-3. DB セットアップ

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput   # S3 へ静的ファイルをアップロード
```

### 2.5-4. gunicorn のセットアップ

```bash
sudo tee /etc/systemd/system/gunicorn.service > /dev/null <<'EOF'
[Unit]
Description=Gunicorn daemon for stock-dialy
After=network.target

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=/home/ec2-user/stock-dialy
ExecStart=/home/ec2-user/stock-dialy/venv/bin/gunicorn \
    --workers 2 \
    --bind unix:/home/ec2-user/gunicorn.sock \
    config.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn
```

### 2.5-5. nginx のセットアップ

```bash
sudo tee /etc/nginx/conf.d/stock-dialy.conf > /dev/null <<'EOF'
server {
    listen 80;
    server_name <EIP>;
    client_max_body_size 10M;

    location /static/ {
        proxy_pass https://<s3_bucket_name>.s3.ap-northeast-1.amazonaws.com/static/;
    }
    location /media/ {
        proxy_pass https://<s3_bucket_name>.s3.ap-northeast-1.amazonaws.com/media/;
    }
    location / {
        proxy_pass http://unix:/home/ec2-user/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

sudo nginx -t && sudo systemctl reload nginx
```

### 2.5-6. django-q / margin-fetch のセットアップ

```bash
sudo tee /etc/systemd/system/django-qcluster.service > /dev/null <<'EOF'
[Unit]
Description=Django Q Cluster (stock-dialy)
After=network.target

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=/home/ec2-user/stock-dialy
Environment="DJANGO_SETTINGS_MODULE=config.settings"
ExecStart=/home/ec2-user/stock-dialy/venv/bin/python manage.py qcluster
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/margin-fetch.service > /dev/null <<'EOF'
[Unit]
Description=JPX 信用取引残高データ日次取得
After=network.target

[Service]
Type=oneshot
User=ec2-user
Group=ec2-user
WorkingDirectory=/home/ec2-user/stock-dialy
Environment="DJANGO_SETTINGS_MODULE=config.settings"
ExecStart=/home/ec2-user/stock-dialy/venv/bin/python manage.py fetch_margin_data --days 40
StandardOutput=journal
StandardError=journal
EOF

sudo tee /etc/systemd/system/margin-fetch.timer > /dev/null <<'EOF'
[Unit]
Description=JPX 信用取引残高データ 日次取得タイマー
Requires=margin-fetch.service

[Timer]
OnCalendar=*-*-* 15:00:00
TimeZone=Asia/Tokyo
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now django-qcluster.service
sudo systemctl enable --now margin-fetch.timer
```

### 2.5-7. 確認チェックリスト

- [ ] `http://<EIP>` でトップページ表示
- [ ] ログイン・ログアウト
- [ ] 日記の新規作成・編集・削除
- [ ] 画像アップロード → S3 保存 → 表示
- [ ] `sudo systemctl status gunicorn django-qcluster` が active
- [ ] `systemctl list-timers | grep margin` でタイマー登録確認

---

## フェーズ 3: データ移行（本番切替前）

### DB（ConoHa PostgreSQL → RDS）

```bash
# ConoHa 側でダンプ
pg_dump -Fc -h localhost -U naoki stock_dialy > stock_dialy.dump

# EC2 に転送してリストア（RDS はプライベートサブネット → EC2 経由で実行）
scp stock_dialy.dump ec2-user@<EIP>:~/
ssh ec2-user@<EIP>
pg_restore --no-owner --no-acl \
  -h <rds_endpoint_host> -U naoki -d stock_dialy ~/stock_dialy.dump

python manage.py showmigrations   # 未適用がないこと確認
```

### メディア（ローカル → S3）

```bash
# ConoHa 側から直接 S3 に sync（IAM ユーザーか EC2 経由）
aws s3 sync ./media/ s3://<bucket_name>/media/
```

---

## フェーズ 4: ドメイン取得 → HTTPS → DNS カットオーバー

### nginx + HTTPS（Let's Encrypt）

```bash
sudo certbot --nginx -d kabu-log.net -d www.kabu-log.net
```

### .env の更新（ドメイン確定後）

```env
ALLOWED_HOSTS=kabu-log.net,www.kabu-log.net
CSRF_TRUSTED_ORIGINS=https://kabu-log.net,https://www.kabu-log.net
HTTP_ONLY=False    # HTTPS が動いたら必ず False に戻す
```

```bash
sudo systemctl restart gunicorn
```

### SES（Gmail → SES）

```bash
# terraform.tfvars で enable_ses=true / domain_name="kabu-log.net" を設定して再 apply
terraform apply
terraform output   # DKIM CNAME × 3 と SPF TXT を DNS に登録

# DNS 認証完了後、AWS コンソールからサンドボックス解除（本番アクセス）申請
# 承認後
USE_SES=True
python manage.py sendtestemail your@example.com
```

---

## 停止・再構築（コスト管理）

### 停止（terraform destroy）

**⚠️ S3 バケットが空でないと destroy が失敗する。先に中身を削除する。**

```bash
# 1. S3 を空にする（静的・メディアファイルを削除）
aws s3 rm s3://<bucket_name> --recursive

# 2. Terraform でインフラを全削除
cd infra/terraform
terraform destroy
```

`terraform destroy` の確認プロンプトに `yes` と入力。
完了すると EC2・RDS・S3・EIP・VPC がすべて削除される。

### 再構築（terraform apply）

```bash
cd infra/terraform
terraform apply     # 同じ tfvars で再構築（EIP は変わる）
terraform output    # 新しい EIP と RDS エンドポイントを確認

# EC2 で再デプロイ（フェーズ 2.5 の手順を繰り返す）
# DB は migrate から、メディアは S3 sync でリストア
```

> EIP は再 apply ごとに変わる。ConoHa から DNS カットオーバー前なら影響なし。

---

## 課金アラーム（必須）

AWS コンソール → Billing → Budgets → 「予算を作成」:
- **無料枠使用率アラート**: AWS が自動で提案してくれる（設定推奨）
- **月額上限**: $5〜10 を超えたらメール通知

12ヶ月後に無料枠が切れて課金が跳ねる「**無料枠の崖**」に注意。

---

## 定常運用（デプロイ手順）

```bash
cd ~/stock-dialy
git pull
# requirements 変更時のみ: pip install -r requirements.txt
# モデル変更時のみ:         python manage.py migrate
# 静的ファイル変更時のみ:   python manage.py collectstatic --noinput
sudo systemctl restart gunicorn django-qcluster
```

ログ確認:
```bash
journalctl -u gunicorn -n 50
journalctl -u django-qcluster -n 50
journalctl -u margin-fetch -n 50
```

---

## 付録: 学習完了後の Supabase 移行（RDS 廃止）

RDS のコストが見合わなくなったら DB を **Supabase（まず無料枠 Free）** へ移す。
接続が環境変数化されているため **コード変更ゼロ**で切り替えられる。

```bash
# 1. RDS をダンプ
pg_dump -Fc -h <rds_endpoint_host> -U naoki stock_dialy > stock_dialy.dump

# 2. Supabase プロジェクトへリストア（接続文字列は Supabase ダッシュボードから）
pg_restore --no-owner --no-acl -d "<Supavisor 接続文字列>" stock_dialy.dump

# 3. .env の DB_* を Supabase 接続情報に差し替え、RDS を terraform destroy
# 4. infra/terraform/rds.tf を削除して terraform apply
```

Supabase Free の制約（DB 500MB / 1週間無活動で自動 pause / バックアップなし）を
`pg_dump` の週次 cron → S3 退避で補う。500MB 接近時・PITR 必要時に **Pro（$25/月）** へ。
