# earnings_analysis/management/commands/daily_update.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from datetime import date, datetime, timedelta
import logging
import traceback

from earnings_analysis.models import DocumentMetadata, BatchExecution, Company
from earnings_analysis.services import EdinetDocumentService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '日次データ更新（本番運用用）'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='更新対象日（YYYY-MM-DD形式、指定しない場合は前営業日）'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='既存データがあっても強制実行'
        )
        parser.add_argument(
            '--send-notification',
            action='store_true',
            help='実行結果をメール通知'
        )
        parser.add_argument(
            '--api-version',
            type=str,
            choices=['v1', 'v2'],
            default='v2',
            help='使用するAPIバージョン'
        )
        parser.add_argument(
            '--retry-count',
            type=int,
            default=3,
            help='エラー時のリトライ回数'
        )
    
    def handle(self, *args, **options):
        target_date = options.get('date')
        force = options.get('force', False)
        send_notification = options.get('send_notification', False)
        api_version = options.get('api_version', 'v2')
        retry_count = options.get('retry_count', 3)
        
        # 対象日の決定
        if target_date:
            try:
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('無効な日付形式です。YYYY-MM-DD形式で指定してください。'))
                return
        else:
            target_date = self._get_last_business_day()
        
        # 未来の日付チェック
        if target_date >= date.today():
            self.stdout.write(self.style.ERROR('未来の日付は指定できません。'))
            return
        
        # 土日チェック
        if target_date.weekday() >= 5:
            self.stdout.write(self.style.WARNING(f'{target_date} は休日です。営業日に調整します。'))
            target_date = self._adjust_to_business_day(target_date)
        
        self.stdout.write(f'日次データ更新開始: {target_date}')
        
        # 実行記録の確認・作成
        batch_execution, created = BatchExecution.objects.get_or_create(
            batch_date=target_date,
            defaults={
                'status': 'RUNNING',
                'started_at': timezone.now()
            }
        )
        
        if not created and batch_execution.status == 'SUCCESS' and not force:
            self.stdout.write(
                self.style.WARNING(f'{target_date} のデータは既に正常に処理済みです。')
            )
            self.stdout.write('強制実行する場合は --force オプションを使用してください。')
            return
        
        # バッチ実行ステータスを更新
        batch_execution.status = 'RUNNING'
        batch_execution.started_at = timezone.now()
        batch_execution.error_message = ''
        batch_execution.save()
        
        success = False
        error_message = ''
        processed_count = 0
        
        try:
            # データ更新実行
            processed_count = self._execute_update_with_retry(
                target_date, api_version, retry_count
            )
            
            # 企業マスタ更新
            self._update_company_master()
            
            # 成功処理
            batch_execution.status = 'SUCCESS'
            batch_execution.processed_count = processed_count
            batch_execution.completed_at = timezone.now()
            batch_execution.save()
            
            success = True
            
            self.stdout.write(
                self.style.SUCCESS(f'日次データ更新完了: {processed_count}件処理')
            )
            
        except Exception as e:
            # エラー処理
            error_message = str(e)
            batch_execution.status = 'FAILED'
            batch_execution.error_message = f"{error_message}\n\n{traceback.format_exc()}"
            batch_execution.completed_at = timezone.now()
            batch_execution.save()
            
            self.stdout.write(
                self.style.ERROR(f'日次データ更新エラー: {error_message}')
            )
            logger.error(f"日次更新エラー: {target_date} - {error_message}", exc_info=True)
        
        # 通知送信
        if send_notification:
            self._send_notification(target_date, success, processed_count, error_message)
        
        # 統計レポート
        self._show_statistics()
    
    def _get_last_business_day(self, days_back=1):
        """最新の営業日を取得"""
        target_date = date.today() - timedelta(days=days_back)
        return self._adjust_to_business_day(target_date)
    
    def _adjust_to_business_day(self, target_date):
        """営業日に調整"""
        while target_date.weekday() >= 5:  # 土日を避ける
            target_date -= timedelta(days=1)
        return target_date
    
    def _execute_update_with_retry(self, target_date, api_version, retry_count):
        """リトライ機能付きでデータ更新実行"""
        last_exception = None
        
        for attempt in range(retry_count + 1):
            try:
                self.stdout.write(f'データ取得試行 {attempt + 1}/{retry_count + 1}')
                
                # APIクライアント初期化
                document_service = EdinetDocumentService(prefer_v1=(api_version == 'v1'))
                
                # データ取得
                date_str = target_date.isoformat()
                response = document_service.get_document_list_with_fallback(date_str, type=2)
                
                # データ処理
                if 'results' in response:
                    documents_data = response['results']
                elif 'metadata' in response and response['metadata'].get('status') == '200':
                    documents_data = response.get('results', [])
                else:
                    raise Exception(f"APIレスポンスエラー: {response}")
                
                # データベース更新
                processed_count = self._process_documents_bulk(documents_data, target_date)
                
                self.stdout.write(
                    self.style.SUCCESS(f'データ取得成功: {processed_count}件 (試行 {attempt + 1})')
                )
                
                return processed_count
                
            except Exception as e:
                last_exception = e
                
                if attempt < retry_count:
                    wait_time = 2 ** attempt  # 指数バックオフ
                    self.stdout.write(
                        self.style.WARNING(f'試行 {attempt + 1} 失敗: {e}')
                    )
                    self.stdout.write(f'{wait_time}秒待機後に再試行...')
                    
                    import time
                    time.sleep(wait_time)
                else:
                    self.stdout.write(
                        self.style.ERROR(f'全ての試行が失敗しました。最後のエラー: {e}')
                    )
        
        # 全ての試行が失敗した場合
        raise last_exception
    
    def _process_documents_bulk(self, documents_data, file_date):
        """バルク処理でドキュメント更新"""
        if not documents_data:
            return 0
        
        documents_to_create = []
        existing_doc_ids = set(
            DocumentMetadata.objects.filter(
                doc_id__in=[doc['docID'] for doc in documents_data]
            ).values_list('doc_id', flat=True)
        )
        
        with transaction.atomic():
            for doc_data in documents_data:
                doc_id = doc_data['docID']
                
                if doc_id in existing_doc_ids:
                    # 既存データの更新
                    DocumentMetadata.objects.filter(doc_id=doc_id).update(
                        legal_status=doc_data['legalStatus'],
                        withdrawal_status=doc_data['withdrawalStatus'],
                        doc_info_edit_status=doc_data['docInfoEditStatus'],
                        disclosure_status=doc_data['disclosureStatus'],
                        updated_at=timezone.now()
                    )
                else:
                    # 新規データ作成
                    new_doc = self._create_document_metadata(doc_data, file_date)
                    documents_to_create.append(new_doc)
            
            # バルクインサート
            if documents_to_create:
                DocumentMetadata.objects.bulk_create(documents_to_create, batch_size=1000)
        
        return len(documents_data)
    
    def _create_document_metadata(self, doc_data, file_date):
        """DocumentMetadataオブジェクト作成"""
        return DocumentMetadata(
            doc_id=doc_data['docID'],
            edinet_code=doc_data['edinetCode'] or '',
            securities_code=doc_data['secCode'] or '',
            company_name=doc_data['filerName'] or '',
            fund_code=doc_data['fundCode'] or '',
            ordinance_code=doc_data['ordinanceCode'] or '',
            form_code=doc_data['formCode'] or '',
            doc_type_code=doc_data['docTypeCode'] or '',
            period_start=self._parse_date(doc_data.get('periodStart')),
            period_end=self._parse_date(doc_data.get('periodEnd')),
            submit_date_time=self._parse_datetime(doc_data['submitDateTime']),
            file_date=file_date,
            doc_description=doc_data['docDescription'] or '',
            xbrl_flag=doc_data['xbrlFlag'] == '1',
            pdf_flag=doc_data['pdfFlag'] == '1',
            attach_doc_flag=doc_data['attachDocFlag'] == '1',
            english_doc_flag=doc_data['englishDocFlag'] == '1',
            csv_flag=doc_data['csvFlag'] == '1',
            legal_status=doc_data['legalStatus'],
            withdrawal_status=doc_data['withdrawalStatus'],
            doc_info_edit_status=doc_data['docInfoEditStatus'],
            disclosure_status=doc_data['disclosureStatus'],
        )
    
    def _parse_date(self, date_str):
        """日付文字列をDateオブジェクトに変換"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None
    
    def _parse_datetime(self, datetime_str):
        """日時文字列をDateTimeオブジェクトに変換"""
        if not datetime_str:
            return timezone.now()
        try:
            return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        except (ValueError, TypeError):
            return timezone.now()
    
    def _update_company_master(self):
        """企業マスタの自動更新"""
        self.stdout.write('企業マスタ更新中...')
        
        # 新しい企業を抽出
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
                else:
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
                        
            except Exception as e:
                logger.warning(f"企業マスタ更新エラー: {company_name} - {e}")
                continue
        
        self.stdout.write(f'企業マスタ更新完了: 新規{created_count}社, 更新{updated_count}社')
    
    def _send_notification(self, target_date, success, processed_count, error_message):
        """実行結果の通知メール送信"""
        try:
            subject = f'[決算書類管理システム] 日次更新結果 ({target_date})'
            
            if success:
                message = f"""
日次データ更新が正常に完了しました。

実行日: {target_date}
処理件数: {processed_count}件
実行時刻: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

システムは正常に動作しています。
                """.strip()
            else:
                message = f"""
日次データ更新でエラーが発生しました。

実行日: {target_date}
エラー内容: {error_message}
実行時刻: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

システム管理者による確認が必要です。
                """.strip()

            recipients = getattr(settings, 'ADMIN_EMAIL_LIST', ['kabulog.information@gmail.com'])

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=True
            )
            
            self.stdout.write('通知メールを送信しました。')
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'通知メール送信エラー: {e}')
            )
    
    def _show_statistics(self):
        """システム統計の表示"""
        self.stdout.write('\n=== システム統計 ===')
        
        try:
            total_companies = Company.objects.filter(is_active=True).count()
            total_documents = DocumentMetadata.objects.filter(legal_status='1').count()
            recent_batches = BatchExecution.objects.filter(
                batch_date__gte=date.today() - timedelta(days=7)
            ).order_by('-batch_date')
            
            self.stdout.write(f'登録企業数: {total_companies}社')
            self.stdout.write(f'利用可能書類数: {total_documents}件')
            
            success_count = recent_batches.filter(status='SUCCESS').count()
            failed_count = recent_batches.filter(status='FAILED').count()
            
            self.stdout.write(f'過去7日間のバッチ実行: 成功{success_count}回, 失敗{failed_count}回')
            
            if failed_count > 0:
                self.stdout.write(
                    self.style.WARNING('最近失敗したバッチがあります。管理画面で確認してください。')
                )
                
        except Exception as e:
            self.stdout.write(f'統計情報取得エラー: {e}')