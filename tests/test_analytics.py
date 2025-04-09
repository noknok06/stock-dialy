import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from stockdiary.models import StockDiary, DiaryNote
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
        # まず日記を作成
        self.diaries = [
            # 1. 保有中の株式（テクノロジー）
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
            # 2. 売却済みの株式（金融）
            StockDiary.objects.create(
                user=self.user,
                stock_symbol='8035',
                stock_name='東京エレクトロン',
                purchase_date=timezone.now().date() - timedelta(days=60),
                sell_date=timezone.now().date() - timedelta(days=10),
                purchase_price=Decimal('6000'),
                sell_price=Decimal('7000'),
                purchase_quantity=50,
                reason='テスト用エントリー2',
                sector='半導体'
            ),
            # 3. メモエントリー
            StockDiary.objects.create(
                user=self.user,
                stock_symbol='4502',
                stock_name='武田薬品工業',
                purchase_date=timezone.now().date() - timedelta(days=15),
                is_memo=True,
                reason='メモ用エントリー'
            )
        ]
        
        # タグを個別に追加 
        self.diaries[0].tags.add(self.tag1)  # テクノロジー
        self.diaries[1].tags.add(self.tag2)  # 金融
        
        # 継続記録の追加
        DiaryNote.objects.create(
            diary=self.diaries[0],
            date=timezone.now().date() - timedelta(days=10),
            content='テスト分析更新',
            current_price=Decimal('2100'),
            note_type='analysis'
        )
        
        # 分析値の追加
        DiaryAnalysisValue.objects.create(
            diary=self.diaries[0],
            analysis_item=self.item1,
            number_value=Decimal('15.5')
        )


    def test_get_sector_analysis_data(self):
        """セクター分析データの詳細テスト"""
        analytics = DiaryAnalytics(self.user)
        sector_data = analytics.get_sector_analysis_data(
            self.diaries, 
            StockDiary.objects.filter(user=self.user)
        )
        
        # セクターデータの詳細検証
        assert 'sector_allocation_data' in sector_data
        assert 'sector_stocks_data' in sector_data
        assert 'sector_performance_data' in sector_data
        
        # セクター名の確認
        sector_names = sector_data['sector_stocks_data']['labels']
        assert '自動車' in sector_names
        assert '半導体' in sector_names
        
        # 投資配分の検証
        total_investment = sector_data['total_investment']
        assert total_investment > 0
        
        # パフォーマンスデータの検証
        performance_data = sector_data['sector_performance_data']
        assert len(performance_data['labels']) > 0
        assert len(performance_data['returns']) > 0
        assert len(performance_data['success_rates']) > 0

    def test_prepare_recent_trends(self):
        """最近の投資傾向分析の詳細テスト"""
        analytics = DiaryAnalytics(self.user)
        trends = analytics.prepare_recent_trends(
            StockDiary.objects.filter(user=self.user)
        )
        
        # トレンドデータの検証
        assert 'purchase_frequency' in trends
        assert 'most_used_tag' in trends
        assert 'most_detailed_record' in trends
        assert 'keywords' in trends
        
        # キーワード抽出の検証
        if trends['keywords']:
            for keyword in trends['keywords']:
                assert 'word' in keyword
                assert 'count' in keyword

    def test_get_activity_analysis_data(self):
        """活動分析データの詳細テスト"""
        analytics = DiaryAnalytics(self.user)
        activity_data = analytics.get_activity_analysis_data(
            self.diaries, 
            StockDiary.objects.filter(user=self.user)
        )
        
        # 活動ヒートマップの検証
        assert 'activity_heatmap' in activity_data
        heatmap = activity_data['activity_heatmap']
        assert len(heatmap) == 31  # 過去30日間
        
        for entry in heatmap:
            assert 'date' in entry
            assert 'day' in entry
            assert 'count' in entry
            assert 'level' in entry
        
        # 月次データの検証
        assert 'monthly_labels' in activity_data
        assert 'monthly_counts' in activity_data
        
        # 曜日別データの検証
        assert 'day_of_week_counts' in activity_data
        assert 'most_active_day' in activity_data
        assert 'weekday_pattern' in activity_data

    def test_get_tag_analysis_data(self):
        """タグ分析データの詳細テスト"""
        analytics = DiaryAnalytics(self.user)
        tag_data = analytics.get_tag_analysis_data(
            StockDiary.objects.filter(user=self.user)
        )
        
        # タグデータの検証
        assert 'tag_names' in tag_data
        assert 'tag_counts' in tag_data
        assert 'top_tags' in tag_data
        assert 'most_profitable_tag' in tag_data
        assert 'tag_performance' in tag_data
        
        # タグパフォーマンスの詳細検証
        for performance in tag_data['tag_performance']:
            assert 'name' in performance
            assert 'count' in performance
            assert 'avg_holding_period' in performance
            assert 'avg_profit_rate' in performance
            assert 'total_profit' in performance

    def test_prepare_holding_period_data(self):
        """保有期間分析の詳細テスト"""
        analytics = DiaryAnalytics(self.user)
        holding_data = analytics.prepare_holding_period_data(
            StockDiary.objects.filter(user=self.user)
        )
        
        # 保有期間データの検証
        assert 'ranges' in holding_data
        assert 'counts' in holding_data
        assert len(holding_data['ranges']) == 6
        assert len(holding_data['counts']) == 6
        
        # 各保有期間の範囲と数の検証
        expected_ranges = ['~1週間', '1週間~1ヶ月', '1~3ヶ月', '3~6ヶ月', '6ヶ月~1年', '1年以上']
        assert holding_data['ranges'] == expected_ranges

    def test_get_template_analysis_data(self):
        """テンプレート分析データの詳細テスト"""
        analytics = DiaryAnalytics(self.user)
        template_data = analytics.get_template_analysis_data()
        
        # テンプレートデータの検証
        assert 'template_stats' in template_data
        assert 'most_used_template' in template_data
        assert 'highest_completion_template' in template_data
        assert 'items_analysis' in template_data
        
        # テンプレート統計の検証
        for stat in template_data['template_stats']:
            assert 'id' in stat
            assert 'name' in stat
            assert 'usage_count' in stat
            assert 'avg_completion_rate' in stat
        
        # 項目分析の検証
        for item in template_data['items_analysis']:
            assert 'template_id' in item
            assert 'template_name' in item
            assert 'name' in item
            assert 'item_type' in item
            assert 'usage_count' in item
            assert 'completion_rate' in item

    def test_collect_stats(self):
        """基本統計データ収集の詳細テスト"""
        analytics = DiaryAnalytics(self.user)
        stats = analytics.collect_stats(
            StockDiary.objects.filter(user=self.user), 
            StockDiary.objects.filter(user=self.user)
        )
        
        # 統計データの検証
        assert 'total_stocks' in stats
        assert 'stocks_change' in stats
        assert 'total_tags' in stats
        assert 'tags_change' in stats
        assert 'checklist_completion_rate' in stats
        assert 'avg_reason_length' in stats
        assert 'reason_length_change' in stats
        
        # 値の型と範囲の検証
        assert isinstance(stats['total_stocks'], int)
        assert isinstance(stats['total_tags'], int)
        assert 'checklist_completion_rate' in stats
        assert isinstance(stats['avg_reason_length'], int)

    def test_get_investment_summary_data(self):
        """投資サマリーデータの詳細テスト"""
        analytics = DiaryAnalytics(self.user)
        active_diaries = [d for d in self.diaries if not d.sell_date and not d.is_memo]
        sold_diaries = [d for d in self.diaries if d.sell_date]
        
        investment_data = analytics.get_investment_summary_data(
            self.diaries, 
            StockDiary.objects.filter(user=self.user),
            active_diaries,
            sold_diaries
        )
        
        # 投資サマリーデータの検証
        assert 'total_investment' in investment_data
        assert 'active_investment' in investment_data
        assert 'investment_change' in investment_data
        assert 'investment_change_percent' in investment_data
        assert 'total_profit' in investment_data
        assert 'profit_change' in investment_data
        assert 'profit_change_percent' in investment_data
        assert 'active_stocks_count' in investment_data
        assert 'stocks_count_change' in investment_data
        assert 'avg_holding_period' in investment_data
        assert 'holding_period_change' in investment_data
        assert 'realized_profit' in investment_data
        assert 'active_holdings_count' in investment_data
        
        # 値の型と基本的な検証
        assert isinstance(investment_data['total_investment'], Decimal)
        assert isinstance(investment_data['active_investment'], Decimal)
        assert isinstance(investment_data['realized_profit'], Decimal)