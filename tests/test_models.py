import pytest
from django.contrib.auth import get_user_model
from stockdiary.models import StockDiary, DiaryNote
from analysis_template.models import AnalysisTemplate, AnalysisItem
from tags.models import Tag

User = get_user_model()

# 全てのテストクラスのデータベースマーカーを強制的に設定
pytestmark = pytest.mark.django_db(transaction=True)

@pytest.mark.django_db(transaction=True)
class TestModels:
    """モデルの基本機能をテスト"""
    
    def setup_method(self):
        # テスト用ユーザーの作成
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_stockdiary_creation(self):
        """StockDiaryモデルの作成テスト"""
        diary = StockDiary.objects.create(
            user=self.user,
            stock_symbol='7203',
            stock_name='トヨタ自動車',
            purchase_date='2023-01-01',
            purchase_price=2000,
            purchase_quantity=100,
            reason='テスト用エントリー'
        )
        assert diary.id is not None
        assert diary.stock_name == 'トヨタ自動車'
        assert diary.purchase_quantity == 100
    
    def test_tag_creation(self):
        """Tagモデルの作成テスト"""
        tag = Tag.objects.create(
            user=self.user,
            name='テストタグ'
        )
        assert tag.id is not None
        assert tag.name == 'テストタグ'
    
    def test_analysis_template_creation(self):
        """AnalysisTemplateモデルの作成テスト"""
        template = AnalysisTemplate.objects.create(
            user=self.user,
            name='テストテンプレート',
            description='テスト用の分析テンプレート'
        )
        
        item = AnalysisItem.objects.create(
            template=template,
            name='PER',
            description='株価収益率',
            item_type='number',
            order=1
        )
        
        assert template.id is not None
        assert template.name == 'テストテンプレート'
        assert item.name == 'PER'