# python manage.py test analysis_template.tests

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from decimal import Decimal

from .models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from stockdiary.models import StockDiary

User = get_user_model()

class AnalysisTemplateModelTest(TestCase):
    def setUp(self):
        """テスト用のユーザーと分析テンプレートを作成"""
        self.user = User.objects.create_user(
            username='testinvestor', 
            email='investor@example.com', 
            password='secure_password_123'
        )
        
        self.template = AnalysisTemplate.objects.create(
            user=self.user,
            name='投資分析テンプレート',
            description='包括的な投資分析のためのテンプレート'
        )

class AnalysisItemModelTest(AnalysisTemplateModelTest):
    def test_create_boolean_item(self):
        """チェックボックス型の分析項目作成"""
        item = AnalysisItem.objects.create(
            template=self.template,
            name='長期投資',
            description='長期投資戦略かどうか',
            item_type='boolean',
            order=1
        )
        
        self.assertEqual(item.name, '長期投資')
        self.assertEqual(item.item_type, 'boolean')
        self.assertEqual(item.order, 1)

    def test_create_number_item(self):
        """数値型の分析項目作成"""
        item = AnalysisItem.objects.create(
            template=self.template,
            name='PER',
            description='株価収益率',
            item_type='number',
            order=2
        )
        
        self.assertEqual(item.name, 'PER')
        self.assertEqual(item.item_type, 'number')
        self.assertEqual(item.order, 2)

    def test_create_select_item(self):
        """選択型の分析項目作成"""
        item = AnalysisItem.objects.create(
            template=self.template,
            name='投資タイプ',
            description='投資戦略のタイプ',
            item_type='select',
            choices='バリュー,グロース,インカム,スペキュレーティブ',
            order=3
        )
        
        self.assertEqual(item.name, '投資タイプ')
        self.assertEqual(item.item_type, 'select')
        self.assertEqual(
            item.get_choices_list(), 
            ['バリュー', 'グロース', 'インカム', 'スペキュレーティブ']
        )

    def test_create_boolean_with_value_item(self):
        """複合型（チェック＋値）の分析項目作成"""
        item = AnalysisItem.objects.create(
            template=self.template,
            name='高配当株',
            description='高配当株かどうか',
            item_type='boolean_with_value',
            value_label='配当利回り',
            order=4
        )
        
        self.assertEqual(item.name, '高配当株')
        self.assertEqual(item.item_type, 'boolean_with_value')
        self.assertEqual(item.value_label, '配当利回り')

    def test_create_text_item(self):
        """テキスト型の分析項目作成"""
        item = AnalysisItem.objects.create(
            template=self.template,
            name='投資理由',
            description='投資判断の詳細な理由',
            item_type='text',
            order=5
        )
        
        self.assertEqual(item.name, '投資理由')
        self.assertEqual(item.item_type, 'text')

class DiaryAnalysisValueModelTest(AnalysisTemplateModelTest):
    def setUp(self):
        """分析値テスト用のデータを準備"""
        super().setUp()
        
        # テスト用の株式日記を作成
        self.diary = StockDiary.objects.create(
            user=self.user,
            stock_name='テスト株式会社',
            stock_symbol='TEST',
            purchase_date='2023-01-01',
            purchase_price=1000,
            purchase_quantity=100
        )
        
        # テスト用の分析項目を作成
        self.boolean_item = AnalysisItem.objects.create(
            template=self.template,
            name='成長株',
            item_type='boolean'
        )
        
        self.number_item = AnalysisItem.objects.create(
            template=self.template,
            name='ROE',
            item_type='number'
        )
        
        self.boolean_value_item = AnalysisItem.objects.create(
            template=self.template,
            name='高配当株',
            item_type='boolean_with_value',
            value_label='配当利回り'
        )

    def test_create_boolean_value(self):
        """チェックボックス型の値を保存"""
        value = DiaryAnalysisValue.objects.create(
            diary=self.diary,
            analysis_item=self.boolean_item,
            boolean_value=True
        )
        
        self.assertTrue(value.boolean_value)
        self.assertEqual(value.analysis_item, self.boolean_item)

    def test_create_number_value(self):
        """数値型の値を保存"""
        value = DiaryAnalysisValue.objects.create(
            diary=self.diary,
            analysis_item=self.number_item,
            number_value=Decimal('15.5')
        )
        
        self.assertEqual(value.number_value, Decimal('15.5'))
        self.assertEqual(value.analysis_item, self.number_item)

    def test_create_boolean_with_value(self):
        """複合型の値を保存"""
        value = DiaryAnalysisValue.objects.create(
            diary=self.diary,
            analysis_item=self.boolean_value_item,
            boolean_value=True,
            number_value=Decimal('3.2')
        )
        
        self.assertTrue(value.boolean_value)
        self.assertEqual(value.number_value, Decimal('3.2'))
        self.assertEqual(value.analysis_item, self.boolean_value_item)

    def test_unique_constraint(self):
        """1つの日記に同じ分析項目の値を2回保存しようとするテスト"""
        DiaryAnalysisValue.objects.create(
            diary=self.diary,
            analysis_item=self.boolean_item,
            boolean_value=True
        )
        
        # 同じ日記と分析項目で2回目の保存を試みる（例外が発生するはず）
        with self.assertRaises(IntegrityError):
            DiaryAnalysisValue.objects.create(
                diary=self.diary,
                analysis_item=self.boolean_item,
                boolean_value=False
            )

    def test_display_value_method(self):
        """get_display_value メソッドのテスト"""
        number_value = DiaryAnalysisValue.objects.create(
            diary=self.diary,
            analysis_item=self.number_item,
            number_value=Decimal('10.5')
        )
        
        self.assertEqual(number_value.get_display_value(), Decimal('10.5'))