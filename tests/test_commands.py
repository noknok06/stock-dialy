import pytest
from django.core.management import call_command
from django.contrib.auth import get_user_model
from io import StringIO
from django.core.management.base import CommandError

User = get_user_model()

# 全てのテストクラスのデータベースマーカーを強制的に設定
pytestmark = pytest.mark.django_db(transaction=True)

@pytest.mark.django_db
class TestCommands:
    """管理コマンドのテスト"""
    
    def setup_method(self):
        # テスト用ユーザーの作成
        self.user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
    
    def test_create_tags(self):
        """create_tagsコマンドのテスト"""
        out = StringIO()
        call_command('create_tags', '--username=admin', stdout=out)
        assert "件のタグを作成しました" in out.getvalue()
    
    def test_create_analysis_templates(self):
        """create_analysis_templatesコマンドのテスト"""
        out = StringIO()
        call_command('create_analysis_templates', '--username=admin', '--templates=1', stdout=out)
        assert "件のテンプレートを作成しました" in out.getvalue()
    
    def test_create_stock_diaries(self):
        """create_stock_diariesコマンドのテスト"""
        out = StringIO()
        # 事前にタグを作成
        call_command('create_tags', '--username=admin')
        # 日記を作成
        call_command('create_stock_diaries', '--username=admin', '--count=2', '--notes=1', stdout=out)
        assert "件の日記" in out.getvalue()