# earnings_analysis/management/commands/sync_earnings_calendar.py
"""決算予定の日次同期コマンド

決算予定API（EDINET DB /v1/calendar）から当日〜90日後の決算発表予定を取得し、
EarningsSchedule を洗い替え保存する。あわせて各日記の next_earnings_date を
事前計算し、決算前日（翌日決算）の通知をファンアウトする。

cron で毎日1回実行する想定（etc/cron.d/earnings-calendar 参照）。
無料枠（100リクエスト/日）に対し、本コマンドのAPI利用は1〜3リクエスト程度。
"""
import logging
import traceback

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '決算予定APIから当日〜90日後の決算予定を取得してDBへ同期する'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=90,
            help='取得期間（当日からの日数、既定90日）',
        )
        parser.add_argument(
            '--skip-notifications', action='store_true',
            help='決算前日通知のファンアウトをスキップする',
        )

    def handle(self, *args, **options):
        from earnings_analysis.services import (
            sync_earnings_calendar,
            update_diary_next_earnings,
            fan_out_earnings_reminders,
        )

        days = options['days']
        skip_notifications = options['skip_notifications']

        self.stdout.write(f'決算予定同期開始（当日〜{days}日後）')

        try:
            saved = sync_earnings_calendar(days=days)
            self.stdout.write(self.style.SUCCESS(f'決算予定 保存: {saved}件'))
        except Exception as e:
            logger.error('決算予定同期エラー: %s', e, exc_info=True)
            self.stdout.write(self.style.ERROR(f'決算予定同期エラー: {e}'))
            self.stdout.write(traceback.format_exc())
            return

        # 各日記の次回決算日を事前計算（失敗してもバッチは止めない）
        try:
            updated = update_diary_next_earnings()
            self.stdout.write(self.style.SUCCESS(f'次回決算日 更新: {updated}件'))
        except Exception as e:
            logger.warning('次回決算日更新エラー（スキップ）: %s', e, exc_info=True)
            self.stdout.write(self.style.WARNING(f'次回決算日更新スキップ: {e}'))

        # 決算前日通知のファンアウト
        if not skip_notifications:
            try:
                notified = fan_out_earnings_reminders()
                self.stdout.write(self.style.SUCCESS(f'決算前日通知: {notified}件'))
            except Exception as e:
                logger.warning('決算前日通知エラー（スキップ）: %s', e, exc_info=True)
                self.stdout.write(self.style.WARNING(f'決算前日通知スキップ: {e}'))

        self.stdout.write(self.style.SUCCESS('決算予定同期完了'))
