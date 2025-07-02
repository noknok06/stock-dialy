"""
earnings_reports/management/commands/sync_edinet_documents.py
EDINET書類同期管理コマンド
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from earnings_reports.models import Company, Document
from earnings_reports.services.edinet_service import EDINETService

logger = logging.getLogger('earnings_analysis')


class Command(BaseCommand):
    """EDINET書類同期コマンド"""
    
    help = 'EDINET APIから最新の書類情報を同期します'
    
    def add_arguments(self, parser):
        """コマンド引数の定義"""
        
        parser.add_argument(
            '--company',
            type=str,
            help='特定企業のみ同期 (証券コード指定)'
        )
        
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='何日前まで遡って同期するか (デフォルト: 7)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際には更新せず、処理内容のみ表示'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='既存書類も強制的に再取得'
        )
        
        parser.add_argument(
            '--max-companies',
            type=int,
            default=0,
            help='処理する最大企業数 (0=無制限)'
        )
    
    def handle(self, *args, **options):
        """コマンド実行"""
        
        self.stdout.write(
            self.style.SUCCESS('EDINET書類同期を開始します...')
        )
        
        try:
            # EDINET APIサービス初期化
            if not hasattr(settings, 'EDINET_API_KEY'):
                raise CommandError('EDINET_API_KEY が設定されていません')
            
            edinet_service = EDINETService(settings.EDINET_API_KEY)
            
            # 接続テスト
            if not edinet_service.test_connection():
                raise CommandError('EDINET APIに接続できません')
            
            # 同期対象企業の決定
            companies = self._get_target_companies(options)
            
            if not companies:
                self.stdout.write(
                    self.style.WARNING('同期対象の企業が見つかりません')
                )
                return
            
            self.stdout.write(f'対象企業数: {len(companies)}社')
            
            # 同期実行
            results = self._sync_companies(companies, edinet_service, options)
            
            # 結果表示
            self._display_results(results)
            
        except Exception as e:
            logger.error(f"同期エラー: {str(e)}")
            raise CommandError(f'同期処理でエラーが発生しました: {str(e)}')
    
    def _get_target_companies(self, options):
        """同期対象企業を取得"""
        
        if options['company']:
            # 特定企業のみ
            companies = Company.objects.filter(stock_code=options['company'])
            if not companies.exists():
                raise CommandError(f"企業 {options['company']} が見つかりません")
        else:
            # 全企業または条件指定
            companies = Company.objects.all().order_by('stock_code')
            
            if options['max_companies'] > 0:
                companies = companies[:options['max_companies']]
        
        return companies
    
    def _sync_companies(self, companies, edinet_service, options):
        """企業の書類同期実行（最適化版）"""
        
        results = {
            'processed_companies': 0,
            'new_documents': 0,
            'updated_documents': 0,
            'errors': 0,
            'error_details': []
        }
        
        days_back = options['days']
        dry_run = options['dry_run']
        force = options['force']
        
        # 企業をバッチ処理
        batch_size = 5  # 同時処理する企業数
        
        for i in range(0, len(companies), batch_size):
            batch_companies = companies[i:i+batch_size]
            
            # バッチ内の企業を並行処理（簡単な実装）
            for j, company in enumerate(batch_companies):
                company_index = i + j + 1
                self.stdout.write(f'[{company_index}/{len(companies)}] {company.name} ({company.stock_code})')
                
                try:
                    # 最適化された同期処理
                    company_results = self._sync_single_company_optimized(
                        company, edinet_service, days_back, dry_run, force
                    )
                    
                    # 結果を集計
                    results['new_documents'] += company_results['new']
                    results['updated_documents'] += company_results['updated']
                    
                    self.stdout.write(
                        f'  └ 新規: {company_results["new"]}件, '
                        f'更新: {company_results["updated"]}件'
                    )
                    
                    results['processed_companies'] += 1
                    
                except Exception as e:
                    logger.error(f"企業{company.name}の同期エラー: {str(e)}")
                    results['errors'] += 1
                    results['error_details'].append(f"{company.name}: {str(e)}")
                    self.stdout.write(
                        self.style.ERROR(f'  └ エラー: {str(e)}')
                    )
        
        return results

    def _sync_single_company_optimized(self, company, edinet_service, days_back, dry_run, force):
        """単一企業の最適化同期"""
        
        # 最適化された検索を使用
        company_docs = edinet_service.search_company_documents_optimized(
            company.stock_code,
            days_back=days_back,
            max_results=100
        )
        
        if not company_docs:
            return {'new': 0, 'updated': 0}
        
        if dry_run:
            # Dry runの場合は件数のみ返す
            return {'new': len(company_docs), 'updated': 0}
        
        # 実際の同期処理
        process_documents_batch = edinet_service.process_documents_batch
        return process_documents_batch(company, company_docs)
    
    def _process_company_documents(self, company, company_docs, dry_run, force):
        """企業の書類を処理"""
        
        results = {'new': 0, 'updated': 0}
        
        for doc_info in company_docs:
            doc_id, company_name, doc_description, submit_date, doc_type, sec_code = doc_info
            
            try:
                # 日付変換
                submit_date_obj = datetime.strptime(submit_date, '%Y-%m-%d').date()
                
                # 既存書類をチェック
                existing_doc = Document.objects.filter(
                    doc_id=doc_id,
                    company=company
                ).first()
                
                if existing_doc:
                    if force:
                        # 強制更新
                        if not dry_run:
                            existing_doc.doc_description = doc_description
                            existing_doc.submit_date = submit_date_obj
                            existing_doc.save()
                        results['updated'] += 1
                else:
                    # 新規作成
                    if not dry_run:
                        Document.objects.create(
                            doc_id=doc_id,
                            company=company,
                            doc_type=doc_type,
                            doc_description=doc_description,
                            submit_date=submit_date_obj
                        )
                    results['new'] += 1
                    
            except Exception as e:
                logger.warning(f"書類{doc_id}の処理エラー: {str(e)}")
                continue
        
        return results
    
    def _display_results(self, results):
        """同期結果を表示"""
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('同期結果'))
        self.stdout.write('='*50)
        
        self.stdout.write(f"処理企業数: {results['processed_companies']}")
        self.stdout.write(f"新規書類: {results['new_documents']}件")
        self.stdout.write(f"更新書類: {results['updated_documents']}件")
        
        if results['errors'] > 0:
            self.stdout.write(
                self.style.ERROR(f"エラー: {results['errors']}件")
            )
            
            if results['error_details']:
                self.stdout.write('\nエラー詳細:')
                for error in results['error_details']:
                    self.stdout.write(f"  - {error}")
        else:
            self.stdout.write(self.style.SUCCESS("エラーなし"))
        
        self.stdout.write('\n同期完了')