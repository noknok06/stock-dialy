# earnings_analysis/management/commands/collect_initial_data.py（修正版）
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction, connection
from django.db.utils import IntegrityError, OperationalError, DatabaseError
from datetime import date, datetime, timedelta
import logging
import time
import random
import gc

from earnings_analysis.models import DocumentMetadata, BatchExecution
from earnings_analysis.services import EdinetAPIClient

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '初期データ収集（デッドロック・制約違反対応版）'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='収集する過去日数（デフォルト: 365日）'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='開始日（YYYY-MM-DD形式）'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='終了日（YYYY-MM-DD形式）'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='既存データがあっても強制実行'
        )
        parser.add_argument(
            '--api-version',
            type=str,
            choices=['v1', 'v2'],
            default='v2',
            help='使用するAPIバージョン（v1はAPIキー不要）'
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=100,
            help='バッチ処理のチャンクサイズ（デフォルト: 100）'
        )
        parser.add_argument(
            '--max-retries',
            type=int,
            default=3,
            help='デッドロック時の最大リトライ回数（デフォルト: 3）'
        )
    
    def handle(self, *args, **options):
        # 初期設定
        self.chunk_size = options['chunk_size']
        self.max_retries = options['max_retries']
        self.initial_memory = self._get_memory_usage()
        
        # 日付設定
        if options['start_date'] and options['end_date']:
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
        else:
            end_date = self._get_last_business_day()
            start_date = end_date - timedelta(days=options['days'])
        
        # 日付の妥当性チェック
        start_date, end_date = self._validate_and_adjust_dates(start_date, end_date, options['days'])
        
        self.stdout.write(
            self.style.SUCCESS(f'初期データ収集開始: {start_date} から {end_date}')
        )
        
        # 日付範囲をチェック
        if start_date > end_date:
            self.stdout.write(
                self.style.ERROR('開始日は終了日より前である必要があります')
            )
            return
        
        # 既存データチェック
        if not options['force']:
            existing_count = DocumentMetadata.objects.count()
            if existing_count > 0:
                self.stdout.write(
                    self.style.WARNING(f'既存データが{existing_count}件あります。')
                )
        
        # データベース最適化設定
        self._optimize_database_settings()
        
        # APIサービス初期化
        document_service = self._initialize_api_service(options)
        if not document_service:
            return
        
        # API接続テスト
        if not self._test_api_connection(document_service):
            return
        
        # メイン処理
        self._process_date_range(document_service, start_date, end_date)
    
    def _validate_and_adjust_dates(self, start_date, end_date, days):
        """日付の妥当性チェックと調整"""
        today = date.today()
        
        if end_date > today:
            end_date = self._get_last_business_day()
            self.stdout.write(
                self.style.WARNING(f'終了日を最新の営業日 {end_date} に変更しました。')
            )
        
        if start_date > today:
            start_date = end_date - timedelta(days=days)
            self.stdout.write(
                self.style.WARNING(f'開始日を {start_date} に変更しました。')
            )
        
        # 営業日に調整
        start_date = self._adjust_to_business_day(start_date)
        end_date = self._adjust_to_business_day(end_date)
        
        # 最終チェック
        if start_date >= today:
            start_date = self._get_last_business_day(days_back=days)
        if end_date >= today:
            end_date = self._get_last_business_day()
        
        return start_date, end_date
    
    def _optimize_database_settings(self):
        """データベース設定の最適化"""
        try:
            with connection.cursor() as cursor:
                # トランザクション分離レベル設定
                cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                # ロックタイムアウト設定
                cursor.execute("SET lock_timeout = '30s'")
                # デッドロック検出時間短縮
                cursor.execute("SET deadlock_timeout = '1s'")
                # ステートメントタイムアウト
                cursor.execute("SET statement_timeout = '300s'")
                
            self.stdout.write('データベース設定を最適化しました。')
        except Exception as e:
            logger.warning(f"データベース設定最適化エラー: {e}")
    
    def _initialize_api_service(self, options):
        """APIサービスの初期化"""
        try:
            from earnings_analysis.services import EdinetDocumentService
            api_version = options.get('api_version', 'v2')
            
            if api_version == 'v1':
                self.stdout.write(
                    self.style.WARNING('v1 APIを使用します（APIキー不要、ただし機能が制限される場合があります）')
                )
                return EdinetDocumentService(prefer_v1=True)
            else:
                from django.conf import settings
                api_key = getattr(settings, 'EDINET_API_SETTINGS', {}).get('API_KEY', '')
                if not api_key:
                    self.stdout.write(
                        self.style.ERROR('v2 API使用にはAPIキーが必要です。')
                    )
                    self.stdout.write('解決方法:')
                    self.stdout.write('1. python manage.py check_api_key でAPIキーを確認')
                    self.stdout.write('2. --api-version v1 でv1 APIを使用')
                    return None
                return EdinetDocumentService(prefer_v1=False)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'APIサービス初期化エラー: {e}')
            )
            return None
    
    def _test_api_connection(self, document_service):
        """API接続テスト"""
        test_date = self._get_last_business_day(days_back=7)
        self.stdout.write(f'EDINET API接続テストを実行中... (テスト日: {test_date})')
        
        try:
            response = document_service.get_document_list_with_fallback(test_date.isoformat(), type=2)
            self.stdout.write(
                self.style.SUCCESS(f'API接続テスト成功: ステータス={response.get("metadata", {}).get("status", "unknown")}')
            )
            return True
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'API接続テスト失敗: {e}')
            )
            self.stdout.write('解決策:')
            self.stdout.write('1. 営業日の日付で再試行してください')
            self.stdout.write('2. APIキー設定を確認してください')
            self.stdout.write('3. ネットワーク接続を確認してください')
            return False
    
    def _process_date_range(self, document_service, start_date, end_date):
        """日付範囲の処理"""
        current_date = start_date
        total_processed = 0
        success_count = 0
        error_count = 0
        
        try:
            while current_date <= end_date:
                self.stdout.write(f'処理中: {current_date}')
                
                try:
                    # デッドロック防止機能付き日次データ収集
                    processed_count = self._collect_date_data_with_retry(document_service, current_date)
                    total_processed += processed_count
                    success_count += 1
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'  完了: {processed_count}件')
                    )
                    
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'  エラー: {current_date} - {e}')
                    )
                    logger.error(f"日次収集エラー: {current_date} - {e}")
                    
                    # 連続エラーが多い場合は処理を停止
                    if error_count >= 5 and success_count == 0:
                        self.stdout.write(
                            self.style.ERROR('連続してエラーが発生しています。処理を停止します。')
                        )
                        break
                
                # メモリ管理
                self._check_memory_usage(f"日次処理 {current_date}")
                
                current_date += timedelta(days=1)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'初期データ収集完了: 総計{total_processed}件 '
                    f'(成功: {success_count}日, エラー: {error_count}日)'
                )
            )
            
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING(f'処理を中断しました。{total_processed}件処理済み。')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'予期しないエラー: {e}')
            )
            logger.error(f"初期データ収集エラー: {e}")
    
    def _collect_date_data_with_retry(self, document_service, target_date):
        """リトライ機能付き日次データ収集"""
        for attempt in range(self.max_retries):
            try:
                return self._collect_date_data_safe(document_service, target_date)
            except (OperationalError, DatabaseError) as e:
                error_msg = str(e).lower()
                
                if 'deadlock' in error_msg or 'lock_timeout' in error_msg:
                    if attempt < self.max_retries - 1:
                        # 指数バックオフでリトライ
                        sleep_time = 0.1 * (2 ** attempt) + random.uniform(0, 0.1)
                        logger.warning(f"デッドロック検出、{sleep_time:.2f}秒後にリトライ: {target_date}")
                        time.sleep(sleep_time)
                        continue
                    else:
                        logger.error(f"デッドロック解決失敗: {target_date}")
                        self._record_batch_failure(target_date, f"デッドロック: {e}")
                        raise
                else:
                    # その他のDBエラー
                    self._record_batch_failure(target_date, str(e))
                    raise
            except Exception as e:
                # 非DBエラー
                self._record_batch_failure(target_date, str(e))
                raise
    
    def _collect_date_data_safe(self, document_service, target_date):
        """安全な日次データ収集"""
        date_str = target_date.isoformat()
        
        # Step1: BatchExecutionを安全に取得・作成
        batch_execution = self._get_or_create_batch_safe(target_date)
        
        if batch_execution.status == 'SUCCESS':
            return batch_execution.processed_count
        
        # Step2: 処理中状態に更新
        batch_execution.status = 'RUNNING'
        batch_execution.started_at = timezone.now()
        batch_execution.save(update_fields=['status', 'started_at'])
        
        try:
            # Step3: API呼び出し（トランザクション外）
            documents_data = self._fetch_documents_safe(document_service, date_str)
            
            if not documents_data:
                batch_execution.status = 'SUCCESS'
                batch_execution.processed_count = 0
                batch_execution.completed_at = timezone.now()
                batch_execution.save(update_fields=['status', 'processed_count', 'completed_at'])
                return 0
            
            # Step4: チャンク単位でデータ処理
            processed_count = self._process_documents_in_chunks(documents_data, target_date)
            
            # Step5: 成功記録
            batch_execution.status = 'SUCCESS'
            batch_execution.processed_count = processed_count
            batch_execution.completed_at = timezone.now()
            batch_execution.save(update_fields=['status', 'processed_count', 'completed_at'])
            
            return processed_count
            
        except Exception as e:
            # エラー記録
            batch_execution.status = 'FAILED'
            batch_execution.error_message = str(e)[:500]
            batch_execution.completed_at = timezone.now()
            batch_execution.save(update_fields=['status', 'error_message', 'completed_at'])
            raise
    
    def _get_or_create_batch_safe(self, target_date):
        """安全なBatchExecution取得・作成"""
        try:
            # 既存レコードをロック付きで取得
            return BatchExecution.objects.select_for_update(nowait=False).get(
                batch_date=target_date
            )
        except BatchExecution.DoesNotExist:
            # 存在しない場合は作成
            try:
                return BatchExecution.objects.create(
                    batch_date=target_date,
                    status='RUNNING',
                    started_at=timezone.now()
                )
            except IntegrityError:
                # 作成中に他のプロセスが作成した場合、再取得
                return BatchExecution.objects.select_for_update().get(
                    batch_date=target_date
                )
    
    def _fetch_documents_safe(self, document_service, date_str):
        """安全なドキュメント取得"""
        response = document_service.get_document_list_with_fallback(date_str, type=2)
        
        # レスポンス形式チェック
        if 'statusCode' in response and response['statusCode'] != 200:
            raise Exception(f"EDINET API Error (Code: {response['statusCode']}): {response.get('message', 'Unknown error')}")
        
        if 'metadata' in response:
            if response['metadata'].get('status') != '200':
                raise Exception(f"EDINET API Error: {response['metadata'].get('message', 'Unknown error')}")
            return response.get('results', [])
        else:
            return response.get('results', [])
    
    def _process_documents_in_chunks(self, documents_data, file_date):
        """チャンク単位での安全な処理"""
        total_processed = 0
        
        for i in range(0, len(documents_data), self.chunk_size):
            chunk = documents_data[i:i + self.chunk_size]
            
            try:
                processed_count = self._process_single_chunk_safe(chunk, file_date)
                total_processed += processed_count
                
                # チャンク間で短い休憩
                if i + self.chunk_size < len(documents_data):
                    time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"チャンク処理エラー ({i}-{i+self.chunk_size}): {e}")
                continue  # チャンクの失敗は記録して継続
        
        return total_processed
    
    def _process_single_chunk_safe(self, chunk_data, file_date):
        """単一チャンクの安全な処理"""
        with transaction.atomic():
            doc_ids = [doc['docID'] for doc in chunk_data]
            
            # ロック付きで既存データ取得
            existing_docs = {
                doc.doc_id: doc for doc in 
                DocumentMetadata.objects.select_for_update(
                    skip_locked=True  # ロック済みレコードはスキップ
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
        
        return created_count
    
    def _record_batch_failure(self, target_date, error_message):
        """バッチ失敗の記録"""
        try:
            with transaction.atomic():
                BatchExecution.objects.update_or_create(
                    batch_date=target_date,
                    defaults={
                        'status': 'FAILED',
                        'error_message': error_message[:500],
                        'completed_at': timezone.now()
                    }
                )
        except Exception as e:
            logger.error(f"バッチ失敗記録エラー: {e}")
    
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
                
                if memory_increase > 500:  # 500MB以上増加
                    logger.warning(f"メモリ使用量増加: {memory_increase:.1f}MB ({operation_name})")
                    
                    # ガベージコレクション実行
                    collected = gc.collect()
                    logger.info(f"ガベージコレクション実行: {collected}個のオブジェクトを回収")
        except Exception as e:
            logger.debug(f"メモリチェックエラー: {e}")
    
    # 既存のヘルパーメソッド（変更なし）
    def _get_last_business_day(self, days_back=1):
        """最新の営業日を取得（土日を避ける）"""
        target_date = date.today() - timedelta(days=days_back)
        while target_date.weekday() >= 5:
            target_date -= timedelta(days=1)
        return target_date
    
    def _adjust_to_business_day(self, target_date):
        """営業日に調整（土日の場合は直前の金曜日）"""
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