# Terraform / プロバイダのバージョン制約
# 東京リージョン(ap-northeast-1)を既定。CloudFront 用 ACM 証明書は us-east-1 必須のため
# us-east-1 のエイリアスプロバイダも用意する。

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
    }
  }
}

# CloudFront に紐づける ACM 証明書は us-east-1 でしか作れない/参照できない
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
    }
  }
}
