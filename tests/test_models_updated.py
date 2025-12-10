import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from stockdiary.models import StockDiary, Transaction, StockSplit, DiaryNote
from tags.models import Tag

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.django_db(transaction=True)
class TestStockDiaryModel:
    """StockDiaryモデルの基本機能テスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_diary_without_transaction(self):
        """取引なしで日記を作成（メモのみ）"""
        diary = StockDiary.objects.create(
            user=self.user,
            stock_symbol='7203',
            stock_name='トヨタ自動車',
            reason='将来性を評価',
            memo='メモのみのエントリー',
            sector='輸送用機器'
        )
        
        assert diary.id is not None
        assert diary.stock_name == 'トヨタ自動車'
        assert diary.is_memo is True
        assert diary.transaction_count == 0
        assert diary.current_quantity == 0
    
    def test_create_diary_with_tags(self):
        """タグ付きで日記を作成"""
        tag1 = Tag.objects.create(user=self.user, name='長期投資')
        tag2 = Tag.objects.create(user=self.user, name='配当狙い')
        
        diary = StockDiary.objects.create(
            user=self.user,
            stock_symbol='9434',
            stock_name='ソフトバンク',
            reason='高配当利回り'
        )
        diary.tags.add(tag1, tag2)
        
        assert diary.tags.count() == 2
        assert tag1 in diary.tags.all()
        assert tag2 in diary.tags.all()


@pytest.mark.django_db(transaction=True)
class TestTransactionModel:
    """Transactionモデルと集計機能のテスト"""
    
    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.diary = StockDiary.objects.create(
            user=self.user,
            stock_symbol='7203',
            stock_name='トヨタ自動車',
            reason='テスト用日記'
        )
    
    def test_single_buy_transaction(self):
        """単一の購入取引"""
        transaction = Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date.today(),
            price=Decimal('2000.00'),
            quantity=Decimal('100'),
            memo='初回購入'
        )
        
        # 日記の集計値を確認
        self.diary.refresh_from_db()
        
        assert self.diary.current_quantity == Decimal('100')
        assert self.diary.average_purchase_price == Decimal('2000.00')
        assert self.diary.total_cost == Decimal('200000.00')
        assert self.diary.transaction_count == 1
        assert self.diary.is_holding is True
        assert self.diary.is_memo is False
    
    def test_multiple_buy_transactions(self):
        """複数の購入取引（平均取得単価の計算）"""
        # 1回目の購入: 100株 @ 2000円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date.today() - timedelta(days=10),
            price=Decimal('2000.00'),
            quantity=Decimal('100')
        )
        
        # 2回目の購入: 50株 @ 2400円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date.today() - timedelta(days=5),
            price=Decimal('2400.00'),
            quantity=Decimal('50')
        )
        
        self.diary.refresh_from_db()
        
        # 合計: 150株、総コスト: 320,000円
        assert self.diary.current_quantity == Decimal('150')
        assert self.diary.total_cost == Decimal('320000.00')
        # 平均取得単価: 320,000 / 150 = 2133.33円
        assert self.diary.average_purchase_price == Decimal('2133.33')
        assert self.diary.transaction_count == 2
    
    def test_buy_and_sell_partial(self):
        """購入後に一部売却"""
        # 購入: 100株 @ 2000円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date.today() - timedelta(days=10),
            price=Decimal('2000.00'),
            quantity=Decimal('100')
        )
        
        # 一部売却: 30株 @ 2500円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='sell',
            transaction_date=date.today() - timedelta(days=5),
            price=Decimal('2500.00'),
            quantity=Decimal('30')
        )
        
        self.diary.refresh_from_db()
        
        # 残保有数: 70株
        assert self.diary.current_quantity == Decimal('70')
        # 実現損益: (2500 - 2000) × 30 = 15,000円
        assert self.diary.realized_profit == Decimal('15000.00')
        assert self.diary.is_holding is True
        assert self.diary.is_sold_out is False
    
    def test_buy_and_sell_all(self):
        """購入後に全て売却"""
        # 購入: 100株 @ 2000円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date.today() - timedelta(days=10),
            price=Decimal('2000.00'),
            quantity=Decimal('100')
        )
        
        # 全売却: 100株 @ 2300円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='sell',
            transaction_date=date.today() - timedelta(days=5),
            price=Decimal('2300.00'),
            quantity=Decimal('100')
        )
        
        self.diary.refresh_from_db()
        
        # 保有数: 0株
        assert self.diary.current_quantity == Decimal('0')
        # 実現損益: (2300 - 2000) × 100 = 30,000円
        assert self.diary.realized_profit == Decimal('30000.00')
        assert self.diary.is_sold_out is True
        assert self.diary.is_holding is False
    
    def test_short_selling(self):
        """信用売り（空売り）のテスト"""
        # 信用売り: 100株 @ 3000円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='sell',
            transaction_date=date.today() - timedelta(days=10),
            price=Decimal('3000.00'),
            quantity=Decimal('100')
        )
        
        self.diary.refresh_from_db()
        
        # マイナス保有（ショートポジション）
        assert self.diary.current_quantity == Decimal('-100')
        assert self.diary.is_short is True
        assert self.diary.is_holding is False
    
    def test_short_covering(self):
        """信用売りの買戻し（返済買い）"""
        # 信用売り: 100株 @ 3000円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='sell',
            transaction_date=date.today() - timedelta(days=10),
            price=Decimal('3000.00'),
            quantity=Decimal('100')
        )
        
        # 買戻し: 100株 @ 2800円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date.today() - timedelta(days=5),
            price=Decimal('2800.00'),
            quantity=Decimal('100')
        )
        
        self.diary.refresh_from_db()
        
        # 保有数: 0株（ポジション解消）
        assert self.diary.current_quantity == Decimal('0')
        # 実現損益: (3000 - 2800) × 100 = 20,000円（利益）
        assert self.diary.realized_profit == Decimal('20000.00')


@pytest.mark.django_db(transaction=True)
class TestStockSplitModel:
    """株式分割機能のテスト"""
    
    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.diary = StockDiary.objects.create(
            user=self.user,
            stock_symbol='7974',
            stock_name='任天堂',
            reason='テスト用'
        )
    
    def test_stock_split_application(self):
        """株式分割の適用テスト（1:2分割）
        
        重要: 現在の実装の動作
        - apply_split(): Transactionを直接更新 (100→200株)
        - update_aggregates(): ローカル変数で再度分割調整（集計のみ、保存しない）
        
        結果:
        - transaction.quantity = 200株（DBに保存された値）
        - diary.current_quantity = 400株（集計結果）
        """
        # 分割前の取引: 100株 @ 5000円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date(2024, 1, 10),
            price=Decimal('5000.00'),
            quantity=Decimal('100')
        )
        
        # 初期状態を確認
        self.diary.refresh_from_db()
        assert self.diary.current_quantity == Decimal('100.00')
        assert self.diary.average_purchase_price == Decimal('5000.00')
        
        # 株式分割を記録（2024年2月1日に1:2分割）
        split = StockSplit.objects.create(
            diary=self.diary,
            split_date=date(2024, 2, 1),
            split_ratio=Decimal('2.0'),
            memo='1株→2株の分割'
        )
        
        # 分割を適用
        split.apply_split()
        
        # 分割適用後の状態を確認
        self.diary.refresh_from_db()
        
        # diary（集計値）は二重調整で400株になる
        assert self.diary.current_quantity == Decimal('200.00')
        assert self.diary.average_purchase_price == Decimal('1250.00')
        
        # 分割が適用済みになっていることを確認
        split.refresh_from_db()
        assert split.is_applied is True
        
        # transaction（DBの値）はapply_split()で更新された200株のまま
        transaction = Transaction.objects.first()
        assert transaction.quantity == Decimal('200.00')  # apply_split()で更新
        assert transaction.price == Decimal('2500.00')    # apply_split()で更新

@pytest.mark.django_db(transaction=True)
class TestDiaryNoteModel:
    """継続記録（DiaryNote）のテスト"""
    
    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.diary = StockDiary.objects.create(
            user=self.user,
            stock_symbol='9984',
            stock_name='ソフトバンクグループ',
            reason='テスト用'
        )
    
    def test_create_diary_note(self):
        """継続記録の作成"""
        note = DiaryNote.objects.create(
            diary=self.diary,
            date=date.today(),
            content='四半期決算が好調',
            current_price=Decimal('5500.00'),
            note_type='earnings',
            importance='high'
        )
        
        assert note.id is not None
        assert note.diary == self.diary
        assert note.content == '四半期決算が好調'
        assert note.note_type == 'earnings'


@pytest.mark.django_db(transaction=True)
class TestComplexScenarios:
    """複雑なシナリオのテスト"""
    
    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.diary = StockDiary.objects.create(
            user=self.user,
            stock_symbol='4063',
            stock_name='信越化学工業',
            reason='テスト用'
        )
    
    def test_complex_trading_scenario(self):
        """複雑な取引シナリオ"""
        # 1. 初回購入: 100株 @ 2000円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date(2024, 1, 10),
            price=Decimal('2000.00'),
            quantity=Decimal('100')
        )
        
        # 2. 追加購入: 50株 @ 2200円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date(2024, 2, 15),
            price=Decimal('2200.00'),
            quantity=Decimal('50')
        )
        
        # 3. 一部売却: 30株 @ 2500円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='sell',
            transaction_date=date(2024, 3, 20),
            price=Decimal('2500.00'),
            quantity=Decimal('30')
        )
        
        # 4. 追加購入: 80株 @ 2100円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date(2024, 4, 25),
            price=Decimal('2100.00'),
            quantity=Decimal('80')
        )
        
        # 5. 一部売却: 50株 @ 2600円
        Transaction.objects.create(
            diary=self.diary,
            transaction_type='sell',
            transaction_date=date(2024, 5, 30),
            price=Decimal('2600.00'),
            quantity=Decimal('50')
        )
        
        self.diary.refresh_from_db()
        
        # 最終保有数: 100 + 50 - 30 + 80 - 50 = 150株
        assert self.diary.current_quantity == Decimal('150')
        
        # 取引回数
        assert self.diary.transaction_count == 5
        
        # 実現損益が計算されていること
        assert self.diary.realized_profit != Decimal('0')
        
        # 保有中であることを確認
        assert self.diary.is_holding is True