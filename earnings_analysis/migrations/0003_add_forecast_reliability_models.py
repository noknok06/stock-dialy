# earnings_analysis/migrations/0003_add_forecast_reliability_models.py
# Generated manually for EarningsForecast and ForecastReliabilityScore models

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('earnings_analysis', '0002_initial'),
    ]

    operations = [
        # ===== EarningsForecast =====
        migrations.CreateModel(
            name='EarningsForecast',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_code', models.CharField(db_index=True, help_text='4桁証券コード', max_length=10, verbose_name='証券コード')),
                ('company_name', models.CharField(blank=True, max_length=255, verbose_name='企業名')),
                ('fiscal_year', models.IntegerField(db_index=True, help_text='例: 2024（2024年3月期 = 2024）', verbose_name='会計年度')),
                ('period_type', models.CharField(
                    choices=[
                        ('annual', '通期'),
                        ('q1', '第1四半期'),
                        ('q2', '第2四半期'),
                        ('q3', '第3四半期'),
                        ('half', '上半期'),
                    ],
                    default='annual',
                    max_length=10,
                    verbose_name='期間種別',
                )),
                # 予想値
                ('forecast_net_sales', models.DecimalField(blank=True, decimal_places=0, help_text='単位: 百万円', max_digits=20, null=True, verbose_name='予想売上高')),
                ('forecast_operating_income', models.DecimalField(blank=True, decimal_places=0, max_digits=20, null=True, verbose_name='予想営業利益')),
                ('forecast_ordinary_income', models.DecimalField(blank=True, decimal_places=0, max_digits=20, null=True, verbose_name='予想経常利益')),
                ('forecast_net_income', models.DecimalField(blank=True, decimal_places=0, max_digits=20, null=True, verbose_name='予想当期純利益')),
                ('forecast_eps', models.DecimalField(blank=True, decimal_places=2, help_text='1株当たり当期純利益（円）', max_digits=12, null=True, verbose_name='予想EPS')),
                ('forecast_revision_count', models.SmallIntegerField(default=0, help_text='当期中に何回業績予想を修正したか', verbose_name='予想修正回数')),
                ('forecast_announced_date', models.DateField(blank=True, null=True, verbose_name='予想発表日')),
                # 実績値
                ('actual_net_sales', models.DecimalField(blank=True, decimal_places=0, max_digits=20, null=True, verbose_name='実績売上高')),
                ('actual_operating_income', models.DecimalField(blank=True, decimal_places=0, max_digits=20, null=True, verbose_name='実績営業利益')),
                ('actual_ordinary_income', models.DecimalField(blank=True, decimal_places=0, max_digits=20, null=True, verbose_name='実績経常利益')),
                ('actual_net_income', models.DecimalField(blank=True, decimal_places=0, max_digits=20, null=True, verbose_name='実績当期純利益')),
                ('actual_eps', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='実績EPS')),
                ('actual_announced_date', models.DateField(blank=True, null=True, verbose_name='実績発表日')),
                # 達成率
                ('achievement_rate_net_sales', models.DecimalField(blank=True, decimal_places=2, help_text='実績 / 予想 × 100', max_digits=8, null=True, verbose_name='売上高達成率(%)')),
                ('achievement_rate_operating_income', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='営業利益達成率(%)')),
                ('achievement_rate_ordinary_income', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='経常利益達成率(%)')),
                ('achievement_rate_net_income', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='当期純利益達成率(%)')),
                # メタ
                ('source', models.CharField(
                    choices=[('tdnet', 'TDNET開示'), ('edinet', 'EDINET'), ('manual', '手動入力')],
                    default='tdnet',
                    max_length=20,
                    verbose_name='データソース',
                )),
                ('has_actual', models.BooleanField(default=False, help_text='実績値が登録されているか', verbose_name='実績確定済み')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='作成日時')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新日時')),
                # FK
                ('disclosure', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='earnings_forecasts',
                    to='earnings_analysis.tdnetdisclosure',
                    verbose_name='元開示情報',
                )),
            ],
            options={
                'verbose_name': '業績予想実績レコード',
                'verbose_name_plural': '業績予想実績一覧',
                'db_table': 'earnings_forecast_record',
                'ordering': ['-fiscal_year', 'company_code'],
            },
        ),
        migrations.AddConstraint(
            model_name='earningsforecast',
            constraint=models.UniqueConstraint(
                fields=['company_code', 'fiscal_year', 'period_type'],
                name='unique_forecast_per_period',
            ),
        ),
        migrations.AddIndex(
            model_name='earningsforecast',
            index=models.Index(fields=['company_code', '-fiscal_year'], name='idx_forecast_co_year'),
        ),
        migrations.AddIndex(
            model_name='earningsforecast',
            index=models.Index(fields=['has_actual'], name='idx_forecast_has_actual'),
        ),

        # ===== ForecastReliabilityScore =====
        migrations.CreateModel(
            name='ForecastReliabilityScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_code', models.CharField(db_index=True, max_length=10, unique=True, verbose_name='証券コード')),
                ('company_name', models.CharField(blank=True, max_length=255, verbose_name='企業名')),
                ('years_tracked', models.SmallIntegerField(default=0, help_text='実績データが揃っている年数', verbose_name='追跡年数')),
                ('earliest_fiscal_year', models.IntegerField(blank=True, null=True, verbose_name='最古会計年度')),
                ('latest_fiscal_year', models.IntegerField(blank=True, null=True, verbose_name='最新会計年度')),
                # 統計
                ('avg_achievement_rate', models.DecimalField(blank=True, decimal_places=2, help_text='全期間の代表達成率の平均', max_digits=8, null=True, verbose_name='平均達成率(%)')),
                ('std_achievement_rate', models.DecimalField(blank=True, decimal_places=2, help_text='低いほど予想が安定している', max_digits=8, null=True, verbose_name='達成率標準偏差')),
                ('min_achievement_rate', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='最低達成率(%)')),
                ('max_achievement_rate', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='最高達成率(%)')),
                # カウント
                ('beat_count', models.SmallIntegerField(default=0, verbose_name='超過達成回数（≥105%）')),
                ('met_count', models.SmallIntegerField(default=0, verbose_name='達成回数（95-105%）')),
                ('miss_count', models.SmallIntegerField(default=0, verbose_name='未達回数（<95%）')),
                # 傾向・評価
                ('forecast_tendency', models.CharField(
                    choices=[
                        ('very_conservative', '超保守的（大幅超過が常態）'),
                        ('conservative', '保守的（継続的に超過）'),
                        ('accurate', '精度高（±5%以内）'),
                        ('optimistic', '楽観的（未達傾向）'),
                        ('very_optimistic', '過度に楽観的（大幅未達が常態）'),
                        ('unknown', '判断不可'),
                    ],
                    default='unknown',
                    max_length=20,
                    verbose_name='予想傾向',
                )),
                ('reliability_score', models.IntegerField(
                    default=0,
                    help_text='予想の信頼性。高いほど予想通りに動く（保守的傾向も加点）',
                    validators=[
                        django.core.validators.MinValueValidator(0),
                        django.core.validators.MaxValueValidator(100),
                    ],
                    verbose_name='信頼性スコア',
                )),
                ('grade', models.CharField(
                    choices=[
                        ('S', 'S（最高信頼性）'),
                        ('A', 'A（高信頼性）'),
                        ('B', 'B（標準）'),
                        ('C', 'C（やや不安）'),
                        ('D', 'D（要注意）'),
                        ('N', 'N（データ不足）'),
                    ],
                    default='N',
                    max_length=2,
                    verbose_name='グレード',
                )),
                # 投資シグナル
                ('investment_signal', models.CharField(
                    choices=[
                        ('strong_positive', '強い買い（超保守×高信頼）'),
                        ('positive', '買い（保守×信頼）'),
                        ('neutral', '中立'),
                        ('caution', '注意（楽観傾向）'),
                        ('warning', '警戒（大幅未達常態）'),
                        ('insufficient_data', 'データ不足'),
                    ],
                    default='insufficient_data',
                    max_length=20,
                    verbose_name='投資シグナル',
                )),
                ('investment_signal_reason', models.TextField(blank=True, verbose_name='判断理由')),
                # 直近傾向
                ('recent_trend', models.CharField(
                    choices=[
                        ('improving', '改善中'),
                        ('stable', '安定'),
                        ('declining', '悪化中'),
                        ('unknown', '不明'),
                    ],
                    default='unknown',
                    max_length=20,
                    verbose_name='直近傾向',
                )),
                # タイムスタンプ
                ('last_calculated', models.DateTimeField(auto_now=True, verbose_name='最終計算日時')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='作成日時')),
            ],
            options={
                'verbose_name': '予想信頼性スコア',
                'verbose_name_plural': '予想信頼性スコア一覧',
                'db_table': 'earnings_forecast_reliability',
                'ordering': ['-reliability_score'],
            },
        ),
        migrations.AddIndex(
            model_name='forecastreliabilityscore',
            index=models.Index(fields=['-reliability_score'], name='idx_reliability_score'),
        ),
        migrations.AddIndex(
            model_name='forecastreliabilityscore',
            index=models.Index(fields=['investment_signal'], name='idx_reliability_signal'),
        ),
        migrations.AddIndex(
            model_name='forecastreliabilityscore',
            index=models.Index(fields=['grade'], name='idx_reliability_grade'),
        ),
    ]
