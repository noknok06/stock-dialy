"""
信用倍率データの定期取得タスク（Django-Q）

毎日早朝に過去40日分をチェックし、未取得分を取得する。
JPXの公開日は木曜が多いが固定ではないため日次で総当たり確認する。

スケジュール登録: apps.py の ready() から setup_margin_fetch_schedule() を呼ぶ。
"""

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def fetch_daily_margin_data():
    """
    過去40日分の信用倍率データを取得する Django-Q タスク。
    毎日 07:30 JST に実行。未取得の日のみ取得（スキップ機能あり）。
    """
    from margin_tracking.services.jpx_margin_service import JPXMarginService

    logger.info("信用倍率データ取得タスク開始")
    service = JPXMarginService()

    today = date.today()
    target_dates = [today - timedelta(days=i) for i in range(39, -1, -1)]  # 過去40日

    success = fail = skipped = not_found = 0

    for target_date in target_dates:
        try:
            result = service.fetch_and_save(target_date, force=False)
            if result.get('skipped'):
                skipped += 1
            elif result.get('not_found'):
                not_found += 1
            elif result['success']:
                success += 1
                logger.info(
                    f"取得完了: {target_date} "
                    f"新規={result['created']} 更新={result['updated']}"
                )
            else:
                fail += 1
                logger.warning(f"取得失敗: {target_date} - {result.get('error')}")
        except Exception as exc:
            fail += 1
            logger.error(f"タスクエラー ({target_date}): {exc}", exc_info=True)

    logger.info(
        f"信用倍率データ取得タスク完了: "
        f"成功={success} スキップ={skipped} 未公開={not_found} 失敗={fail}"
    )
    return {'success': success, 'skipped': skipped, 'not_found': not_found, 'fail': fail}


def setup_margin_fetch_schedule():
    """
    Django-Q スケジュールを登録する（AppConfig.ready() から呼ぶ）。
    既に登録済みの場合は何もしない。
    """
    from django_q.models import Schedule

    func = 'margin_tracking.tasks.fetch_daily_margin_data'
    if Schedule.objects.filter(func=func).exists():
        logger.debug("信用倍率取得スケジュール: 既に登録済み")
        return

    Schedule.objects.create(
        name='信用倍率データ日次取得',
        func=func,
        schedule_type=Schedule.CRON,
        cron='0 15 * * *',   # 毎日 15:00 (サーバー時刻 = JST)
        repeats=-1,           # 無限繰り返し
    )
    logger.info("信用倍率取得スケジュール登録完了: 毎日 07:30")
