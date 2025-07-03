# earnings_analysis/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.management import call_command
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from datetime import date, datetime, timedelta
import traceback

from .models import Company, DocumentMetadata, BatchExecution

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3)
def daily_data_update(self, target_date=None):
    """
    日次データ更新タスク
    毎日自動実行される主要なデータ取得処理
    """
    try:
        logger.info(f"日次データ更新タスク開始: {target_date or '前営業日'}")
        
        # management commandを実行
        call_command(
            'daily_update',
            date=target_date,
            send_notification=True,
            verbosity=2
        )
        
        logger.info("日次データ更新タスク完了")
        return "SUCCESS"
        
    except Exception as exc:
        logger.error(f"日次データ更新タスクエラー: {exc}")
        
        # リトライ処理
        if self.request.retries < self.max_retries:
            logger.info(f"リトライ実行: {self.request.retries + 1}/{self.max_retries}")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        # 最終的に失敗した場合の通知
        send_error_notification.delay(
            subject="日次データ更新タスク失敗",
            message=f"日次データ更新タスクが最終的に失敗しました。\nエラー: {str(exc)}\n\n{traceback.format_exc()}"
        )
        
        raise exc

@shared_task
def update_company_master():
    """
    企業マスタ更新タスク
    書類データから企業情報を抽出・更新
    """
    try:
        logger.info("企業マスタ更新タスク開始")
        
        call_command('update_company_master', verbosity=2)
        
        logger.info("企業マスタ更新タスク完了")
        return "SUCCESS"
        
    except Exception as exc:
        logger.error(f"企業マスタ更新タスクエラー: {exc}")
        raise exc

@shared_task
def weekly_cleanup():
    """
    週次クリーンアップタスク
    古いデータの整理とシステム最適化
    """
    try:
        logger.info("週次クリーンアップタスク開始")
        
        # 古いバッチ実行ログの削除（6ヶ月以上前）
        old_date = date.today() - timedelta(days=180)
        deleted_batches = BatchExecution.objects.filter(
            batch_date__lt=old_date,
            status__in=['SUCCESS', 'FAILED']
        ).delete()
        
        logger.info(f"古いバッチログ削除: {deleted_batches[0]}件")
        
        # 非活性企業の整理
        inactive_companies = Company.objects.filter(
            is_active=False,
            updated_at__lt=timezone.now() - timedelta(days=365)
        )
        
        for company in inactive_companies:
            # 関連書類がない場合は削除
            if not DocumentMetadata.objects.filter(edinet_code=company.edinet_code).exists():
                company.delete()
                logger.info(f"非活性企業削除: {company.company_name}")
        
        logger.info("週次クリーンアップタスク完了")
        return "SUCCESS"
        
    except Exception as exc:
        logger.error(f"週次クリーンアップタスクエラー: {exc}")
        raise exc

@shared_task
def monthly_statistics():
    """
    月次統計レポート作成タスク
    システム利用状況の分析と報告
    """
    try:
        logger.info("月次統計レポート作成開始")
        
        # 前月の統計データ作成
        last_month = date.today().replace(day=1) - timedelta(days=1)
        month_start = last_month.replace(day=1)
        
        # 統計データ収集
        stats = {
            'period': f"{last_month.year}年{last_month.month}月",
            'total_companies': Company.objects.filter(is_active=True).count(),
            'total_documents': DocumentMetadata.objects.filter(legal_status='1').count(),
            'monthly_documents': DocumentMetadata.objects.filter(
                submit_date_time__gte=month_start,
                submit_date_time__lt=month_start + timedelta(days=32),
                legal_status='1'
            ).count(),
            'batch_executions': BatchExecution.objects.filter(
                batch_date__gte=month_start,
                batch_date__lt=month_start + timedelta(days=32)
            ).count(),
            'success_rate': 0,
        }
        
        # 成功率計算
        total_batches = BatchExecution.objects.filter(
            batch_date__gte=month_start,
            batch_date__lt=month_start + timedelta(days=32)
        ).count()
        
        if total_batches > 0:
            success_batches = BatchExecution.objects.filter(
                batch_date__gte=month_start,
                batch_date__lt=month_start + timedelta(days=32),
                status='SUCCESS'
            ).count()
            stats['success_rate'] = round((success_batches / total_batches) * 100, 2)
        
        # 書類種別統計
        doc_type_stats = DocumentMetadata.objects.filter(
            submit_date_time__gte=month_start,
            submit_date_time__lt=month_start + timedelta(days=32),
            legal_status='1'
        ).values('doc_type_code').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # レポートメール作成
        report_content = f"""
決算書類管理システム月次レポート

【期間】{stats['period']}

【基本統計】
- 登録企業数: {stats['total_companies']:,}社
- 総書類数: {stats['total_documents']:,}件
- 当月新着書類: {stats['monthly_documents']:,}件
- バッチ実行回数: {stats['batch_executions']}回
- バッチ成功率: {stats['success_rate']}%

【当月の書類種別TOP10】
        """.strip()
        
        for i, doc_type in enumerate(doc_type_stats, 1):
            report_content += f"\n{i}. {doc_type['doc_type_code']}: {doc_type['count']:,}件"
        
        report_content += f"""

【システム状況】
- 最新データ更新: {timezone.now().strftime('%Y-%m-%d %H:%M')}
- システム稼働状況: 正常

このレポートは自動生成されています。
詳細な分析が必要な場合は管理画面をご確認ください。
        """
        
        # メール送信
        send_mail(
            subject=f"[決算書類管理システム] 月次レポート ({stats['period']})",
            message=report_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=getattr(settings, 'ADMIN_EMAIL_LIST', ['admin@example.com']),
            fail_silently=False
        )
        
        logger.info("月次統計レポート作成完了")
        return "SUCCESS"
        
    except Exception as exc:
        logger.error(f"月次統計レポート作成エラー: {exc}")
        raise exc

@shared_task
def health_check():
    """
    システムヘルスチェックタスク
    定期的なシステム状況確認
    """
    try:
        logger.info("システムヘルスチェック開始")
        
        health_status = {
            'database': False,
            'api_connection': False,
            'recent_updates': False,
            'error_rate': 0,
        }
        
        # データベース接続チェック
        try:
            Company.objects.count()
            health_status['database'] = True
        except Exception:
            logger.error("データベース接続エラー")
        
        # 最近の更新チェック
        recent_batch = BatchExecution.objects.filter(
            batch_date__gte=date.today() - timedelta(days=3)
        ).exists()
        health_status['recent_updates'] = recent_batch
        
        # エラー率チェック
        recent_batches = BatchExecution.objects.filter(
            batch_date__gte=date.today() - timedelta(days=7)
        )
        
        if recent_batches.exists():
            total_batches = recent_batches.count()
            failed_batches = recent_batches.filter(status='FAILED').count()
            health_status['error_rate'] = round((failed_batches / total_batches) * 100, 2)
        
        # 異常検知とアラート
        alerts = []
        
        if not health_status['database']:
            alerts.append("データベース接続エラー")
        
        if not health_status['recent_updates']:
            alerts.append("過去3日間にデータ更新がありません")
        
        if health_status['error_rate'] > 20:
            alerts.append(f"エラー率が高すぎます: {health_status['error_rate']}%")
        
        # アラートがある場合は通知
        if alerts and getattr(settings, 'MONITORING', {}).get('ALERT_EMAIL_ENABLED', False):
            alert_message = "システムで以下の問題が検出されました:\n\n" + "\n".join(f"- {alert}" for alert in alerts)
            
            send_error_notification.delay(
                subject="[緊急] システムアラート",
                message=alert_message
            )
        
        logger.info(f"システムヘルスチェック完了: {health_status}")
        return health_status
        
    except Exception as exc:
        logger.error(f"システムヘルスチェックエラー: {exc}")
        raise exc

@shared_task
def send_error_notification(subject, message):
    """
    エラー通知メール送信タスク
    システムエラーの通知用
    """
    try:
        recipients = getattr(settings, 'ADMIN_EMAIL_LIST', ['admin@example.com'])
        
        send_mail(
            subject=subject,
            message=f"{message}\n\n発生時刻: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False
        )
        
        logger.info(f"エラー通知メール送信完了: {subject}")
        return "SUCCESS"
        
    except Exception as exc:
        logger.error(f"エラー通知メール送信失敗: {exc}")
        raise exc

@shared_task
def api_key_validation():
    """
    APIキー有効性確認タスク
    定期的なAPIキーの動作確認
    """
    try:
        logger.info("APIキー確認タスク開始")
        
        call_command('check_api_key', verbosity=2)
        
        logger.info("APIキー確認タスク完了")
        return "SUCCESS"
        
    except Exception as exc:
        logger.error(f"APIキー確認タスクエラー: {exc}")
        
        # APIキーエラーの場合は即座に通知
        send_error_notification.delay(
            subject="[緊急] EDINET APIキーエラー",
            message=f"EDINET APIキーの確認でエラーが発生しました。\nエラー: {str(exc)}\n\nAPIキーの設定を確認してください。"
        )
        
        raise exc

@shared_task(bind=True)
def bulk_document_download(self, doc_ids, doc_type='pdf'):
    """
    大量書類一括ダウンロードタスク
    管理者用の一括処理機能
    """
    try:
        logger.info(f"一括ダウンロードタスク開始: {len(doc_ids)}件 ({doc_type})")
        
        from .services import EdinetDocumentService
        document_service = EdinetDocumentService()
        
        success_count = 0
        error_count = 0
        
        for i, doc_id in enumerate(doc_ids):
            try:
                # プログレス更新
                progress = int((i / len(doc_ids)) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={'current': i, 'total': len(doc_ids), 'progress': progress}
                )
                
                # ダウンロード実行
                result = document_service.download_document(doc_id, doc_type)
                success_count += 1
                
                logger.info(f"ダウンロード成功: {doc_id} ({result['size']} bytes)")
                
            except Exception as e:
                error_count += 1
                logger.error(f"ダウンロードエラー: {doc_id} - {e}")
                
                # エラーが多すぎる場合は中断
                if error_count > len(doc_ids) * 0.5:  # 50%以上がエラー
                    raise Exception(f"エラー率が高すぎるため処理を中断しました。エラー数: {error_count}")
        
        result = {
            'success_count': success_count,
            'error_count': error_count,
            'total_count': len(doc_ids)
        }
        
        logger.info(f"一括ダウンロードタスク完了: 成功{success_count}件, エラー{error_count}件")
        return result
        
    except Exception as exc:
        logger.error(f"一括ダウンロードタスクエラー: {exc}")
        raise exc