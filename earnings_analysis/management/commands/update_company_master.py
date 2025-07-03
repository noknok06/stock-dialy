from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import logging

from earnings_analysis.models import Company, DocumentMetadata

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '企業マスタ更新'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='既存企業の情報も更新する'
        )
        parser.add_argument(
            '--deactivate-unused',
            action='store_true',
            help='書類のない企業を非活性化する'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('企業マスタ更新開始...')
        
        try:
            with transaction.atomic():
                # 1. 書類データから企業情報を抽出
                new_companies = self._extract_companies_from_documents(options['update_existing'])
                
                # 2. 必要に応じて非活性化
                if options['deactivate_unused']:
                    deactivated_count = self._deactivate_unused_companies()
                    self.stdout.write(f'非活性化: {deactivated_count}社')
                
                self.stdout.write(
                    self.style.SUCCESS(f'企業マスタ更新完了: {new_companies}社追加')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'更新エラー: {e}')
            )
            logger.error(f"企業マスタ更新エラー: {e}")
    
    def _extract_companies_from_documents(self, update_existing):
        """書類データから企業情報を抽出して更新"""
        
        # ユニークな企業情報を取得
        unique_companies = DocumentMetadata.objects.values(
            'edinet_code', 'securities_code', 'company_name'
        ).distinct()
        
        created_count = 0
        updated_count = 0
        
        for company_data in unique_companies:
            edinet_code = company_data['edinet_code']
            securities_code = company_data['securities_code']
            company_name = company_data['company_name']
            
            if not edinet_code or not company_name:
                continue
            
            try:
                company, created = Company.objects.get_or_create(
                    edinet_code=edinet_code,
                    defaults={
                        'securities_code': securities_code,
                        'company_name': company_name,
                        'is_active': True,
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f'追加: {company_name} ({edinet_code})')
                elif update_existing:
                    # 既存企業の情報更新
                    updated = False
                    if company.securities_code != securities_code:
                        company.securities_code = securities_code
                        updated = True
                    if company.company_name != company_name:
                        company.company_name = company_name
                        updated = True
                    
                    if updated:
                        company.updated_at = timezone.now()
                        company.save()
                        updated_count += 1
                        self.stdout.write(f'更新: {company_name} ({edinet_code})')
                
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'企業処理エラー: {company_name} - {e}')
                )
                logger.warning(f"企業処理エラー: {company_name} - {e}")
                continue
        
        self.stdout.write(f'新規作成: {created_count}社, 更新: {updated_count}社')
        return created_count
    
    def _deactivate_unused_companies(self):
        """書類のない企業を非活性化"""
        
        # 書類がある企業のEDINETコードを取得
        active_edinet_codes = set(
            DocumentMetadata.objects.values_list('edinet_code', flat=True).distinct()
        )
        
        # 書類のない企業を非活性化
        deactivated = Company.objects.filter(
            is_active=True
        ).exclude(
            edinet_code__in=active_edinet_codes
        ).update(
            is_active=False,
            updated_at=timezone.now()
        )
        
        return deactivated