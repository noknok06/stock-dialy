# infra/terraform — AWS インフラ（案B: EC2 + RDS + S3 + CloudFront + SES）

カブログを ConoHa VPS から AWS へ移行するための IaC。**無料枠最適化**（t3.micro /
db.t3.micro / Single-AZ / NAT・ALB なし）で構成し、`terraform destroy/apply` で
使わない時は壊して課金停止できる。詳細な構築・移行手順は `docs/aws-deployment.md` を参照。

## ファイル構成

| ファイル | 内容 |
|---------|------|
| `versions.tf` | プロバイダ定義（ap-northeast-1 / CloudFront 用 us-east-1 エイリアス） |
| `variables.tf` | 入力変数（無料枠の既定値） |
| `terraform.tfvars.example` | 値の記入例（コピーして `terraform.tfvars` を作る） |
| `vpc.tf` | VPC・public/private サブネット・IGW（NAT なし） |
| `sg.tf` | EC2 用 SG / RDS 用 SG（EC2 からのみ 5432） |
| `iam.tf` | EC2 ロール + S3/SES 最小権限 + インスタンスプロファイル |
| `ec2.tf` | t3.micro（AL2023）+ Elastic IP + user-data |
| `rds.tf` | PostgreSQL 16 db.t3.micro Single-AZ |
| `s3.tf` | メディア/静的バケット（CloudFront OAC or 公開読取） |
| `cloudfront.tf` | CDN（任意・`enable_cloudfront`） |
| `ses.tf` | SES ドメイン ID + DKIM（任意・`enable_ses`） |
| `outputs.tf` | EIP / RDS エンドポイント / バケット名 / CloudFront ドメイン 等 |
| `user-data.sh` | EC2 初回ブートストラップ（swap・パッケージ・naoki ユーザー） |

## 使い方（概要）

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # 値を記入（db_password 等）
export TF_VAR_db_password='...'                # 機密は環境変数推奨

terraform init
terraform plan
terraform apply

terraform output            # EIP・RDS エンドポイント・バケット名を確認
```

事前に **SSH キーペア**（`key_pair_name`）と **一意な S3 バケット名**（`media_bucket_name`）を用意する。
`ssh_ingress_cidr` は必ず自分の固定 IP（/32）に絞ること。

## 段階導入

1. まず `enable_cloudfront=false` / `enable_ses=false` で VPC/EC2/RDS/S3 を構築
2. アプリ稼働・データ移行が済んだら CloudFront・SES を有効化（`docs/aws-deployment.md`）

## コスト停止

```bash
terraform destroy   # 全リソース削除（RDS は最終スナップショットを取得してから消える）
```
