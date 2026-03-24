"""
JPX 信用取引残高データ取得コマンド

使い方:
  # 直近の木曜日（最新週）のデータを取得
  python manage.py fetch_margin_data

  # 特定日付を指定
  python manage.py fetch_margin_data --date 2026-03-19

  # 直近N週分をまとめて取得（過去データ一括取得）
  python manage.py fetch_margin_data --weeks 10

  # 開始・終了日を指定して範囲取得
  python manage.py fetch_margin_data --start-date 2025-01-01 --end-date 2025-12-31

  # 既存データを強制上書き
  python manage.py fetch_margin_data --weeks 4 --force
"""

import time
from datetime import date, datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
import logging

logger = logging.getLogger(__name__)


def get_thursdays_in_range(start_date: date, end_date: date):
    """指定期間内のすべての木曜日を返す（古い順）"""
    thursdays = []
    # 最初の木曜日を探す
    current = start_date
    while current.weekday() != 3:  # 3 = 木曜日
        current += timedelta(days=1)

    while current <= end_date:
        thursdays.append(current)
        current += timedelta(weeks=1)
    return thursdays


class Command(BaseCommand):
    help = 'JPX信用取引残高データを取得してDBに保存する（週次・過去データ対応）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='取得対象の申込日（YYYY-MM-DD形式）。木曜日を指定してください。',
        )
        parser.add_argument(
            '--weeks',
            type=int,
            default=1,
            help='直近N週分のデータを取得（デフォルト: 1）。--date未指定時に有効。',
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
            default=2.0,
            help='複数週取得時のリクエスト間隔（秒）。デフォルト: 2.0',
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
                f"取得対象: {len(target_dates)}週分 "
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

            self.stdout.write(f"  [{i+1}/{len(target_dates)}] {target_date} 取得中...")

            result = service.fetch_and_save(target_date, force=force)

            if result.get('skipped'):
                self.stdout.write(
                    self.style.WARNING(f"    スキップ（取得済み）: {target_date}")
                )
                success_count += 1
                continue

            if result.get('not_found'):
                # 404 = 未公開週（祝日・休場等）。エラーではなく正常スキップ。
                not_found_count += 1
                self.stdout.write(
                    f"    未公開（404）: {target_date}  ※JPX未掲載のため正常"
                )
                continue

            if result['success']:
                total_created += result['created']
                total_updated += result['updated']
                success_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"    完了: 新規={result['created']} 更新={result['updated']} "
                        f"合計={result['total']}件"
                    )
                )
            else:
                fail_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"    失敗: {result.get('error', '不明なエラー')}"
                    )
                )

        # 結果サマリー
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('=== 取得完了 ==='))
        self.stdout.write(f"  取得成功: {success_count}週  未公開(404): {not_found_count}週  エラー: {fail_count}週")
        self.stdout.write(f"  合計新規: {total_created}件  合計更新: {total_updated}件")

        if fail_count > 0:
            self.stdout.write(
                self.style.ERROR(
                    f"{fail_count}週分でエラーが発生しました。ログを確認してください。"
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
            if d.weekday() != 3:
                self.stdout.write(
                    self.style.WARNING(
                        f"警告: {d} は木曜日ではありません（weekday={d.weekday()}）。"
                        "JPXの申込日は通常木曜日です。処理は続行します。"
                    )
                )
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
            dates = get_thursdays_in_range(start, end)
            if not dates:
                raise CommandError(f"{start} 〜 {end} の期間に木曜日がありません。")
            return dates

        # 直近N週分（デフォルト）
        weeks = options.get('weeks', 1)
        if weeks < 1:
            raise CommandError('--weeks は1以上の整数を指定してください。')

        today = date.today()
        # 直近の木曜日を求める
        days_since_thursday = (today.weekday() - 3) % 7
        last_thursday = today - timedelta(days=days_since_thursday)

        dates = [last_thursday - timedelta(weeks=i) for i in range(weeks)]
        dates.sort()  # 古い順
        return dates
