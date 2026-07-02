# RDS PostgreSQL 16。無料枠: db.t3.micro / Single-AZ / 20GB gp3。
# プライベートサブネット配置・publicly_accessible=false で、EC2 の SG からのみ到達可能。
#
# 注意: 学習完了後は Supabase へ移行しこのファイルを削除する想定（docs/aws-deployment.md 参照）。
# その際は最終スナップショットを取得してから destroy すること。

resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name = "${var.project}-db-subnet-group"
  }
}

resource "aws_db_instance" "main" {
  identifier     = "${var.project}-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = false

  # 無料枠では backup_retention_period = 0 が必須（自動バックアップ無効）
  # 学習完了後 Supabase 移行前に手動スナップショットで代替する
  backup_retention_period = 0
  maintenance_window      = "Mon:19:30-Mon:20:30"

  auto_minor_version_upgrade = true
  deletion_protection        = false # 学習用途。本番運用に固定するなら true 推奨
  skip_final_snapshot        = false
  final_snapshot_identifier  = "${var.project}-db-final"

  tags = {
    Name = "${var.project}-db"
  }
}
