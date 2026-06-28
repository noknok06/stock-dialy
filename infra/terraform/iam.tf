# EC2 用 IAM ロール + インスタンスプロファイル。
# アプリは静的アクセスキーを置かず、このロールから S3/SES にアクセスする（boto3 が自動取得）。
# 最小権限: 対象バケットの読み書きと SES 送信のみ。

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${var.project}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

# --- S3: 対象バケットのオブジェクト操作のみ許可 ---
data "aws_iam_policy_document" "s3_access" {
  statement {
    sid       = "ListBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.media.arn]
  }
  statement {
    sid = "ObjectRW"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.media.arn}/*"]
  }
}

resource "aws_iam_role_policy" "s3" {
  name   = "${var.project}-s3-access"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.s3_access.json
}

# --- SES: メール送信のみ許可 ---
data "aws_iam_policy_document" "ses_send" {
  statement {
    sid = "SendEmail"
    actions = [
      "ses:SendEmail",
      "ses:SendRawEmail",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "ses" {
  name   = "${var.project}-ses-send"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ses_send.json
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project}-ec2-profile"
  role = aws_iam_role.ec2.name
}
