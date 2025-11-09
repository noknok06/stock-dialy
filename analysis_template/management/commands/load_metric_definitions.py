# ========================================
# analysis_template/management/commands/load_metric_definitions.py
# 初期指標定義を投入するコマンド
# ========================================
from django.core.management.base import BaseCommand
from analysis_template.models import MetricDefinition


class Command(BaseCommand):
    help = '指標定義の初期データを投入'

    def handle(self, *args, **options):
        metrics = [
            # 収益性
            {
                'name': 'roe',
                'display_name': 'ROE（自己資本利益率）',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '株主資本に対してどれだけ利益を上げているかを示す指標',
                'unit': '%',
                'display_order': 1,
            },
            {
                'name': 'roa',
                'display_name': 'ROA（総資産利益率）',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '総資産に対してどれだけ利益を上げているかを示す指標',
                'unit': '%',
                'display_order': 2,
            },
            {
                'name': 'operating_margin',
                'display_name': '営業利益率',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '売上高に対する営業利益の割合',
                'unit': '%',
                'display_order': 3,
            },
            {
                'name': 'net_margin',
                'display_name': '純利益率',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '売上高に対する純利益の割合',
                'unit': '%',
                'display_order': 4,
            },
            # 成長性
            {
                'name': 'revenue_growth',
                'display_name': '売上高成長率',
                'metric_type': 'percentage',
                'metric_group': 'growth',
                'description': '前年比の売上高成長率',
                'unit': '%',
                'display_order': 11,
            },
            {
                'name': 'profit_growth',
                'display_name': '利益成長率',
                'metric_type': 'percentage',
                'metric_group': 'growth',
                'description': '前年比の利益成長率',
                'unit': '%',
                'display_order': 12,
            },
            # バリュエーション
            {
                'name': 'per',
                'display_name': 'PER（株価収益率）',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': '株価が1株あたり純利益の何倍かを示す指標',
                'unit': '倍',
                'display_order': 21,
            },
            {
                'name': 'pbr',
                'display_name': 'PBR（株価純資産倍率）',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': '株価が1株あたり純資産の何倍かを示す指標',
                'unit': '倍',
                'display_order': 22,
            },
            # 配当
            {
                'name': 'dividend_yield',
                'display_name': '配当利回り',
                'metric_type': 'percentage',
                'metric_group': 'dividend',
                'description': '株価に対する年間配当金の割合',
                'unit': '%',
                'display_order': 31,
            },
            # 財務健全性
            {
                'name': 'equity_ratio',
                'display_name': '自己資本比率',
                'metric_type': 'percentage',
                'metric_group': 'financial_health',
                'description': '総資産に対する自己資本の割合',
                'unit': '%',
                'display_order': 41,
            },
            {
                'name': 'debt_equity_ratio',
                'display_name': '負債比率',
                'metric_type': 'percentage',
                'metric_group': 'financial_health',
                'description': '自己資本に対する負債の割合',
                'unit': '%',
                'display_order': 42,
            },
            # 規模
            {
                'name': 'market_cap',
                'display_name': '時価総額',
                'metric_type': 'amount',
                'metric_group': 'scale',
                'description': '発行済株式数×株価で算出される企業価値',
                'unit': '億円',
                'display_order': 51,
                'chart_suitable': False,
            },
        ]
        
        for metric_data in metrics:
            metric, created = MetricDefinition.objects.update_or_create(
                name=metric_data['name'],
                defaults=metric_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 作成: {metric.display_name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠ 更新: {metric.display_name}')
                )
        
        self.stdout.write(self.style.SUCCESS('\n✓ 指標定義の投入が完了しました'))