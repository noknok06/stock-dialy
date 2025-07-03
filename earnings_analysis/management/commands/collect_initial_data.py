from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import date, datetime, timedelta
import logging

from earnings_analysis.models import DocumentMetadata, BatchExecution
from earnings_analysis.services import EdinetAPIClient

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '初期データ収集'
    
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
    
    def handle(self, *args, **options):
        if options['start_date'] and options['end_date']:
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
        else:
            # 過去の営業日を使用（土日祝日を避ける）
            end_date = self._get_last_business_day()
            start_date = end_date - timedelta(days=options['days'])
        
        # 未来の日付をチェック（重要な修正）
        today = date.today()
        if end_date > today:
            # 最新の営業日に調整
            end_date = self._get_last_business_day()
            self.stdout.write(
                self.style.WARNING(f'終了日を最新の営業日 {end_date} に変更しました。')
            )
        
        if start_date > today:
            start_date = end_date - timedelta(days=options['days'])
            self.stdout.write(
                self.style.WARNING(f'開始日を {start_date} に変更しました。')
            )
        
        # 両方とも営業日に調整
        start_date = self._adjust_to_business_day(start_date)
        end_date = self._adjust_to_business_day(end_date)
        
        # 日付が現在より未来にならないように最終チェック
        if start_date >= today:
            start_date = self._get_last_business_day(days_back=options['days'])
        if end_date >= today:
            end_date = self._get_last_business_day()
        
        self.style.SUCCESS(f'初期データ収集開始: {start_date} から {end_date}')
        self.stdout.write('EDINET API接続テストを実行中...')
        
        # 日付範囲をチェック
        if start_date > end_date:

            self.style.ERROR('開始日は終了日より前である必要があります')

            return
        
        # 既存データチェック
        if not options['force']:
            existing_count = DocumentMetadata.objects.count()
            if existing_count > 0:
                self.stdout.write(
                    self.style.WARNING(f'既存データが{existing_count}件あります。')
                )
                self.stdout.write('継続しますか？ (y/N): ', ending='')
                choice = input().lower()
                if choice != 'y':
                    self.stdout.write('処理を中止しました。')
                    return
        
        current_date = start_date
        total_processed = 0
        success_count = 0
        error_count = 0
        
        try:
            # APIクライアントを初期化（EdinetDocumentServiceを使用）
            from earnings_analysis.services import EdinetDocumentService
            api_version = options.get('api_version', 'v2')
            
            if api_version == 'v1':
                self.stdout.write(
                    self.style.WARNING('v1 APIを使用します（APIキー不要、ただし機能が制限される場合があります）')
                )
                document_service = EdinetDocumentService(prefer_v1=True)
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
                    return
                document_service = EdinetDocumentService(prefer_v1=False)
            
            # APIの接続テスト（営業日で試行）
            test_date = self._get_last_business_day(days_back=7)  # 1週間前の営業日
            self.stdout.write(f'EDINET API接続テストを実行中... (テスト日: {test_date})')
            test_result = self._test_api_connection(document_service, test_date)
            if not test_result:
                self.stdout.write(
                    self.style.ERROR('API接続テストに失敗しました。')
                )
                self.stdout.write('解決策:')
                self.stdout.write('1. 営業日の日付で再試行してください')
                self.stdout.write('2. APIキー設定を確認してください')
                self.stdout.write('3. ネットワーク接続を確認してください')
                return
            
            while current_date <= end_date:
                # 土日をスキップ
                if current_date.weekday() >= 5:  # 5=土曜, 6=日曜
                    self.stdout.write(f'スキップ（休日）: {current_date}')
                    current_date += timedelta(days=1)
                    continue
                
                self.stdout.write(f'処理中: {current_date}')
                
                try:
                    # 日次データ収集
                    processed_count = self._collect_date_data(document_service, current_date)
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
                
                current_date += timedelta(days=1)
            
            self.stdout.write(
                self.style.SUCCESS(f'初期データ収集完了: 総計{total_processed}件 (成功: {success_count}日, エラー: {error_count}日)')
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
    
    def _get_last_business_day(self, days_back=1):
        """最新の営業日を取得（土日を避ける）"""
        target_date = date.today() - timedelta(days=days_back)
        
        # 土日を避ける
        while target_date.weekday() >= 5:  # 5=土曜, 6=日曜
            target_date -= timedelta(days=1)
        
        return target_date
    
    def _adjust_to_business_day(self, target_date):
        """営業日に調整（土日の場合は直前の金曜日）"""
        while target_date.weekday() >= 5:  # 5=土曜, 6=日曜
            target_date -= timedelta(days=1)
        return target_date
            
    def _test_api_connection(self, document_service, test_date):
        """API接続テスト"""
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
            return False
    
    def _collect_date_data(self, document_service, target_date):
        """指定日のデータ収集"""
        date_str = target_date.isoformat()
        
        # バッチ実行記録作成・確認
        batch_execution, created = BatchExecution.objects.get_or_create(
            batch_date=target_date,
            defaults={
                'status': 'RUNNING',
                'started_at': timezone.now()
            }
        )
        
        if not created and batch_execution.status == 'SUCCESS':
            # 既に成功している場合はスキップ
            return batch_execution.processed_count
        
        try:
            # フォールバック機能付きでEDINET APIから書類一覧取得
            response = document_service.get_document_list_with_fallback(date_str, type=2)
            
            # レスポンス形式をチェック（v2 APIの新形式に対応）
            if 'statusCode' in response and response['statusCode'] != 200:
                raise Exception(f"EDINET API Error (Code: {response['statusCode']}): {response.get('message', 'Unknown error')}")
            
            # 従来のmetadata形式もサポート
            if 'metadata' in response:
                if response['metadata'].get('status') != '200':
                    raise Exception(f"EDINET API Error: {response['metadata'].get('message', 'Unknown error')}")
                documents_data = response.get('results', [])
            else:
                # 新しい形式（診断で確認された形式）
                if 'results' in response:
                    documents_data = response['results']
                else:
                    # 不明な形式
                    logger.warning(f"予期しないレスポンス形式: {response}")
                    documents_data = []
            
            # データが0件の場合も正常として処理
            if not documents_data:
                batch_execution.status = 'SUCCESS'
                batch_execution.processed_count = 0
                batch_execution.completed_at = timezone.now()
                batch_execution.save()
                return 0
            
            # バルク処理でデータベース更新
            with transaction.atomic():
                processed_count = self._process_documents_bulk(documents_data, target_date)
            
            # 成功記録
            batch_execution.status = 'SUCCESS'
            batch_execution.processed_count = processed_count
            batch_execution.completed_at = timezone.now()
            batch_execution.save()
            
            return processed_count
            
        except Exception as e:
            # エラー記録
            batch_execution.status = 'FAILED'
            batch_execution.error_message = str(e)
            batch_execution.completed_at = timezone.now()
            batch_execution.save()
            
            raise
    
    def _process_documents_bulk(self, documents_data, file_date):
        """バルク処理でドキュメント更新"""
        documents_to_create = []
        existing_doc_ids = set(
            DocumentMetadata.objects.filter(
                doc_id__in=[doc['docID'] for doc in documents_data]
            ).values_list('doc_id', flat=True)
        )
        
        for doc_data in documents_data:
            doc_id = doc_data['docID']
            
            if doc_id in existing_doc_ids:
                # 既存データの更新（ステータス変更等）
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