import sys
import os
import django

# プロジェクトルートを import パスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../')

# Django設定をロード
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

# analyze_company.py の Command をインポート
from earnings_analysis.management.commands.analyze_company import Command

# 管理コマンドを手動で呼び出す（引数指定）
cmd = Command()
cmd.handle(
    company_code="9102",
    force=False,
    verbose=True,
    dry_run=False
)
