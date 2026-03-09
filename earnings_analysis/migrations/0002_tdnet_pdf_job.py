"""
TDNETPDFJob テーブルを追加するマイグレーション

PDF処理を非同期化するために必要な新しいテーブル。

【適用手順】
既存テーブルがある場合:
    python manage.py migrate --fake earnings_analysis 0001
    python manage.py migrate earnings_analysis

初回セットアップ（テーブルが存在しない場合）:
    python manage.py migrate earnings_analysis
"""
from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('earnings_analysis', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TDNETPDFJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True, verbose_name='ジョブID')),
                ('status', models.CharField(
                    choices=[
                        ('pending', '待機中'),
                        ('processing', '処理中'),
                        ('done', '完了'),
                        ('error', 'エラー'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20,
                    verbose_name='ステータス',
                )),
                ('pdf_url', models.URLField(max_length=500, verbose_name='PDF URL')),
                ('company_code', models.CharField(max_length=10, verbose_name='証券コード')),
                ('company_name', models.CharField(max_length=255, verbose_name='企業名')),
                ('disclosure_type', models.CharField(max_length=50, verbose_name='開示種別')),
                ('title', models.CharField(max_length=500, verbose_name='タイトル')),
                ('max_pdf_pages', models.IntegerField(default=50, verbose_name='最大ページ数')),
                ('error_message', models.TextField(blank=True, verbose_name='エラーメッセージ')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='作成日時')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新日時')),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pdf_jobs',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='作成者',
                )),
                ('disclosure', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pdf_jobs',
                    to='earnings_analysis.tdnetdisclosure',
                    verbose_name='開示情報',
                )),
                ('report', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pdf_jobs',
                    to='earnings_analysis.tdnetreport',
                    verbose_name='レポート',
                )),
            ],
            options={
                'verbose_name': 'PDFジョブ',
                'verbose_name_plural': 'PDFジョブ一覧',
                'db_table': 'earnings_tdnet_pdf_job',
                'ordering': ['-created_at'],
            },
        ),
    ]
