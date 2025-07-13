# earnings_analysis/services/batch_service.py（新規作成）
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from ..models import BatchExecution, DocumentMetadata, Company
from .document_service import EdinetDocumentService

logger = logging.getLogger(__name__)

class BatchService:
    """バッチ処理サービス"""
    
    def __init__(self):
        self.edinet_service = EdinetDocumentService()
    
    def execute_daily_batch(self, target_date_str, force_rerun=False, include_analysis=True):
        """
        日次バッチ処理を実行
        
        Args:
            target_date_str (str): 対象日付 (YYYY-MM-DD)
            force_rerun (bool): 強制再実行フラグ
            include_analysis (bool): 分析処理も実行するか
        
        Returns:
            dict: 実行結果
        """
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            
            # 既存のバッチ実行チェック
            existing_batch = BatchExecution.objects.filter(batch_date=target_date).first()
            
            if existing_batch and existing_batch.status == 'SUCCESS' and not force_rerun:
                return {
                    'success': False,
                    'error': f'{target_date}のバッチは既に正常に実行済みです。強制実行が必要な場合はforce_rerunを有効にしてください。',
                    'existing_batch_id': existing_batch.id
                }
            
            # バッチ実行レコード作成または更新
            if existing_batch:
                batch_execution = existing_batch
                batch_execution.status = 'RUNNING'
                batch_execution.started_at = timezone.now()
                batch_execution.completed_at = None
                batch_execution.error_message = ''
                batch_execution.save()
            else:
                batch_execution = BatchExecution.objects.create(
                    batch_date=target_date,
                    status='RUNNING',
                    started_at=timezone.now()
                )
            
            logger.info(f"バッチ処理開始: {target_date}")
            
            # 処理実行
            with transaction.atomic():
                result = self._execute_batch_logic(target_date, include_analysis)
            
            # 成功時の処理
            batch_execution.status = 'SUCCESS'
            batch_execution.completed_at = timezone.now()
            batch_execution.processed_count = result['processed_count']
            batch_execution.save()
            
            logger.info(f"バッチ処理完了: {target_date}, 処理件数: {result['processed_count']}")
            
            return {
                'success': True,
                'processed_count': result['processed_count'],
                'details': result['details'],
                'batch_id': batch_execution.id
            }
            
        except Exception as e:
            logger.error(f"バッチ処理エラー: {target_date}, エラー: {str(e)}")
            
            # エラー時の処理
            if 'batch_execution' in locals():
                batch_execution.status = 'FAILED'
                batch_execution.completed_at = timezone.now()
                batch_execution.error_message = str(e)
                batch_execution.save()
            
            return {
                'success': False,
                'error': str(e),
                'batch_id': batch_execution.id if 'batch_execution' in locals() else None
            }
    
    def _execute_batch_logic(self, target_date, include_analysis=True):
        """
        バッチ処理のメインロジック
        
        Args:
            target_date (date): 対象日付
            include_analysis (bool): 分析処理も実行するか
        
        Returns:
            dict: 処理結果
        """
        results = {
            'processed_count': 0,
            'details': {
                'documents_fetched': 0,
                'companies_updated': 0,
                'analyses_executed': 0,
                'errors': []
            }
        }
        
        try:
            # 1. 書類データの取得と更新
            documents_result = self._fetch_and_update_documents(target_date)
            results['details']['documents_fetched'] = documents_result['count']
            results['details']['errors'].extend(documents_result['errors'])
            
            # 2. 企業マスタの更新
            companies_result = self._update_companies_master()
            results['details']['companies_updated'] = companies_result['count']
            results['details']['errors'].extend(companies_result['errors'])
            
            # 3. 分析処理の実行（オプション）
            if include_analysis:
                analysis_result = self._execute_analyses(target_date)
                results['details']['analyses_executed'] = analysis_result['count']
                results['details']['errors'].extend(analysis_result['errors'])
            
            # 4. データクリーンアップ
            cleanup_result = self._cleanup_old_data()
            results['details']['cleanup'] = cleanup_result
            
            # 総処理件数
            results['processed_count'] = (
                results['details']['documents_fetched'] +
                results['details']['companies_updated'] +
                results['details']['analyses_executed']
            )
            
            logger.info(f"バッチ処理詳細: {results['details']}")
            
            return results
            
        except Exception as e:
            logger.error(f"バッチロジック実行エラー: {str(e)}")
            results['details']['errors'].append(f"バッチロジックエラー: {str(e)}")
            raise
    
    def _fetch_and_update_documents(self, target_date):
        """書類データの取得と更新"""
        result = {'count': 0, 'errors': []}
        
        try:
            # EDINET APIから書類一覧を取得
            date_str = target_date.strftime('%Y-%m-%d')
            documents_data = self.edinet_service.get_documents_list(date_str)
            
            if not documents_data:
                logger.warning(f"対象日({target_date})の書類データが取得できませんでした")
                return result
            
            # 書類メタデータの更新
            for doc_data in documents_data:
                try:
                    # 既存チェック
                    existing_doc = DocumentMetadata.objects.filter(
                        doc_id=doc_data['docID']
                    ).first()
                    
                    if existing_doc:
                        # 更新処理
                        self._update_document_metadata(existing_doc, doc_data)
                    else:
                        # 新規作成
                        self._create_document_metadata(doc_data)
                    
                    result['count'] += 1
                    
                except Exception as e:
                    error_msg = f"書類({doc_data.get('docID', 'Unknown')})処理エラー: {str(e)}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)
            
            logger.info(f"書類データ処理完了: {result['count']}件")
            
        except Exception as e:
            error_msg = f"書類データ取得エラー: {str(e)}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
        
        return result
    
    def _update_companies_master(self):
        """企業マスタの更新"""
        result = {'count': 0, 'errors': []}
        
        try:
            # 最新の書類データから企業情報を抽出
            recent_documents = DocumentMetadata.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=1),
                legal_status='1'
            ).exclude(
                edinet_code__isnull=True
            ).exclude(
                edinet_code=''
            ).values(
                'edinet_code', 'securities_code', 'company_name'
            ).distinct()
            
            for doc in recent_documents:
                try:
                    company, created = Company.objects.get_or_create(
                        edinet_code=doc['edinet_code'],
                        defaults={
                            'securities_code': doc['securities_code'],
                            'company_name': doc['company_name'],
                            'is_active': True
                        }
                    )
                    
                    if not created:
                        # 既存企業の情報更新
                        updated = False
                        if company.securities_code != doc['securities_code']:
                            company.securities_code = doc['securities_code']
                            updated = True
                        if company.company_name != doc['company_name']:
                            company.company_name = doc['company_name']
                            updated = True
                        
                        if updated:
                            company.save()
                    
                    result['count'] += 1
                    
                except Exception as e:
                    error_msg = f"企業({doc['edinet_code']})更新エラー: {str(e)}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)
            
            logger.info(f"企業マスタ更新完了: {result['count']}件")
            
        except Exception as e:
            error_msg = f"企業マスタ更新エラー: {str(e)}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
        
        return result
    
    def _execute_analyses(self, target_date):
        """分析処理の実行"""
        result = {'count': 0, 'errors': []}
        
        try:
            # 分析対象の書類を取得（決算関連、XBRLあり）
            target_documents = DocumentMetadata.objects.filter(
                file_date=target_date,
                legal_status='1',
                xbrl_flag=True,
                doc_type_code__in=['120', '160', '030']  # 有価証券報告書、半期報告書、有価証券届出書
            )[:10]  # 一度に最大10件まで
            
            for document in target_documents:
                try:
                    # 既に分析済みかチェック
                    recent_analysis = document.has_recent_analysis(hours=24)
                    if recent_analysis:
                        continue
                    
                    # 財務分析を実行
                    analysis_result = self._execute_financial_analysis(document)
                    if analysis_result['success']:
                        result['count'] += 1
                    else:
                        result['errors'].append(analysis_result['error'])
                    
                except Exception as e:
                    error_msg = f"書類({document.doc_id})分析エラー: {str(e)}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)
            
            logger.info(f"分析処理完了: {result['count']}件")
            
        except Exception as e:
            error_msg = f"分析処理エラー: {str(e)}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
        
        return result
    
    def _execute_financial_analysis(self, document):
        """個別の財務分析実行"""
        try:
            from .comprehensive_analyzer import ComprehensiveAnalysisService
            
            service = ComprehensiveAnalysisService()
            result = service.start_comprehensive_analysis(
                document.doc_id, 
                force=False, 
                user_ip='127.0.0.1'  # バッチ処理用
            )
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _cleanup_old_data(self):
        """古いデータのクリーンアップ"""
        result = {'cleaned_sessions': 0, 'cleaned_histories': 0}
        
        try:
            # 期限切れセッションの削除
            from ..models import SentimentAnalysisSession, FinancialAnalysisSession
            
            cutoff_time = timezone.now() - timedelta(days=7)
            
            # 感情分析セッション
            expired_sentiment = SentimentAnalysisSession.objects.filter(
                expires_at__lt=cutoff_time
            )
            sentiment_count = expired_sentiment.count()
            expired_sentiment.delete()
            result['cleaned_sessions'] += sentiment_count
            
            # 財務分析セッション
            expired_financial = FinancialAnalysisSession.objects.filter(
                expires_at__lt=cutoff_time
            )
            financial_count = expired_financial.count()
            expired_financial.delete()
            result['cleaned_sessions'] += financial_count
            
            logger.info(f"データクリーンアップ完了: セッション{result['cleaned_sessions']}件削除")
            
        except Exception as e:
            logger.error(f"データクリーンアップエラー: {str(e)}")
        
        return result
    
    def _create_document_metadata(self, doc_data):
        """新規書類メタデータ作成"""
        try:
            document = DocumentMetadata.objects.create(
                doc_id=doc_data['docID'],
                edinet_code=doc_data.get('edinetCode', ''),
                securities_code=doc_data.get('secCode', ''),
                company_name=doc_data.get('filerName', ''),
                fund_code=doc_data.get('fundCode', ''),
                ordinance_code=doc_data.get('ordinanceCode', ''),
                form_code=doc_data.get('formCode', ''),
                doc_type_code=doc_data.get('docTypeCode', ''),
                period_start=self._parse_date(doc_data.get('periodStart')),
                period_end=self._parse_date(doc_data.get('periodEnd')),
                submit_date_time=self._parse_datetime(doc_data.get('submitDateTime')),
                file_date=self._parse_date(doc_data.get('submitDateTime')),
                doc_description=doc_data.get('docDescription', ''),
                xbrl_flag=doc_data.get('xbrlFlag') == '1',
                pdf_flag=doc_data.get('pdfFlag') == '1',
                attach_doc_flag=doc_data.get('attachDocFlag') == '1',
                english_doc_flag=doc_data.get('englishDocFlag') == '1',
                legal_status=doc_data.get('legalStatus', '1'),
                withdrawal_status=doc_data.get('withdrawalStatus', '0'),
                doc_info_edit_status=doc_data.get('docInfoEditStatus', '0'),
                disclosure_status=doc_data.get('disclosureStatus', '0')
            )
            
            logger.debug(f"書類メタデータ作成: {document.doc_id}")
            return document
            
        except Exception as e:
            logger.error(f"書類メタデータ作成エラー: {str(e)}")
            raise
    
    def _update_document_metadata(self, document, doc_data):
        """既存書類メタデータ更新"""
        try:
            # 更新が必要なフィールドのみ更新
            updated = False
            
            if document.legal_status != doc_data.get('legalStatus', '1'):
                document.legal_status = doc_data.get('legalStatus', '1')
                updated = True
            
            if document.withdrawal_status != doc_data.get('withdrawalStatus', '0'):
                document.withdrawal_status = doc_data.get('withdrawalStatus', '0')
                updated = True
            
            if updated:
                document.save()
                logger.debug(f"書類メタデータ更新: {document.doc_id}")
            
        except Exception as e:
            logger.error(f"書類メタデータ更新エラー: {str(e)}")
            raise
    
    def _parse_date(self, date_str):
        """日付文字列をdateオブジェクトに変換"""
        if not date_str:
            return None
        
        try:
            if len(date_str) >= 10:
                return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
        except ValueError:
            pass
        
        return None
    
    def _parse_datetime(self, datetime_str):
        """日時文字列をdatetimeオブジェクトに変換"""
        if not datetime_str:
            return timezone.now()
        
        try:
            # EDINET APIの日時形式に対応
            if 'T' in datetime_str:
                dt = datetime.strptime(datetime_str[:19], '%Y-%m-%dT%H:%M:%S')
            else:
                dt = datetime.strptime(datetime_str[:19], '%Y-%m-%d %H:%M:%S')
            
            return timezone.make_aware(dt)
            
        except ValueError:
            logger.warning(f"日時パースエラー: {datetime_str}")
            return timezone.now()
    
    def get_batch_status(self, batch_date=None):
        """バッチ実行状況の取得"""
        try:
            if batch_date:
                batch = BatchExecution.objects.filter(batch_date=batch_date).first()
                return {
                    'exists': bool(batch),
                    'status': batch.status if batch else None,
                    'started_at': batch.started_at if batch else None,
                    'completed_at': batch.completed_at if batch else None,
                    'processed_count': batch.processed_count if batch else 0,
                    'error_message': batch.error_message if batch else None
                }
            else:
                # 最近の実行状況を取得
                recent_batches = BatchExecution.objects.order_by('-batch_date')[:5]
                return {
                    'recent_batches': [
                        {
                            'batch_date': batch.batch_date,
                            'status': batch.status,
                            'processed_count': batch.processed_count
                        }
                        for batch in recent_batches
                    ]
                }
                
        except Exception as e:
            logger.error(f"バッチ状況取得エラー: {str(e)}")
            return {'error': str(e)}