# AWS デプロイ・移行手順（ConoHa VPS → AWS 案B）

ConoHa VPS（全部入り単一サーバー）から **AWS 案B（EC2 + RDS + S3 + CloudFront + SES）** へ
移行する手順書。インフラは Terraform（`infra/terraform/`）で構築し、**無料利用枠**（最初の12ヶ月）で
ほぼ無料で学べるようにする。アプリ側は `USE_S3` / `USE_SES` フラグで AWS 構成へ切替える。

> サーバー内のアプリ配置・マイグレーション・初期データ・systemd の詳細は
> `docs/server-reconstruction.md` と共通。本書は **差分（DB を RDS、メディアを S3、メールを SES）** を中心に記す。

---

## 0. 構成の全体像

| 層 | ConoHa VPS（現状） | AWS（移行後） |
|----|------------------|--------------|
| アプリ | nginx + gunicorn + django-q（同一 VPS） | EC2 t3.micro（同じ構成を踏襲） |
| DB | 同一 VPS の PostgreSQL | RDS PostgreSQL 16（db.t3.micro / Single-AZ） |
| メディア/静的 | ローカルディスク | S3（+ 任意で CloudFront） |
| メール | Gmail SMTP | SES（移行は任意・段階的） |
| HTTPS | Let's Encrypt | Let's Encrypt（ALB は使わない） |

**コスト方針**: t3.micro / db.t3.micro / Single-AZ、NAT・ALB なし。使わない期間は `terraform destroy` で停止。

---

## 1. 前提

| 項目 | 内容 |
|------|------|
| AWS アカウント | 作成済み・請求アラート設定可能 |
| AWS CLI | `aws configure` 済み（管理用 IAM ユーザー） |
| Terraform | >= 1.6 |
| ドメイン | `kabu-log.net`（DNS を操作できること） |
| SSH キーペア | EC2 用に事前作成（`key_pair_name` に指定） |
| S3 バケット名 | グローバル一意な名前を決める |

事前に EC2 用 SSH キーペアを作成（既存があれば流用）:

```bash
aws ec2 create-key-pair --key-name stock-dialy-key \
  --query 'KeyMaterial' --output text > ~/.ssh/stock-dialy-key.pem
chmod 600 ~/.ssh/stock-dialy-key.pem
```

---

## 2. Terraform でインフラ構築

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars          # key_pair_name / media_bucket_name / ssh_ingress_cidr 等
export TF_VAR_db_password='<強いパスワード>'   # 機密は環境変数で

terraform init
terraform plan                # 無料枠リソースのみか確認（t3.micro / db.t3.micro）
terraform apply

terraform output              # EIP・RDS エンドポイント・S3 バケット名を控える
```

初回は **`enable_cloudfront=false` / `enable_ses=false`** のまま VPC/EC2/RDS/S3 を構築する。
CloudFront・SES は後の章で有効化する（段階導入）。

`ssh_ingress_cidr` は必ず自分の固定 IP（`/32`）に絞ること。

---

## 3. EC2 へアプリをデプロイ

`user-data.sh` が swap・python3.11・nginx・postgresql クライアント・`naoki` ユーザーを用意済み。

```bash
ssh -i ~/.ssh/stock-dialy-key.pem ec2-user@<EIP>

sudo -iu naoki
cd /var/www/django
git clone <リポジトリURL> stock-dialy
cd stock-dialy

python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

`.env` を作成（`server-reconstruction.md` の必須変数に加え、以下を AWS 向けに設定）:

```env
# DB は RDS を指す
DB_HOST=<terraform output rds_endpoint>
DB_PORT=5432
DB_NAME=stock_dialy
DB_USER=naoki
DB_PASSWORD=<TF_VAR_db_password と同じ>

# S3 を有効化（CloudFront 導入後に AWS_S3_CUSTOM_DOMAIN を設定）
USE_S3=True
AWS_STORAGE_BUCKET_NAME=<terraform output s3_bucket_name>
AWS_S3_REGION_NAME=ap-northeast-1
AWS_S3_CUSTOM_DOMAIN=

# メールは当面 Gmail のまま（SES 移行は後の章）
USE_SES=False
EMAIL_HOST_PASSWORD=<Gmail アプリパスワード>
```

> アクセスキーは `.env` に置かない。S3/SES へは EC2 の **IAM インスタンスプロファイル**から
> boto3 が自動で認証する（`infra/terraform/iam.tf`）。

`gunicorn` の workers は t3.micro（メモリ1GB）に合わせ **2〜3** に抑える。

---

## 4. データ移行（DB・メディア）

### 4-1. DB（ConoHa PostgreSQL → RDS）

PG16 同士なので論理ダンプで移送する。

```bash
# 旧サーバー（ConoHa）でダンプ
pg_dump -Fc -h localhost -U naoki stock_dialy > stock_dialy.dump

# ダンプを EC2 に転送し、EC2 から RDS へリストア
#（RDS はプライベート配置のため EC2 経由で実行）
pg_restore --no-owner --no-acl \
  -h <rds_endpoint> -U naoki -d stock_dialy stock_dialy.dump

# 整合性確認
export DJANGO_SETTINGS_MODULE=config.settings
python manage.py showmigrations | grep '\[ \]'   # 未適用がないこと
python manage.py migrate                          # 念のため
```

### 4-2. メディア（ローカル → S3）

```bash
# 旧サーバーの media/ を S3 へ同期（EC2 の IAM ロールで認証）
aws s3 sync ./media/ s3://<bucket>/media/

# 静的ファイルを S3 へ収集（USE_S3=True なので出力先は S3）
python manage.py collectstatic --noinput
```

ブラウザで画像・静的アセットが S3（または後述 CloudFront）から配信されることを確認する。

---

## 5. systemd（django-q / margin-fetch）

`docs/server-reconstruction.md` の「8. systemd サービス設定」をそのまま流用する
（`etc/systemd/system/*` をコピーして有効化）。タイムゾーンは `user-data.sh` で Asia/Tokyo 済み。

```bash
sudo cp etc/systemd/system/django-qcluster.service /etc/systemd/system/
sudo cp etc/systemd/system/margin-fetch.service    /etc/systemd/system/
sudo cp etc/systemd/system/margin-fetch.timer      /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now django-qcluster.service
sudo systemctl enable --now margin-fetch.timer
```

---

## 6. nginx + HTTPS（Let's Encrypt）

ALB は使わず EC2 上で証明書を取得する（コスト削減）。

```bash
# nginx のリバースプロキシ設定（127.0.0.1:8000 の gunicorn へ）を配置後
sudo certbot --nginx -d kabu-log.net -d www.kabu-log.net
```

DNS を先に EIP へ向けてから certbot を実行する（HTTP-01 検証のため）。

---

## 7. CloudFront・SES の有効化（段階導入）

### 7-1. CloudFront（S3 の CDN 配信）

独自ドメインで配信する場合、**us-east-1** の ACM 証明書が必要（CloudFront はこのリージョン固定）。

```bash
# us-east-1 で証明書を発行（DNS 検証）し、ARN を取得
# その ARN を terraform.tfvars に設定して再適用
#   enable_cloudfront   = true
#   acm_certificate_arn = "arn:aws:acm:us-east-1:...:certificate/..."
terraform apply

terraform output cloudfront_domain
```

`.env` の `AWS_S3_CUSTOM_DOMAIN` に CloudFront ドメイン（または `cdn.kabu-log.net`）を設定し、
`collectstatic` をやり直す。`STATIC_URL`/`MEDIA_URL` が CloudFront を指すようになる（`config/settings.py`）。

> CloudFront を有効化すると S3 バケットは非公開（OAC 経由のみ）に切り替わる（`infra/terraform/s3.tf`）。

### 7-2. SES（Gmail → SES）

```bash
# enable_ses=true / domain_name="kabu-log.net" で適用
terraform apply
terraform output ses_dkim_tokens          # CNAME×3 を DNS 登録
terraform output ses_verification_token   # _amazonses TXT を DNS 登録
```

DNS 認証が完了したら **プロダクションアクセス申請**（サンドボックス解除）を AWS コンソールから行う。
承認まで時間がかかるため **早めに申請**する。承認後に `.env` で `USE_SES=True` にして送信テスト:

```bash
python manage.py sendtestemail your@example.com
```

---

## 8. DNS カットオーバー

1. `kabu-log.net` の A レコードを **EIP** に向ける
2. `.env` の `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` に本番ドメインが含まれることを確認
3. TTL を短くしてから切替え、旧 VPS は数日並行稼働させてフォールバック可能にする

---

## 9. 課金アラーム（必須）

無料枠の超過に早く気づくため、**AWS Budgets** で月次予算アラートを設定する。

```bash
# 例: 月 $5 を超えそうなら通知（コンソール: Billing → Budgets でも可）
aws budgets create-budget --account-id <ID> \
  --budget '{"BudgetName":"stock-dialy-monthly","BudgetLimit":{"Amount":"5","Unit":"USD"},"TimeUnit":"MONTHLY","BudgetType":"COST"}' \
  --notifications-with-subscribers '[{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"you@example.com"}]}]'
```

12ヶ月後に無料枠が切れて課金が跳ねる「無料枠の崖」に注意。

---

## 10. 停止・再構築（コスト管理）

学習が主目的で常時稼働が不要な期間は、丸ごと削除して課金を止められる。

```bash
cd infra/terraform
terraform destroy     # RDS は最終スナップショット取得後に削除される

# 再開するとき
terraform apply       # 同じ構成を再構築（DB は手順4でリストア）
```

---

## 付録: 学習完了後の Supabase 移行（RDS 廃止）

将来、RDS のコストが見合わなくなったら DB を **Supabase（まず無料枠 Free）** へ移す。
アプリは DB 接続が環境変数化されているため **コード変更ゼロ**で切り替えられる。

```bash
# 1. RDS をダンプ
pg_dump -Fc -h <rds_endpoint> -U naoki stock_dialy > stock_dialy.dump

# 2. Supabase プロジェクトへリストア（接続文字列は Supabase ダッシュボードから）
pg_restore --no-owner --no-acl -d "<supabase 接続文字列>" stock_dialy.dump

# 3. .env の DB_* を Supabase（接続プーラ Supavisor 推奨）に差し替え
# 4. infra/terraform/rds.tf を削除して terraform apply（RDS を破棄）
```

Supabase Free の制約（DB 500MB / 1週間無活動で自動 pause / マネージドバックアップなし）を、
**`pg_dump` の cron → S3 退避** で補う。DB が 500MB に近づく・PITR が必要になったら **Pro（$25/月）** へ。
詳細は移行計画書（`/root/.claude/plans/` の AWS 移行プラン「将来のコスト見直し」章）を参照。
