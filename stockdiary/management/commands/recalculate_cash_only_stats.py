"""
管理コマンド: 既存 StockDiary の cash_only 集計フィールドを再計算する

マイグレーション 0001_add_cash_only_fields 適用後に一度だけ実行してください:

    python manage.py recalculate_cash_only_stats
    python manage.py recalculate_cash_only_stats --user-id=123  # 特定ユーザーのみ
"""
from django.core.management.base import BaseCommand
from stockdiary.models import StockDiary


class Command(BaseCommand):
    help = '既存の StockDiary レコードの cash_only 集計フィールドを再計算する'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            default=None,
            help='特定ユーザーIDのみ処理する（省略時は全ユーザー）',
        )

    def handle(self, *args, **options):
        qs = StockDiary.objects.all()
        if options['user_id']:
            qs = qs.filter(user_id=options['user_id'])

        total = qs.count()
        self.stdout.write(f'処理対象: {total} 件')

        updated = 0
        errors = 0
        for diary in qs.iterator():
            try:
                # _update_cash_only_aggregates() は cash_only フィールドを更新するが save() を呼ばない
                diary._update_cash_only_aggregates()
                StockDiary.objects.filter(pk=diary.pk).update(
                    cash_only_current_quantity=diary.cash_only_current_quantity,
                    cash_only_average_purchase_price=diary.cash_only_average_purchase_price,
                    cash_only_total_cost=diary.cash_only_total_cost,
                    cash_only_realized_profit=diary.cash_only_realized_profit,
                    cash_only_total_bought_quantity=diary.cash_only_total_bought_quantity,
                    cash_only_total_sold_quantity=diary.cash_only_total_sold_quantity,
                    cash_only_total_buy_amount=diary.cash_only_total_buy_amount,
                    cash_only_total_sell_amount=diary.cash_only_total_sell_amount,
                )
                updated += 1
                if updated % 100 == 0:
                    self.stdout.write(f'  {updated}/{total} 件処理済み')
            except Exception as e:
                errors += 1
                self.stderr.write(f'  エラー diary_id={diary.pk}: {e}')

        self.stdout.write(self.style.SUCCESS(
            f'完了: {updated} 件更新, {errors} 件エラー'
        ))
