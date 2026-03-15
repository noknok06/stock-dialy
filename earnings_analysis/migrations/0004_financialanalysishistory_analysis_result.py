from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('earnings_analysis', '0003_batchexecution_company_companyfinancialdata_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='financialanalysishistory',
            name='analysis_result',
            field=models.JSONField(
                blank=True,
                help_text='セッション期限切れ後も参照できる全結果JSON',
                null=True,
                verbose_name='分析結果詳細',
            ),
        ),
    ]
