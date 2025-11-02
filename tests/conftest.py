"""
Pytestの共通設定とフィクスチャ
tests/conftest.py に配置
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from decimal import Decimal
from datetime import date, timedelta

from stockdiary.models import StockDiary, Transaction, DiaryNote, StockSplit
from analysis_template.models import AnalysisTemplate, AnalysisItem
from tags.models import Tag

User = get_user_model()


@pytest.fixture
def user(db):
    """テスト用ユーザー"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def another_user(db):
    """別のテスト用ユーザー"""
    return User.objects.create_user(
        username='anotheruser',
        email='another@example.com',
        password='anotherpass123'
    )


@pytest.fixture
def client():
    """Djangoテストクライアント"""
    return Client()


@pytest.fixture
def authenticated_client(client, user):
    """認証済みクライアント"""
    client.login(username='testuser', password='testpass123')
    return client


@pytest.fixture
def sample_diary(user):
    """サンプル日記"""
    return StockDiary.objects.create(
        user=user,
        stock_symbol='7203',
        stock_name='トヨタ自動車',
        reason='長期保有目的',
        sector='輸送用機器'
    )


@pytest.fixture
def sample_diary_with_transaction(sample_diary):
    """取引付きのサンプル日記"""
    Transaction.objects.create(
        diary=sample_diary,
        transaction_type='buy',
        transaction_date=date.today(),
        price=Decimal('2000.00'),
        quantity=Decimal('100')
    )
    sample_diary.refresh_from_db()
    return sample_diary


@pytest.fixture
def sample_sold_diary(user):
    """売却済み日記"""
    diary = StockDiary.objects.create(
        user=user,
        stock_symbol='9984',
        stock_name='ソフトバンクグループ',
        reason='短期売買'
    )
    
    # 購入
    Transaction.objects.create(
        diary=diary,
        transaction_type='buy',
        transaction_date=date.today() - timedelta(days=10),
        price=Decimal('5000.00'),
        quantity=Decimal('50')
    )
    
    # 売却
    Transaction.objects.create(
        diary=diary,
        transaction_type='sell',
        transaction_date=date.today() - timedelta(days=5),
        price=Decimal('5500.00'),
        quantity=Decimal('50')
    )
    
    diary.refresh_from_db()
    return diary


@pytest.fixture
def sample_memo_diary(user):
    """メモのみの日記"""
    return StockDiary.objects.create(
        user=user,
        stock_symbol='6758',
        stock_name='ソニーグループ',
        reason='監視銘柄',
        memo='今後の動向を注視'
    )


@pytest.fixture
def sample_tags(user):
    """サンプルタグ"""
    tag1 = Tag.objects.create(user=user, name='長期投資')
    tag2 = Tag.objects.create(user=user, name='配当狙い')
    tag3 = Tag.objects.create(user=user, name='成長株')
    return [tag1, tag2, tag3]


@pytest.fixture
def sample_template(user):
    """サンプル分析テンプレート"""
    template = AnalysisTemplate.objects.create(
        user=user,
        name='基本分析',
        description='基本的な分析項目'
    )
    
    # 数値型項目
    AnalysisItem.objects.create(
        template=template,
        name='PER',
        description='株価収益率',
        item_type='number',
        order=1
    )
    
    # ブール型項目
    AnalysisItem.objects.create(
        template=template,
        name='業績好調',
        description='直近の業績',
        item_type='boolean',
        order=2
    )
    
    # テキスト型項目
    AnalysisItem.objects.create(
        template=template,
        name='投資メモ',
        description='その他メモ',
        item_type='text',
        order=3
    )
    
    return template


@pytest.fixture
def complex_diary_with_multiple_transactions(user):
    """複数取引を持つ複雑な日記"""
    diary = StockDiary.objects.create(
        user=user,
        stock_symbol='4063',
        stock_name='信越化学工業',
        reason='優良企業'
    )
    
    # 複数の取引を追加
    transactions = [
        {'type': 'buy', 'date': date(2024, 1, 10), 'price': '2000.00', 'quantity': '100'},
        {'type': 'buy', 'date': date(2024, 2, 15), 'price': '2200.00', 'quantity': '50'},
        {'type': 'sell', 'date': date(2024, 3, 20), 'price': '2500.00', 'quantity': '30'},
        {'type': 'buy', 'date': date(2024, 4, 25), 'price': '2100.00', 'quantity': '80'},
        {'type': 'sell', 'date': date(2024, 5, 30), 'price': '2600.00', 'quantity': '50'},
    ]
    
    for t in transactions:
        Transaction.objects.create(
            diary=diary,
            transaction_type=t['type'],
            transaction_date=t['date'],
            price=Decimal(t['price']),
            quantity=Decimal(t['quantity'])
        )
    
    diary.refresh_from_db()
    return diary


@pytest.fixture
def diary_with_notes(sample_diary_with_transaction):
    """継続記録付きの日記"""
    DiaryNote.objects.create(
        diary=sample_diary_with_transaction,
        date=date.today() - timedelta(days=5),
        content='四半期決算が好調',
        current_price=Decimal('2100.00'),
        note_type='earnings',
        importance='high'
    )
    
    DiaryNote.objects.create(
        diary=sample_diary_with_transaction,
        date=date.today() - timedelta(days=2),
        content='新製品発表のニュース',
        current_price=Decimal('2150.00'),
        note_type='news',
        importance='medium'
    )
    
    return sample_diary_with_transaction


@pytest.fixture
def diary_with_stock_split(user):
    """株式分割を含む日記"""
    diary = StockDiary.objects.create(
        user=user,
        stock_symbol='7974',
        stock_name='任天堂',
        reason='ゲーム事業の成長期待'
    )
    
    # 分割前の取引
    Transaction.objects.create(
        diary=diary,
        transaction_type='buy',
        transaction_date=date(2024, 1, 10),
        price=Decimal('5000.00'),
        quantity=Decimal('100')
    )
    
    # 株式分割記録（未適用）
    StockSplit.objects.create(
        diary=diary,
        split_date=date(2024, 2, 1),
        split_ratio=Decimal('2.0'),
        memo='1株→2株の分割'
    )
    
    return diary


# データベーストランザクションの自動ロールバック
@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """全てのテストでデータベースアクセスを有効化"""
    pass


# テスト実行前後のフック
@pytest.fixture(scope='session', autouse=True)
def setup_test_environment(django_db_setup, django_db_blocker):
    """テスト環境のセットアップ"""
    with django_db_blocker.unblock():
        # テスト用の初期データがあればここで作成
        pass


# カスタムマーカー
def pytest_configure(config):
    """Pytestの設定"""
    config.addinivalue_line(
        "markers", "slow: マークが付けられたテストは実行に時間がかかります"
    )
    config.addinivalue_line(
        "markers", "integration: 統合テスト"
    )
    config.addinivalue_line(
        "markers", "unit: 単体テスト"
    )