"""
margin_ratio を long_balance / short_balance から再計算して上書きする。

使用法:
  python manage.py fix_margin_ratio
  python manage.py fix_margin_ratio --dry-run    # 変更内容のみ表示
"""

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand

from margin_tracking.models import MarginData


class Command(BaseCommand):
    help = 'margin_ratio を long_balance / short_balance から再計算して修正する'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='DBを変更せず、修正対象のみ表示する',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fixed = 0
        skipped = 0

        records = MarginData.objects.all()
        self.stdout.write(f'総レコード数: {records.count()}')

        for rec in records:
            if not rec.short_balance or rec.short_balance <= 0:
                skipped += 1
                continue

            try:
                correct = (
                    Decimal(str(rec.long_balance)) / Decimal(str(rec.short_balance))
                ).quantize(Decimal('0.01'))
            except InvalidOperation:
                skipped += 1
                continue

            if rec.margin_ratio != correct:
                self.stdout.write(
                    f'  [{rec.stock_code} {rec.record_date}] '
                    f'stored={rec.margin_ratio} → correct={correct} '
                    f'(long={rec.long_balance}, short={rec.short_balance})'
                )
                if not dry_run:
                    MarginData.objects.filter(pk=rec.pk).update(margin_ratio=correct)
                fixed += 1

        action = 'の修正対象' if dry_run else 'を修正'
        self.stdout.write(
            self.style.SUCCESS(
                f'完了: {fixed} 件{action}、{skipped} 件スキップ'
            )
        )
