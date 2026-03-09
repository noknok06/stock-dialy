"""
初期マイグレーション（既存テーブル用）

【重要】このマイグレーションは既存のテーブル（earnings_tdnet_disclosure,
earnings_tdnet_report, earnings_tdnet_report_section）が既に存在する場合は
--fake オプションで適用してください:

    python manage.py migrate --fake earnings_analysis 0001

その後、0002 を通常通り適用すると earnings_tdnet_pdf_job テーブルが作成されます:

    python manage.py migrate earnings_analysis
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TDNETDisclosure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('disclosure_id', models.CharField(db_index=True, help_text='TDNET開示ID', max_length=50, unique=True, verbose_name='開示ID')),
                ('company_code', models.CharField(db_index=True, help_text='証券コード（4桁）', max_length=10, verbose_name='証券コード')),
                ('company_name', models.CharField(db_index=True, max_length=255, verbose_name='企業名')),
                ('disclosure_date', models.DateTimeField(db_index=True, help_text='適時開示された日時', verbose_name='開示日時')),
                ('disclosure_type', models.CharField(choices=[('earnings', '決算短信'), ('forecast', '業績予想修正'), ('dividend', '配当予想修正'), ('buyback', '自己株式取得'), ('merger', '合併・買収'), ('offering', '募集・発行'), ('governance', 'ガバナンス'), ('other', 'その他')], db_index=True, default='other', max_length=50, verbose_name='開示種別')),
                ('disclosure_category', models.CharField(blank=True, help_text='詳細な開示区分', max_length=100, verbose_name='開示区分')),
                ('title', models.CharField(max_length=500, verbose_name='タイトル')),
                ('summary', models.TextField(blank=True, help_text='開示内容の概要', verbose_name='概要')),
                ('raw_data', models.JSONField(default=dict, help_text='TDNET APIから取得した生データ', verbose_name='元データ')),
                ('pdf_url', models.URLField(blank=True, help_text='PDFファイルのURL', max_length=500, verbose_name='PDF URL')),
                ('pdf_cached', models.BooleanField(default=False, help_text='PDFファイルがローカルに保存済みか', verbose_name='PDF取得済み')),
                ('pdf_file_path', models.CharField(blank=True, help_text='ローカルに保存されたPDFのパス', max_length=500, verbose_name='PDFパス')),
                ('is_processed', models.BooleanField(default=False, help_text='データ処理が完了したか', verbose_name='処理済み')),
                ('report_generated', models.BooleanField(default=False, help_text='AIレポートが生成済みか', verbose_name='レポート生成済み')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='作成日時')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新日時')),
            ],
            options={
                'verbose_name': 'TDNET開示情報',
                'verbose_name_plural': 'TDNET開示情報一覧',
                'db_table': 'earnings_tdnet_disclosure',
                'ordering': ['-disclosure_date'],
            },
        ),
        migrations.CreateModel(
            name='TDNETReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_id', models.CharField(db_index=True, max_length=100, unique=True, verbose_name='レポートID')),
                ('title', models.CharField(max_length=500, verbose_name='レポートタイトル')),
                ('report_type', models.CharField(choices=[('earnings', '決算短信'), ('forecast', '業績予想'), ('dividend', '配当'), ('merger', '合併・買収'), ('offering', '募集・発行'), ('governance', 'ガバナンス'), ('other', 'その他')], db_index=True, default='other', max_length=50, verbose_name='レポート種別')),
                ('overall_score', models.IntegerField(default=50, help_text='0-100の総合評価スコア', validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='総合スコア')),
                ('signal', models.CharField(choices=[('strong_positive', '強気'), ('positive', 'やや強気'), ('neutral', '中立'), ('negative', 'やや弱気'), ('strong_negative', '弱気')], default='neutral', help_text='投資判断シグナル', max_length=20, verbose_name='投資シグナル')),
                ('one_line_summary', models.CharField(blank=True, help_text='スマホ画面で最初に表示する一言', max_length=100, verbose_name='一言サマリー')),
                ('summary', models.TextField(help_text='レポートの要約（3-5文）', verbose_name='要約')),
                ('key_points', models.JSONField(default=list, verbose_name='重要ポイント')),
                ('analysis', models.TextField(blank=True, verbose_name='分析')),
                ('score_details', models.JSONField(default=dict, help_text='各項目の採点詳細', verbose_name='採点詳細')),
                ('status', models.CharField(choices=[('draft', '下書き'), ('published', '公開'), ('archived', 'アーカイブ')], db_index=True, default='draft', max_length=20, verbose_name='ステータス')),
                ('generation_model', models.CharField(default='gemini-pro', max_length=100, verbose_name='生成モデル')),
                ('generation_prompt', models.TextField(blank=True, verbose_name='生成プロンプト')),
                ('generation_token_count', models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name='生成トークン数')),
                ('view_count', models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name='閲覧数')),
                ('published_at', models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='公開日時')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='作成日時')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新日時')),
                ('disclosure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='earnings_analysis.tdnetdisclosure', verbose_name='元開示情報')),
                ('generated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_tdnet_reports', to=settings.AUTH_USER_MODEL, verbose_name='生成者')),
            ],
            options={
                'verbose_name': 'TDNETレポート',
                'verbose_name_plural': 'TDNETレポート一覧',
                'db_table': 'earnings_tdnet_report',
                'ordering': ['-published_at', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TDNETReportSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('section_type', models.CharField(choices=[('overview', '概要'), ('financial', '財務情報'), ('forecast', '業績予想'), ('analysis', '分析'), ('risk', 'リスク'), ('opportunity', '機会'), ('conclusion', '結論'), ('other', 'その他')], default='other', max_length=50, verbose_name='セクション種別')),
                ('title', models.CharField(max_length=255, verbose_name='セクションタイトル')),
                ('content', models.TextField(verbose_name='内容')),
                ('order', models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name='表示順')),
                ('data', models.JSONField(blank=True, default=dict, null=True, verbose_name='構造化データ')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='作成日時')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新日時')),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='earnings_analysis.tdnetreport', verbose_name='レポート')),
            ],
            options={
                'verbose_name': 'TDNETレポートセクション',
                'verbose_name_plural': 'TDNETレポートセクション一覧',
                'db_table': 'earnings_tdnet_report_section',
                'ordering': ['report', 'order'],
            },
        ),
        migrations.AddIndex(
            model_name='tdnetdisclosure',
            index=models.Index(fields=['company_code', '-disclosure_date'], name='idx_tdnet_disc_co_date'),
        ),
        migrations.AddIndex(
            model_name='tdnetdisclosure',
            index=models.Index(fields=['disclosure_type', '-disclosure_date'], name='idx_tdnet_disc_type_date'),
        ),
        migrations.AddIndex(
            model_name='tdnetdisclosure',
            index=models.Index(fields=['is_processed', 'report_generated'], name='idx_tdnet_disc_status'),
        ),
        migrations.AddIndex(
            model_name='tdnetreport',
            index=models.Index(fields=['status', '-published_at'], name='idx_tdnet_rep_status_pub'),
        ),
        migrations.AddIndex(
            model_name='tdnetreport',
            index=models.Index(fields=['report_type', '-published_at'], name='idx_tdnet_rep_type_pub'),
        ),
        migrations.AddIndex(
            model_name='tdnetreport',
            index=models.Index(fields=['disclosure', '-created_at'], name='idx_tdnet_rep_disc_date'),
        ),
        migrations.AlterUniqueTogether(
            name='tdnetreportsection',
            unique_together={('report', 'order')},
        ),
        migrations.AddIndex(
            model_name='tdnetreportsection',
            index=models.Index(fields=['report', 'order'], name='idx_tdnet_sec_rep_order'),
        ),
    ]
