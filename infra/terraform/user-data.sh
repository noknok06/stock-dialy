#!/bin/bash
# EC2 初回ブート時の最小セットアップ（Amazon Linux 2023）。
# アプリ本体のデプロイは docs/aws-deployment.md に従い手動で行う。
set -euxo pipefail

# --- 2GB スワップ（t3.micro はメモリ 1GB のため必須） ---
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# --- タイムゾーン（バッチのスケジュール基準を JST に） ---
timedatectl set-timezone Asia/Tokyo || true

# --- OS パッケージ ---
dnf update -y
dnf install -y \
  python3.11 python3.11-pip python3.11-devel \
  gcc git \
  nginx \
  postgresql16 \
  libpq-devel

# certbot は dnf に無い場合があるため pip で導入
python3.11 -m pip install --upgrade pip
python3.11 -m pip install certbot certbot-nginx

# --- アプリ実行ユーザー（systemd ユニットが naoki 前提のため作成） ---
if ! id naoki >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash naoki
fi

# --- デプロイ先ディレクトリ ---
mkdir -p /var/www/django
chown naoki:naoki /var/www/django

systemctl enable --now nginx

echo "user-data bootstrap complete. Continue with docs/aws-deployment.md"
