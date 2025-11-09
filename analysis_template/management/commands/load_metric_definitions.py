# analysis_template/management/commands/create_metric_definitions.py
from django.core.management.base import BaseCommand
from analysis_template.models import MetricDefinition


class Command(BaseCommand):
    help = 'Yahoo Finance APIから取得可能な指標定義を作成'

    def handle(self, *args, **options):
        metrics = [
            # 収益性指標
            {
                'name': 'roe',
                'display_name': 'ROE（自己資本利益率）',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': 'Return on Equity - 自己資本に対する当期純利益の割合',
                'display_order': 1,
                'chart_suitable': True,
            },
            {
                'name': 'roa',
                'display_name': 'ROA（総資産利益率）',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': 'Return on Assets - 総資産に対する当期純利益の割合',
                'display_order': 2,
                'chart_suitable': True,
            },
            {
                'name': 'operating_margin',
                'display_name': '営業利益率',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '売上高に対する営業利益の割合',
                'display_order': 3,
                'chart_suitable': True,
            },
            {
                'name': 'profit_margin',
                'display_name': '純利益率',
                'metric_type': 'percentage',
                'metric_group': 'profitability',
                'description': '売上高に対する純利益の割合',
                'display_order': 4,
                'chart_suitable': True,
            },
            
            # バリュエーション指標
            {
                'name': 'per',
                'display_name': 'PER（株価収益率）',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': 'Price Earnings Ratio - 株価が1株当たり純利益の何倍か',
                'display_order': 10,
                'chart_suitable': True,
            },
            {
                'name': 'forward_per',
                'display_name': '予想PER',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': '予想利益ベースのPER',
                'display_order': 11,
                'chart_suitable': False,
            },
            {
                'name': 'pbr',
                'display_name': 'PBR（株価純資産倍率）',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': 'Price Book-value Ratio - 株価が1株当たり純資産の何倍か',
                'display_order': 12,
                'chart_suitable': True,
            },
            {
                'name': 'psr',
                'display_name': 'PSR（株価売上高倍率）',
                'metric_type': 'ratio',
                'metric_group': 'valuation',
                'description': 'Price to Sales Ratio - 株価が1株当たり売上高の何倍か',
                'display_order': 13,
                'chart_suitable': False,
            },
            
            # 配当指標
            {
                'name': 'dividend_yield',
                'display_name': '配当利回り',
                'metric_type': 'percentage',
                'metric_group': 'dividend',
                'description': '株価に対する年間配当金の割合',
                'display_order': 20,
                'chart_suitable': True,
            },
            {
                'name': 'dividend_rate',
                'display_name': '配当額',
                'metric_type': 'amount',
                'metric_group': 'dividend',
                'unit': '円',
                'description': '1株当たりの年間配当金',
                'display_order': 21,
                'chart_suitable': False,
            },
            {
                'name': 'payout_ratio',
                'display_name': '配当性向',
                'metric_type': 'percentage',
                'metric_group': 'dividend',
                'description': '純利益に対する配当金の割合',
                'display_order': 22,
                'chart_suitable': True,
            },
            
            # 財務健全性指標
            {
                'name': 'equity_ratio',
                'display_name': '自己資本比率',
                'metric_type': 'percentage',
                'metric_group': 'financial_health',
                'description': '総資産に対する自己資本の割合',
                'display_order': 30,
                'chart_suitable': True,
            },
            {
                'name': 'debt_equity_ratio',
                'display_name': '負債比率',
                'metric_type': 'percentage',
                'metric_group': 'financial_health',
                'description': '自己資本に対する負債の割合',
                'display_order': 31,
                'chart_suitable': True,
            },
            {
                'name': 'current_ratio',
                'display_name': '流動比率',
                'metric_type': 'percentage',
                'metric_group': 'financial_health',
                'description': '流動負債に対する流動資産の割合',
                'display_order': 32,
                'chart_suitable': False,
            },
            {
                'name': 'quick_ratio',
                'display_name': '当座比率',
                'metric_type': 'percentage',
                'metric_group': 'financial_health',
                'description': '流動負債に対する当座資産の割合',
                'display_order': 33,
                'chart_suitable': False,
            },
            
            # 成長性指標
            {
                'name': 'revenue_growth',
                'display_name': '売上成長率',
                'metric_type': 'percentage',
                'metric_group': 'growth',
                'description': '前年比の売上高成長率',
                'display_order': 40,
                'chart_suitable': True,
            },
            {
                'name': 'earnings_growth',
                'display_name': '利益成長率',
                'metric_type': 'percentage',
                'metric_group': 'growth',
                'description': '前年比の利益成長率',
                'display_order': 41,
                'chart_suitable': True,
            },
            
            # 規模・実績指標
            {
                'name': 'market_cap',
                'display_name': '時価総額',
                'metric_type': 'amount',
                'metric_group': 'scale',
                'description': '発行済株式総数 × 株価',
                'display_order': 50,
                'chart_suitable': False,
            },
            {
                'name': 'revenue',
                'display_name': '売上高',
                'metric_type': 'amount',
                'metric_group': 'scale',
                'description': '年間の総売上高',
                'display_order': 51,
                'chart_suitable': False,
            },
            {
                'name': 'total_assets',
                'display_name': '総資産',
                'metric_type': 'amount',
                'metric_group': 'scale',
                'description': '貸借対照表の総資産',
                'display_order': 52,
                'chart_suitable': False,
            },
            {
                'name': 'eps',
                'display_name': 'EPS（1株利益）',
                'metric_type': 'amount',
                'unit': '円',
                'metric_group': 'scale',
                'description': '1株当たり純利益',
                'display_order': 53,
                'chart_suitable': False,
            },
            {
                'name': 'forward_eps',
                'display_name': '予想EPS',
                'metric_type': 'amount',
                'unit': '円',
                'metric_group': 'scale',
                'description': '予想の1株当たり純利益',
                'display_order': 54,
                'chart_suitable': False,
            },
            {
                'name': 'beta',
                'display_name': 'ベータ値',
                'metric_type': 'ratio',
                'metric_group': 'scale',
                'description': '市場全体に対する株価の感応度',
                'display_order': 55,
                'chart_suitable': False,
            },
            
            # 効率性指標
            {
                'name': 'asset_turnover',
                'display_name': '総資産回転率',
                'metric_type': 'ratio',
                'metric_group': 'efficiency',
                'description': '総資産に対する売上高の比率',
                'display_order': 60,
                'chart_suitable': True,
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for metric_data in metrics:
            metric, created = MetricDefinition.objects.update_or_create(
                name=metric_data['name'],
                defaults=metric_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'作成: {metric.display_name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'更新: {metric.display_name}'))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n完了: {created_count}件作成、{updated_count}件更新'
        ))