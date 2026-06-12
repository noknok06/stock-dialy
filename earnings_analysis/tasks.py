# earnings_analysis/tasks.py
"""
Django-Q バックグラウンドタスク

PDF処理は時間がかかる（60〜150秒）ため、HTTPリクエストではなく
バックグラウンドタスクとして実行することで502エラーを防ぐ。
"""

import logging
import uuid

logger = logging.getLogger('earnings_analysis.tdnet')


def auto_analyze_disclosure_task(event_id: int):
    """新規開示イベント（有報・半報）の財務・トーン分析を自動実行する。

    DisclosureSync が新規 DisclosureEvent を作成した際に async_task で
    キューされる。対象は記録中銘柄の重要開示のみ（年2回×ユニーク銘柄）
    のため件数は少ない。AI（Gemini）は使用しない。

    - XBRL 財務分析 → CompanyFinancialData（detail 開示タブの財務バッジ・
      決算レビュー下書きの財務サマリー）
    - 語彙ベース感情分析 → SentimentAnalysisHistory（経営トーンの前回比）
    """
    from .models import CompanyFinancialData, DisclosureEvent, DocumentMetadata
    from .services.xbrl_analysis_service import XBRLAnalysisService

    try:
        event = DisclosureEvent.objects.get(pk=event_id)
    except DisclosureEvent.DoesNotExist:
        logger.warning(f'開示自動分析: イベントが見つかりません event_id={event_id}')
        return

    doc = DocumentMetadata.objects.filter(doc_id=event.doc_id).first()
    if not doc or not doc.xbrl_flag:
        return

    # XBRL 財務分析（分析済みならスキップ）
    if not CompanyFinancialData.objects.filter(document=doc).exists():
        result = XBRLAnalysisService().analyze_document(doc)
        if result.get('ok'):
            logger.info(f'XBRL自動分析完了: doc_id={event.doc_id} ({event.doc_type_name})')
        else:
            logger.warning(
                f"XBRL自動分析失敗: doc_id={event.doc_id}, error={result.get('error')}"
            )

    # 語彙ベース感情分析（経営トーン蓄積。失敗しても財務分析の結果は活きる）
    try:
        from .services.sentiment_analyzer import SentimentAnalysisService
        SentimentAnalysisService().run_lexicon_analysis(doc)
    except Exception as e:
        logger.warning(f'語彙感情分析失敗: doc_id={event.doc_id}, {e}')


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
