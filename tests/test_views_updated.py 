import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
import json

from stockdiary.models import StockDiary, Transaction, DiaryNote
from tags.models import Tag

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.django_db(transaction=True)
class TestStockDiaryListView:
    """日記一覧ビューのテスト"""
    
    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # テスト用日記を複数作成
        self.diary1 = StockDiary.objects.create(
            user=self.user,
            stock_symbol='7203',
            stock_name='トヨタ自動車',
            reason='長期保有目的',
            sector='輸送用機器'
        )
        
        # 取引を追加（保有中）
        Transaction.objects.create(
            diary=self.diary1,
            transaction_type='buy',
            transaction_date=date.today(),
            price=Decimal('2000.00'),
            quantity=Decimal('100')
        )
        
        self.diary2 = StockDiary.objects.create(
            user=self.user,
            stock_symbol='9984',
            stock_name='ソフトバンクグループ',
            reason='高配当狙い',
            sector='情報・通信業'
        )
        
        # 売却済み
        Transaction.objects.create(
            diary=self.diary2,
            transaction_type='buy',
            transaction_date=date.today() - timedelta(days=10),
            price=Decimal('5000.00'),
            quantity=Decimal('50')
        )
        Transaction.objects.create(
            diary=self.diary2,
            transaction_type='sell',
            transaction_date=date.today() - timedelta(days=5),
            price=Decimal('5500.00'),
            quantity=Decimal('50')
        )
        
        # メモのみ
        self.diary3 = StockDiary.objects.create(
            user=self.user,
            stock_symbol='6758',
            stock_name='ソニーグループ',
            reason='監視銘柄',
            memo='今後の動向を注視'
        )
    
    def test_home_view_authenticated(self, client):
        """認証済みユーザーのホーム画面表示"""
        client.login(username='testuser', password='testpass123')
        response = client.get(reverse('stockdiary:home'))
        
        assert response.status_code == 200
        assert 'diaries' in response.context
    
    def test_home_view_unauthenticated(self, client):
        """未認証ユーザーのリダイレクト"""
        response = client.get(reverse('stockdiary:home'))
        
        # ログインページにリダイレクトされる
        assert response.status_code == 302
        assert '/accounts/login/' in response.url
    
    def test_filter_by_status_active(self, client):
        """保有中フィルター"""
        client.login(username='testuser', password='testpass123')
        response = client.get(reverse('stockdiary:home') + '?status=active')
        
        assert response.status_code == 200
        # 保有中の銘柄のみ表示される（diary1のみ）
        diaries = list(response.context['diaries'])
        assert len(diaries) == 1
        assert diaries[0].id == self.diary1.id
    
    def test_filter_by_status_sold(self, client):
        """売却済みフィルター"""
        client.login(username='testuser', password='testpass123')
        response = client.get(reverse('stockdiary:home') + '?status=sold')
        
        assert response.status_code == 200
        diaries = list(response.context['diaries'])
        assert len(diaries) == 1
        assert diaries[0].id == self.diary2.id
    
    def test_filter_by_status_memo(self, client):
        """メモのみフィルター"""
        client.login(username='testuser', password='testpass123')
        response = client.get(reverse('stockdiary:home') + '?status=memo')
        
        assert response.status_code == 200
        diaries = list(response.context['diaries'])
        assert len(diaries) == 1
        assert diaries[0].id == self.diary3.id
    
    def test_search_by_stock_name(self, client):
        """銘柄名で検索"""
        client.login(username='testuser', password='testpass123')
        response = client.get(reverse('stockdiary:home') + '?query=トヨタ')
        
        assert response.status_code == 200
        diaries = list(response.context['diaries'])
        assert len(diaries) == 1
        assert diaries[0].stock_name == 'トヨタ自動車'


@pytest.mark.django_db(transaction=True)
class TestStockDiaryDetailView:
    """日記詳細ビューのテスト"""
    
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
            reason='長期保有',
            sector='輸送用機器'
        )
        
        # 取引を追加
        self.transaction1 = Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date.today() - timedelta(days=10),
            price=Decimal('2000.00'),
            quantity=Decimal('100')
        )
        
        self.transaction2 = Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date.today() - timedelta(days=5),
            price=Decimal('2200.00'),
            quantity=Decimal('50')
        )
    
    def test_detail_view_displays_diary(self, client):
        """日記詳細の表示"""
        client.login(username='testuser', password='testpass123')
        url = reverse('stockdiary:detail', kwargs={'pk': self.diary.pk})
        response = client.get(url)
        
        assert response.status_code == 200
        assert response.context['diary'] == self.diary
    
    def test_detail_view_displays_transactions(self, client):
        """取引履歴の表示"""
        client.login(username='testuser', password='testpass123')
        url = reverse('stockdiary:detail', kwargs={'pk': self.diary.pk})
        response = client.get(url)
        
        assert response.status_code == 200
        transactions = response.context['transactions']
        assert transactions.count() == 2
    
    def test_detail_view_other_user_diary(self, client):
        """他ユーザーの日記へのアクセス（404）"""
        # 別のユーザーを作成
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        client.login(username='otheruser', password='otherpass123')
        url = reverse('stockdiary:detail', kwargs={'pk': self.diary.pk})
        response = client.get(url)
        
        # 404またはリダイレクト
        assert response.status_code in [302, 404]


@pytest.mark.django_db(transaction=True)
class TestStockDiaryCreateView:
    """日記作成ビューのテスト"""
    
    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_view_get(self, client):
        """作成画面の表示"""
        client.login(username='testuser', password='testpass123')
        response = client.get(reverse('stockdiary:create'))
        
        assert response.status_code == 200
        assert 'form' in response.context
    
    def test_create_diary_without_transaction(self, client):
        """取引なしで日記を作成"""
        client.login(username='testuser', password='testpass123')
        
        data = {
            'stock_name': 'テスト株式会社',
            'stock_symbol': '9999',
            'reason': 'テスト理由',
            'sector': 'テスト業種',
            'add_initial_purchase': False
        }
        
        response = client.post(reverse('stockdiary:create'), data)
        
        # リダイレクトまたは成功
        assert response.status_code in [200, 302]
        
        # 日記が作成されたことを確認
        diary = StockDiary.objects.filter(stock_name='テスト株式会社').first()
        assert diary is not None
        assert diary.user == self.user
        assert diary.is_memo is True
    
    def test_create_diary_with_initial_purchase(self, client):
        """初回購入情報付きで日記を作成"""
        client.login(username='testuser', password='testpass123')
        
        data = {
            'stock_name': 'テスト株式会社2',
            'stock_symbol': '9998',
            'reason': 'テスト理由2',
            'add_initial_purchase': True,
            'initial_purchase_date': date.today().strftime('%Y-%m-%d'),
            'initial_purchase_price': '3000.00',
            'initial_purchase_quantity': '200'
        }
        
        response = client.post(reverse('stockdiary:create'), data)
        
        assert response.status_code in [200, 302]
        
        # 日記と取引が作成されたことを確認
        diary = StockDiary.objects.filter(stock_name='テスト株式会社2').first()
        assert diary is not None
        assert diary.transactions.count() == 1
        
        transaction = diary.transactions.first()
        assert transaction.quantity == Decimal('200')
        assert transaction.price == Decimal('3000.00')


@pytest.mark.django_db(transaction=True)
class TestTransactionManagement:
    """取引管理のテスト"""
    
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
            reason='テスト用'
        )
    
    def test_add_transaction(self, client):
        """取引の追加"""
        client.login(username='testuser', password='testpass123')
        
        url = reverse('stockdiary:add_transaction', kwargs={'diary_id': self.diary.pk})
        data = {
            'transaction_type': 'buy',
            'transaction_date': date.today().strftime('%Y-%m-%d'),
            'price': '2500.00',
            'quantity': '150',
            'memo': 'テスト購入'
        }
        
        response = client.post(url, data)
        
        # リダイレクト
        assert response.status_code == 302
        
        # 取引が追加されたことを確認
        assert Transaction.objects.filter(diary=self.diary).count() == 1
        
        transaction = Transaction.objects.first()
        assert transaction.transaction_type == 'buy'
        assert transaction.quantity == Decimal('150')
        assert transaction.price == Decimal('2500.00')
    
    def test_delete_transaction(self, client):
        """取引の削除"""
        client.login(username='testuser', password='testpass123')
        
        # 取引を作成
        transaction = Transaction.objects.create(
            diary=self.diary,
            transaction_type='buy',
            transaction_date=date.today(),
            price=Decimal('2000.00'),
            quantity=Decimal('100')
        )
        
        url = reverse('stockdiary:delete_transaction', kwargs={'transaction_id': transaction.pk})
        response = client.post(url)
        
        # リダイレクト
        assert response.status_code == 302
        
        # 取引が削除されたことを確認
        assert Transaction.objects.filter(pk=transaction.pk).count() == 0


@pytest.mark.django_db(transaction=True)
class TestDiaryNoteManagement:
    """継続記録管理のテスト"""
    
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
    
    def test_add_diary_note(self, client):
        """継続記録の追加"""
        client.login(username='testuser', password='testpass123')
        
        url = reverse('stockdiary:add_note', kwargs={'pk': self.diary.pk})
        data = {
            'date': date.today().strftime('%Y-%m-%d'),
            'content': '四半期決算が好調だった',
            'current_price': '5500.00',
            'note_type': 'earnings',
            'importance': 'high'
        }
        
        response = client.post(url, data)
        
        # リダイレクト
        assert response.status_code == 302
        
        # 継続記録が追加されたことを確認
        assert DiaryNote.objects.filter(diary=self.diary).count() == 1
        
        note = DiaryNote.objects.first()
        assert note.content == '四半期決算が好調だった'
        assert note.note_type == 'earnings'


@pytest.mark.django_db(transaction=True)
class TestCSVUpload:
    """CSVアップロード機能のテスト"""
    
    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_trade_upload_view_get(self, client):
        """アップロード画面の表示"""
        client.login(username='testuser', password='testpass123')
        response = client.get(reverse('stockdiary:trade_upload'))
        
        assert response.status_code == 200
        assert 'form' in response.context


@pytest.mark.django_db(transaction=True)
class TestTagManagement:
    """タグ管理のテスト"""
    
    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_tag(self, client):
        """タグの作成"""
        client.login(username='testuser', password='testpass123')
        
        data = {'name': '長期投資'}
        response = client.post(reverse('tags:create'), data)
        
        # リダイレクト
        assert response.status_code == 302
        
        # タグが作成されたことを確認
        tag = Tag.objects.filter(name='長期投資', user=self.user).first()
        assert tag is not None
    
    def test_tag_list_view(self, client):
        """タグ一覧の表示"""
        client.login(username='testuser', password='testpass123')
        
        # タグを作成
        Tag.objects.create(user=self.user, name='配当狙い')
        Tag.objects.create(user=self.user, name='成長株')
        
        response = client.get(reverse('tags:list'))
        
        assert response.status_code == 200
        assert response.context['tags'].count() == 2