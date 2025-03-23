# python manage.py create_analysis_data --username admin

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from stockdiary.models import StockDiary
import random
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = "分析テンプレートとサンプルデータを作成します"

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='データを作成するユーザー名')
        parser.add_argument('--templates', type=int, default=1, help='作成するテンプレート数 (デフォルト: 1)')

    def handle(self, *args, **options):
        username = options['username']
        template_count = options['templates']

        if not username:
            self.stdout.write(
                    self.style.ERROR('ユーザー名が指定されていません。--username オプションを指定してください。')
                )
            return

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(
                    self.style.ERROR(f'ユーザー "{username}" が見つかりません。')
                )
            return

        # テンプレートデータの定義（前回と同様）
        template_configs = [
            {
                'name': '総合財務分析テンプレート',
                'description': '企業の財務状況を多角的に評価するための包括的な分析テンプレート',
                'items': [
                    {
                        'name': 'バリュエーション指標',
                        'description': '企業の相対的な価値を評価する指標群',
                        'sub_items': [
                            {
                                'name': 'PER（株価収益率）',
                                'description': '株価÷1株当たり利益で算出。企業の収益性を評価',
                                'item_type': 'number',
                            },
                            {
                                'name': 'PBR（株価純資産倍率）',
                                'description': '株価÷1株当たり純資産で算出。企業の資産価値を評価',
                                'item_type': 'number',
                            }
                        ]
                    },
                    {
                        'name': '収益性指標',
                        'description': '企業の収益創出能力を評価する指標',
                        'sub_items': [
                            {
                                'name': 'ROE（自己資本利益率）',
                                'description': '当期純利益÷自己資本で算出。株主の投資効率を評価',
                                'item_type': 'number',
                            },
                            {
                                'name': '高収益企業',
                                'description': '収益性が高いと判断できるか',
                                'item_type': 'boolean_with_value',
                                'value_label': '収益性スコア'
                            }
                        ]
                    },
                    {
                        'name': '成長性評価',
                        'description': '企業の将来的な成長可能性を評価',
                        'sub_items': [
                            {
                                'name': '売上高成長率',
                                'description': '過去3年間の売上高の年平均成長率',
                                'item_type': 'number',
                            },
                            {
                                'name': '成長株判定',
                                'description': '成長株と判断できるか',
                                'item_type': 'boolean',
                            }
                        ]
                    },
                    {
                        'name': '財務健全性',
                        'description': '企業の財務的な安定性を評価',
                        'sub_items': [
                            {
                                'name': '負債比率',
                                'description': '総負債÷総資産で算出。財務レバレッジを評価',
                                'item_type': 'number',
                            },
                            {
                                'name': '財務リスク',
                                'description': '財務リスクの評価',
                                'item_type': 'select',
                                'choices': '低リスク,中リスク,高リスク'
                            }
                        ]
                    }
                ]
            }
        ]

        # テンプレートとサブ項目の作成
        for template_data in template_configs:
            # テンプレート作成
            template = AnalysisTemplate.objects.create(
                user=user,
                name=template_data['name'],
                description=template_data['description']
            )
            
            # サブ項目の順序管理
            order_counter = 1
            
            # カテゴリごとのサブ項目作成
            for category in template_data['items']:
                category_name = category['name']
                category_description = category['description']
                
                for item_data in category['sub_items']:
                    # 分析項目の作成
                    item = AnalysisItem.objects.create(
                        template=template,
                        name=f"{category_name} - {item_data['name']}",
                        description=item_data['description'],
                        item_type=item_data['item_type'],
                        order=order_counter,
                        choices=item_data.get('choices', ''),
                        value_label=item_data.get('value_label', '')
                    )
                    
                    order_counter += 1
            
            self.stdout.write(self.style.SUCCESS(f'テンプレート "{template.name}" を作成しました。'))
        
        # サンプルの株式日記を取得（存在しない場合は作成）
        stocks = [
            {"symbol": "7203", "name": "トヨタ自動車"},
            {"symbol": "6758", "name": "ソニーグループ"},
            {"symbol": "9984", "name": "ソフトバンクグループ"},
            {"symbol": "4063", "name": "信越化学工業"},
            {"symbol": "9433", "name": "KDDI"},
        ]
        
        # 分析値の作成
        for stock in stocks:
            try:
                # 既存の日記がない場合は作成
                diary, created = StockDiary.objects.get_or_create(
                    user=user,
                    stock_symbol=stock['symbol'],
                    stock_name=stock['name'],
                    defaults={
                        'purchase_date': '2023-01-01',
                        'purchase_price': Decimal(random.uniform(1000, 10000)).quantize(Decimal('0.01')),
                        'purchase_quantity': random.randint(10, 500),
                        'reason': f"{stock['name']}の投資分析"
                    }
                )
                
                # テンプレートを取得
                template = AnalysisTemplate.objects.first()
                
                # テンプレートの各項目に対してランダムな分析値を生成
                for item in template.items.all():
                    # 項目タイプに応じた値の生成
                    if item.item_type == 'number':
                        DiaryAnalysisValue.objects.create(
                            diary=diary,
                            analysis_item=item,
                            number_value=Decimal(random.uniform(1, 50)).quantize(Decimal('0.01'))
                        )
                    elif item.item_type == 'boolean':
                        DiaryAnalysisValue.objects.create(
                            diary=diary,
                            analysis_item=item,
                            boolean_value=random.choice([True, False])
                        )
                    elif item.item_type == 'boolean_with_value':
                        DiaryAnalysisValue.objects.create(
                            diary=diary,
                            analysis_item=item,
                            boolean_value=random.choice([True, False]),
                            number_value=Decimal(random.uniform(1, 10)).quantize(Decimal('0.01'))
                        )
                    elif item.item_type == 'select':
                        choices = item.get_choices_list()
                        DiaryAnalysisValue.objects.create(
                            diary=diary,
                            analysis_item=item,
                            text_value=random.choice(choices)
                        )
                
                self.stdout.write(self.style.SUCCESS(f'{stock["name"]} の分析データを作成しました。'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'{stock["name"]} のデータ作成中にエラー: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'合計 {template_count} 件のテンプレートと分析データを作成しました。'))