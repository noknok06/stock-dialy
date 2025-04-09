import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from stockdiary.models import StockDiary
from stockdiary.analytics import DiaryAnalytics
from tags.models import Tag
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue

User = get_user_model()

@pytest.mark.django_db
class TestDiaryAnalytics:
    def setup_method(self):
        """テスト用のユーザーと初期データを準備"""
        self.user = User.objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='testpass123'
        )
        
        # タグの作成
        self.tag1 = Tag.objects.create(user=self.user, name='テクノロジー')
        self.tag2 = Tag.objects.create(user=self.user, name='金融')
        
        # 分析テンプレートの作成
        self.template = AnalysisTemplate.objects.create(
            user=self.user,
            name='テスト分析テンプレート',
            description='テスト用のテンプレート'
        )
        
        # 分析項目の作成
        self.item1 = AnalysisItem.objects.create(
            template=self.template,
            name='PER',
            description='株価収益率',
            item_type='number'
        )
        
        # 日記の作成（複数のケース）
        self.diaries = [
            # 保有中の株式
            StockDiary.objects.create(
                user=self.user,
                stock_symbol='7203',
                stock_name='トヨタ自動車',
                purchase_date=timezone.now().date() - timedelta(days=30),
                purchase_price=Decimal('2000'),
                purchase_quantity=100,
                reason='テスト用エントリー1',
                sector='自動車'
            ),
            # 売却済みの株式
            StockDiary.objects.create(
                user=self.user,
                stock_symbol='9984',
                stock_name='ソフトバンクグループ',
                purchase_date=timezone.now().date() - timedelta(days=60),
                sell_date=timezone.now().date() - timedelta(days=10),
                purchase_price=Decimal('6000'),
                sell_price=Decimal('7000'),
                purchase_quantity=50,
                reason='テスト用エントリー2',
                sector='通信'
            ),
            # メモエントリー
            StockDiary.objects.create(
                user=self.user,
                stock_symbol='4502',
                stock_name='武田薬品工業',
                purchase_date=timezone.now().date() - timedelta(days=15),
                is_memo=True,
                reason='メモ用エントリー'
            )
        ]
        
        # タグの追加
        self.diaries[0].tags.add(self.tag1)
        self.diaries[1].tags.add(self.tag2)
        
        # 分析値の追加
        DiaryAnalysisValue.objects.create(
            diary=self.diaries[0],
            analysis_item=self.item1,
            number_value=Decimal('15.5')
        )
    
    def test_collect_stats(self):
        """基本統計データの収集テスト"""
        analytics = DiaryAnalytics(self.user)
        stats = analytics.collect_stats(
            StockDiary.objects.filter(user=self.user), 
            StockDiary.objects.filter(user=self.user)
        )
        
        assert stats['total_stocks'] == 3
        assert stats['total_tags'] == 2
        assert 'checklist_completion_rate' in stats
    
    def test_get_investment_summary_data(self):
        """投資サマリーデータのテスト"""
        analytics = DiaryAnalytics(self.user)
        active_diaries = [d for d in self.diaries if not d.sell_date and not d.is_memo]
        sold_diaries = [d for d in self.diaries if d.sell_date]
        
        investment_data = analytics.get_investment_summary_data(
            self.diaries, 
            StockDiary.objects.filter(user=self.user),
            active_diaries,
            sold_diaries
        )
        
        assert investment_data['total_investment'] == Decimal('200000')  # 2000 * 100
        assert investment_data['active_investment'] == Decimal('200000')
        assert investment_data['realized_profit'] == Decimal('50000')  # (7000 - 6000) * 50
    
    def test_get_tag_analysis_data(self):
        """タグ分析データのテスト"""
        analytics = DiaryAnalytics(self.user)
        tag_data = analytics.get_tag_analysis_data(
            StockDiary.objects.filter(user=self.user)
        )
        
        assert len(tag_data['top_tags']) == 2
        assert tag_data['top_tags'][0].name in ['テクノロジー', '金融']
    
    def test_get_template_analysis_data(self):
        """テンプレート分析データのテスト"""
        analytics = DiaryAnalytics(self.user)
        template_data = analytics.get_template_analysis_data()
        
        assert len(template_data['template_stats']) > 0
        assert template_data['template_stats'][0]['name'] == 'テスト分析テンプレート'
    
    def test_prepare_holding_period_data(self):
        """保有期間分析のテスト"""
        analytics = DiaryAnalytics(self.user)
        holding_data = analytics.prepare_holding_period_data(
            StockDiary.objects.filter(user=self.user)
        )
        
        assert len(holding_data['ranges']) == 6
        assert len(holding_data['counts']) == 6
    
    def test_prepare_recent_trends(self):
        """最近の投資傾向テスト"""
        analytics = DiaryAnalytics(self.user)
        trends = analytics.prepare_recent_trends(
            StockDiary.objects.filter(user=self.user)
        )
        
        assert 'purchase_frequency' in trends
        assert 'most_used_tag' in trends
        assert 'keywords' in trends
    
    def test_get_sector_analysis_data(self):
        """セクター分析データのテスト"""
        analytics = DiaryAnalytics(self.user)
        sector_data = analytics.get_sector_analysis_data(
            self.diaries, 
            StockDiary.objects.filter(user=self.user)
        )
        
        assert 'sector_allocation_data' in sector_data
        assert 'sector_stocks_data' in sector_data
        assert 'sector_performance_data' in sector_data
        
        # セクター名の確認
        sector_names = [sector['name'] for sector in sector_data['sector_stocks_data']['labels']]
        assert '自動車' in sector_names
        assert '通信' in sector_names