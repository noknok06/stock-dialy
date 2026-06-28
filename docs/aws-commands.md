# AWS 構築・運用 コマンドリファレンス

---

## SSH 接続

### 基本コマンド

```bash
ssh -i ~/.ssh/stock-dialy-key.pem ec2-user@<EIP>
```

| 部分 | 内容 |
|------|------|
| `-i ~/.ssh/stock-dialy-key.pem` | 秘密鍵のパス |
| `ec2-user` | Amazon Linux 2023 のデフォルトユーザー名（変更不要） |
| `<EIP>` | Elastic IP（`terraform output` または AWS コンソールで確認） |

### IP アドレスの確認方法

```bash
# Terraform output から確認（インフラ構築後）
cd infra/terraform
terraform output ec2_public_ip

# Makefile がある場合は SSH まで自動化されている
make ssh
```

### よくあるエラー

| エラー | 原因 | 対処 |
|--------|------|------|
| `Permission denied (publickey)` | 秘密鍵が違う / 権限が緩い | `chmod 600 ~/.ssh/stock-dialy-key.pem` |
| `Connection timed out` | セキュリティグループの SSH 許可 IP が違う | `make apply` で IP を更新（Makefile の MY_IP が自動取得） |
| `WARNING: UNPROTECTED PRIVATE KEY FILE` | .pem の権限が 600 になっていない | `chmod 600 ~/.ssh/stock-dialy-key.pem` |
| `Host key verification failed` | EC2 を再作成して IP が変わった | `ssh-keygen -R <旧EIP>` で既知ホストを削除 |

### キーペアの準備（初回のみ）

```bash
# 作成
aws ec2 create-key-pair --key-name stock-dialy-key \
  --query 'KeyMaterial' --output text > ~/.ssh/stock-dialy-key.pem

# 権限設定（必須）
chmod 600 ~/.ssh/stock-dialy-key.pem
```

> 秘密鍵（.pem）は作成時の1回しかダウンロードできない。紛失したらキーペアを作り直してEC2を再作成。

---

## 0. 前提準備（初回のみ）

```bash
# SSH キーペア作成
aws ec2 create-key-pair --key-name stock-dialy-key \
  --query 'KeyMaterial' --output text > ~/.ssh/stock-dialy-key.pem
chmod 600 ~/.ssh/stock-dialy-key.pem

# 自分の IP 確認（ssh_ingress_cidr に使う）
curl ifconfig.me   # → 例: 203.0.113.10  → /32 をつけて 203.0.113.10/32

# tfvars 作成
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# → key_pair_name / media_bucket_name / ssh_ingress_cidr / db_password を編集
```

---

## 1. インフラ構築（terraform）

```bash
cd infra/terraform

terraform init          # 初回のみ（プロバイダをダウンロード）
terraform plan          # 作成内容を確認（無料枠外リソースがないか）
terraform apply         # 作成（yes で確定）
terraform output        # EIP / RDS エンドポイント / S3 バケット名を確認
```

出力例:
```
ec2_public_ip  = "35.76.97.160"
rds_endpoint   = "stock-dialy-db.xxxx.ap-northeast-1.rds.amazonaws.com:5432"
s3_bucket_name = "your-unique-bucket-name"
```

---

## 2. EC2 デプロイ（初回）

```bash
ssh -i ~/.ssh/stock-dialy-key.pem ec2-user@<EIP>
```

### 2-1. アプリ取得

```bash
cd ~
git clone <リポジトリURL> stock-dialy
cd stock-dialy

python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

chmod 755 /home/ec2-user   # nginx が sock ファイルを読めるようにする
```

### 2-2. .env 作成

```bash
cp .env.example .env
vim .env
```

```env
SECRET_KEY=<下記コマンドで生成>
DEBUG=False
ALLOWED_HOSTS=<EIP>

DB_HOST=<rds_endpoint のホスト部分（:5432 を除く）>
DB_PORT=5432
DB_NAME=stock_dialy
DB_USER=naoki
DB_PASSWORD=<terraform.tfvars の db_password と同じ値>

USE_S3=True
AWS_STORAGE_BUCKET_NAME=<s3_bucket_name>
AWS_S3_REGION_NAME=ap-northeast-1
AWS_S3_CUSTOM_DOMAIN=

USE_SES=False
EMAIL_HOST_PASSWORD=<Gmail アプリパスワード>

HTTP_ONLY=True
EXTRA_CSRF_ORIGINS=http://<EIP>

GEMINI_API_KEY=...
EDINET_API_KEY=...
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_ADMIN_EMAIL=...
```

```bash
# SECRET_KEY 生成
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### 2-3. DB セットアップ

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput   # S3 に静的ファイルをアップロード
```

### 2-4. gunicorn

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
sudo systemctl status gunicorn
```

### 2-5. nginx

```bash
sudo tee /etc/nginx/conf.d/stock-dialy.conf > /dev/null <<EOF
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
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

sudo nginx -t && sudo systemctl reload nginx
```

### 2-6. django-q / margin-fetch

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

### 2-7. 動作確認

```bash
sudo systemctl status gunicorn django-qcluster
systemctl list-timers | grep margin
curl http://localhost/   # 200 が返れば OK
```

ブラウザで `http://<EIP>` を開いてログイン・日記作成・画像アップロードを確認。

---

## 3. コード更新（日常デプロイ）

```bash
ssh -i ~/.ssh/stock-dialy-key.pem ec2-user@<EIP>

cd ~/stock-dialy
git pull

# requirements 変更時のみ
pip install -r requirements.txt

# モデル変更時のみ
python manage.py migrate

# 静的ファイル変更時のみ
python manage.py collectstatic --noinput

sudo systemctl restart gunicorn django-qcluster
```

---

## 4. ログ確認

```bash
journalctl -u gunicorn       -n 50 -f
journalctl -u django-qcluster -n 50 -f
journalctl -u margin-fetch    -n 50
sudo tail -f /var/log/nginx/error.log
```

---

## 5. 停止（terraform destroy）

```bash
# Step 1: S3 を空にする（必須。空でないと destroy が失敗する）
aws s3 rm s3://<s3_bucket_name> --recursive

# Step 2: 全リソースを削除
cd infra/terraform
terraform destroy   # yes で確定

# 確認（何も出なければ削除完了）
terraform output
```

EC2・RDS・EIP・VPC がすべて削除され課金が止まる。

---

## 6. 再構築

```bash
cd infra/terraform
terraform apply     # 同じ tfvars で再構築（EIP は変わる）
terraform output    # 新しい EIP と RDS エンドポイントを確認

# EC2 に SSH → 「2. EC2 デプロイ」を再実行
# .env の EIP / DB_HOST を新しい値に更新することを忘れずに
```

---

## 付録: HTTPS 対応（ドメイン取得後）

```bash
# nginx に HTTPS ブロックを追加（certbot が自動で設定）
sudo certbot --nginx -d kabu-log.net -d www.kabu-log.net

# .env を更新
# ALLOWED_HOSTS=kabu-log.net,www.kabu-log.net
# CSRF_TRUSTED_ORIGINS=https://kabu-log.net,https://www.kabu-log.net
# HTTP_ONLY=False   ← 必ず False に戻す
sudo systemctl restart gunicorn
```
