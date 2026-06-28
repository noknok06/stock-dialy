# 出力値。apply 後にアプリの .env 設定やデプロイで使う。

output "ec2_public_ip" {
  description = "EC2 の Elastic IP（DNS の A レコードをここに向ける）"
  value       = aws_eip.app.public_ip
}

output "ssh_command" {
  description = "EC2 への SSH コマンド例"
  value       = "ssh -i <key.pem> ec2-user@${aws_eip.app.public_ip}"
}

output "rds_endpoint" {
  description = "RDS エンドポイント（.env の DB_HOST に設定）"
  value       = aws_db_instance.main.address
}

output "rds_port" {
  description = "RDS ポート（.env の DB_PORT）"
  value       = aws_db_instance.main.port
}

output "s3_bucket_name" {
  description = "S3 バケット名（.env の AWS_STORAGE_BUCKET_NAME）"
  value       = aws_s3_bucket.media.bucket
}

output "cloudfront_domain" {
  description = "CloudFront ドメイン（.env の AWS_S3_CUSTOM_DOMAIN）。未作成なら空"
  value       = var.enable_cloudfront ? aws_cloudfront_distribution.cdn[0].domain_name : ""
}

output "ses_dkim_tokens" {
  description = "SES DKIM トークン（DNS に <token>._domainkey CNAME を登録）。未作成なら空"
  value       = var.enable_ses && var.domain_name != "" ? aws_ses_domain_dkim.main[0].dkim_tokens : []
}

output "ses_verification_token" {
  description = "SES ドメイン検証 TXT 値（_amazonses.<domain> に登録）。未作成なら空"
  value       = var.enable_ses && var.domain_name != "" ? aws_ses_domain_identity.main[0].verification_token : ""
}
