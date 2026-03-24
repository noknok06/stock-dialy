from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stockdiary', '0003_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarginRatioData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stock_symbol', models.CharField(db_index=True, max_length=20, verbose_name='証券コード')),
                ('date', models.DateField(db_index=True, verbose_name='基準日')),
                ('margin_ratio', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='信用倍率')),
                ('margin_buy_balance', models.BigIntegerField(blank=True, null=True, verbose_name='信用買い残')),
                ('margin_sell_balance', models.BigIntegerField(blank=True, null=True, verbose_name='信用売り残')),
                ('short_ratio', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='空売り比率(参考)')),
                ('data_source', models.CharField(default='yfinance', max_length=50, verbose_name='データソース')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '信用倍率データ',
                'verbose_name_plural': '信用倍率データ',
                'ordering': ['-date'],
                'indexes': [
                    models.Index(fields=['stock_symbol', '-date'], name='stockdiary_stock_s_9c1b24_idx'),
                ],
                'unique_together': {('stock_symbol', 'date')},
            },
        ),
    ]
