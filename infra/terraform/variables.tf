# 入力変数。機密値（DBパスワード等）は terraform.tfvars か環境変数 TF_VAR_* で渡す。
# 無料枠を厳守するための既定値（t3.micro / db.t3.micro / single-az / NAT・ALB なし）。

variable "project" {
  description = "プロジェクト名（リソース名・タグの接頭辞）"
  type        = string
  default     = "stock-dialy"
}

variable "region" {
  description = "AWS リージョン"
  type        = string
  default     = "ap-northeast-1"
}

variable "vpc_cidr" {
  description = "VPC の CIDR"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "パブリックサブネット（EC2 用）の CIDR"
  type        = string
  default     = "10.0.1.0/24"
}

variable "private_subnet_cidrs" {
  description = "プライベートサブネット（RDS 用、複数 AZ）の CIDR。RDS サブネットグループは 2AZ 以上必須"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "ssh_ingress_cidr" {
  description = "SSH(22) を許可する送信元 CIDR。自分の固定 IP に絞ること（例: 203.0.113.10/32）"
  type        = string
  default     = "0.0.0.0/0"
}

variable "ec2_instance_type" {
  description = "EC2 インスタンスタイプ（無料枠は t3.micro）"
  type        = string
  default     = "t3.micro"
}

variable "key_pair_name" {
  description = "EC2 に紐づける既存の SSH キーペア名（事前に作成しておく）"
  type        = string
}

variable "root_volume_gb" {
  description = "EC2 ルート EBS サイズ(GB)。無料枠は 30GB まで"
  type        = number
  default     = 20
}

variable "db_instance_class" {
  description = "RDS インスタンスクラス（無料枠は db.t3.micro）"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "RDS ストレージ(GB)。無料枠は 20GB まで"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "RDS の初期データベース名"
  type        = string
  default     = "stock_dialy"
}

variable "db_username" {
  description = "RDS マスターユーザー名"
  type        = string
  default     = "naoki"
}

variable "db_password" {
  description = "RDS マスターパスワード（機密。tfvars か TF_VAR_db_password で渡す）"
  type        = string
  sensitive   = true
}

variable "media_bucket_name" {
  description = "メディア・静的ファイル用 S3 バケット名（グローバル一意）"
  type        = string
}

variable "domain_name" {
  description = "サイトのドメイン（SES 認証・CloudFront 別名に使用）。未使用なら空文字"
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "CloudFront 用 ACM 証明書 ARN（us-east-1）。空なら CloudFront のデフォルト証明書を使用"
  type        = string
  default     = ""
}

variable "enable_cloudfront" {
  description = "CloudFront を作成するか（段階導入用。初期は false でも可）"
  type        = bool
  default     = false
}

variable "enable_ses" {
  description = "SES ドメイン ID を作成するか"
  type        = bool
  default     = false
}
