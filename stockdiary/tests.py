from django.test import TestCase
from django.urls import reverse
from users.models import CustomUser  # CustomUserモデルをインポート
from checklist.models import Checklist
from tags.models import Tag
from stockdiary.models import StockDiary
from django.utils import timezone
from datetime import timedelta

class StockDiaryTests(TestCase):

    def setUp(self):
        # CustomUserモデルを使ってテスト用ユーザーを作成
        self.user = CustomUser.objects.create_user(username='testuser', password='password')
        # チェックリストとタグを作成
        self.checklist_item = Checklist.objects.create(user=self.user, name="チェック項目1")
        self.tag = Tag.objects.create(user=self.user, name="タグ1")
        self.login_url = reverse('login')  # ログインURL
        self.home_url = reverse('stockdiary:stockdiary_home')  # 日記一覧ページ

    def test_login_redirect(self):
        """ログインしていない場合はログインページにリダイレクトされる"""
        response = self.client.get(self.home_url)
        self.assertRedirects(response, f'{self.login_url}?next={self.home_url}')

    def test_create_stock_diary(self):
        """新規日記が正しく作成される"""
        # ログイン
        self.client.login(username='testuser', password='password')

        # 新規日記作成用のURL
        create_url = reverse('stockdiary:stockdiary_create')
        
        # フォームに送信するデータ
        data = {
            'stock_symbol': 'AAPL',
            'stock_name': 'Apple Inc.',
            'purchase_date': (timezone.now() - timedelta(days=30)).date(),
            'purchase_price': 150.00,
            'purchase_quantity': 10,
            'reason': '安定した業績を見込んで購入。',
            'checklist': [self.checklist_item.id],
            'tags': [self.tag.id],
        }

        # POSTリクエストで新規日記作成
        response = self.client.post(create_url, data)

        # 作成後に日記詳細ページにリダイレクトされることを確認
        self.assertRedirects(response, self.home_url)
        
        # 作成された日記がデータベースに存在するか確認
        stock_diary = StockDiary.objects.first()
        self.assertEqual(stock_diary.stock_symbol, 'AAPL')
        self.assertEqual(stock_diary.stock_name, 'Apple Inc.')
        self.assertEqual(stock_diary.purchase_price, 150.00)
        self.assertEqual(stock_diary.purchase_quantity, 10)
        self.assertEqual(stock_diary.reason, '安定した業績を見込んで購入。')
        self.assertEqual(stock_diary.checklist.count(), 1)
        self.assertEqual(stock_diary.tags.count(), 1)
    
    def test_stock_diary_view(self):
        """日記一覧ページが正しく表示される"""
        # ログイン
        self.client.login(username='testuser', password='password')

        # 日記作成
        StockDiary.objects.create(
            user=self.user,
            stock_symbol='GOOG',
            stock_name='Google Inc.',
            purchase_date=(timezone.now() - timedelta(days=30)).date(),
            purchase_price=2000.00,
            purchase_quantity=5,
            reason='成長性を見込んで購入。',
        )

        # 日記一覧ページにアクセス
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Google Inc.')  # 日記内容が含まれているか確認
