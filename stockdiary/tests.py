# python manage.py test analysis_template

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.http import JsonResponse

from .models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from stockdiary.models import StockDiary

User = get_user_model()

class AnalysisTemplateTestCase(TestCase):
    """分析テンプレート機能のテストケース"""
    
    def setUp(self):
        """テスト用のデータを作成"""
        # テストユーザーを作成
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # テスト用のテンプレートを作成
        self.template = AnalysisTemplate.objects.create(
            user=self.user,
            name='株式投資基準テンプレート',
            description='投資判断の基準となる分析テンプレート'
        )
        
        # テンプレートに分析項目を追加
        self.number_item = AnalysisItem.objects.create(
            template=self.template,
            name='PER',
            description='株価収益率',
            item_type='number',
            order=1
        )
        
        self.text_item = AnalysisItem.objects.create(
            template=self.template,
            name='業界動向',
            description='業界全体の成長性や動向',
            item_type='text',
            order=2
        )
        
        self.select_item = AnalysisItem.objects.create(
            template=self.template,
            name='企業規模',
            description='企業の規模感',
            item_type='select',
            choices='大型,中型,小型',
            order=3
        )
        
        self.boolean_item = AnalysisItem.objects.create(
            template=self.template,
            name='配当あり',
            description='配当金の有無',
            item_type='boolean',
            order=4
        )
        
        self.compound_item = AnalysisItem.objects.create(
            template=self.template,
            name='PBR 1倍以下',
            description='PBRが1倍以下かどうか',
            item_type='boolean_with_value',
            value_label='実際のPBR値',
            order=5
        )
        
        # テスト用の株式日記を作成
        self.diary = StockDiary.objects.create(
            user=self.user,
            stock_name='テスト株式会社',
            stock_symbol='1234',
            date=timezone.now(),
            content='テスト株式会社についての分析'
        )
        
        # 日記に分析値を追加
        DiaryAnalysisValue.objects.create(
            diary=self.diary,
            analysis_item=self.number_item,
            number_value=15.5
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary,
            analysis_item=self.text_item,
            text_value='成長産業で今後の拡大が期待できる'
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary,
            analysis_item=self.select_item,
            text_value='中型'
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary,
            analysis_item=self.boolean_item,
            boolean_value=True
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary,
            analysis_item=self.compound_item,
            boolean_value=False,
            number_value=1.2
        )
        
        # クライアントを設定
        self.client = Client()
        
    def test_template_list_view(self):
        """テンプレート一覧ページのテスト"""
        # ログイン
        self.client.login(username='testuser', password='testpassword')
        
        # テンプレート一覧ページにアクセス
        response = self.client.get(reverse('analysis_template:list'))
        
        # レスポンスのステータスコードを確認
        self.assertEqual(response.status_code, 200)
        
        # テンプレートがコンテキストに含まれていることを確認
        self.assertIn('templates', response.context)
        templates = response.context['templates']
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0].name, '株式投資基準テンプレート')
        
    def test_template_detail_view(self):
        """テンプレート詳細ページのテスト"""
        # ログイン
        self.client.login(username='testuser', password='testpassword')
        
        # テンプレート詳細ページにアクセス
        response = self.client.get(
            reverse('analysis_template:detail', kwargs={'pk': self.template.pk})
        )
        
        # レスポンスのステータスコードを確認
        self.assertEqual(response.status_code, 200)
        
        # テンプレートと関連項目がコンテキストに含まれていることを確認
        self.assertIn('template', response.context)
        template = response.context['template']
        self.assertEqual(template.name, '株式投資基準テンプレート')
        self.assertEqual(template.items.count(), 5)
        
    def test_template_create_view(self):
        """テンプレート作成ページのテスト"""
        # ログイン
        self.client.login(username='testuser', password='testpassword')
        
        # 新規テンプレート作成ページにアクセス
        response = self.client.get(reverse('analysis_template:create'))
        self.assertEqual(response.status_code, 200)
        
        # フォームとフォームセットが含まれていることを確認
        self.assertIn('form', response.context)
        self.assertIn('items_formset', response.context)
        
        # フォームの送信データを作成
        form_data = {
            'name': '新しいテンプレート',
            'description': 'テスト用の新しいテンプレート',
            
            # フォームセット用のデータ
            'items-TOTAL_FORMS': '2',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '1000',
            
            # 1つ目の分析項目
            'items-0-name': 'ROE',
            'items-0-description': '自己資本利益率',
            'items-0-item_type': 'number',
            'items-0-order': '1',
            
            # 2つ目の分析項目
            'items-1-name': '成長性',
            'items-1-description': '将来の成長可能性',
            'items-1-item_type': 'select',
            'items-1-choices': '高い,中程度,低い',
            'items-1-order': '2',
        }
        
        # POSTリクエストを送信
        response = self.client.post(reverse('analysis_template:create'), form_data)
        
        # リダイレクトを確認
        self.assertEqual(response.status_code, 302)
        
        # テンプレートが作成されたか確認
        self.assertEqual(AnalysisTemplate.objects.count(), 2)
        new_template = AnalysisTemplate.objects.get(name='新しいテンプレート')
        self.assertEqual(new_template.items.count(), 2)
        self.assertEqual(new_template.user, self.user)
        
    def test_template_update_view(self):
        """テンプレート更新ページのテスト"""
        # ログイン
        self.client.login(username='testuser', password='testpassword')
        
        # 更新ページにアクセス
        response = self.client.get(
            reverse('analysis_template:update', kwargs={'pk': self.template.pk})
        )
        self.assertEqual(response.status_code, 200)
        
        # テンプレート名を更新するデータを作成
        form_data = {
            'name': '更新されたテンプレート',
            'description': self.template.description,
            
            # フォームセット用のデータ
            'items-TOTAL_FORMS': '5',
            'items-INITIAL_FORMS': '5',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '1000',
        }
        
        # 既存の分析項目のデータを追加
        for i, item in enumerate([self.number_item, self.text_item, self.select_item, 
                                 self.boolean_item, self.compound_item]):
            form_data[f'items-{i}-id'] = item.id
            form_data[f'items-{i}-name'] = item.name
            form_data[f'items-{i}-description'] = item.description
            form_data[f'items-{i}-item_type'] = item.item_type
            form_data[f'items-{i}-order'] = item.order
            form_data[f'items-{i}-choices'] = item.choices
            form_data[f'items-{i}-value_label'] = item.value_label
        
        # 1つ目の項目を更新
        form_data['items-0-name'] = '更新された項目'
        
        # POSTリクエストを送信
        response = self.client.post(
            reverse('analysis_template:update', kwargs={'pk': self.template.pk}),
            form_data
        )
        
        # リダイレクトを確認
        self.assertEqual(response.status_code, 302)
        
        # テンプレートが更新されたか確認
        self.template.refresh_from_db()
        self.assertEqual(self.template.name, '更新されたテンプレート')
        
        # 項目が更新されたか確認
        self.number_item.refresh_from_db()
        self.assertEqual(self.number_item.name, '更新された項目')
        
    def test_template_delete_view(self):
        """テンプレート削除ページのテスト"""
        # ログイン
        self.client.login(username='testuser', password='testpassword')
        
        # 削除ページにアクセス
        response = self.client.get(
            reverse('analysis_template:delete', kwargs={'pk': self.template.pk})
        )
        self.assertEqual(response.status_code, 200)
        
        # POSTリクエストで削除を実行
        response = self.client.post(
            reverse('analysis_template:delete', kwargs={'pk': self.template.pk})
        )
        
        # リダイレクトを確認
        self.assertEqual(response.status_code, 302)
        
        # テンプレートが削除されたか確認
        self.assertEqual(AnalysisTemplate.objects.count(), 0)
        
        # 関連する分析項目も削除されたか確認
        self.assertEqual(AnalysisItem.objects.count(), 0)
        
        # 関連する分析値も削除されたか確認
        self.assertEqual(DiaryAnalysisValue.objects.count(), 0)
        
    def test_report_view(self):
        """分析レポートページのテスト"""
        # ログイン
        self.client.login(username='testuser', password='testpassword')
        
        # レポートページにアクセス
        response = self.client.get(
            reverse('analysis_template:report', kwargs={'pk': self.template.pk})
        )
        
        # レスポンスのステータスコードを確認
        self.assertEqual(response.status_code, 200)
        
        # レポートデータがコンテキストに含まれていることを確認
        self.assertIn('report_data', response.context)
        report_data = response.context['report_data']
        self.assertEqual(len(report_data), 1)
        
        # 日記のデータが正しく含まれているか確認
        diary_data = report_data[0]
        self.assertEqual(diary_data['diary'], self.diary)
        self.assertIn(self.number_item.id, diary_data['values'])
        self.assertEqual(diary_data['values'][self.number_item.id], 15.5)
        
    def test_api_get_template_items(self):
        """APIのテスト: テンプレート項目の取得"""
        # ログイン
        self.client.login(username='testuser', password='testpassword')
        
        # APIエンドポイントにアクセス
        response = self.client.get(
            reverse('analysis_template:api_get_items'),
            {'template_id': self.template.id}
        )
        
        # レスポンスのステータスコードを確認
        self.assertEqual(response.status_code, 200)
        
        # JSONレスポンスを取得
        data = response.json()
        
        # レスポンスが成功したことを確認
        self.assertTrue(data['success'])
        
        # テンプレート情報が含まれていることを確認
        self.assertEqual(data['template']['id'], self.template.id)
        self.assertEqual(data['template']['name'], self.template.name)
        
        # 分析項目が含まれていることを確認
        self.assertEqual(len(data['items']), 5)
        
        # 日記IDを指定してAPIにアクセス
        response = self.client.get(
            reverse('analysis_template:api_get_items'),
            {'template_id': self.template.id, 'diary_id': self.diary.id}
        )
        
        # JSONレスポンスを取得
        data = response.json()
        
        # 分析値が含まれていることを確認
        self.assertIn('values', data)
        self.assertEqual(data['values'][str(self.number_item.id)], 15.5)
        
    def test_unauthorized_access(self):
        """未認証アクセスのテスト"""
        # ログアウト状態
        self.client.logout()
        
        # 各ビューへのアクセスをテスト
        urls = [
            reverse('analysis_template:list'),
            reverse('analysis_template:detail', kwargs={'pk': self.template.pk}),
            reverse('analysis_template:create'),
            reverse('analysis_template:update', kwargs={'pk': self.template.pk}),
            reverse('analysis_template:delete', kwargs={'pk': self.template.pk}),
            reverse('analysis_template:report', kwargs={'pk': self.template.pk}),
        ]
        
        for url in urls:
            response = self.client.get(url)
            # ログインページにリダイレクトされることを確認
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith('/accounts/login/'))
            
    def test_other_user_data_access(self):
        """他ユーザーのデータへのアクセス制限テスト"""
        # 別のユーザーを作成
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpassword'
        )
        
        # 別ユーザーでログイン
        self.client.login(username='otheruser', password='otherpassword')
        
        # 他ユーザーのテンプレートにアクセスを試みる
        response = self.client.get(
            reverse('analysis_template:detail', kwargs={'pk': self.template.pk})
        )
        
        # 404エラーになることを確認
        self.assertEqual(response.status_code, 404)


class AnalysisComprehensiveTestCase(TestCase):
    """複数の日記エントリーを含む総合テスト"""
    
    def setUp(self):
        """複数の日記エントリーを持つテストデータを作成"""
        # テストユーザーを作成
        self.user = User.objects.create_user(
            username='investor',
            email='investor@example.com',
            password='investpass'
        )
        
        # テスト用のテンプレートを作成
        self.template = AnalysisTemplate.objects.create(
            user=self.user,
            name='投資チェックリスト',
            description='株式投資判断のためのチェックリスト'
        )
        
        # テンプレートに分析項目を追加
        self.per_item = AnalysisItem.objects.create(
            template=self.template,
            name='PER',
            description='株価収益率',
            item_type='number',
            order=1
        )
        
        self.pbr_check = AnalysisItem.objects.create(
            template=self.template,
            name='PBRが1.0倍以下',
            description='株価純資産倍率が1.0倍以下かどうか',
            item_type='boolean_with_value',
            value_label='実際のPBR値',
            order=2
        )
        
        self.roe_item = AnalysisItem.objects.create(
            template=self.template,
            name='ROE',
            description='自己資本利益率',
            item_type='number',
            order=3
        )
        
        self.dividend_item = AnalysisItem.objects.create(
            template=self.template,
            name='配当利回り',
            description='配当利回り（%）',
            item_type='number',
            order=4
        )
        
        self.growth_item = AnalysisItem.objects.create(
            template=self.template,
            name='成長性評価',
            description='今後の成長可能性',
            item_type='select',
            choices='高い,中程度,低い',
            order=5
        )
        
        # 複数の株式日記を作成
        # 日記1: 高配当株
        self.diary1 = StockDiary.objects.create(
            user=self.user,
            stock_name='高配当株式会社',
            stock_symbol='8001',
            date=timezone.now(),
            content='高配当が魅力の銘柄。配当利回りは4.5%と高く、安定した業績。'
        )
        
        # 日記1の分析値
        DiaryAnalysisValue.objects.create(
            diary=self.diary1,
            analysis_item=self.per_item,
            number_value=12.5
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary1,
            analysis_item=self.pbr_check,
            boolean_value=False,
            number_value=1.2
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary1,
            analysis_item=self.roe_item,
            number_value=8.5
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary1,
            analysis_item=self.dividend_item,
            number_value=4.5
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary1,
            analysis_item=self.growth_item,
            text_value='低い'
        )
        
        # 日記2: 成長株
        self.diary2 = StockDiary.objects.create(
            user=self.user,
            stock_name='成長テクノロジー',
            stock_symbol='4565',
            date=timezone.now(),
            content='IT分野で急成長中の企業。高い成長率が期待できる。'
        )
        
        # 日記2の分析値
        DiaryAnalysisValue.objects.create(
            diary=self.diary2,
            analysis_item=self.per_item,
            number_value=35.8
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary2,
            analysis_item=self.pbr_check,
            boolean_value=False,
            number_value=3.2
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary2,
            analysis_item=self.roe_item,
            number_value=15.2
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary2,
            analysis_item=self.dividend_item,
            number_value=0.8
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary2,
            analysis_item=self.growth_item,
            text_value='高い'
        )
        
        # 日記3: バリュー株
        self.diary3 = StockDiary.objects.create(
            user=self.user,
            stock_name='割安商事',
            stock_symbol='3333',
            date=timezone.now(),
            content='PBRが低く割安な印象。底堅い業績で徐々に評価が高まる可能性。'
        )
        
        # 日記3の分析値
        DiaryAnalysisValue.objects.create(
            diary=self.diary3,
            analysis_item=self.per_item,
            number_value=9.2
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary3,
            analysis_item=self.pbr_check,
            boolean_value=True,
            number_value=0.8
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary3,
            analysis_item=self.roe_item,
            number_value=7.8
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary3,
            analysis_item=self.dividend_item,
            number_value=2.5
        )
        
        DiaryAnalysisValue.objects.create(
            diary=self.diary3,
            analysis_item=self.growth_item,
            text_value='中程度'
        )
        
        # クライアントを設定
        self.client = Client()
        
    def test_comprehensive_report(self):
        """総合的なレポート機能のテスト"""
        # ログイン
        self.client.login(username='investor', password='investpass')
        
        # レポートページにアクセス
        response = self.client.get(
            reverse('analysis_template:report', kwargs={'pk': self.template.pk})
        )
        
        # レスポンスのステータスコードを確認
        self.assertEqual(response.status_code, 200)
        
        # レポートデータがコンテキストに含まれていることを確認
        self.assertIn('report_data', response.context)
        report_data = response.context['report_data']
        
        # 3つの日記データが含まれていることを確認
        self.assertEqual(len(report_data), 3)
        
        # 各日記のデータを確認
        diary_symbols = [data['diary'].stock_symbol for data in report_data]
        self.assertIn('8001', diary_symbols)
        self.assertIn('4565', diary_symbols)
        self.assertIn('3333', diary_symbols)
        
        # PBRのチェック結果を確認
        for data in report_data:
            if data['diary'].stock_symbol == '3333':  # 割安商事
                self.assertTrue(data['values'][self.pbr_check.id]['boolean_value'])
                self.assertEqual(data['values'][self.pbr_check.id]['number_value'], 0.8)
            else:
                self.assertFalse(data['values'][self.pbr_check.id]['boolean_value'])