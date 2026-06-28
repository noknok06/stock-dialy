# ================================================================
# ★ アプリを追加・再構築するときはここだけ変更する
# ================================================================
APP    = kblog-prod               # プロジェクト識別子（リソース名の接頭辞）
BUCKET = your-unique-bucket-name  # S3 バケット名（全世界で一意）
KEY    = stock-dialy-key          # EC2 キーペア名

# SSH 許可 IP — 固定 IP がある場合は直接書く。なければ自動取得。
MY_IP  = $(shell curl -sf ifconfig.me)/32

# db_password は機密のため Makefile に書かない。
# 実行前に 1 度だけ export する:
#   export TF_VAR_db_password='StrongPass123!'
# ================================================================

_VARS = \
  -var="project=$(APP)" \
  -var="media_bucket_name=$(BUCKET)" \
  -var="key_pair_name=$(KEY)" \
  -var="ssh_ingress_cidr=$(MY_IP)"

.PHONY: init plan apply output destroy ssh help

help:
	@echo "使い方:"
	@echo "  make init      # 初回のみ（プロバイダのダウンロード）"
	@echo "  make plan      # 変更内容を確認"
	@echo "  make apply     # リソースを作成"
	@echo "  make output    # EIP / RDS エンドポイント / S3 バケット名を表示"
	@echo "  make destroy   # リソースをすべて削除（S3 も空にして削除）"
	@echo "  make ssh       # EC2 に SSH 接続"
	@echo ""
	@echo "現在の設定:"
	@echo "  APP    = $(APP)"
	@echo "  BUCKET = $(BUCKET)"
	@echo "  KEY    = $(KEY)"
	@echo "  MY_IP  = $(MY_IP)"

init:
	terraform init

plan:
	terraform plan $(_VARS)

apply:
	@if [ -z "$$TF_VAR_db_password" ]; then \
	  echo "エラー: TF_VAR_db_password が未設定です"; \
	  echo "実行前に: export TF_VAR_db_password='パスワード'"; \
	  exit 1; \
	fi
	terraform apply $(_VARS)

output:
	terraform output

destroy:
	@echo "▼ S3 バケット $(BUCKET) を空にします..."
	-aws s3 rm s3://$(BUCKET) --recursive
	terraform destroy $(_VARS)

ssh:
	ssh -i ~/.ssh/$(KEY).pem ec2-user@$(shell terraform output -raw ec2_public_ip 2>/dev/null)
