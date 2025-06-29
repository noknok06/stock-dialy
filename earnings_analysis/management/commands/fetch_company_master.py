# earnings_analysis/management/commands/fetch_company_master.py
"""
企業マスタデータをEDINETから取得するコマンド
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import logging
import requests
import csv
from io import StringIO

from earnings_analysis.models import CompanyEarnings
from earnings_analysis.services import EDINETAPIService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '企業マスタデータをEDINETから取得'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='既存企業情報も更新する',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際の更新は行わず、処理内容のみ表示',
        )
    
    def handle(self, *args, **options):
        update_existing = options['update_existing']
        dry_run = options['dry_run']
        
        self.stdout.write(
            self.style.SUCCESS('企業マスタデータの取得を開始します...')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('ドライランモード: 実際の更新は行いません')
            )
        
        try:
            # 1. EDINETから企業マスタを取得
            companies_data = self._fetch_edinet_company_list()
            
            if not companies_data:
                raise CommandError('企業マスタデータの取得に失敗しました')
            
            self.stdout.write(f"取得した企業数: {len(companies_data)}")
            
            # 2. データベースに保存
            created_count = 0
            updated_count = 0
            
            for company_data in companies_data:
                try:
                    if dry_run:
                        self.stdout.write(f"[DRY RUN] {company_data['company_name']} ({company_data['company_code']})")
                        continue
                    
                    company, created = CompanyEarnings.objects.get_or_create(
                        company_code=company_data['company_code'],
                        defaults={
                            'edinet_code': company_data['edinet_code'],
                            'company_name': company_data['company_name'],
                            'fiscal_year_end_month': company_data.get('fiscal_year_end_month', 3),
                            'is_active': True
                        }
                    )
                    
                    if created:
                        created_count += 1
                        self.stdout.write(f"✓ 新規作成: {company.company_name} ({company.company_code})")
                    elif update_existing:
                        # 既存企業の情報を更新
                        company.company_name = company_data['company_name']
                        company.edinet_code = company_data['edinet_code']
                        company.save()
                        updated_count += 1
                        self.stdout.write(f"✓ 更新: {company.company_name} ({company.company_code})")
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"エラー: {company_data.get('company_name', 'Unknown')} - {str(e)}")
                    )
                    continue
            
            if not dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f'処理完了: 新規作成 {created_count}件, 更新 {updated_count}件')
                )
            
        except Exception as e:
            raise CommandError(f'企業マスタ取得処理に失敗しました: {str(e)}')
    
    def _fetch_edinet_company_list(self):
        """EDINETから企業一覧を取得"""
        try:
            # EDINETの企業一覧API（簡略版実装）
            edinet_service = EDINETAPIService()
            
            # 実際にはEDINETの企業マスタAPIを呼び出す
            # ここでは既知の企業を手動で追加する簡易版
            
            known_companies = [
                {
                    'edinet_code': 'E04236',
                    'company_code': '9101',
                    'company_name': '日本郵船',
                    'fiscal_year_end_month': 3
                },
                {
                    'edinet_code': 'S100W1NC',  # 実際のEDINETコードに要調整
                    'company_code': '9104',
                    'company_name': '商船三井',
                    'fiscal_year_end_month': 3
                },
                {
                    'edinet_code': 'E02144',
                    'company_code': '7203',
                    'company_name': 'トヨタ自動車',
                    'fiscal_year_end_month': 3
                },
                {
                    'edinet_code': 'E01777',
                    'company_code': '6758',
                    'company_name': 'ソニーグループ',
                    'fiscal_year_end_month': 3
                },
                {
                    'edinet_code': 'E04425',
                    'company_code': '9984',
                    'company_name': 'ソフトバンクグループ',
                    'fiscal_year_end_month': 3
                },
            ]
            
            self.stdout.write("既知の企業データを使用します")
            return known_companies
            
        except Exception as e:
            logger.error(f"Error fetching company list: {str(e)}")
            return []
    
    def _get_company_from_edinet_api(self):
        """実際のEDINET企業マスタAPI実装（将来版）"""
        # TODO: 実際のEDINET企業マスタAPIを実装
        # https://disclosure.edinet-fsa.go.jp/api/v2/documents.json で企業情報を取得
        pass


class UpdateCompanyMasterCommand(BaseCommand):
    """簡易版: よく使われる企業を手動追加"""
    help = '主要企業を手動でマスタに追加'
    
    def handle(self, *args, **options):
        major_companies = [
            ('7203', 'トヨタ自動車', 'E02144'),
            ('6758', 'ソニーグループ', 'E01777'), 
            ('9984', 'ソフトバンクグループ', 'E04425'),
            ('6861', 'キーエンス', 'E01974'),
            ('4519', '中外製薬', 'E00945'),
            ('9434', 'ソフトバンク', 'E04371'),
            ('8306', '三菱UFJフィナンシャル・グループ', 'E03569'),
            ('9101', '日本郵船', 'E04236'),
            ('9104', '商船三井', 'S100W1NC'),
        ]
        
        created_count = 0
        for code, name, edinet_code in major_companies:
            company, created = CompanyEarnings.objects.get_or_create(
                company_code=code,
                defaults={
                    'edinet_code': edinet_code,
                    'company_name': name,
                    'fiscal_year_end_month': 3,
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(f"✓ 追加: {name} ({code})")
                created_count += 1
            else:
                self.stdout.write(f"- 既存: {name} ({code})")
        
        self.stdout.write(
            self.style.SUCCESS(f'主要企業の追加完了: {created_count}件追加')
        )