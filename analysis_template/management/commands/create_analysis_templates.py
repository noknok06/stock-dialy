# python manage.py create_analysis_templates --username naotaro --templates 3
# analysis_template/management/commands/create_analysis_templates.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from analysis_template.models import AnalysisTemplate, AnalysisItem
import random

User = get_user_model()

class Command(BaseCommand):
    help = "分析テンプレートのテストデータを作成します"

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='テストデータを作成するユーザー名')
        parser.add_argument('--templates', type=int, default=3, help='作成するテンプレート数 (デフォルト: 3)')

    def handle(self, *args, **options):
        username = options['username']
        template_count = options['templates']

        if not username:
            self.stdout.write(self.style.ERROR('ユーザー名が指定されていません。--username オプションを指定してください。'))
            return

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'ユーザー "{username}" が見つかりません。'))
            return

        self.stdout.write(f'{username} 用の分析テンプレートを {template_count} 件作成します...')

        # テンプレートデータ定義
        templates = [
            {
                'name': '基本財務分析テンプレート',
                'description': '企業の財務状態を評価するための基本的な分析項目を含むテンプレートです。',
                'items': [
                    {
                        'name': 'PER',
                        'description': '株価収益率（Price Earnings Ratio）。株価÷1株当たり利益で算出。',
                        'item_type': 'number',
                        'order': 1,
                    },
                    {
                        'name': 'PBR',
                        'description': '株価純資産倍率（Price Book-value Ratio）。株価÷1株当たり純資産で算出。',
                        'item_type': 'number',
                        'order': 2,
                    },
                    {
                        'name': 'ROE',
                        'description': '自己資本利益率（Return On Equity）。当期純利益÷自己資本で算出。',
                        'item_type': 'number',
                        'order': 3,
                    },
                    {
                        'name': '配当利回り',
                        'description': '年間配当金÷株価で算出される投資収益率。',
                        'item_type': 'number',
                        'order': 4,
                    },
                    {
                        'name': '成長性評価',
                        'description': '企業の成長性に対する評価。',
                        'item_type': 'select',
                        'order': 5,
                        'choices': '高い,普通,低い',
                    },
                    {
                        'name': '投資判断',
                        'description': 'この銘柄への投資判断。',
                        'item_type': 'select',
                        'order': 6,
                        'choices': '買い,様子見,売り',
                    }
                ]
            },
            {
                'name': 'グロース株評価テンプレート',
                'description': '成長株（グロース株）の評価に特化したテンプレートです。',
                'items': [
                    {
                        'name': '売上高成長率',
                        'description': '過去3年間の売上高の年平均成長率（％）',
                        'item_type': 'number',
                        'order': 1,
                    },
                    {
                        'name': '利益成長率',
                        'description': '過去3年間の純利益の年平均成長率（％）',
                        'item_type': 'number',
                        'order': 2,
                    },
                    {
                        'name': 'PSR',
                        'description': '株価売上高倍率（Price to Sales Ratio）。株価÷1株当たり売上高で算出。',
                        'item_type': 'number',
                        'order': 3,
                    },
                    {
                        'name': 'PER > 40',
                        'description': 'PERが40倍を超えているか',
                        'item_type': 'boolean_with_value',
                        'order': 4,
                        'value_label': '実際のPER',
                    },
                    {
                        'name': '市場シェア',
                        'description': '企業が属する市場におけるシェア評価',
                        'item_type': 'select',
                        'order': 5,
                        'choices': '独占的,高い,中程度,低い',
                    },
                    {
                        'name': '競争優位性',
                        'description': '企業の競争優位性の評価',
                        'item_type': 'text',
                        'order': 6,
                    },
                    {
                        'name': '今後3年間の予想',
                        'description': '今後3年間の成長見通し',
                        'item_type': 'select',
                        'order': 7,
                        'choices': '高成長継続,緩やかな成長,成長鈍化,成長停滞',
                    }
                ]
            },
            {
                'name': '高配当株スクリーニング',
                'description': '高配当株の選定に使用するスクリーニングテンプレートです。',
                'items': [
                    {
                        'name': '配当利回り',
                        'description': '年間配当金÷株価（％）',
                        'item_type': 'number',
                        'order': 1,
                    },
                    {
                        'name': '配当性向',
                        'description': '配当金総額÷当期純利益（％）',
                        'item_type': 'number',
                        'order': 2,
                    },
                    {
                        'name': '連続増配年数',
                        'description': '連続して配当を増加させている年数',
                        'item_type': 'number',
                        'order': 3,
                    },
                    {
                        'name': '配当利回り 3%超',
                        'description': '配当利回りが3%を超えているか',
                        'item_type': 'boolean_with_value',
                        'order': 4,
                        'value_label': '実際の配当利回り',
                    },
                    {
                        'name': '安定配当',
                        'description': '過去5年間で無配になったことがないか',
                        'item_type': 'boolean',
                        'order': 5,
                    },
                    {
                        'name': '財務健全性',
                        'description': '財務状態の健全性評価',
                        'item_type': 'select',
                        'order': 6,
                        'choices': '非常に健全,健全,やや懸念あり,問題あり',
                    },
                    {
                        'name': '配当の継続性予想',
                        'description': '今後も配当が継続・成長する可能性の評価',
                        'item_type': 'select',
                        'order': 7,
                        'choices': '非常に高い,高い,普通,低い',
                    }
                ]
            },
            {
                'name': '業界比較分析',
                'description': '同業他社との比較分析用テンプレートです。',
                'items': [
                    {
                        'name': '業界内PER順位',
                        'description': '業界内でのPERの順位（低いほど割安）',
                        'item_type': 'number',
                        'order': 1,
                    },
                    {
                        'name': '業界内ROE順位',
                        'description': '業界内でのROEの順位（高いほど収益性が高い）',
                        'item_type': 'number',
                        'order': 2,
                    },
                    {
                        'name': '売上高シェア',
                        'description': '業界内での売上高シェア（％）',
                        'item_type': 'number',
                        'order': 3,
                    },
                    {
                        'name': '利益率比較',
                        'description': '業界平均と比較した営業利益率の評価',
                        'item_type': 'select',
                        'order': 4,
                        'choices': '大幅に上回る,上回る,同程度,下回る,大幅に下回る',
                    },
                    {
                        'name': '成長率比較',
                        'description': '業界平均と比較した売上成長率の評価',
                        'item_type': 'select',
                        'order': 5,
                        'choices': '大幅に上回る,上回る,同程度,下回る,大幅に下回る',
                    },
                    {
                        'name': '競争優位性あり',
                        'description': '業界内で明確な競争優位性を持っているか',
                        'item_type': 'boolean_with_value',
                        'order': 6,
                        'value_label': '優位性の内容',
                    }
                ]
            },
            {
                'name': 'バリュー投資チェックリスト',
                'description': 'バリュー投資の観点からの銘柄評価用チェックリストです。',
                'items': [
                    {
                        'name': 'PER < 15',
                        'description': 'PERが15倍未満か（割安基準）',
                        'item_type': 'boolean_with_value',
                        'order': 1,
                        'value_label': '実際のPER',
                    },
                    {
                        'name': 'PBR < 1.0',
                        'description': 'PBRが1.0倍未満か（割安基準）',
                        'item_type': 'boolean_with_value',
                        'order': 2,
                        'value_label': '実際のPBR',
                    },
                    {
                        'name': 'ROE > 10%',
                        'description': 'ROEが10%を超えているか（収益性基準）',
                        'item_type': 'boolean_with_value',
                        'order': 3,
                        'value_label': '実際のROE',
                    },
                    {
                        'name': '負債比率',
                        'description': '総資産に対する負債の比率（％）',
                        'item_type': 'number',
                        'order': 4,
                    },
                    {
                        'name': 'FCF',
                        'description': 'フリーキャッシュフロー（億円）',
                        'item_type': 'number',
                        'order': 5,
                    },
                    {
                        'name': '業績の安定性',
                        'description': '過去5年間の業績の安定性評価',
                        'item_type': 'select',
                        'order': 6,
                        'choices': '非常に安定,安定,やや不安定,不安定',
                    },
                    {
                        'name': '株主還元姿勢',
                        'description': '株主還元（配当・自社株買い）に対する姿勢の評価',
                        'item_type': 'select',
                        'order': 7,
                        'choices': '積極的,普通,消極的',
                    },
                    {
                        'name': '市場での過小評価理由',
                        'description': '市場が企業を過小評価している理由（推測）',
                        'item_type': 'text',
                        'order': 8,
                    }
                ]
            }
        ]

        # テンプレート作成
        created_count = 0
        for i in range(min(template_count, len(templates))):
            template_data = templates[i]
            
            # テンプレート作成
            template = AnalysisTemplate.objects.create(
                user=user,
                name=template_data['name'],
                description=template_data['description']
            )
            
            # 分析項目作成
            for item_data in template_data['items']:
                AnalysisItem.objects.create(
                    template=template,
                    name=item_data['name'],
                    description=item_data['description'],
                    item_type=item_data['item_type'],
                    order=item_data['order'],
                    choices=item_data.get('choices', ''),
                    value_label=item_data.get('value_label', '')
                )
            
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f'テンプレート "{template.name}" を作成しました。'))
        
        self.stdout.write(self.style.SUCCESS(f'合計 {created_count} 件のテンプレートを作成しました。'))