# ========================================
# analysis_template/management/commands/load_benchmarks.py
# 初期ベンチマークデータを投入するコマンド
# ========================================
from django.core.management.base import BaseCommand
from analysis_template.models import MetricDefinition, IndustryBenchmark


class Command(BaseCommand):
    help = '業種別ベンチマークの初期データを投入'

    def handle(self, *args, **options):
        # サンプル業種データ
        industries = [
            {'code': '16', 'name': '輸送用機器'},
            {'code': '15', 'name': '電気機器'},
            {'code': '12', 'name': '情報・通信業'},
            {'code': '20', 'name': '銀行業'},
            {'code': '14', 'name': '医薬品'},
        ]
        
        # サンプルベンチマークデータ
        benchmarks_data = {
            '16': {  # 輸送用機器
                'roe': {'avg': 10.5, 'excellent': 15, 'poor': 5, 'upper': 13, 'lower': 8},
                'roa': {'avg': 4.2, 'excellent': 6, 'poor': 2, 'upper': 5, 'lower': 3},
                'operating_margin': {'avg': 7.5, 'excellent': 10, 'poor': 3, 'upper': 9, 'lower': 5},
                'per': {'avg': 12.0, 'excellent': 8, 'poor': 20, 'upper': 10, 'lower': 15},
                'pbr': {'avg': 1.2, 'excellent': 2, 'poor': 0.8, 'upper': 1.5, 'lower': 1.0},
            },
            '15': {  # 電気機器
                'roe': {'avg': 12.0, 'excellent': 18, 'poor': 6, 'upper': 15, 'lower': 9},
                'roa': {'avg': 5.5, 'excellent': 8, 'poor': 2, 'upper': 7, 'lower': 4},
                'operating_margin': {'avg': 9.0, 'excellent': 12, 'poor': 4, 'upper': 11, 'lower': 6},
                'per': {'avg': 16.0, 'excellent': 10, 'poor': 25, 'upper': 13, 'lower': 20},
                'pbr': {'avg': 1.8, 'excellent': 2.5, 'poor': 1.0, 'upper': 2.2, 'lower': 1.4},
            },
            '12': {  # 情報・通信業
                'roe': {'avg': 11.5, 'excellent': 17, 'poor': 5, 'upper': 14, 'lower': 8},
                'roa': {'avg': 6.0, 'excellent': 9, 'poor': 3, 'upper': 7.5, 'lower': 4.5},
                'operating_margin': {'avg': 12.0, 'excellent': 18, 'poor': 5, 'upper': 15, 'lower': 8},
                'per': {'avg': 20.0, 'excellent': 12, 'poor': 30, 'upper': 15, 'lower': 25},
                'pbr': {'avg': 2.0, 'excellent': 3, 'poor': 1.0, 'upper': 2.5, 'lower': 1.5},
            },
            '20': {  # 銀行業
                'roe': {'avg': 8.0, 'excellent': 12, 'poor': 4, 'upper': 10, 'lower': 6},
                'roa': {'avg': 0.5, 'excellent': 0.8, 'poor': 0.2, 'upper': 0.65, 'lower': 0.35},
                'operating_margin': {'avg': 25.0, 'excellent': 35, 'poor': 15, 'upper': 30, 'lower': 20},
                'per': {'avg': 10.0, 'excellent': 7, 'poor': 15, 'upper': 8, 'lower': 12},
                'pbr': {'avg': 0.6, 'excellent': 1.0, 'poor': 0.4, 'upper': 0.8, 'lower': 0.5},
            },
            '14': {  # 医薬品
                'roe': {'avg': 10.0, 'excellent': 15, 'poor': 5, 'upper': 12, 'lower': 7},
                'roa': {'avg': 5.0, 'excellent': 8, 'poor': 2, 'upper': 6.5, 'lower': 3.5},
                'operating_margin': {'avg': 15.0, 'excellent': 25, 'poor': 8, 'upper': 20, 'lower': 10},
                'per': {'avg': 20.0, 'excellent': 12, 'poor': 30, 'upper': 15, 'lower': 25},
                'pbr': {'avg': 2.0, 'excellent': 3, 'poor': 1.0, 'upper': 2.5, 'lower': 1.5},
            },
        }
        
        fiscal_year = "2024"
        
        for industry in industries:
            industry_code = industry['code']
            industry_name = industry['name']
            
            if industry_code not in benchmarks_data:
                continue
            
            for metric_name, values in benchmarks_data[industry_code].items():
                try:
                    metric_def = MetricDefinition.objects.get(name=metric_name)
                    
                    IndustryBenchmark.objects.update_or_create(
                        industry_code=industry_code,
                        metric_definition=metric_def,
                        fiscal_year=fiscal_year,
                        defaults={
                            'industry_name': industry_name,
                            'average_value': values['avg'],
                            'excellent_threshold': values['excellent'],
                            'poor_threshold': values['poor'],
                            'upper_quartile': values['upper'],
                            'lower_quartile': values['lower'],
                        }
                    )
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ {industry_name} - {metric_def.display_name}'
                        )
                    )
                except MetricDefinition.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠ 指標定義が見つかりません: {metric_name}'
                        )
                    )
        
        self.stdout.write(self.style.SUCCESS('\n✓ ベンチマークデータの投入が完了しました'))
