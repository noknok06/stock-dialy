# earnings_analysis/tasks.py
"""
Django-Q バックグラウンドタスク

PDF処理は時間がかかる（60〜150秒）ため、HTTPリクエストではなく
バックグラウンドタスクとして実行することで502エラーを防ぐ。
"""

import logging
import uuid

logger = logging.getLogger('earnings_analysis.tdnet')


def generate_report_from_pdf_url_task(
    job_id: str,
    pdf_url: str,
    company_code: str,
    company_name: str,
    disclosure_type: str,
    title: str,
    user_id,
    max_pdf_pages: int = 50,
):
    """
    PDFからレポートを生成するバックグラウンドタスク。

    Django-Q の async_task() から呼び出される。
    TDNETPDFJob.status を随時更新してフロントエンドがポーリングできるようにする。
    """
    from .models.tdnet import TDNETPDFJob
    from .services.tdnet_report_generator import TDNETReportGeneratorService
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        job = TDNETPDFJob.objects.get(job_id=job_id)
    except TDNETPDFJob.DoesNotExist:
        logger.error(f"PDFジョブが見つかりません: job_id={job_id}")
        return

    try:
        job.status = TDNETPDFJob.STATUS_PROCESSING
        job.save(update_fields=['status', 'updated_at'])

        user = None
        if user_id:
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                pass

        generator_service = TDNETReportGeneratorService()
        result = generator_service.generate_report_from_pdf_url(
            pdf_url=pdf_url,
            company_code=company_code,
            company_name=company_name,
            disclosure_type=disclosure_type,
            title=title,
            user=user,
            max_pdf_pages=max_pdf_pages,
        )

        if result['success']:
            job.status = TDNETPDFJob.STATUS_DONE
            job.disclosure = result.get('disclosure')
            job.report = result.get('report')
            job.save(update_fields=['status', 'disclosure', 'report', 'updated_at'])
            logger.info(f"PDFジョブ完了: job_id={job_id}")
        else:
            job.status = TDNETPDFJob.STATUS_ERROR
            job.error_message = result.get('error', '不明なエラー')
            job.save(update_fields=['status', 'error_message', 'updated_at'])
            logger.error(f"PDFジョブ失敗: job_id={job_id}, error={job.error_message}")

    except Exception as e:
        logger.error(f"PDFジョブ例外: job_id={job_id}, error={e}", exc_info=True)
        try:
            job.status = TDNETPDFJob.STATUS_ERROR
            job.error_message = str(e)
            job.save(update_fields=['status', 'error_message', 'updated_at'])
        except Exception:
            pass
