from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='MarginData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('record_date', models.DateField(db_index=True, verbose_name='申込日')),
                ('stock_code', models.CharField(db_index=True, max_length=4, verbose_name='銘柄コード')),
                ('stock_name', models.CharField(blank=True, max_length=100, verbose_name='銘柄名')),
                ('short_balance', models.BigIntegerField(verbose_name='売り残高（合計）')),
                ('long_balance', models.BigIntegerField(verbose_name='買い残高（合計）')),
                ('margin_ratio', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='信用倍率'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '信用取引残高',
                'verbose_name_plural': '信用取引残高',
                'ordering': ['-record_date', 'stock_code'],
            },
        ),
        migrations.CreateModel(
            name='MarginFetchLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('record_date', models.DateField(unique=True, verbose_name='対象申込日')),
                ('status', models.CharField(
                    choices=[
                        ('running', '実行中'),
                        ('success', '成功'),
                        ('failed', '失敗'),
                        ('partial', '一部成功'),
                    ],
                    default='running',
                    max_length=10,
                    verbose_name='ステータス',
                )),
                ('records_created', models.IntegerField(default=0, verbose_name='新規作成件数')),
                ('records_updated', models.IntegerField(default=0, verbose_name='更新件数')),
                ('total_records', models.IntegerField(default=0, verbose_name='処理件数合計')),
                ('pdf_url', models.URLField(blank=True, verbose_name='取得元PDF URL')),
                ('error_message', models.TextField(blank=True, verbose_name='エラーメッセージ')),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': '取得ログ',
                'verbose_name_plural': '取得ログ',
                'ordering': ['-record_date'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='margindata',
            unique_together={('record_date', 'stock_code')},
        ),
        migrations.AddIndex(
            model_name='margindata',
            index=models.Index(fields=['stock_code', '-record_date'], name='margin_trac_stock_c_idx'),
        ),
        migrations.AddIndex(
            model_name='margindata',
            index=models.Index(fields=['-record_date'], name='margin_trac_record__idx'),
        ),
    ]
