# analysis_template/management/commands/load_industry_benchmarks.py
from django.core.management.base import BaseCommand
from analysis_template.models import MetricDefinition, IndustryBenchmark
from decimal import Decimal


class Command(BaseCommand):
    help = '業種別ベンチマークデータをロードします（33業種）'

    def handle(self, *args, **options):
        """
        業種別ベンチマークデータ
        
        データソース参考:
        - 日本取引所グループ (JPX) 統計データ
        - 東洋経済 業種別財務データ
        - 各業種の一般的な特性に基づく推定値
        
        注意: 実際の投資判断には最新の公式データをご利用ください
        """
        
        benchmark_data = [
            # 高収益・高成長業種
            {
                'industry_code': '3250',
                'industry_name': '医薬品',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 10.5, 'excellent': 18.0, 'poor': 4.0, 'upper': 14.0, 'lower': 6.0},
                    'roa': {'avg': 6.2, 'excellent': 12.0, 'poor': 2.0, 'upper': 9.0, 'lower': 3.5},
                    'operating_margin': {'avg': 12.5, 'excellent': 20.0, 'poor': 5.0, 'upper': 16.0, 'lower': 8.0},
                    'per': {'avg': 20.5, 'excellent': 14.0, 'poor': 32.0, 'upper': 17.0, 'lower': 25.0},
                    'pbr': {'avg': 2.0, 'excellent': 1.2, 'poor': 3.2, 'upper': 1.5, 'lower': 2.6},
                    'equity_ratio': {'avg': 55.0, 'excellent': 70.0, 'poor': 40.0, 'upper': 65.0, 'lower': 45.0},
                    'dividend_yield': {'avg': 1.9, 'excellent': 3.2, 'poor': 0.5, 'upper': 2.6, 'lower': 1.2},
                    'revenue_growth': {'avg': 4.5, 'excellent': 12.0, 'poor': -3.0, 'upper': 8.0, 'lower': 1.0},
                    'profit_growth': {'avg': 7.0, 'excellent': 18.0, 'poor': -5.0, 'upper': 12.0, 'lower': 2.0},
                }
            },
            {
                'industry_code': '5250',
                'industry_name': '情報・通信業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 11.2, 'excellent': 18.0, 'poor': 5.0, 'upper': 15.0, 'lower': 7.0},
                    'roa': {'avg': 6.8, 'excellent': 12.0, 'poor': 2.0, 'upper': 9.0, 'lower': 4.0},
                    'operating_margin': {'avg': 9.5, 'excellent': 15.0, 'poor': 3.0, 'upper': 12.0, 'lower': 6.0},
                    'per': {'avg': 18.5, 'excellent': 12.0, 'poor': 30.0, 'upper': 15.0, 'lower': 22.0},
                    'pbr': {'avg': 2.1, 'excellent': 1.2, 'poor': 3.5, 'upper': 1.6, 'lower': 2.8},
                    'equity_ratio': {'avg': 52.0, 'excellent': 65.0, 'poor': 35.0, 'upper': 60.0, 'lower': 42.0},
                    'dividend_yield': {'avg': 1.8, 'excellent': 3.0, 'poor': 0.3, 'upper': 2.5, 'lower': 1.2},
                    'revenue_growth': {'avg': 8.0, 'excellent': 20.0, 'poor': -2.0, 'upper': 15.0, 'lower': 3.0},
                    'profit_growth': {'avg': 12.0, 'excellent': 25.0, 'poor': -5.0, 'upper': 18.0, 'lower': 5.0},
                }
            },
            {
                'industry_code': '9050',
                'industry_name': 'サービス業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 9.8, 'excellent': 16.0, 'poor': 4.0, 'upper': 13.0, 'lower': 6.0},
                    'roa': {'avg': 5.5, 'excellent': 10.0, 'poor': 1.5, 'upper': 7.5, 'lower': 3.0},
                    'operating_margin': {'avg': 7.8, 'excellent': 13.0, 'poor': 2.5, 'upper': 10.0, 'lower': 5.0},
                    'per': {'avg': 17.2, 'excellent': 11.0, 'poor': 28.0, 'upper': 14.0, 'lower': 21.0},
                    'pbr': {'avg': 1.8, 'excellent': 1.0, 'poor': 2.8, 'upper': 1.3, 'lower': 2.3},
                    'equity_ratio': {'avg': 48.0, 'excellent': 62.0, 'poor': 32.0, 'upper': 56.0, 'lower': 38.0},
                    'dividend_yield': {'avg': 2.0, 'excellent': 3.3, 'poor': 0.5, 'upper': 2.7, 'lower': 1.3},
                    'revenue_growth': {'avg': 6.5, 'excellent': 16.0, 'poor': -3.0, 'upper': 11.0, 'lower': 2.0},
                    'profit_growth': {'avg': 9.0, 'excellent': 20.0, 'poor': -6.0, 'upper': 14.0, 'lower': 3.0},
                }
            },
            
            # 金融業種
            {
                'industry_code': '7050',
                'industry_name': '銀行業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 7.5, 'excellent': 12.0, 'poor': 3.0, 'upper': 10.0, 'lower': 5.0},
                    'roa': {'avg': 0.4, 'excellent': 0.8, 'poor': 0.1, 'upper': 0.6, 'lower': 0.2},
                    'operating_margin': {'avg': 45.0, 'excellent': 60.0, 'poor': 30.0, 'upper': 55.0, 'lower': 38.0},
                    'per': {'avg': 10.8, 'excellent': 7.0, 'poor': 18.0, 'upper': 8.5, 'lower': 13.0},
                    'pbr': {'avg': 0.6, 'excellent': 0.4, 'poor': 1.0, 'upper': 0.5, 'lower': 0.8},
                    'equity_ratio': {'avg': 5.5, 'excellent': 8.0, 'poor': 3.5, 'upper': 7.0, 'lower': 4.0},
                    'dividend_yield': {'avg': 3.5, 'excellent': 5.0, 'poor': 1.5, 'upper': 4.3, 'lower': 2.5},
                    'revenue_growth': {'avg': 2.0, 'excellent': 8.0, 'poor': -4.0, 'upper': 5.0, 'lower': -1.0},
                    'profit_growth': {'avg': 3.5, 'excellent': 12.0, 'poor': -8.0, 'upper': 7.0, 'lower': 0.0},
                }
            },
            {
                'industry_code': '7150',
                'industry_name': '保険業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 8.2, 'excellent': 13.0, 'poor': 4.0, 'upper': 11.0, 'lower': 5.5},
                    'roa': {'avg': 0.6, 'excellent': 1.2, 'poor': 0.2, 'upper': 0.9, 'lower': 0.3},
                    'operating_margin': {'avg': 15.0, 'excellent': 25.0, 'poor': 8.0, 'upper': 20.0, 'lower': 11.0},
                    'per': {'avg': 11.5, 'excellent': 8.0, 'poor': 18.0, 'upper': 9.5, 'lower': 14.0},
                    'pbr': {'avg': 0.9, 'excellent': 0.6, 'poor': 1.4, 'upper': 0.7, 'lower': 1.1},
                    'equity_ratio': {'avg': 8.0, 'excellent': 12.0, 'poor': 5.0, 'upper': 10.0, 'lower': 6.0},
                    'dividend_yield': {'avg': 3.2, 'excellent': 4.8, 'poor': 1.2, 'upper': 4.0, 'lower': 2.2},
                    'revenue_growth': {'avg': 3.0, 'excellent': 10.0, 'poor': -3.0, 'upper': 6.5, 'lower': 0.0},
                    'profit_growth': {'avg': 5.0, 'excellent': 15.0, 'poor': -6.0, 'upper': 10.0, 'lower': 1.0},
                }
            },
            {
                'industry_code': '7100',
                'industry_name': '証券、商品先物取引業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 6.5, 'excellent': 12.0, 'poor': 2.0, 'upper': 9.5, 'lower': 3.5},
                    'roa': {'avg': 1.2, 'excellent': 2.5, 'poor': 0.3, 'upper': 1.9, 'lower': 0.6},
                    'operating_margin': {'avg': 25.0, 'excellent': 40.0, 'poor': 12.0, 'upper': 33.0, 'lower': 17.0},
                    'per': {'avg': 14.5, 'excellent': 9.0, 'poor': 24.0, 'upper': 11.5, 'lower': 18.0},
                    'pbr': {'avg': 0.8, 'excellent': 0.5, 'poor': 1.3, 'upper': 0.6, 'lower': 1.0},
                    'equity_ratio': {'avg': 18.0, 'excellent': 28.0, 'poor': 10.0, 'upper': 24.0, 'lower': 13.0},
                    'dividend_yield': {'avg': 2.8, 'excellent': 4.5, 'poor': 0.8, 'upper': 3.7, 'lower': 1.8},
                    'revenue_growth': {'avg': 5.0, 'excellent': 18.0, 'poor': -8.0, 'upper': 12.0, 'lower': -1.0},
                    'profit_growth': {'avg': 8.0, 'excellent': 25.0, 'poor': -15.0, 'upper': 16.0, 'lower': 0.0},
                }
            },
            {
                'industry_code': '7200',
                'industry_name': 'その他金融業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 8.0, 'excellent': 14.0, 'poor': 3.0, 'upper': 11.5, 'lower': 4.5},
                    'roa': {'avg': 2.8, 'excellent': 5.5, 'poor': 0.8, 'upper': 4.2, 'lower': 1.5},
                    'operating_margin': {'avg': 35.0, 'excellent': 50.0, 'poor': 20.0, 'upper': 43.0, 'lower': 27.0},
                    'per': {'avg': 12.8, 'excellent': 8.5, 'poor': 20.0, 'upper': 10.5, 'lower': 16.0},
                    'pbr': {'avg': 1.0, 'excellent': 0.6, 'poor': 1.6, 'upper': 0.8, 'lower': 1.3},
                    'equity_ratio': {'avg': 25.0, 'excellent': 38.0, 'poor': 15.0, 'upper': 32.0, 'lower': 18.0},
                    'dividend_yield': {'avg': 2.5, 'excellent': 4.0, 'poor': 0.8, 'upper': 3.3, 'lower': 1.5},
                    'revenue_growth': {'avg': 4.5, 'excellent': 14.0, 'poor': -5.0, 'upper': 9.5, 'lower': 0.5},
                    'profit_growth': {'avg': 7.0, 'excellent': 18.0, 'poor': -8.0, 'upper': 12.5, 'lower': 1.5},
                }
            },
            
            # 製造業（高付加価値）
            {
                'industry_code': '3650',
                'industry_name': '電気機器',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 8.5, 'excellent': 15.0, 'poor': 3.0, 'upper': 12.0, 'lower': 5.0},
                    'roa': {'avg': 4.2, 'excellent': 8.0, 'poor': 1.0, 'upper': 6.0, 'lower': 2.5},
                    'operating_margin': {'avg': 6.8, 'excellent': 12.0, 'poor': 2.0, 'upper': 10.0, 'lower': 4.0},
                    'per': {'avg': 15.2, 'excellent': 10.0, 'poor': 25.0, 'upper': 12.0, 'lower': 18.0},
                    'pbr': {'avg': 1.3, 'excellent': 0.8, 'poor': 2.0, 'upper': 1.0, 'lower': 1.6},
                    'equity_ratio': {'avg': 45.0, 'excellent': 60.0, 'poor': 30.0, 'upper': 55.0, 'lower': 35.0},
                    'dividend_yield': {'avg': 2.1, 'excellent': 3.5, 'poor': 0.5, 'upper': 2.8, 'lower': 1.5},
                    'revenue_growth': {'avg': 5.0, 'excellent': 15.0, 'poor': -5.0, 'upper': 10.0, 'lower': 0.0},
                    'profit_growth': {'avg': 8.0, 'excellent': 20.0, 'poor': -10.0, 'upper': 15.0, 'lower': 2.0},
                }
            },
            {
                'industry_code': '3750',
                'industry_name': '精密機器',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 9.2, 'excellent': 16.0, 'poor': 3.5, 'upper': 13.0, 'lower': 5.5},
                    'roa': {'avg': 5.0, 'excellent': 9.5, 'poor': 1.5, 'upper': 7.0, 'lower': 3.0},
                    'operating_margin': {'avg': 8.5, 'excellent': 14.0, 'poor': 3.0, 'upper': 11.5, 'lower': 5.0},
                    'per': {'avg': 16.8, 'excellent': 11.0, 'poor': 26.0, 'upper': 13.5, 'lower': 20.0},
                    'pbr': {'avg': 1.5, 'excellent': 0.9, 'poor': 2.3, 'upper': 1.1, 'lower': 1.9},
                    'equity_ratio': {'avg': 50.0, 'excellent': 65.0, 'poor': 35.0, 'upper': 58.0, 'lower': 40.0},
                    'dividend_yield': {'avg': 1.9, 'excellent': 3.2, 'poor': 0.4, 'upper': 2.6, 'lower': 1.2},
                    'revenue_growth': {'avg': 6.0, 'excellent': 16.0, 'poor': -4.0, 'upper': 11.0, 'lower': 1.5},
                    'profit_growth': {'avg': 9.5, 'excellent': 22.0, 'poor': -8.0, 'upper': 16.0, 'lower': 3.0},
                }
            },
            {
                'industry_code': '3600',
                'industry_name': '機械',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 8.8, 'excellent': 15.0, 'poor': 3.0, 'upper': 12.0, 'lower': 5.0},
                    'roa': {'avg': 4.5, 'excellent': 8.5, 'poor': 1.2, 'upper': 6.5, 'lower': 2.8},
                    'operating_margin': {'avg': 7.2, 'excellent': 12.5, 'poor': 2.5, 'upper': 10.0, 'lower': 4.5},
                    'per': {'avg': 14.5, 'excellent': 9.5, 'poor': 23.0, 'upper': 11.5, 'lower': 17.5},
                    'pbr': {'avg': 1.2, 'excellent': 0.7, 'poor': 1.9, 'upper': 0.9, 'lower': 1.5},
                    'equity_ratio': {'avg': 43.0, 'excellent': 58.0, 'poor': 28.0, 'upper': 52.0, 'lower': 33.0},
                    'dividend_yield': {'avg': 2.2, 'excellent': 3.6, 'poor': 0.6, 'upper': 2.9, 'lower': 1.5},
                    'revenue_growth': {'avg': 4.8, 'excellent': 14.0, 'poor': -6.0, 'upper': 9.5, 'lower': 0.5},
                    'profit_growth': {'avg': 7.5, 'excellent': 19.0, 'poor': -10.0, 'upper': 13.5, 'lower': 2.0},
                }
            },
            {
                'industry_code': '3700',
                'industry_name': '輸送用機器',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 7.8, 'excellent': 14.0, 'poor': 2.5, 'upper': 11.0, 'lower': 4.5},
                    'roa': {'avg': 3.8, 'excellent': 7.5, 'poor': 0.8, 'upper': 5.5, 'lower': 2.0},
                    'operating_margin': {'avg': 5.5, 'excellent': 10.0, 'poor': 1.5, 'upper': 8.0, 'lower': 3.0},
                    'per': {'avg': 12.5, 'excellent': 8.0, 'poor': 20.0, 'upper': 10.0, 'lower': 15.5},
                    'pbr': {'avg': 0.9, 'excellent': 0.6, 'poor': 1.4, 'upper': 0.7, 'lower': 1.1},
                    'equity_ratio': {'avg': 38.0, 'excellent': 52.0, 'poor': 25.0, 'upper': 46.0, 'lower': 30.0},
                    'dividend_yield': {'avg': 2.8, 'excellent': 4.2, 'poor': 0.8, 'upper': 3.5, 'lower': 1.8},
                    'revenue_growth': {'avg': 3.5, 'excellent': 12.0, 'poor': -7.0, 'upper': 8.0, 'lower': -0.5},
                    'profit_growth': {'avg': 6.0, 'excellent': 18.0, 'poor': -12.0, 'upper': 12.0, 'lower': 0.5},
                }
            },
            
            # 製造業（素材）
            {
                'industry_code': '3200',
                'industry_name': '化学',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 7.5, 'excellent': 13.0, 'poor': 2.5, 'upper': 10.5, 'lower': 4.5},
                    'roa': {'avg': 4.0, 'excellent': 7.5, 'poor': 1.0, 'upper': 5.8, 'lower': 2.3},
                    'operating_margin': {'avg': 8.0, 'excellent': 13.5, 'poor': 3.0, 'upper': 11.0, 'lower': 5.0},
                    'per': {'avg': 13.8, 'excellent': 9.0, 'poor': 22.0, 'upper': 11.0, 'lower': 17.0},
                    'pbr': {'avg': 1.0, 'excellent': 0.6, 'poor': 1.6, 'upper': 0.8, 'lower': 1.3},
                    'equity_ratio': {'avg': 48.0, 'excellent': 62.0, 'poor': 32.0, 'upper': 56.0, 'lower': 38.0},
                    'dividend_yield': {'avg': 2.3, 'excellent': 3.8, 'poor': 0.7, 'upper': 3.1, 'lower': 1.5},
                    'revenue_growth': {'avg': 4.0, 'excellent': 12.0, 'poor': -5.0, 'upper': 8.5, 'lower': 0.0},
                    'profit_growth': {'avg': 6.5, 'excellent': 17.0, 'poor': -9.0, 'upper': 12.0, 'lower': 1.5},
                }
            },
            {
                'industry_code': '3450',
                'industry_name': '鉄鋼',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 6.2, 'excellent': 11.0, 'poor': 1.5, 'upper': 9.0, 'lower': 3.5},
                    'roa': {'avg': 3.0, 'excellent': 6.0, 'poor': 0.5, 'upper': 4.5, 'lower': 1.5},
                    'operating_margin': {'avg': 4.8, 'excellent': 9.0, 'poor': 1.0, 'upper': 7.0, 'lower': 2.5},
                    'per': {'avg': 11.5, 'excellent': 7.5, 'poor': 18.0, 'upper': 9.0, 'lower': 14.5},
                    'pbr': {'avg': 0.7, 'excellent': 0.4, 'poor': 1.1, 'upper': 0.5, 'lower': 0.9},
                    'equity_ratio': {'avg': 35.0, 'excellent': 48.0, 'poor': 22.0, 'upper': 42.0, 'lower': 27.0},
                    'dividend_yield': {'avg': 3.0, 'excellent': 4.8, 'poor': 1.0, 'upper': 3.9, 'lower': 2.0},
                    'revenue_growth': {'avg': 2.5, 'excellent': 10.0, 'poor': -8.0, 'upper': 6.5, 'lower': -1.5},
                    'profit_growth': {'avg': 5.0, 'excellent': 16.0, 'poor': -14.0, 'upper': 10.5, 'lower': -1.0},
                }
            },
            {
                'industry_code': '3500',
                'industry_name': '非鉄金属',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 6.8, 'excellent': 12.0, 'poor': 2.0, 'upper': 9.5, 'lower': 4.0},
                    'roa': {'avg': 3.5, 'excellent': 6.5, 'poor': 0.8, 'upper': 5.0, 'lower': 1.8},
                    'operating_margin': {'avg': 5.5, 'excellent': 10.0, 'poor': 1.5, 'upper': 8.0, 'lower': 3.0},
                    'per': {'avg': 12.0, 'excellent': 8.0, 'poor': 19.0, 'upper': 9.5, 'lower': 15.0},
                    'pbr': {'avg': 0.8, 'excellent': 0.5, 'poor': 1.3, 'upper': 0.6, 'lower': 1.0},
                    'equity_ratio': {'avg': 40.0, 'excellent': 55.0, 'poor': 25.0, 'upper': 48.0, 'lower': 30.0},
                    'dividend_yield': {'avg': 2.6, 'excellent': 4.2, 'poor': 0.8, 'upper': 3.4, 'lower': 1.6},
                    'revenue_growth': {'avg': 3.0, 'excellent': 11.0, 'poor': -7.0, 'upper': 7.5, 'lower': -1.0},
                    'profit_growth': {'avg': 5.5, 'excellent': 17.0, 'poor': -12.0, 'upper': 11.5, 'lower': 0.0},
                }
            },
            {
                'industry_code': '3550',
                'industry_name': '金属製品',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 7.0, 'excellent': 12.5, 'poor': 2.5, 'upper': 10.0, 'lower': 4.0},
                    'roa': {'avg': 3.8, 'excellent': 7.0, 'poor': 1.0, 'upper': 5.5, 'lower': 2.0},
                    'operating_margin': {'avg': 5.8, 'excellent': 10.5, 'poor': 2.0, 'upper': 8.5, 'lower': 3.5},
                    'per': {'avg': 13.2, 'excellent': 8.5, 'poor': 20.0, 'upper': 10.5, 'lower': 16.0},
                    'pbr': {'avg': 0.9, 'excellent': 0.5, 'poor': 1.4, 'upper': 0.7, 'lower': 1.1},
                    'equity_ratio': {'avg': 42.0, 'excellent': 56.0, 'poor': 28.0, 'upper': 50.0, 'lower': 33.0},
                    'dividend_yield': {'avg': 2.4, 'excellent': 3.9, 'poor': 0.7, 'upper': 3.2, 'lower': 1.5},
                    'revenue_growth': {'avg': 3.8, 'excellent': 12.0, 'poor': -6.0, 'upper': 8.0, 'lower': 0.0},
                    'profit_growth': {'avg': 6.5, 'excellent': 16.0, 'poor': -10.0, 'upper': 11.5, 'lower': 1.5},
                }
            },
            {
                'industry_code': '3300',
                'industry_name': '石油・石炭製品',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 5.5, 'excellent': 10.0, 'poor': 1.0, 'upper': 8.0, 'lower': 3.0},
                    'roa': {'avg': 2.8, 'excellent': 5.5, 'poor': 0.5, 'upper': 4.2, 'lower': 1.3},
                    'operating_margin': {'avg': 3.5, 'excellent': 7.0, 'poor': 0.5, 'upper': 5.5, 'lower': 1.5},
                    'per': {'avg': 10.5, 'excellent': 7.0, 'poor': 17.0, 'upper': 8.5, 'lower': 13.5},
                    'pbr': {'avg': 0.6, 'excellent': 0.4, 'poor': 1.0, 'upper': 0.5, 'lower': 0.8},
                    'equity_ratio': {'avg': 32.0, 'excellent': 45.0, 'poor': 20.0, 'upper': 39.0, 'lower': 24.0},
                    'dividend_yield': {'avg': 3.2, 'excellent': 5.0, 'poor': 1.2, 'upper': 4.1, 'lower': 2.2},
                    'revenue_growth': {'avg': 2.0, 'excellent': 10.0, 'poor': -10.0, 'upper': 6.0, 'lower': -2.5},
                    'profit_growth': {'avg': 4.0, 'excellent': 15.0, 'poor': -18.0, 'upper': 9.5, 'lower': -2.0},
                }
            },
            {
                'industry_code': '3350',
                'industry_name': 'ゴム製品',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 7.2, 'excellent': 12.5, 'poor': 2.5, 'upper': 10.0, 'lower': 4.5},
                    'roa': {'avg': 3.9, 'excellent': 7.2, 'poor': 1.0, 'upper': 5.6, 'lower': 2.2},
                    'operating_margin': {'avg': 6.5, 'excellent': 11.0, 'poor': 2.5, 'upper': 9.0, 'lower': 4.0},
                    'per': {'avg': 12.8, 'excellent': 8.5, 'poor': 19.5, 'upper': 10.5, 'lower': 15.5},
                    'pbr': {'avg': 0.9, 'excellent': 0.6, 'poor': 1.4, 'upper': 0.7, 'lower': 1.1},
                    'equity_ratio': {'avg': 40.0, 'excellent': 54.0, 'poor': 26.0, 'upper': 48.0, 'lower': 31.0},
                    'dividend_yield': {'avg': 2.5, 'excellent': 4.0, 'poor': 0.8, 'upper': 3.3, 'lower': 1.6},
                    'revenue_growth': {'avg': 3.5, 'excellent': 11.0, 'poor': -6.0, 'upper': 7.5, 'lower': 0.0},
                    'profit_growth': {'avg': 6.0, 'excellent': 16.0, 'poor': -10.0, 'upper': 11.0, 'lower': 1.0},
                }
            },
            {
                'industry_code': '3400',
                'industry_name': 'ガラス・土石製品',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 6.5, 'excellent': 11.5, 'poor': 2.0, 'upper': 9.5, 'lower': 3.8},
                    'roa': {'avg': 3.5, 'excellent': 6.5, 'poor': 0.8, 'upper': 5.0, 'lower': 1.8},
                    'operating_margin': {'avg': 6.0, 'excellent': 10.5, 'poor': 2.0, 'upper': 8.5, 'lower': 3.5},
                    'per': {'avg': 12.5, 'excellent': 8.0, 'poor': 19.0, 'upper': 10.0, 'lower': 15.5},
                    'pbr': {'avg': 0.8, 'excellent': 0.5, 'poor': 1.2, 'upper': 0.6, 'lower': 1.0},
                    'equity_ratio': {'avg': 44.0, 'excellent': 58.0, 'poor': 30.0, 'upper': 52.0, 'lower': 35.0},
                    'dividend_yield': {'avg': 2.6, 'excellent': 4.1, 'poor': 0.9, 'upper': 3.4, 'lower': 1.7},
                    'revenue_growth': {'avg': 3.2, 'excellent': 11.0, 'poor': -6.0, 'upper': 7.5, 'lower': -0.5},
                    'profit_growth': {'avg': 5.5, 'excellent': 15.0, 'poor': -11.0, 'upper': 10.5, 'lower': 0.5},
                }
            },
            
            # その他製造業
            {
                'industry_code': '3050',
                'industry_name': '食料品',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 8.0, 'excellent': 13.5, 'poor': 3.0, 'upper': 11.0, 'lower': 5.0},
                    'roa': {'avg': 4.5, 'excellent': 8.0, 'poor': 1.5, 'upper': 6.3, 'lower': 2.8},
                    'operating_margin': {'avg': 5.2, 'excellent': 9.5, 'poor': 2.0, 'upper': 7.5, 'lower': 3.5},
                    'per': {'avg': 16.0, 'excellent': 11.0, 'poor': 24.0, 'upper': 13.0, 'lower': 19.5},
                    'pbr': {'avg': 1.3, 'excellent': 0.8, 'poor': 2.0, 'upper': 1.0, 'lower': 1.6},
                    'equity_ratio': {'avg': 46.0, 'excellent': 60.0, 'poor': 32.0, 'upper': 54.0, 'lower': 37.0},
                    'dividend_yield': {'avg': 2.2, 'excellent': 3.6, 'poor': 0.7, 'upper': 2.9, 'lower': 1.5},
                    'revenue_growth': {'avg': 2.8, 'excellent': 9.0, 'poor': -3.0, 'upper': 6.0, 'lower': 0.0},
                    'profit_growth': {'avg': 5.0, 'excellent': 14.0, 'poor': -7.0, 'upper': 9.5, 'lower': 1.0},
                }
            },
            {
                'industry_code': '3100',
                'industry_name': '繊維製品',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 5.5, 'excellent': 10.0, 'poor': 1.5, 'upper': 8.0, 'lower': 3.0},
                    'roa': {'avg': 2.8, 'excellent': 5.5, 'poor': 0.5, 'upper': 4.2, 'lower': 1.3},
                    'operating_margin': {'avg': 4.0, 'excellent': 8.0, 'poor': 1.0, 'upper': 6.5, 'lower': 2.0},
                    'per': {'avg': 13.5, 'excellent': 9.0, 'poor': 21.0, 'upper': 11.0, 'lower': 17.0},
                    'pbr': {'avg': 0.7, 'excellent': 0.4, 'poor': 1.1, 'upper': 0.5, 'lower': 0.9},
                    'equity_ratio': {'avg': 42.0, 'excellent': 56.0, 'poor': 28.0, 'upper': 50.0, 'lower': 33.0},
                    'dividend_yield': {'avg': 2.8, 'excellent': 4.3, 'poor': 1.0, 'upper': 3.6, 'lower': 1.9},
                    'revenue_growth': {'avg': 1.5, 'excellent': 8.0, 'poor': -7.0, 'upper': 5.0, 'lower': -1.5},
                    'profit_growth': {'avg': 3.5, 'excellent': 12.0, 'poor': -12.0, 'upper': 7.5, 'lower': -1.0},
                }
            },
            {
                'industry_code': '3150',
                'industry_name': 'パルプ・紙',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 5.8, 'excellent': 10.5, 'poor': 1.8, 'upper': 8.5, 'lower': 3.2},
                    'roa': {'avg': 2.9, 'excellent': 5.8, 'poor': 0.6, 'upper': 4.4, 'lower': 1.4},
                    'operating_margin': {'avg': 4.5, 'excellent': 8.5, 'poor': 1.2, 'upper': 7.0, 'lower': 2.5},
                    'per': {'avg': 12.8, 'excellent': 8.5, 'poor': 19.5, 'upper': 10.5, 'lower': 16.0},
                    'pbr': {'avg': 0.7, 'excellent': 0.4, 'poor': 1.1, 'upper': 0.5, 'lower': 0.9},
                    'equity_ratio': {'avg': 38.0, 'excellent': 52.0, 'poor': 25.0, 'upper': 46.0, 'lower': 30.0},
                    'dividend_yield': {'avg': 2.9, 'excellent': 4.5, 'poor': 1.1, 'upper': 3.7, 'lower': 2.0},
                    'revenue_growth': {'avg': 2.2, 'excellent': 9.0, 'poor': -6.0, 'upper': 6.0, 'lower': -1.0},
                    'profit_growth': {'avg': 4.5, 'excellent': 13.0, 'poor': -10.0, 'upper': 8.8, 'lower': 0.0},
                }
            },
            {
                'industry_code': '3800',
                'industry_name': 'その他製品',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 7.8, 'excellent': 13.5, 'poor': 2.8, 'upper': 11.0, 'lower': 4.8},
                    'roa': {'avg': 4.3, 'excellent': 8.0, 'poor': 1.2, 'upper': 6.2, 'lower': 2.5},
                    'operating_margin': {'avg': 6.5, 'excellent': 11.5, 'poor': 2.5, 'upper': 9.5, 'lower': 4.0},
                    'per': {'avg': 15.5, 'excellent': 10.5, 'poor': 23.0, 'upper': 12.5, 'lower': 19.0},
                    'pbr': {'avg': 1.2, 'excellent': 0.7, 'poor': 1.8, 'upper': 0.9, 'lower': 1.5},
                    'equity_ratio': {'avg': 47.0, 'excellent': 61.0, 'poor': 33.0, 'upper': 55.0, 'lower': 38.0},
                    'dividend_yield': {'avg': 2.1, 'excellent': 3.5, 'poor': 0.6, 'upper': 2.8, 'lower': 1.4},
                    'revenue_growth': {'avg': 4.2, 'excellent': 12.5, 'poor': -5.0, 'upper': 8.5, 'lower': 0.5},
                    'profit_growth': {'avg': 6.8, 'excellent': 17.0, 'poor': -9.0, 'upper': 12.0, 'lower': 1.8},
                }
            },
            
            # 商業・流通
            {
                'industry_code': '6100',
                'industry_name': '小売業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 7.2, 'excellent': 12.0, 'poor': 2.0, 'upper': 10.0, 'lower': 4.0},
                    'roa': {'avg': 3.5, 'excellent': 6.0, 'poor': 1.0, 'upper': 5.0, 'lower': 2.0},
                    'operating_margin': {'avg': 4.8, 'excellent': 8.0, 'poor': 1.5, 'upper': 6.5, 'lower': 3.0},
                    'per': {'avg': 16.8, 'excellent': 11.0, 'poor': 28.0, 'upper': 13.0, 'lower': 20.0},
                    'pbr': {'avg': 1.1, 'excellent': 0.7, 'poor': 1.8, 'upper': 0.9, 'lower': 1.4},
                    'equity_ratio': {'avg': 38.0, 'excellent': 55.0, 'poor': 25.0, 'upper': 48.0, 'lower': 30.0},
                    'dividend_yield': {'avg': 2.3, 'excellent': 3.8, 'poor': 0.8, 'upper': 3.0, 'lower': 1.6},
                    'revenue_growth': {'avg': 3.5, 'excellent': 10.0, 'poor': -3.0, 'upper': 7.0, 'lower': 0.5},
                    'profit_growth': {'avg': 5.0, 'excellent': 15.0, 'poor': -8.0, 'upper': 10.0, 'lower': 1.0},
                }
            },
            {
                'industry_code': '6050',
                'industry_name': '卸売業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 8.5, 'excellent': 14.0, 'poor': 3.5, 'upper': 11.5, 'lower': 5.5},
                    'roa': {'avg': 3.2, 'excellent': 6.0, 'poor': 1.0, 'upper': 4.8, 'lower': 1.8},
                    'operating_margin': {'avg': 3.2, 'excellent': 6.0, 'poor': 1.0, 'upper': 4.8, 'lower': 1.8},
                    'per': {'avg': 13.5, 'excellent': 9.0, 'poor': 21.0, 'upper': 11.0, 'lower': 16.5},
                    'pbr': {'avg': 1.0, 'excellent': 0.6, 'poor': 1.6, 'upper': 0.8, 'lower': 1.3},
                    'equity_ratio': {'avg': 40.0, 'excellent': 54.0, 'poor': 26.0, 'upper': 48.0, 'lower': 31.0},
                    'dividend_yield': {'avg': 2.4, 'excellent': 3.9, 'poor': 0.8, 'upper': 3.2, 'lower': 1.6},
                    'revenue_growth': {'avg': 4.5, 'excellent': 12.0, 'poor': -4.0, 'upper': 8.5, 'lower': 0.8},
                    'profit_growth': {'avg': 6.5, 'excellent': 16.0, 'poor': -7.0, 'upper': 11.5, 'lower': 1.5},
                }
            },
            
            # 運輸業
            {
                'industry_code': '5050',
                'industry_name': '陸運業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 6.5, 'excellent': 11.5, 'poor': 2.0, 'upper': 9.5, 'lower': 3.8},
                    'roa': {'avg': 2.8, 'excellent': 5.5, 'poor': 0.8, 'upper': 4.2, 'lower': 1.5},
                    'operating_margin': {'avg': 6.0, 'excellent': 10.5, 'poor': 2.0, 'upper': 8.5, 'lower': 3.5},
                    'per': {'avg': 13.0, 'excellent': 8.5, 'poor': 20.0, 'upper': 10.5, 'lower': 16.0},
                    'pbr': {'avg': 0.9, 'excellent': 0.5, 'poor': 1.4, 'upper': 0.7, 'lower': 1.1},
                    'equity_ratio': {'avg': 32.0, 'excellent': 46.0, 'poor': 20.0, 'upper': 40.0, 'lower': 24.0},
                    'dividend_yield': {'avg': 2.7, 'excellent': 4.2, 'poor': 0.9, 'upper': 3.5, 'lower': 1.8},
                    'revenue_growth': {'avg': 3.0, 'excellent': 10.0, 'poor': -5.0, 'upper': 7.0, 'lower': -0.5},
                    'profit_growth': {'avg': 5.5, 'excellent': 15.0, 'poor': -9.0, 'upper': 10.5, 'lower': 0.5},
                }
            },
            {
                'industry_code': '5100',
                'industry_name': '海運業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 5.8, 'excellent': 11.0, 'poor': 1.5, 'upper': 8.8, 'lower': 3.0},
                    'roa': {'avg': 2.5, 'excellent': 5.0, 'poor': 0.5, 'upper': 3.8, 'lower': 1.2},
                    'operating_margin': {'avg': 8.5, 'excellent': 15.0, 'poor': 2.5, 'upper': 12.0, 'lower': 4.5},
                    'per': {'avg': 11.0, 'excellent': 7.0, 'poor': 17.5, 'upper': 8.8, 'lower': 14.0},
                    'pbr': {'avg': 0.7, 'excellent': 0.4, 'poor': 1.1, 'upper': 0.5, 'lower': 0.9},
                    'equity_ratio': {'avg': 38.0, 'excellent': 52.0, 'poor': 25.0, 'upper': 46.0, 'lower': 30.0},
                    'dividend_yield': {'avg': 3.5, 'excellent': 5.5, 'poor': 1.2, 'upper': 4.5, 'lower': 2.3},
                    'revenue_growth': {'avg': 3.5, 'excellent': 14.0, 'poor': -10.0, 'upper': 9.0, 'lower': -1.5},
                    'profit_growth': {'avg': 6.0, 'excellent': 20.0, 'poor': -18.0, 'upper': 13.0, 'lower': -2.0},
                }
            },
            {
                'industry_code': '5150',
                'industry_name': '空運業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 4.5, 'excellent': 9.5, 'poor': 0.5, 'upper': 7.5, 'lower': 2.0},
                    'roa': {'avg': 2.0, 'excellent': 4.5, 'poor': 0.2, 'upper': 3.3, 'lower': 0.8},
                    'operating_margin': {'avg': 5.5, 'excellent': 11.0, 'poor': 1.0, 'upper': 8.5, 'lower': 2.5},
                    'per': {'avg': 12.5, 'excellent': 8.0, 'poor': 20.0, 'upper': 10.0, 'lower': 16.0},
                    'pbr': {'avg': 0.8, 'excellent': 0.5, 'poor': 1.3, 'upper': 0.6, 'lower': 1.0},
                    'equity_ratio': {'avg': 28.0, 'excellent': 42.0, 'poor': 16.0, 'upper': 36.0, 'lower': 20.0},
                    'dividend_yield': {'avg': 2.0, 'excellent': 3.5, 'poor': 0.3, 'upper': 2.8, 'lower': 1.0},
                    'revenue_growth': {'avg': 4.0, 'excellent': 15.0, 'poor': -12.0, 'upper': 10.0, 'lower': -2.0},
                    'profit_growth': {'avg': 7.0, 'excellent': 22.0, 'poor': -20.0, 'upper': 14.5, 'lower': -3.0},
                }
            },
            {
                'industry_code': '5200',
                'industry_name': '倉庫・運輸関連業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 7.8, 'excellent': 13.5, 'poor': 3.0, 'upper': 11.0, 'lower': 5.0},
                    'roa': {'avg': 3.5, 'excellent': 6.5, 'poor': 1.0, 'upper': 5.0, 'lower': 2.0},
                    'operating_margin': {'avg': 8.0, 'excellent': 13.5, 'poor': 3.0, 'upper': 11.0, 'lower': 5.0},
                    'per': {'avg': 14.0, 'excellent': 9.5, 'poor': 21.0, 'upper': 11.5, 'lower': 17.0},
                    'pbr': {'avg': 1.1, 'excellent': 0.7, 'poor': 1.7, 'upper': 0.9, 'lower': 1.4},
                    'equity_ratio': {'avg': 42.0, 'excellent': 56.0, 'poor': 28.0, 'upper': 50.0, 'lower': 33.0},
                    'dividend_yield': {'avg': 2.5, 'excellent': 4.0, 'poor': 0.8, 'upper': 3.3, 'lower': 1.6},
                    'revenue_growth': {'avg': 5.0, 'excellent': 13.0, 'poor': -4.0, 'upper': 9.5, 'lower': 1.0},
                    'profit_growth': {'avg': 7.5, 'excellent': 18.0, 'poor': -7.0, 'upper': 13.0, 'lower': 2.0},
                }
            },
            
            # その他
            {
                'industry_code': '2050',
                'industry_name': '建設業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 9.5, 'excellent': 15.5, 'poor': 4.0, 'upper': 13.0, 'lower': 6.5},
                    'roa': {'avg': 4.8, 'excellent': 8.5, 'poor': 1.8, 'upper': 6.8, 'lower': 3.0},
                    'operating_margin': {'avg': 5.8, 'excellent': 10.0, 'poor': 2.5, 'upper': 8.0, 'lower': 3.8},
                    'per': {'avg': 11.0, 'excellent': 7.5, 'poor': 17.0, 'upper': 9.0, 'lower': 13.5},
                    'pbr': {'avg': 1.0, 'excellent': 0.6, 'poor': 1.6, 'upper': 0.8, 'lower': 1.3},
                    'equity_ratio': {'avg': 42.0, 'excellent': 56.0, 'poor': 28.0, 'upper': 50.0, 'lower': 33.0},
                    'dividend_yield': {'avg': 3.0, 'excellent': 4.8, 'poor': 1.0, 'upper': 3.9, 'lower': 2.0},
                    'revenue_growth': {'avg': 3.8, 'excellent': 12.0, 'poor': -5.0, 'upper': 8.5, 'lower': 0.0},
                    'profit_growth': {'avg': 6.5, 'excellent': 17.0, 'poor': -9.0, 'upper': 12.0, 'lower': 1.5},
                }
            },
            {
                'industry_code': '8050',
                'industry_name': '不動産業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 6.8, 'excellent': 12.0, 'poor': 2.5, 'upper': 9.8, 'lower': 4.0},
                    'roa': {'avg': 2.5, 'excellent': 5.0, 'poor': 0.8, 'upper': 3.8, 'lower': 1.3},
                    'operating_margin': {'avg': 15.0, 'excellent': 25.0, 'poor': 7.5, 'upper': 20.5, 'lower': 10.0},
                    'per': {'avg': 14.5, 'excellent': 10.0, 'poor': 22.0, 'upper': 12.0, 'lower': 17.5},
                    'pbr': {'avg': 1.2, 'excellent': 0.7, 'poor': 1.9, 'upper': 0.9, 'lower': 1.5},
                    'equity_ratio': {'avg': 35.0, 'excellent': 48.0, 'poor': 22.0, 'upper': 42.0, 'lower': 27.0},
                    'dividend_yield': {'avg': 3.2, 'excellent': 5.0, 'poor': 1.2, 'upper': 4.1, 'lower': 2.2},
                    'revenue_growth': {'avg': 4.0, 'excellent': 12.0, 'poor': -6.0, 'upper': 8.5, 'lower': 0.0},
                    'profit_growth': {'avg': 6.0, 'excellent': 16.0, 'poor': -10.0, 'upper': 11.0, 'lower': 1.0},
                }
            },
            {
                'industry_code': '4050',
                'industry_name': '電気・ガス業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 5.2, 'excellent': 9.5, 'poor': 1.5, 'upper': 7.8, 'lower': 2.8},
                    'roa': {'avg': 2.2, 'excellent': 4.5, 'poor': 0.5, 'upper': 3.4, 'lower': 1.0},
                    'operating_margin': {'avg': 8.5, 'excellent': 14.0, 'poor': 3.5, 'upper': 11.5, 'lower': 5.5},
                    'per': {'avg': 13.5, 'excellent': 9.0, 'poor': 21.0, 'upper': 11.0, 'lower': 16.5},
                    'pbr': {'avg': 0.7, 'excellent': 0.4, 'poor': 1.1, 'upper': 0.5, 'lower': 0.9},
                    'equity_ratio': {'avg': 28.0, 'excellent': 40.0, 'poor': 18.0, 'upper': 35.0, 'lower': 21.0},
                    'dividend_yield': {'avg': 3.5, 'excellent': 5.2, 'poor': 1.5, 'upper': 4.4, 'lower': 2.5},
                    'revenue_growth': {'avg': 2.0, 'excellent': 8.0, 'poor': -5.0, 'upper': 5.5, 'lower': -1.0},
                    'profit_growth': {'avg': 4.0, 'excellent': 13.0, 'poor': -10.0, 'upper': 8.5, 'lower': -1.0},
                }
            },
            {
                'industry_code': '1050',
                'industry_name': '鉱業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 6.0, 'excellent': 11.5, 'poor': 1.5, 'upper': 9.2, 'lower': 3.0},
                    'roa': {'avg': 3.2, 'excellent': 6.5, 'poor': 0.5, 'upper': 4.9, 'lower': 1.5},
                    'operating_margin': {'avg': 12.0, 'excellent': 20.0, 'poor': 4.0, 'upper': 16.5, 'lower': 7.0},
                    'per': {'avg': 10.5, 'excellent': 7.0, 'poor': 17.0, 'upper': 8.5, 'lower': 13.5},
                    'pbr': {'avg': 0.8, 'excellent': 0.5, 'poor': 1.3, 'upper': 0.6, 'lower': 1.0},
                    'equity_ratio': {'avg': 42.0, 'excellent': 56.0, 'poor': 28.0, 'upper': 50.0, 'lower': 33.0},
                    'dividend_yield': {'avg': 3.8, 'excellent': 5.8, 'poor': 1.5, 'upper': 4.8, 'lower': 2.6},
                    'revenue_growth': {'avg': 3.0, 'excellent': 13.0, 'poor': -10.0, 'upper': 8.5, 'lower': -1.5},
                    'profit_growth': {'avg': 5.5, 'excellent': 18.0, 'poor': -16.0, 'upper': 12.0, 'lower': -2.0},
                }
            },
            {
                'industry_code': '50',
                'industry_name': '水産・農林業',
                'fiscal_year': '2024',
                'metrics': {
                    'roe': {'avg': 5.5, 'excellent': 10.5, 'poor': 1.5, 'upper': 8.5, 'lower': 3.0},
                    'roa': {'avg': 2.8, 'excellent': 5.8, 'poor': 0.5, 'upper': 4.3, 'lower': 1.3},
                    'operating_margin': {'avg': 4.2, 'excellent': 8.5, 'poor': 1.0, 'upper': 6.8, 'lower': 2.2},
                    'per': {'avg': 14.0, 'excellent': 9.5, 'poor': 21.0, 'upper': 11.5, 'lower': 17.0},
                    'pbr': {'avg': 0.8, 'excellent': 0.5, 'poor': 1.3, 'upper': 0.6, 'lower': 1.0},
                    'equity_ratio': {'avg': 40.0, 'excellent': 54.0, 'poor': 26.0, 'upper': 48.0, 'lower': 31.0},
                    'dividend_yield': {'avg': 2.5, 'excellent': 4.2, 'poor': 0.8, 'upper': 3.4, 'lower': 1.6},
                    'revenue_growth': {'avg': 2.5, 'excellent': 10.0, 'poor': -6.0, 'upper': 6.8, 'lower': -0.8},
                    'profit_growth': {'avg': 4.5, 'excellent': 14.0, 'poor': -11.0, 'upper': 9.5, 'lower': 0.0},
                }
            },
        ]
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        self.stdout.write(self.style.SUCCESS('\n🚀 業種別ベンチマークデータの登録を開始します\n'))
        self.stdout.write(f'対象業種数: {len(benchmark_data)}業種\n')
        
        for industry in benchmark_data:
            industry_code = industry['industry_code']
            industry_name = industry['industry_name']
            fiscal_year = industry['fiscal_year']
            
            self.stdout.write(f"\n業種: {industry_name} ({industry_code})")
            
            for metric_name, values in industry['metrics'].items():
                try:
                    metric_def = MetricDefinition.objects.get(name=metric_name, is_active=True)
                    
                    benchmark, created = IndustryBenchmark.objects.update_or_create(
                        industry_code=industry_code,
                        metric_definition=metric_def,
                        fiscal_year=fiscal_year,
                        defaults={
                            'industry_name': industry_name,
                            'average_value': Decimal(str(values['avg'])),
                            'median_value': Decimal(str(values['avg'])),
                            'excellent_threshold': Decimal(str(values['excellent'])) if values.get('excellent') else None,
                            'poor_threshold': Decimal(str(values['poor'])) if values.get('poor') else None,
                            'upper_quartile': Decimal(str(values['upper'])) if values.get('upper') else None,
                            'lower_quartile': Decimal(str(values['lower'])) if values.get('lower') else None,
                        }
                    )
                    
                    if created:
                        created_count += 1
                        self.stdout.write(f"  ✓ {metric_def.display_name}: 作成")
                    else:
                        updated_count += 1
                        self.stdout.write(f"  ↻ {metric_def.display_name}: 更新")
                        
                except MetricDefinition.DoesNotExist:
                    error_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"  ⚠ 指標定義が見つかりません: {metric_name}")
                    )
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ エラー ({metric_name}): {str(e)}")
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n\n✅ 完了: {created_count}件作成, {updated_count}件更新, {error_count}件エラー"
            )
        )
        
        # 登録された業種の一覧を表示
        self.stdout.write(self.style.SUCCESS('\n📊 登録済み業種一覧:'))
        industries = IndustryBenchmark.objects.values('industry_code', 'industry_name').distinct().order_by('industry_code')
        for idx, industry in enumerate(industries, 1):
            self.stdout.write(f"  {idx}. {industry['industry_name']} ({industry['industry_code']})")