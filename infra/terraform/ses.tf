# SES（任意）。enable_ses=true かつ domain_name 指定時にドメイン ID と DKIM を作成。
# 本番送信にはサンドボックス解除（プロダクションアクセス申請）が別途必要（手動・docs 参照）。
# 出力された DNS レコード（検証 TXT / DKIM CNAME×3）を DNS に登録すると認証が完了する。

resource "aws_ses_domain_identity" "main" {
  count  = var.enable_ses && var.domain_name != "" ? 1 : 0
  domain = var.domain_name
}

resource "aws_ses_domain_dkim" "main" {
  count  = var.enable_ses && var.domain_name != "" ? 1 : 0
  domain = aws_ses_domain_identity.main[0].domain
}
