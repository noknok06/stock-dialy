# earnings_analysis/management/commands/test_company_search.py
"""
企業検索のテスト用コマンド

マスタに登録されていない企業でもEDINET APIから検索できるかテスト
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import logging

from earnings_analysis.services import EDINETAPIService
from earnings_analysis.analysis_service import OnDemandAnalysisService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '企業検索のテスト（EDINET API使用）'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'company_code',
            type=str,
            help='検索する企業の証券コード (例: 9983)',
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=90,
            help='何日前まで検索するか（デフォルト: 90日）',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='詳細ログを出力',
        )
    
    def handle(self, *args, **options):
        company_code = options['company_code']
        days_back = options['days_back']
        verbose = options['verbose']
        
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        
        self.stdout.write(
            self.style.SUCCESS(f'企業検索テスト: {company_code}')
        )
        self.stdout.write(f'検索期間: 過去{days_back}日')
        
        try:
            # 1. EDINET APIサービスで直接検索
            self.stdout.write('\n=== EDINET API直接検索 ===')
            edinet_service = EDINETAPIService()
            
            company_info = edinet_service.get_company_info_by_code(company_code, days_back)
            
            if company_info:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 企業情報を発見しました:')
                )
                self.stdout.write(f'  企業名: {company_info["company_name"]}')
                self.stdout.write(f'  証券コード: {company_info["company_code"]}')
                self.stdout.write(f'  EDINETコード: {company_info["edinet_code"]}')
                self.stdout.write(f'  決算月: {company_info["fiscal_year_end_month"]}月')
                self.stdout.write(f'  情報源: {company_info.get("source", "不明")}')
                
                # 発見した書類の情報
                if company_info.get('found_document'):
                    doc = company_info['found_document']
                    self.stdout.write(f'\n--- 発見書類の詳細 ---')
                    self.stdout.write(f'  書類ID: {doc.get("document_id")}')
                    self.stdout.write(f'  提出日: {doc.get("submission_date")}')
                    self.stdout.write(f'  書類説明: {doc.get("doc_description", "")[:100]}...')
                
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠ 企業情報が見つかりませんでした')
                )
            
            # 2. 分析サービスでの検索テスト
            self.stdout.write(f'\n=== 分析サービス検索テスト ===')
            analysis_service = OnDemandAnalysisService()
            
            # 企業の作成テスト（実際には作成しない）
            from earnings_analysis.models import CompanyEarnings
            existing_company = CompanyEarnings.objects.filter(company_code=company_code).first()
            
            if existing_company:
                self.stdout.write(f'✓ 既に登録済み: {existing_company.company_name}')
            else:
                self.stdout.write(f'✗ 未登録企業です')
                
                if company_info:
                    self.stdout.write(f'💡 分析実行時に自動登録されます:')
                    self.stdout.write(f'  python manage.py analyze_company {company_code}')
            
            # 3. 最近の書類検索テスト
            self.stdout.write(f'\n=== 最近の書類検索テスト ===')
            
            # 過去30日分の書類を検索
            from datetime import datetime, timedelta
            
            found_documents = []
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
            
            current_date = start_date
            search_count = 0
            
            while current_date <= end_date and search_count < 10:
                date_str = current_date.strftime('%Y-%m-%d')
                
                try:
                    documents = edinet_service.get_document_list(date_str, company_code)
                    if documents:
                        found_documents.extend(documents)
                        self.stdout.write(f'  {date_str}: {len(documents)}件の書類')
                        for doc in documents[:2]:  # 最初の2件表示
                            self.stdout.write(f'    - {doc.get("doc_description", "")[:60]}...')
                
                except Exception as e:
                    if verbose:
                        self.stdout.write(f'  {date_str}: エラー - {str(e)}')
                
                current_date += timedelta(days=3)
                search_count += 1
            
            if found_documents:
                self.stdout.write(f'\n✓ 合計 {len(found_documents)} 件の決算関連書類を発見')
                self.stdout.write(f'💡 分析可能です！')
            else:
                self.stdout.write(f'\n⚠ 過去30日間に決算関連書類が見つかりませんでした')
                self.stdout.write(f'💡 --days-back オプションで期間を延長してみてください')
            
            # 4. 推奨コマンドの表示
            self.stdout.write(f'\n=== 推奨コマンド ===')
            
            if company_info and found_documents:
                self.stdout.write(f'✅ 分析実行:')
                self.stdout.write(f'  python manage.py analyze_company {company_code}')
                self.stdout.write(f'')
                self.stdout.write(f'📋 詳細情報取得:')
                self.stdout.write(f'  python manage.py analyze_company {company_code} --search-only')
            elif company_info:
                self.stdout.write(f'⚠ 企業情報は見つかりましたが、最近の書類がありません')
                self.stdout.write(f'  python manage.py analyze_company {company_code} --search-only')
            else:
                self.stdout.write(f'❌ 企業情報が見つかりません')
                self.stdout.write(f'• 証券コードが正しいか確認してください')
                self.stdout.write(f'• 上場企業かどうか確認してください')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'検索テスト中にエラーが発生しました: {str(e)}')
            )
            raise CommandError(f'検索テストに失敗しました: {str(e)}')


class TestKnownCompaniesCommand(BaseCommand):
    """既知の企業での一括テスト"""
    
    def handle(self, *args, **options):
        # テスト対象の企業
        test_companies = [
            ('7203', 'トヨタ自動車'),
            ('6758', 'ソニーグループ'),
            ('9984', 'ソフトバンクグループ'),
            ('9983', 'ファーストリテイリング'),
            ('6861', 'キーエンス'),
        ]
        
        self.stdout.write('=== 既知企業の検索テスト ===')
        
        edinet_service = EDINETAPIService()
        
        for company_code, expected_name in test_companies:
            self.stdout.write(f'\n--- {company_code} ({expected_name}) ---')
            
            try:
                company_info = edinet_service.get_company_info_by_code(company_code, days_back=60)
                
                if company_info:
                    found_name = company_info['company_name']
                    if expected_name in found_name or found_name in expected_name:
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ 正しく発見: {found_name}')
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'⚠ 名前が一致しません: {found_name}')
                        )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'✗ 見つかりませんでした')
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ エラー: {str(e)}')
                )
        
        self.stdout.write(f'\n=== テスト完了 ===')