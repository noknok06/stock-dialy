# analysis_template/management/commands/load_metric_definitions.py
from django.core.management.base import BaseCommand
from analysis_template.models import MetricDefinition
from decimal import Decimal


class Command(BaseCommand):
    help = '指標定義の初期データをロードします'

    def handle(self, *args, **options):
        metrics = [
            # 収益性指標
            {
                'name': 'roe',
                'display_name': 'ROE（自己資本利益率）',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '株主資本に対する当期純利益の割合。株主資本の効率性を示す。',
                'unit': '%',
                'display_order': 10,
                'chart_suitable': True,
            },
            {
                'name': 'roa',
                'display_name': 'ROA（総資産利益率）',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '総資産に対する当期純利益の割合。企業全体の収益性を示す。',
                'unit': '%',
                'display_order': 20,
                'chart_suitable': True,
            },
            {
                'name': 'dividend_rate',  # ⭐ 追加
                'display_name': '配当金額',
                'metric_type': 'amount',
                'metric_group': 'dividend',
                'description': '1株あたりの年間配当金額。株主が受け取る配当の実額を示す。',
                'unit': '円',
                'display_order': 85,
                'chart_suitable': False,
            },
            {
                'name': 'operating_margin',
                'display_name': '営業利益率',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '売上高に対する営業利益の割合。本業の収益力を示す。',
                'unit': '%',
                'display_order': 30,
                'chart_suitable': True,
            },
            
            # 成長性指標
            {
                'name': 'revenue_growth',
                'display_name': '売上成長率',
                'metric_type': 'percentage',
                'metric_group': 'growth',
                'description': '前年比の売上高増加率。企業の成長スピードを示す。',
                'unit': '%',
                'display_order': 40,
                'chart_suitable': True,
            },
            {
                'name': 'profit_growth',
                'display_name': '利益成長率',
                'metric_type': 'percentage',
                'metric_group': 'growth',
                'description': '前年比の営業利益または純利益の増加率。',
                'unit': '%',
                'display_order': 50,
                'chart_suitable': True,
            },
            
            # バリュエーション指標
            {
                'name': 'per',
                'display_name': 'PER（株価収益率）',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': '株価を1株当たり利益で割った値。株価の割安度を示す。',
                'unit': '倍',
                'display_order': 60,
                'chart_suitable': True,
            },
            {
                'name': 'pbr',
                'display_name': 'PBR（株価純資産倍率）',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': '株価を1株当たり純資産で割った値。資産面からの割安度を示す。',
                'unit': '倍',
                'display_order': 70,
                'chart_suitable': True,
            },
            
            # 配当指標
            {
                'name': 'dividend_yield',
                'display_name': '配当利回り',
                'metric_type': 'percentage',
                'metric_group': 'dividend',
                'description': '株価に対する年間配当金の割合。インカムゲインの指標。',
                'unit': '%',
                'display_order': 80,
                'chart_suitable': True,
            },
            {
                'name': 'payout_ratio',
                'display_name': '配当性向',
                'metric_type': 'percentage',
                'metric_group': 'dividend',
                'description': '当期純利益に対する配当金の割合。',
                'unit': '%',
                'display_order': 90,
                'chart_suitable': False,
            },
            
            # 財務健全性指標
            {
                'name': 'equity_ratio',
                'display_name': '自己資本比率',
                'metric_type': 'percentage',
                'metric_group': 'financial_health',
                'description': '総資産に対する自己資本の割合。財務の安定性を示す。',
                'unit': '%',
                'display_order': 100,
                'chart_suitable': True,
            },
            {
                'name': 'debt_equity_ratio',
                'display_name': '負債比率',
                'metric_type': 'percentage',
                'metric_group': 'financial_health',
                'description': '自己資本に対する負債の割合。財務レバレッジを示す。',
                'unit': '%',
                'display_order': 110,
                'chart_suitable': False,
            },
            {
                'name': 'current_ratio',
                'display_name': '流動比率',
                'metric_type': 'percentage',
                'metric_group': 'financial_health',
                'description': '流動負債に対する流動資産の割合。短期的な支払能力を示す。',
                'unit': '%',
                'display_order': 120,
                'chart_suitable': False,
            },
            
            # 効率性指標
            {
                'name': 'asset_turnover',
                'display_name': '総資産回転率',
                'metric_type': 'ratio',
                'metric_group': 'efficiency',
                'description': '総資産に対する売上高の比率。資産の効率的な使用度を示す。',
                'unit': '回',
                'display_order': 130,
                'chart_suitable': False,
            },
            
            # 規模・実績指標
            {
                'name': 'market_cap',
                'display_name': '時価総額',
                'metric_type': 'amount',
                'metric_group': 'scale',
                'description': '発行済株式数×株価。企業の市場価値。',
                'unit': '億円',
                'display_order': 140,
                'chart_suitable': False,
            },
            {
                'name': 'revenue',
                'display_name': '売上高',
                'metric_type': 'amount',
                'metric_group': 'scale',
                'description': '年間の総売上高。',
                'unit': '億円',
                'display_order': 150,
                'chart_suitable': False,
            },
            {
                'name': 'operating_profit',
                'display_name': '営業利益',
                'metric_type': 'amount',
                'metric_group': 'scale',
                'description': '本業による利益。',
                'unit': '億円',
                'display_order': 160,
                'chart_suitable': False,
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
                    'display_order': metric_data['display_order'],
                    'chart_suitable': metric_data['chart_suitable'],
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ {metric.display_name} を作成しました")
                )
            else:
                updated_count += 1
                self.stdout.write(f"↻ {metric.display_name} を更新しました")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n完了: {created_count}件作成, {updated_count}件更新"
            )
        )