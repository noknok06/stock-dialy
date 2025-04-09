import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from tags.models import Tag
from stockdiary.models import StockDiary

import json
import requests_mock

User = get_user_model()

@pytest.mark.django_db
class TestStockDiaryAPI:
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
    
    @pytest.fixture
    def client_login(self, client):
        """ログインしたクライアントを返すフィクスチャ"""
        client.login(username='testuser', password='testpass123')
        return client
    
    def test_get_stock_info_successful(self, client_login):
        """株式情報取得APIのテスト（成功ケース）"""
        with requests_mock.Mocker() as m:
            # Yahoo Finance APIのモック
            mock_response = {
                'chart': {
                    'result': [{
                        'meta': {
                            'regularMarketPrice': 3000,
                            'previousClose': 2900,
                            'shortName': 'テスト株式会社',
                            'exchangeName': '東証プライム'
                        }
                    }]
                }
            }
            m.get('https://query1.finance.yahoo.com/v8/finance/chart/7203.T', json=mock_response)
            
            # APIエンドポイントにリクエスト
            url = reverse('stockdiary:api_stock_info', kwargs={'stock_code': '7203'})
            response = client_login.get(url)
            
            # レスポンスの検証
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert data['company_name'] == 'テスト株式会社'
            assert data['price'] == 3000
            assert data['change_percent'] is not None
            assert data['market'] == '東証プライム'
    
    def test_get_stock_price_successful(self, client_login):
        """株価取得APIのテスト（成功ケース）"""
        with requests_mock.Mocker() as m:
            # Yahoo Finance APIのモック
            mock_response = {
                'chart': {
                    'result': [{
                        'meta': {
                            'regularMarketPrice': 3000,
                            'currency': 'JPY'
                        }
                    }]
                }
            }
            m.get('https://query1.finance.yahoo.com/v8/finance/chart/7203.T', json=mock_response)
            
            # APIエンドポイントにリクエスト
            url = reverse('stockdiary:api_stock_price', kwargs={'stock_code': '7203'})
            response = client_login.get(url)
            
            # レスポンスの検証
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert data['price'] == 3000
            assert data['currency'] == 'JPY'
    
    def test_api_create_diary_minimal(self, client_login):
        """最小限の情報で日記を作成するAPIテスト"""
        url = reverse('stockdiary:api_create')
        
        # 最小限の必須パラメータで日記を作成
        data = {
            'stock_name': 'テスト株式会社',
        }
        
        response = client_login.post(url, data)
        
        # レスポンスの検証
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert 'diary_id' in response_data
        
        # データベースに日記が作成されたことを確認
        diary = StockDiary.objects.get(id=response_data['diary_id'])
        assert diary.stock_name == 'テスト株式会社'
        assert diary.user == self.user
    
    def test_api_create_diary_full(self, client_login):
        """全情報を含めて日記を作成するAPIテスト"""
        url = reverse('stockdiary:api_create')
        
        # タグを追加
        tag_ids = [str(self.tag1.id), str(self.tag2.id)]
        
        # 完全な情報で日記を作成
        data = {
            'stock_name': 'テスト株式会社',
            'stock_symbol': '7203',
            'purchase_date': '2023-01-01',
            'purchase_price': '2000.50',
            'purchase_quantity': '100',
            'sector': '製造業',
            'reason': '将来性を評価',
            'tags': tag_ids
        }
        
        response = client_login.post(url, data)
        
        # レスポンスの検証
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert 'diary_id' in response_data
        
        # データベースに日記が作成されたことを確認
        diary = StockDiary.objects.get(id=response_data['diary_id'])
        assert diary.stock_name == 'テスト株式会社'
        assert diary.stock_symbol == '7203'
        assert diary.purchase_date.strftime('%Y-%m-%d') == '2023-01-01'
        assert float(diary.purchase_price) == 2000.50
        assert diary.purchase_quantity == 100
        assert diary.sector == '製造業'
        assert diary.reason == '将来性を評価'
        
        # タグの確認
        assert set(diary.tags.all()) == set([self.tag1, self.tag2])
    
    def test_api_create_diary_invalid_data(self, client_login):
        """不正なデータでの日記作成APIテスト"""
        url = reverse('stockdiary:api_create')
        
        # 必須の銘柄名を省略
        data = {
            'purchase_price': '2000.50',
            'purchase_quantity': '100'
        }
        
        response = client_login.post(url, data)
        
        # エラーレスポンスの検証
        assert response.status_code == 400
        response_data = response.json()
        assert response_data['success'] is False
        assert '銘柄名は必須です' in response_data['message']
    
    def test_non_authenticated_api_create_diary(self, client):
        """未認証ユーザーによる日記作成APIテスト"""
        url = reverse('stockdiary:api_create')
        
        data = {
            'stock_name': 'テスト株式会社'
        }
        
        response = client.post(url, data)
        
        # 認証エラーの検証
        assert response.status_code == 302  # リダイレクト（ログインページへ）