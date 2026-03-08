"""
マイグレーション: StockDiary に現物取引専用の集計フィールドを追加

このマイグレーションは既存テーブルに対して AddField のみを実行します。
stockdiary アプリがこれまでマイグレーション未使用（syncdb管理）だった場合は、
以下の手順で適用してください:

    # 既存テーブルをそのままにしつつ、このマイグレーションだけを適用
    python manage.py migrate stockdiary

フィールド追加後、既存データを再計算するコマンドを実行してください:

    python manage.py recalculate_cash_only_stats
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    # stockdiary アプリには初回マイグレーションがないため initial=True で作成
    initial = False

    dependencies = []

    operations = [
        migrations.AddField(
            model_name='stockdiary',
            name='cash_only_current_quantity',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=15, verbose_name='現物保有数'
            ),
        ),
        migrations.AddField(
            model_name='stockdiary',
            name='cash_only_average_purchase_price',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                verbose_name='現物平均取得単価'
            ),
        ),
        migrations.AddField(
            model_name='stockdiary',
            name='cash_only_total_cost',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=15, verbose_name='現物総原価'
            ),
        ),
        migrations.AddField(
            model_name='stockdiary',
            name='cash_only_realized_profit',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=15, verbose_name='現物実現損益'
            ),
        ),
        migrations.AddField(
            model_name='stockdiary',
            name='cash_only_total_bought_quantity',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=15, verbose_name='現物累計購入数'
            ),
        ),
        migrations.AddField(
            model_name='stockdiary',
            name='cash_only_total_sold_quantity',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=15, verbose_name='現物累計売却数'
            ),
        ),
        migrations.AddField(
            model_name='stockdiary',
            name='cash_only_total_buy_amount',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=15, verbose_name='現物累計購入額'
            ),
        ),
        migrations.AddField(
            model_name='stockdiary',
            name='cash_only_total_sell_amount',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=15, verbose_name='現物累計売却額'
            ),
        ),
    ]
