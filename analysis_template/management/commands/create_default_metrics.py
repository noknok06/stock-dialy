# analysis_template/management/commands/create_default_metrics.py
from django.core.management.base import BaseCommand
from analysis_template.models import MetricDefinition


class Command(BaseCommand):
    help = 'デフォルトの指標定義を作成します'

    def handle(self, *args, **options):
        metrics = [
            # 収益性指標
            {
                'name': 'roe',
                'display_name': 'ROE',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '自己資本利益率。企業が株主資本をどれだけ効率的に利益に変えているかを示す指標',
                'unit': '%',
                'min_value': -100,
                'max_value': 100,
                'display_order': 1,
                'chart_suitable': True
            },
            {
                'name': 'roa',
                'display_name': 'ROA',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '総資産利益率。企業が保有する資産をどれだけ効率的に利益に変えているかを示す指標',
                'unit': '%',
                'min_value': -100,
                'max_value': 100,
                'display_order': 2,
                'chart_suitable': True
            },
            {
                'name': 'operating_margin',
                'display_name': '営業利益率',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '売上高に対する営業利益の割合',
                'unit': '%',
                'min_value': -100,
                'max_value': 100,
                'display_order': 3,
                'chart_suitable': True
            },
            {
                'name': 'net_margin',
                'display_name': '純利益率',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '売上高に対する純利益の割合',
                'unit': '%',
                'min_value': -100,
                'max_value': 100,
                'display_order': 4,
                'chart_suitable': True
            },
            
            # 成長性指標
            {
                'name': 'revenue_growth',
                'display_name': '売上成長率',
                'metric_type': 'percentage',
                'metric_group': 'growth',
                'description': '前年比の売上高成長率',
                'unit': '%',
                'min_value': -100,
                'max_value': 1000,
                'display_order': 5,
                'chart_suitable': True
            },
            {
                'name': 'profit_growth',
                'display_name': '利益成長率',
                'metric_type': 'percentage',
                'metric_group': 'growth',
                'description': '前年比の純利益成長率',
                'unit': '%',
                'min_value': -100,
                'max_value': 1000,
                'display_order': 6,
                'chart_suitable': True
            },
            {
                'name': 'eps_growth',
                'display_name': 'EPS成長率',
                'metric_type': 'percentage',
                'metric_group': 'growth',
                'description': '前年比の1株当たり利益成長率',
                'unit': '%',
                'min_value': -100,
                'max_value': 1000,
                'display_order': 7,
                'chart_suitable': True
            },
            
            # バリュエーション指標
            {
                'name': 'per',
                'display_name': 'PER',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': '株価収益率。株価が1株当たり利益の何倍かを示す',
                'unit': '倍',
                'min_value': 0,
                'max_value': 1000,
                'display_order': 8,
                'chart_suitable': True
            },
            {
                'name': 'pbr',
                'display_name': 'PBR',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': '株価純資産倍率。株価が1株当たり純資産の何倍かを示す',
                'unit': '倍',
                'min_value': 0,
                'max_value': 100,
                'display_order': 9,
                'chart_suitable': True
            },
            {
                'name': 'psr',
                'display_name': 'PSR',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': '株価売上高倍率。株価が1株当たり売上高の何倍かを示す',
                'unit': '倍',
                'min_value': 0,
                'max_value': 100,
                'display_order': 10,
                'chart_suitable': True
            },
            {
                'name': 'pcfr',
                'display_name': 'PCFR',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': '株価キャッシュフロー倍率',
                'unit': '倍',
                'min_value': 0,
                'max_value': 100,
                'display_order': 11,
                'chart_suitable': True
            },
            {
                'name': 'ev_ebitda',
                'display_name': 'EV/EBITDA',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': '企業価値がEBITDAの何倍かを示す',
                'unit': '倍',
                'min_value': 0,
                'max_value': 100,
                'display_order': 12,
                'chart_suitable': True
            },
            
            # 配当関連
            {
                'name': 'dividend_yield',
                'display_name': '配当利回り',
                'metric_type': 'percentage',
                'metric_group': 'dividend',
                'description': '株価に対する年間配当金の割合',
                'unit': '%',
                'min_value': 0,
                'max_value': 20,
                'display_order': 13,
                'chart_suitable': True
            },
            {
                'name': 'dividend_payout',
                'display_name': '配当性向',
                'metric_type': 'percentage',
                'metric_group': 'dividend',
                'description': '純利益に対する配当金の割合',
                'unit': '%',
                'min_value': 0,
                'max_value': 200,
                'display_order': 14,
                'chart_suitable': True
            },
            
            # 財務健全性
            {
                'name': 'equity_ratio',
                'display_name': '自己資本比率',
                'metric_type': 'percentage',
                'metric_group': 'financial_health',
                'description': '総資産に対する自己資本の割合',
                'unit': '%',
                'min_value': 0,
                'max_value': 100,
                'display_order': 15,
                'chart_suitable': True
            },
            {
                'name': 'debt_equity_ratio',
                'display_name': '負債比率',
                'metric_type': 'percentage',
                'metric_group': 'financial_health',
                'description': '自己資本に対する負債の割合',
                'unit': '%',
                'min_value': 0,
                'max_value': 1000,
                'display_order': 16,
                'chart_suitable': True
            },
            {
                'name': 'current_ratio',
                'display_name': '流動比率',
                'metric_type': 'percentage',
                'metric_group': 'financial_health',
                'description': '流動負債に対する流動資産の割合',
                'unit': '%',
                'min_value': 0,
                'max_value': 1000,
                'display_order': 17,
                'chart_suitable': True
            },
            
            # 効率性指標
            {
                'name': 'asset_turnover',
                'display_name': '総資産回転率',
                'metric_type': 'ratio',
                'metric_group': 'efficiency',
                'description': '総資産が1年間に何回転したかを示す',
                'unit': '回',
                'min_value': 0,
                'max_value': 10,
                'display_order': 18,
                'chart_suitable': True
            },
            {
                'name': 'inventory_turnover',
                'display_name': '棚卸資産回転率',
                'metric_type': 'ratio',
                'metric_group': 'efficiency',
                'description': '棚卸資産が1年間に何回転したかを示す',
                'unit': '回',
                'min_value': 0,
                'max_value': 100,
                'display_order': 19,
                'chart_suitable': True
            },
            
            # 規模・実績（チャート表示には不適切な場合が多い）
            {
                'name': 'market_cap',
                'display_name': '時価総額',
                'metric_type': 'amount',
                'metric_group': 'scale',
                'description': '発行済株式数×株価で算出される企業の市場価値',
                'unit': '億円',
                'min_value': 0,
                'display_order': 20,
                'chart_suitable': False  # 規模が異なりすぎるためチャート不適
            },
            {
                'name': 'revenue',
                'display_name': '売上高',
                'metric_type': 'amount',
                'metric_group': 'scale',
                'description': '年間の売上高',
                'unit': '億円',
                'min_value': 0,
                'display_order': 21,
                'chart_suitable': False
            },
            {
                'name': 'operating_profit',
                'display_name': '営業利益',
                'metric_type': 'amount',
                'metric_group': 'scale',
                'description': '年間の営業利益',
                'unit': '億円',
                'display_order': 22,
                'chart_suitable': False
            },
            {
                'name': 'net_income',
                'display_name': '純利益',
                'metric_type': 'amount',
                'metric_group': 'scale',
                'description': '年間の純利益',
                'unit': '億円',
                'display_order': 23,
                'chart_suitable': False
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for metric_data in metrics:
            metric, created = MetricDefinition.objects.update_or_create(
                name=metric_data['name'],
                defaults={
                    'display_name': metric_data['display_name'],
                    'metric_type': metric_data['metric_type'],
                    'metric_group': metric_data['metric_group'],
                    'description': metric_data['description'],
                    'unit': metric_data.get('unit', ''),
                    'min_value': metric_data.get('min_value'),
                    'max_value': metric_data.get('max_value'),
                    'display_order': metric_data['display_order'],
                    'chart_suitable': metric_data.get('chart_suitable', True),
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 作成: {metric.display_name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'→ 更新: {metric.display_name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n完了: {created_count}件作成, {updated_count}件更新'
            )
        )