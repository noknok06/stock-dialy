# CloudFront（任意・段階導入）。enable_cloudfront=true のときのみ作成。
# S3 をオリジンに OAC（Origin Access Control）で非公開アクセス。
# 独自ドメイン配信時は acm_certificate_arn（us-east-1 の証明書）を指定する。

resource "aws_cloudfront_origin_access_control" "s3" {
  count                             = var.enable_cloudfront ? 1 : 0
  name                              = "${var.project}-s3-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "cdn" {
  count   = var.enable_cloudfront ? 1 : 0
  enabled = true
  comment = "${var.project} media/static CDN"

  # 独自ドメインを使う場合のみ別名を設定（ACM 証明書が必要）
  aliases = var.acm_certificate_arn != "" && var.domain_name != "" ? ["cdn.${var.domain_name}"] : []

  origin {
    domain_name              = aws_s3_bucket.media.bucket_regional_domain_name
    origin_id                = "s3-${var.media_bucket_name}"
    origin_access_control_id = aws_cloudfront_origin_access_control.s3[0].id
  }

  default_cache_behavior {
    target_origin_id       = "s3-${var.media_bucket_name}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 86400
    max_ttl     = 31536000
    compress    = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  price_class = "PriceClass_200" # 北米・欧州・アジア（東京含む）。最安は PriceClass_100

  viewer_certificate {
    # ACM 証明書（us-east-1）があれば独自ドメイン + SNI、なければ CloudFront 既定証明書
    cloudfront_default_certificate = var.acm_certificate_arn == "" ? true : null
    acm_certificate_arn            = var.acm_certificate_arn != "" ? var.acm_certificate_arn : null
    ssl_support_method             = var.acm_certificate_arn != "" ? "sni-only" : null
    minimum_protocol_version       = var.acm_certificate_arn != "" ? "TLSv1.2_2021" : null
  }

  tags = {
    Name = "${var.project}-cdn"
  }
}
