# earnings_analysis/management/commands/daily_update.py（修正版）
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction, connection
from django.db.utils import IntegrityError, OperationalError, DatabaseError
from django.core.mail import send_mail
from django.conf import settings
from datetime import date, datetime, timedelta
import logging
import traceback
import time
import random
import gc

from earnings_analysis.models import DocumentMetadata, BatchExecution, Company
from earnings_analysis.services import EdinetDocumentService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '日次データ更新（本番運用用・制約違反対応版）'
    
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
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=100,
            help='バッチ処理のチャンクサイズ'
        )
        parser.add_argument(
            '--db-retry-count',
            type=int,
            default=3,
            help='データベースエラー時のリトライ回数'
        )
        parser.add_argument(
            '--stop-on-error',
            action='store_true',
            help='エラー発生時に即座に停止（デフォルトは継続）'
        )
    
    def handle(self, *args, **options):
        # 初期設定
        self.chunk_size = options['chunk_size']
        self.db_retry_count = options['db_retry_count']
        self.stop_on_error = options['stop_on_error']
        self.initial_memory = self._get_memory_usage()
        
        target_date = options.get('date')
        force = options.get('force', False)
        send_notification = options.get('send_notification', False)
        api_version = options.get('api_version', 'v2')
        retry_count = options.get('retry_count', 3)
        
        # 実行前チェック
        if not self._pre_execution_check():
            return
        
        # 対象日の決定と検証
        target_date = self._determine_target_date(target_date)
        if not target_date:
            return
        
        self.stdout.write(f'日次データ更新開始: {target_date}')
        
        # データベース最適化設定
        self._optimize_database_settings()
        
        # バッチ実行管理
        success = False
        error_message = ''
        processed_count = 0
        
        try:
            # 安全なバッチ実行記録の作成・取得
            batch_execution = self._get_or_create_batch_safe(target_date, force)
            if not batch_execution:
                return
            
            # メイン処理実行
            processed_count = self._execute_main_process(
                batch_execution, target_date, api_version, retry_count
            )
            
            # 企業マスタ更新（安全版）
            self._update_company_master_safe()
            
            # 成功処理
            self._record_batch_success(batch_execution, processed_count)
            success = True
            
            self.stdout.write(
                self.style.SUCCESS(f'日次データ更新完了: {processed_count}件処理')
            )
            
        except Exception as e:
            # エラー処理
            error_message = str(e)
            self._record_batch_failure(target_date, error_message, e)
            
            self.stdout.write(
                self.style.ERROR(f'日次データ更新エラー: {error_message}')
            )
            logger.error(f"日次更新エラー: {target_date} - {error_message}", exc_info=True)
            
            # stop-on-error オプションが有効な場合は即座に終了
            if self.stop_on_error:
                self.stdout.write(
                    self.style.ERROR('--stop-on-error オプションが有効のため、処理を停止します。')
                )
                raise  # エラーを再発生させて終了コード1で終了
        
        # 通知送信
        if send_notification:
            self._send_notification(target_date, success, processed_count, error_message)
        
        # 統計レポート
        self._show_statistics()
        
        # メモリクリーンアップ
        self._cleanup_memory()
    
    def _pre_execution_check(self):
        """実行前チェック"""
        try:
            # データベース接続確認
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            # 重要テーブルの存在確認
            if not DocumentMetadata.objects.model._meta.db_table:
                self.stdout.write(
                    self.style.ERROR('DocumentMetadataテーブルにアクセスできません。')
                )
                return False
            
            self.stdout.write('実行前チェック完了')
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'実行前チェック失敗: {e}')
            )
            return False
    
    def _determine_target_date(self, target_date_str):
        """対象日の決定と検証"""
        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('無効な日付形式です。YYYY-MM-DD形式で指定してください。')
                )
                return None
        else:
            target_date = self._get_last_business_day()
        
        # 未来の日付チェック
        if target_date >= date.today():
            self.stdout.write(
                self.style.ERROR('未来の日付は指定できません。')
            )
            return None
        
        # 土日チェック
        if target_date.weekday() >= 5:
            self.stdout.write(
                self.style.WARNING(f'{target_date} は休日です。営業日に調整します。')
            )
            target_date = self._adjust_to_business_day(target_date)
        
        return target_date
    
    def _optimize_database_settings(self):
        """データベース設定の最適化"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                cursor.execute("SET lock_timeout = '30s'")
                cursor.execute("SET deadlock_timeout = '1s'")
                cursor.execute("SET statement_timeout = '300s'")
            
            self.stdout.write('データベース設定を最適化しました。')
        except Exception as e:
            logger.warning(f"データベース設定最適化エラー: {e}")
    
    def _get_or_create_batch_safe(self, target_date, force):
        """安全なバッチ実行記録の作成・取得"""
        for attempt in range(self.db_retry_count):
            try:
                with transaction.atomic():
                    batch_execution, created = BatchExecution.objects.select_for_update().get_or_create(
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
                        return None
                    
                    # 処理中状態に更新
                    batch_execution.status = 'RUNNING'
                    batch_execution.started_at = timezone.now()
                    batch_execution.error_message = ''
                    batch_execution.save()
                    
                    return batch_execution
                    
            except (IntegrityError, OperationalError, DatabaseError) as e:
                if attempt < self.db_retry_count - 1:
                    sleep_time = 0.1 * (2 ** attempt) + random.uniform(0, 0.1)
                    logger.warning(f"バッチ作成リトライ {attempt + 1}: {e}")
                    time.sleep(sleep_time)
                    continue
                else:
                    raise Exception(f"バッチ実行記録の作成に失敗: {e}")
    
    def _execute_main_process(self, batch_execution, target_date, api_version, retry_count):
        """メイン処理の実行"""
        try:
            # API呼び出しでデータ取得
            documents_data = self._execute_update_with_retry(target_date, api_version, retry_count)
            
            if not documents_data:
                self.stdout.write('取得データが0件でした。')
                return 0
            
            # 安全なバルク処理
            processed_count = self._process_documents_bulk_safe(documents_data, target_date)
            
            return processed_count
            
        except Exception as e:
            logger.error(f"メイン処理エラー: {e}")
            raise
    
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
                
                # レスポンス処理
                if 'statusCode' in response and response['statusCode'] != 200:
                    raise Exception(f"EDINET API Error (Code: {response['statusCode']}): {response.get('message', 'Unknown error')}")
                
                if 'metadata' in response:
                    if response['metadata'].get('status') != '200':
                        raise Exception(f"EDINET API Error: {response['metadata'].get('message', 'Unknown error')}")
                    documents_data = response.get('results', [])
                else:
                    documents_data = response.get('results', [])
                
                self.stdout.write(
                    self.style.SUCCESS(f'データ取得成功: {len(documents_data)}件 (試行 {attempt + 1})')
                )
                
                return documents_data
                
            except Exception as e:
                last_exception = e
                
                if attempt < retry_count:
                    wait_time = 2 ** attempt  # 指数バックオフ
                    self.stdout.write(
                        self.style.WARNING(f'試行 {attempt + 1} 失敗: {e}')
                    )
                    self.stdout.write(f'{wait_time}秒待機後に再試行...')
                    time.sleep(wait_time)
                else:
                    self.stdout.write(
                        self.style.ERROR(f'全ての試行が失敗しました。最後のエラー: {e}')
                    )
        
        # 全ての試行が失敗した場合
        raise last_exception
    
    def _process_documents_bulk_safe(self, documents_data, file_date):
        """安全なバルク処理でドキュメント更新"""
        if not documents_data:
            return 0
        
        total_processed = 0
        
        # チャンク単位で処理
        for i in range(0, len(documents_data), self.chunk_size):
            chunk = documents_data[i:i + self.chunk_size]
            
            try:
                processed_count = self._process_single_chunk_safe(chunk, file_date)
                total_processed += processed_count
                
                # メモリチェック
                if i % (self.chunk_size * 5) == 0:  # 5チャンクごと
                    self._check_memory_usage(f"チャンク処理 {i//self.chunk_size + 1}")
                
                # チャンク間で短い休憩
                if i + self.chunk_size < len(documents_data):
                    time.sleep(0.01)
                    
            except Exception as e:
                logger.error(f"チャンク処理エラー ({i}-{i+self.chunk_size}): {e}")
                if self.stop_on_error:
                    raise  # エラー時停止オプションが有効な場合は即座に停止
                continue  # そうでなければ継続
        
        return total_processed
    
    def _process_single_chunk_safe(self, chunk_data, file_date):
        """単一チャンクの安全な処理"""
        for attempt in range(self.db_retry_count):
            try:
                with transaction.atomic():
                    doc_ids = [doc['docID'] for doc in chunk_data]
                    
                    # ロック付きで既存データ取得
                    existing_docs = {
                        doc.doc_id: doc for doc in 
                        DocumentMetadata.objects.select_for_update(
                            skip_locked=True
                        ).filter(doc_id__in=doc_ids)
                    }
                    
                    documents_to_create = []
                    documents_to_update = []
                    
                    for doc_data in chunk_data:
                        doc_id = doc_data['docID']
                        
                        if doc_id in existing_docs:
                            # 既存データの更新
                            existing_doc = existing_docs[doc_id]
                            existing_doc.legal_status = doc_data['legalStatus']
                            existing_doc.withdrawal_status = doc_data['withdrawalStatus']
                            existing_doc.doc_info_edit_status = doc_data['docInfoEditStatus']
                            existing_doc.disclosure_status = doc_data['disclosureStatus']
                            existing_doc.updated_at = timezone.now()
                            documents_to_update.append(existing_doc)
                        else:
                            # 新規データ作成
                            new_doc = self._create_document_metadata(doc_data, file_date)
                            documents_to_create.append(new_doc)
                    
                    # バルク更新
                    if documents_to_update:
                        DocumentMetadata.objects.bulk_update(
                            documents_to_update,
                            ['legal_status', 'withdrawal_status', 'doc_info_edit_status', 
                             'disclosure_status', 'updated_at'],
                            batch_size=50
                        )
                    
                    # バルク作成（ignore_conflicts で重複を無視）
                    created_count = 0
                    if documents_to_create:
                        try:
                            created_objects = DocumentMetadata.objects.bulk_create(
                                documents_to_create, 
                                batch_size=50,
                                ignore_conflicts=True
                            )
                            created_count = len(created_objects)
                        except Exception as e:
                            # フォールバック: 個別作成
                            logger.warning(f"バルク作成失敗、個別処理に切り替え: {e}")
                            created_count = self._individual_create_fallback(documents_to_create)
                
                return len(chunk_data)
                
            except (OperationalError, DatabaseError) as e:
                error_msg = str(e).lower()
                
                if 'deadlock' in error_msg or 'lock_timeout' in error_msg:
                    if attempt < self.db_retry_count - 1:
                        sleep_time = 0.1 * (2 ** attempt) + random.uniform(0, 0.1)
                        logger.warning(f"デッドロック検出、リトライ {attempt + 1}: {e}")
                        time.sleep(sleep_time)
                        continue
                    else:
                        logger.error(f"デッドロック解決失敗")
                        if self.stop_on_error:
                            raise
                        return 0  # 失敗として0を返す
                else:
                    logger.error(f"データベースエラー: {e}")
                    if self.stop_on_error:
                        raise
                    return 0
    
    def _individual_create_fallback(self, documents_to_create):
        """個別作成のフォールバック"""
        created_count = 0
        for doc in documents_to_create:
            try:
                DocumentMetadata.objects.get_or_create(
                    doc_id=doc.doc_id,
                    defaults={
                        'edinet_code': doc.edinet_code,
                        'securities_code': doc.securities_code,
                        'company_name': doc.company_name,
                        'fund_code': doc.fund_code,
                        'ordinance_code': doc.ordinance_code,
                        'form_code': doc.form_code,
                        'doc_type_code': doc.doc_type_code,
                        'period_start': doc.period_start,
                        'period_end': doc.period_end,
                        'submit_date_time': doc.submit_date_time,
                        'file_date': doc.file_date,
                        'doc_description': doc.doc_description,
                        'xbrl_flag': doc.xbrl_flag,
                        'pdf_flag': doc.pdf_flag,
                        'attach_doc_flag': doc.attach_doc_flag,
                        'english_doc_flag': doc.english_doc_flag,
                        'csv_flag': doc.csv_flag,
                        'legal_status': doc.legal_status,
                        'withdrawal_status': doc.withdrawal_status,
                        'doc_info_edit_status': doc.doc_info_edit_status,
                        'disclosure_status': doc.disclosure_status,
                    }
                )
                created_count += 1
            except Exception as e:
                logger.warning(f"個別作成失敗 {doc.doc_id}: {e}")
                if self.stop_on_error:
                    raise
        
        return created_count
    
    def _update_company_master_safe(self):
        """企業マスタの安全な自動更新"""
        self.stdout.write('企業マスタ更新中...')
        
        try:
            # 新しい企業を抽出（効率的なクエリ）
            unique_companies = DocumentMetadata.objects.filter(
                legal_status='1'
            ).values(
                'edinet_code', 'securities_code', 'company_name'
            ).distinct()
            
            created_count = 0
            updated_count = 0
            error_count = 0
            
            for company_data in unique_companies:
                edinet_code = company_data['edinet_code']
                securities_code = company_data['securities_code']
                company_name = company_data['company_name']
                
                if not edinet_code or not company_name:
                    continue
                
                try:
                    with transaction.atomic():
                        company, created = Company.objects.select_for_update().get_or_create(
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
                    error_count += 1
                    logger.warning(f"企業マスタ更新エラー: {company_name} - {e}")
                    if self.stop_on_error:
                        raise
                    continue
            
            self.stdout.write(
                f'企業マスタ更新完了: 新規{created_count}社, 更新{updated_count}社, エラー{error_count}社'
            )
            
        except Exception as e:
            logger.error(f"企業マスタ更新エラー: {e}")
            if self.stop_on_error:
                raise
    
    def _record_batch_success(self, batch_execution, processed_count):
        """バッチ成功記録"""
        try:
            batch_execution.status = 'SUCCESS'
            batch_execution.processed_count = processed_count
            batch_execution.completed_at = timezone.now()
            batch_execution.save()
        except Exception as e:
            logger.error(f"バッチ成功記録エラー: {e}")
    
    def _record_batch_failure(self, target_date, error_message, exception):
        """バッチ失敗記録"""
        try:
            with transaction.atomic():
                BatchExecution.objects.update_or_create(
                    batch_date=target_date,
                    defaults={
                        'status': 'FAILED',
                        'error_message': f"{error_message}\n\n{traceback.format_exc()}"[:1000],  # 1000文字制限
                        'completed_at': timezone.now()
                    }
                )
        except Exception as e:
            logger.error(f"バッチ失敗記録エラー: {e}")
    
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
メモリ使用量: {self._get_memory_usage():.1f}MB

システムは正常に動作しています。
                """.strip()
            else:
                message = f"""
日次データ更新でエラーが発生しました。

実行日: {target_date}
エラー内容: {error_message}
実行時刻: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
停止オプション: {'有効' if self.stop_on_error else '無効'}

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
            
            # メモリ使用量表示
            current_memory = self._get_memory_usage()
            if current_memory > 0:
                memory_increase = current_memory - self.initial_memory
                self.stdout.write(f'メモリ使用量: {current_memory:.1f}MB (増加: {memory_increase:+.1f}MB)')
            
            if failed_count > 0:
                self.stdout.write(
                    self.style.WARNING('最近失敗したバッチがあります。管理画面で確認してください。')
                )
                
        except Exception as e:
            self.stdout.write(f'統計情報取得エラー: {e}')
    
    def _get_memory_usage(self):
        """現在のメモリ使用量（MB）"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0
    
    def _check_memory_usage(self, operation_name):
        """メモリ使用量チェック"""
        try:
            current_memory = self._get_memory_usage()
            if current_memory > 0:
                memory_increase = current_memory - self.initial_memory
                
                if memory_increase > 300:  # 300MB以上増加
                    logger.warning(f"メモリ使用量増加: {memory_increase:.1f}MB ({operation_name})")
                    
                    # ガベージコレクション実行
                    collected = gc.collect()
                    logger.info(f"ガベージコレクション実行: {collected}個のオブジェクトを回収")
        except Exception as e:
            logger.debug(f"メモリチェックエラー: {e}")
    
    def _cleanup_memory(self):
        """メモリクリーンアップ"""
        try:
            collected = gc.collect()
            final_memory = self._get_memory_usage()
            if final_memory > 0:
                memory_change = final_memory - self.initial_memory
                self.stdout.write(f'最終メモリ使用量: {final_memory:.1f}MB (変化: {memory_change:+.1f}MB)')
        except Exception as e:
            logger.debug(f"メモリクリーンアップエラー: {e}")
    
    # 既存のヘルパーメソッド（変更なし）
    def _get_last_business_day(self, days_back=1):
        """最新の営業日を取得"""
        target_date = date.today() - timedelta(days=days_back)
        return self._adjust_to_business_day(target_date)
    
    def _adjust_to_business_day(self, target_date):
        """営業日に調整"""
        while target_date.weekday() >= 5:
            target_date -= timedelta(days=1)
        return target_date
    
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