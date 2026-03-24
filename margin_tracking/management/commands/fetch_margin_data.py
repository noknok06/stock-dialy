"""
JPX 信用取引残高データ取得コマンド

JPXの公開日は木曜が多いが固定ではないため、
過去N日分を日次で総当たりチェックして取得する。

使い方:
  # 過去40日分をチェック（デフォルト）
  python manage.py fetch_margin_data

  # チェック日数を変更
  python manage.py fetch_margin_data --days 60

  # 特定日付のみ
  python manage.py fetch_margin_data --date 2026-03-19

  # 開始・終了日範囲指定
  python manage.py fetch_margin_data --start-date 2025-01-01 --end-date 2025-12-31

  # 既存データを強制上書き
  python manage.py fetch_margin_data --days 14 --force
"""

import time
from datetime import date, datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
import logging

logger = logging.getLogger(__name__)


def get_dates_in_range(start_date: date, end_date: date):
    """指定期間内の全日付を返す（古い順）"""
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


class Command(BaseCommand):
    help = 'JPX信用取引残高データを取得してDBに保存する（日次・過去データ対応）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='取得対象の申込日（YYYY-MM-DD形式）。',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=40,
            help='過去N日分をチェック（デフォルト: 40）。--date未指定時に有効。',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='範囲取得の開始日（YYYY-MM-DD形式）。--end-dateと併用。',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='範囲取得の終了日（YYYY-MM-DD形式）。--start-dateと併用。',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='既存データがある場合も強制的に上書き取得する。',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='複数日取得時のリクエスト間隔（秒）。デフォルト: 1.0',
        )

    def handle(self, *args, **options):
        from margin_tracking.services.jpx_margin_service import JPXMarginService

        force = options['force']
        delay = options['delay']
        service = JPXMarginService()

        # 取得対象日リストを決定
        target_dates = self._resolve_target_dates(options)
        if not target_dates:
            raise CommandError('取得対象日が決定できませんでした。')

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"取得対象: {len(target_dates)}日分 "
                f"({target_dates[0]} 〜 {target_dates[-1]})"
            )
        )

        total_created = 0
        total_updated = 0
        success_count = 0
        fail_count = 0
        not_found_count = 0

        for i, target_date in enumerate(target_dates):
            if i > 0:
                time.sleep(delay)

            self.stdout.write(f"  [{i+1}/{len(target_dates)}] {target_date} チェック中...", ending='\r')
            self.stdout.flush()

            result = service.fetch_and_save(target_date, force=force)

            if result.get('skipped'):
                # 取得済みは表示なしでスキップ（大量になるため）
                success_count += 1
                continue

            if result.get('not_found'):
                # 404 = 未公開日。通常の日は大半が404なので表示しない。
                not_found_count += 1
                continue

            if result['success']:
                total_created += result['created']
                total_updated += result['updated']
                success_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [{i+1}/{len(target_dates)}] {target_date} "
                        f"取得完了: 新規={result['created']} 更新={result['updated']} "
                        f"合計={result['total']}件"
                    )
                )
            else:
                fail_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  [{i+1}/{len(target_dates)}] {target_date} "
                        f"失敗: {result.get('error', '不明なエラー')}"
                    )
                )

        # 結果サマリー
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('=== 取得完了 ==='))
        self.stdout.write(
            f"  チェック: {len(target_dates)}日  "
            f"データあり: {success_count}日  "
            f"未公開(404): {not_found_count}日  "
            f"エラー: {fail_count}日"
        )
        self.stdout.write(f"  合計新規: {total_created}件  合計更新: {total_updated}件")

        if fail_count > 0:
            self.stdout.write(
                self.style.ERROR(
                    f"{fail_count}日分でエラーが発生しました。ログを確認してください。"
                )
            )

    def _resolve_target_dates(self, options) -> list:
        """オプションから取得対象日リストを決定する"""
        # 個別日付指定
        if options.get('date'):
            try:
                d = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError(f"日付形式が不正です: {options['date']} (YYYY-MM-DD形式で指定)")
            return [d]

        # 開始・終了日範囲指定
        if options.get('start_date') or options.get('end_date'):
            if not (options.get('start_date') and options.get('end_date')):
                raise CommandError('--start-date と --end-date は両方指定してください。')
            try:
                start = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
                end = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            except ValueError as e:
                raise CommandError(f"日付形式が不正です: {e}")
            if start > end:
                raise CommandError('--start-date は --end-date より前の日付を指定してください。')
            return get_dates_in_range(start, end)

        # 過去N日分（デフォルト）
        days = options.get('days', 40)
        if days < 1:
            raise CommandError('--days は1以上の整数を指定してください。')

        today = date.today()
        dates = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
        return dates
