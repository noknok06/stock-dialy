# メディア（ユーザーアップロード画像）＋ 静的ファイル用 S3 バケット。
# プレフィックス media/ と static/ を 1 バケットに同居（settings.py の STORAGES と対応）。
#
# 公開方針:
#   - enable_cloudfront = true : バケットは非公開のまま CloudFront(OAC) からのみ読取許可（推奨）
#   - enable_cloudfront = false: 直接 S3 配信のため media/* static/* を公開読取（段階導入の暫定）
# どちらも EC2 はオブジェクトの読み書きを IAM ロール（iam.tf）で行う。

resource "aws_s3_bucket" "media" {
  bucket = var.media_bucket_name

  tags = {
    Name = "${var.project}-media"
  }
}

# ACL は使わず所有者強制（オブジェクト ACL を無効化）
resource "aws_s3_bucket_ownership_controls" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket = aws_s3_bucket.media.id

  block_public_acls  = true
  ignore_public_acls = true
  # CloudFront(OAC) 利用時はパブリックポリシーを完全ブロック。
  # 直接 S3 配信(暫定)時のみ公開ポリシーを許可する。
  block_public_policy     = var.enable_cloudfront
  restrict_public_buckets = var.enable_cloudfront
}

# ブラウザからの直接表示用 CORS（GET/HEAD のみ）
resource "aws_s3_bucket_cors_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  cors_rule {
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"]
    allowed_headers = ["*"]
    max_age_seconds = 3600
  }
}

# --- バケットポリシー（CloudFront 有無で切替） ---
data "aws_iam_policy_document" "media_cloudfront" {
  count = var.enable_cloudfront ? 1 : 0

  statement {
    sid       = "AllowCloudFrontOAC"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.media.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.cdn[0].arn]
    }
  }
}

data "aws_iam_policy_document" "media_public" {
  count = var.enable_cloudfront ? 0 : 1

  statement {
    sid     = "PublicReadMediaStatic"
    actions = ["s3:GetObject"]
    resources = [
      "${aws_s3_bucket.media.arn}/media/*",
      "${aws_s3_bucket.media.arn}/static/*",
    ]
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
  }
}

resource "aws_s3_bucket_policy" "media" {
  bucket = aws_s3_bucket.media.id
  policy = var.enable_cloudfront ? data.aws_iam_policy_document.media_cloudfront[0].json : data.aws_iam_policy_document.media_public[0].json

  depends_on = [aws_s3_bucket_public_access_block.media]
}
