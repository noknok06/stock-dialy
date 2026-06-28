# infra/terraform — Terraform 設定リファレンス

AWS インフラ（EC2 + RDS + S3）を Terraform で管理する。
無料枠最適化（t3.micro / db.t3.micro / Single-AZ / NAT・ALB なし）。
詳細な構築・移行手順は `docs/aws-deployment.md` を参照。

---

## ファイル構成と役割

```
infra/terraform/
├── Makefile                  ← ★ 操作の起点。変更箇所はここの先頭4行だけ
├── variables.tf              ← 全変数の定義と既定値（直接編集しない）
├── terraform.tfvars.example  ← tfvars のひな型（git 管理）
├── terraform.tfvars          ← 実際の値（gitignore・手元で管理）
│
├── versions.tf       プロバイダバージョン / リージョン設定
├── vpc.tf            VPC / サブネット / IGW / ルートテーブル
├── sg.tf             セキュリティグループ（EC2用 / RDS用）
├── iam.tf            EC2ロール / S3・SES 権限 / インスタンスプロファイル
├── ec2.tf            EC2インスタンス / Elastic IP
├── rds.tf            RDS PostgreSQL 16
├── s3.tf             S3バケット / CORS / バケットポリシー
├── cloudfront.tf     CloudFront CDN（任意 / enable_cloudfront=true で有効）
├── ses.tf            SES ドメイン認証（任意 / enable_ses=true で有効）
├── outputs.tf        apply 後に確認する値（EIP / RDS エンドポイント等）
└── user-data.sh      EC2 初回起動時に自動実行されるブートストラップ
```

---

## 設定の流れ

```
Makefile の先頭4行
  APP / BUCKET / KEY / MY_IP
      ↓  -var で渡す
variables.tf（変数の定義・既定値）
      ↓  各 .tf ファイルで参照
AWS リソース（EC2 / RDS / S3 / ...）
```

`db_password` のみ機密のため環境変数で渡す:
```bash
export TF_VAR_db_password='StrongPass123!'
```

---

## 各ファイルの詳細

### Makefile（操作の起点）

```makefile
APP    = kblog-prod               # プロジェクト識別子 → リソース名の接頭辞
BUCKET = your-unique-bucket-name  # S3 バケット名（全世界で一意）
KEY    = stock-dialy-key          # EC2 キーペア名
MY_IP  = $(shell curl -s ifconfig.me)/32  # SSH 許可 IP（自動取得）
```

```bash
make init     # 初回のみ
make plan     # 変更内容を確認
make apply    # リソースを作成
make output   # EIP / RDS エンドポイント / S3 バケット名を表示
make destroy  # S3を空にして全削除
make ssh      # EC2 に SSH（IP を自動取得）
```

---

### variables.tf（変数定義）

変更しない。各変数の既定値と説明が書かれている。
カスタムしたい場合は Makefile か terraform.tfvars で上書きする。

| 変数 | 既定値 | 説明 |
|------|--------|------|
| `project` | `stock-dialy` | リソース名の接頭辞 |
| `region` | `ap-northeast-1` | AWS リージョン（東京） |
| `ec2_instance_type` | `t3.micro` | 無料枠 |
| `db_instance_class` | `db.t3.micro` | 無料枠 |
| `db_allocated_storage` | `20` | 無料枠（GB） |
| `enable_cloudfront` | `false` | 段階導入用フラグ |
| `enable_ses` | `false` | 段階導入用フラグ |

---

### versions.tf（プロバイダ設定）

変更しない。

- `ap-northeast-1`（東京）をデフォルトリージョンに設定
- `us-east-1` エイリアスは CloudFront 用 ACM 証明書専用（CloudFront は us-east-1 の証明書必須）
- 全リソースに `Project` / `ManagedBy=terraform` タグを自動付与

---

### vpc.tf（ネットワーク）

変更しない。

```
Internet
    ↓
IGW（インターネットゲートウェイ）
    ↓
パブリックサブネット（10.0.1.0/24）  ← EC2 を配置
    ↓（VPC 内部のみ）
プライベートサブネット × 2 AZ       ← RDS を配置（外部から直接到達不可）
```

NAT Gateway は使わない（約 $33/月 節約）。RDS は外向き通信不要なので問題なし。

---

### sg.tf（ファイアウォール）

| SG | 許可するポート | 送信元 |
|----|--------------|--------|
| EC2用 | 80（HTTP）/ 443（HTTPS） | 全世界 |
| EC2用 | 22（SSH） | Makefile の MY_IP のみ |
| RDS用 | 5432（PostgreSQL） | EC2用 SG からのみ |

SSH の許可 IP は `make apply` のたびに Makefile の MY_IP で更新される。

---

### iam.tf（EC2 の権限）

EC2 にアタッチする IAM ロール。アプリ（boto3）がこのロールを使って S3/SES に接続する。
**アクセスキーをコードや .env に書く必要がない。**

| 権限 | 対象 |
|------|------|
| S3: ListBucket / GetObject / PutObject / DeleteObject | 自アプリのバケットのみ |
| SES: SendEmail / SendRawEmail | 全リソース（ドメイン制限は SES 側で行う） |

---

### ec2.tf（アプリサーバー）

| 設定 | 値 |
|------|----|
| AMI | Amazon Linux 2023 最新（SSM パラメータから自動取得） |
| インスタンスタイプ | `var.ec2_instance_type`（既定: t3.micro） |
| EBS | gp3 / 暗号化済み / `var.root_volume_gb`（既定: 20GB） |
| Elastic IP | 固定 IP を付与（再起動で IP が変わらない） |
| 初回起動 | `user-data.sh` を自動実行 |

---

### rds.tf（データベース）

| 設定 | 値 |
|------|----|
| エンジン | PostgreSQL 16 |
| インスタンス | `var.db_instance_class`（既定: db.t3.micro） |
| ストレージ | gp3 / 暗号化済み / 20GB |
| 配置 | プライベートサブネット / EC2 の SG からのみ接続可 |
| バックアップ | `backup_retention_period=0`（無料枠の制約）|
| 削除時 | `skip_final_snapshot=false` → 最終スナップショットを取得してから削除 |

> 学習完了後は Supabase に移行し、このファイルを削除する想定。

---

### s3.tf（ファイルストレージ）

`media/` と `static/` を 1 バケットに同居させる。

| 設定 | 値 |
|------|----|
| バケット名 | `var.media_bucket_name` |
| 所有権 | BucketOwnerEnforced（ACL 無効） |
| CORS | GET/HEAD を全オリジン許可（ブラウザから直接取得するため） |
| 公開設定 | `enable_cloudfront=false` → `media/*` / `static/*` を公開読取 |
| 公開設定 | `enable_cloudfront=true` → バケット非公開・CloudFront OAC 経由のみ |

---

### cloudfront.tf / ses.tf（段階導入）

初期は無効（`enable_cloudfront=false` / `enable_ses=false`）。

有効化するには Makefile の apply コマンドに変数を追加するか、`terraform.tfvars` に記載:
```hcl
enable_cloudfront   = true
acm_certificate_arn = "arn:aws:acm:us-east-1:..."   # us-east-1 の証明書 ARN
enable_ses          = true
domain_name         = "kabu-log.net"
```

---

### outputs.tf（apply 後の確認値）

`make output` または `terraform output` で表示される。`.env` に設定する値が揃っている。

| 出力キー | .env への使い方 |
|---------|----------------|
| `ec2_public_ip` | `ALLOWED_HOSTS` / DNS の A レコード |
| `ssh_command` | SSH コマンドそのまま使える |
| `rds_endpoint` | `DB_HOST` |
| `rds_port` | `DB_PORT`（通常 5432） |
| `s3_bucket_name` | `AWS_STORAGE_BUCKET_NAME` |
| `cloudfront_domain` | `AWS_S3_CUSTOM_DOMAIN`（CloudFront 有効時） |
| `ses_dkim_tokens` | DNS に CNAME として登録（SES 有効時） |

---

### user-data.sh（EC2 初回ブートストラップ）

EC2 の初回起動時に自動実行される。手動での実行は不要。

実行内容:
1. 2GB スワップ作成（t3.micro はメモリ 1GB のため必須）
2. タイムゾーンを Asia/Tokyo に設定
3. OS パッケージ更新 + Python3.11 / nginx / postgresql-client 等をインストール
4. certbot をインストール（HTTPS 対応用）
5. `naoki` ユーザーと `/var/www/django/` を作成
6. nginx を有効化

---

## .gitignore（何を除外しているか）

```
*.tfstate        ← 実際のリソース状態（RDSパスワード等の機密を含む）
*.tfstate.*
.terraform/      ← プロバイダのバイナリ（大きいため除外）
.terraform.lock.hcl
terraform.tfvars ← 実際の設定値（db_password を含む）
*.auto.tfvars
*.tfplan
```

`terraform.tfstate` は手元で管理する。紛失するとリソースの状態が Terraform から見えなくなる。
バックアップとして `~/.terraform.d/` や安全なストレージに保管すること。
