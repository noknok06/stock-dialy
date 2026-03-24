"""
信用倍率データの定期取得タスク（Celery）

週次スケジュール: 毎週金曜日の早朝（前日木曜日の申込分を取得）
JPXは木曜日の申込データを翌週木曜〜金曜に公開することが多いため、
金曜日の朝に直近木曜分を取得する。
"""

import logging
from celery import shared_task
from datetime import date, timedelta

logger = logging.getLogger(__name__)


@shared_task(
    name='margin_tracking.tasks.fetch_weekly_margin_data',
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5分後にリトライ
)
def fetch_weekly_margin_data(self):
    """
    最新週の信用倍率データを取得するCeleryタスク。
    毎週金曜日の早朝に実行することを想定。
    直近2週分を取得（前週分が未取得の場合もカバー）。
    """
    from margin_tracking.services.jpx_margin_service import JPXMarginService

    logger.info("週次信用倍率データ取得タスク開始")
    service = JPXMarginService()

    today = date.today()
    # 直近の木曜日を求める
    days_since_thursday = (today.weekday() - 3) % 7
    last_thursday = today - timedelta(days=days_since_thursday)

    # 直近2週分（最新 + 念のため前週）
    target_dates = [last_thursday, last_thursday - timedelta(weeks=1)]

    success_total = 0
    fail_total = 0

    for target_date in target_dates:
        try:
            result = service.fetch_and_save(target_date, force=False)
            if result.get('skipped'):
                logger.info(f"スキップ（取得済み）: {target_date}")
            elif result['success']:
                success_total += 1
                logger.info(
                    f"取得完了: {target_date} "
                    f"新規={result['created']} 更新={result['updated']}"
                )
            else:
                fail_total += 1
                logger.warning(f"取得失敗: {target_date} - {result.get('error')}")
        except Exception as exc:
            fail_total += 1
            logger.error(f"タスクエラー ({target_date}): {exc}", exc_info=True)
            # 最終的な失敗時のみリトライ
            if target_date == target_dates[0]:
                raise self.retry(exc=exc)

    logger.info(
        f"週次信用倍率データ取得タスク完了: 成功={success_total} 失敗={fail_total}"
    )
    return {'success': success_total, 'fail': fail_total}
