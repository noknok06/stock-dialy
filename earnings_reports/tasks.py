"""
earnings_reports/tasks.py
Celeryタスク定義 - 非同期処理
"""

import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail, send_mass_mail
from celery import shared_task, current_task
from celery.exceptions import Retry

from .models import Analysis, Company, Document, AnalysisHistory
from .services.analysis_service import EarningsAnalysisService
from .services.edinet_service import EDINETService

logger = logging.getLogger('earnings_analysis')
User = get_user_model()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def execute_analysis_task(self, analysis_id):
    """
    分析実行タスク（非同期）
    
    Args:
        analysis_id: 分析ID
        
    Returns:
        dict: 実行結果
    """
    try:
        # 分析オブジェクトを取得
        analysis = Analysis.objects.get(id=analysis_id)
        
        # 現在のタスクIDを保存
        analysis.task_id = self.request.id
        analysis.save()
        
        logger.info(f"非同期分析開始: {analysis.document.company.name} (Task: {self.request.id})")
        
        # 分析サービスを初期化して実行
        service = EarningsAnalysisService()
        success = service.execute_analysis(analysis)
        
        if success:
            logger.info(f"非同期分析完了: {analysis.document.company.name}")
            
            # 完了通知の送信
            if analysis.settings_json.get('notify_on_completion', False):
                send_analysis_completion_notification_task.delay(analysis_id)
            
            return {
                'success': True,
                'analysis_id': analysis_id,
                'score': analysis.overall_score,
                'processing_time': analysis.processing_time
            }
        else:
            raise Exception("分析処理が失敗しました")
    
    except Analysis.DoesNotExist:
        logger.error(f"分析オブジェクトが見つかりません: {analysis_id}")
        return {'success': False, 'error': '分析オブジェクトが見つかりません'}
    
    except Exception as exc:
        logger.error(f"分析タスクエラー (ID: {analysis_id}): {str(exc)}")
        
        # リトライ処理
        if self.request.retries < self.max_retries:
            logger.info(f"分析タスクをリトライします (試行: {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        
        # 最終的に失敗した場合
        try:
            analysis = Analysis.objects.get(id=analysis_id)
            analysis.status = 'failed'
            analysis.error_message = str(exc)
            analysis.save()
        except:
            pass
        
        return {
            'success': False,
            'error': str(exc),
            'analysis_id': analysis_id
        }


@shared_task(bind=True, max_retries=2)
def sync_company_documents_task(self, company_id):
    """
    企業書類同期タスク（非同期）
    
    Args:
        company_id: 企業ID
        
    Returns:
        dict: 同期結果
    """
    try:
        company = Company.objects.get(id=company_id)
        edinet_service = EDINETService(settings.EDINET_API_KEY)
        
        logger.info(f"企業書類同期開始: {company.name}")
        
        # 書類同期実行
        company_docs = edinet_service.search_company_documents(
            company.stock_code,
            days_back=30,
            max_results=50
        )
        
        new_count = 0
        updated_count = 0
        
        for doc_info in company_docs:
            doc_id, company_name, doc_description, submit_date, doc_type, sec_code = doc_info
            
            try:
                submit_date_obj = datetime.strptime(submit_date, '%Y-%m-%d').date()
                
                document, created = Document.objects.get_or_create(
                    doc_id=doc_id,
                    company=company,
                    defaults={
                        'doc_type': doc_type,
                        'doc_description': doc_description,
                        'submit_date': submit_date_obj,
                    }
                )
                
                if created:
                    new_count += 1
                else:
                    # 既存文書の更新チェック
                    if (document.doc_description != doc_description or 
                        document.submit_date != submit_date_obj):
                        document.doc_description = doc_description
                        document.submit_date = submit_date_obj
                        document.save()
                        updated_count += 1
            
            except Exception as e:
                logger.warning(f"書類処理エラー {doc_id}: {str(e)}")
                continue
        
        # 最終同期日時を更新
        company.last_sync = timezone.now()
        company.save()
        
        logger.info(f"企業書類同期完了: {company.name} - 新規:{new_count}, 更新:{updated_count}")
        
        return {
            'success': True,
            'company_name': company.name,
            'new_documents': new_count,
            'updated_documents': updated_count
        }
    
    except Company.DoesNotExist:
        return {'success': False, 'error': '企業が見つかりません'}
    
    except Exception as exc:
        logger.error(f"書類同期エラー: {str(exc)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300)  # 5分後にリトライ
        
        return {'success': False, 'error': str(exc)}


@shared_task
def send_analysis_completion_notification_task(analysis_id):
    """
    分析完了通知送信タスク
    
    Args:
        analysis_id: 分析ID
    """
    try:
        analysis = Analysis.objects.select_related(
            'user', 'document__company'
        ).get(id=analysis_id)
        
        user = analysis.user
        company = analysis.document.company
        
        subject = f'【カブログ】{company.name}の分析が完了しました'
        
        message = f"""
{user.username}様

{company.name}（{company.stock_code}）の決算分析が完了しました。

■ 分析結果サマリー
・総合スコア: {analysis.overall_score or 'N/A'}
・信頼性: {analysis.get_confidence_level_display() or 'N/A'}
・処理時間: {analysis.processing_time or 'N/A'}秒

■ 分析対象書類
・{analysis.document.get_doc_type_display()}
・提出日: {analysis.document.submit_date}

詳細な分析結果は以下のリンクからご確認ください。
{settings.SITE_URL}/earnings/analysis/{analysis.pk}/

---
カブログ決算分析システム
        """.strip()
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )
        
        logger.info(f"分析完了通知送信完了: {user.email}")
        return {'success': True}
    
    except Exception as e:
        logger.error(f"通知送信エラー: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def daily_sync_all_companies_task():
    """
    全企業の日次書類同期タスク
    """
    try:
        companies = Company.objects.all()
        total_companies = companies.count()
        
        logger.info(f"全企業日次同期開始: {total_companies}社")
        
        success_count = 0
        error_count = 0
        
        for company in companies:
            try:
                # 各企業の同期を非同期で実行
                sync_company_documents_task.delay(company.id)
                success_count += 1
            except Exception as e:
                logger.error(f"企業{company.name}の同期タスク起動エラー: {str(e)}")
                error_count += 1
        
        logger.info(f"全企業日次同期完了: 成功{success_count}社, エラー{error_count}社")
        
        return {
            'success': True,
            'total_companies': total_companies,
            'success_count': success_count,
            'error_count': error_count
        }
    
    except Exception as e:
        logger.error(f"日次同期エラー: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def send_earnings_calendar_notifications_task():
    """
    決算カレンダー通知送信タスク
    """
    try:
        from .utils.company_utils import get_earnings_schedule
        
        # 通知設定が有効なユーザーを取得
        notification_histories = AnalysisHistory.objects.filter(
            notify_on_earnings=True
        ).select_related('user', 'company')
        
        notification_count = 0
        
        for history in notification_histories:
            try:
                # 企業の決算予定を確認（7日先まで）
                schedule = get_earnings_schedule(history.company, days_ahead=7)
                
                if schedule:
                    send_earnings_schedule_notification_task.delay(
                        history.user.id,
                        history.company.id,
                        schedule
                    )
                    notification_count += 1
                    
            except Exception as e:
                logger.warning(f"決算予定通知エラー {history.company.name}: {str(e)}")
                continue
        
        logger.info(f"決算カレンダー通知送信完了: {notification_count}件")
        
        return {
            'success': True,
            'notification_count': notification_count
        }
    
    except Exception as e:
        logger.error(f"決算カレンダー通知エラー: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def send_earnings_schedule_notification_task(user_id, company_id, schedule):
    """
    決算予定通知送信タスク
    
    Args:
        user_id: ユーザーID
        company_id: 企業ID
        schedule: 決算予定リスト
    """
    try:
        user = User.objects.get(id=user_id)
        company = Company.objects.get(id=company_id)
        
        subject = f'【カブログ】{company.name}の決算発表予定'
        
        schedule_text = '\n'.join([
            f"・{item['date'].strftime('%m月%d日')}: {item['description']}"
            for item in schedule
        ])
        
        message = f"""
{user.username}様

{company.name}（{company.stock_code}）の決算発表が近づいています。

■ 予定
{schedule_text}

分析の準備をお忘れなく。

---
カブログ決算分析システム
        """.strip()
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )
        
        logger.info(f"決算予定通知送信完了: {user.email} - {company.name}")
        return {'success': True}
    
    except Exception as e:
        logger.error(f"決算予定通知送信エラー: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def cleanup_old_analysis_data_task():
    """
    古い分析データのクリーンアップタスク
    """
    try:
        # 90日以上前の失敗した分析を削除
        cutoff_date = timezone.now() - timedelta(days=90)
        
        old_failed_analyses = Analysis.objects.filter(
            status='failed',
            analysis_date__lt=cutoff_date
        )
        
        deleted_count = old_failed_analyses.count()
        old_failed_analyses.delete()
        
        logger.info(f"古い分析データクリーンアップ完了: {deleted_count}件削除")
        
        return {
            'success': True,
            'deleted_count': deleted_count
        }
    
    except Exception as e:
        logger.error(f"データクリーンアップエラー: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def generate_weekly_analysis_report_task():
    """
    週次分析レポート生成タスク
    """
    try:
        from django.template.loader import render_to_string
        
        # 過去7日間の分析統計
        week_ago = timezone.now() - timedelta(days=7)
        
        weekly_stats = {
            'total_analyses': Analysis.objects.filter(
                analysis_date__gte=week_ago,
                status='completed'
            ).count(),
            'unique_companies': Company.objects.filter(
                documents__analysis__analysis_date__gte=week_ago,
                documents__analysis__status='completed'
            ).distinct().count(),
            'avg_score': Analysis.objects.filter(
                analysis_date__gte=week_ago,
                status='completed',
                overall_score__isnull=False
            ).aggregate(avg=models.Avg('overall_score'))['avg'],
        }
        
        # アクティブユーザーにレポート送信
        active_users = User.objects.filter(
            analyses__analysis_date__gte=week_ago
        ).distinct()
        
        emails_to_send = []
        
        for user in active_users:
            user_stats = Analysis.objects.filter(
                user=user,
                analysis_date__gte=week_ago,
                status='completed'
            ).count()
            
            if user_stats > 0:
                subject = '【カブログ】週次分析レポート'
                message = f"""
{user.username}様

過去7日間の分析活動をお知らせします。

■ あなたの分析実績
・分析回数: {user_stats}回

■ 全体統計
・総分析数: {weekly_stats['total_analyses']}回
・分析企業数: {weekly_stats['unique_companies']}社
・平均スコア: {weekly_stats['avg_score']:.1f if weekly_stats['avg_score'] else 'N/A'}

継続的な分析で投資判断の精度を高めましょう！

---
カブログ決算分析システム
                """.strip()
                
                emails_to_send.append((
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email]
                ))
        
        if emails_to_send:
            send_mass_mail(emails_to_send, fail_silently=True)
            logger.info(f"週次レポート送信完了: {len(emails_to_send)}名")
        
        return {
            'success': True,
            'report_sent': len(emails_to_send),
            'weekly_stats': weekly_stats
        }
    
    except Exception as e:
        logger.error(f"週次レポート生成エラー: {str(e)}")
        return {'success': False, 'error': str(e)}