from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('earnings_analysis', '0004_financialanalysishistory_analysis_result'),
    ]

    operations = [
        migrations.AddField(
            model_name='sentimentanalysishistory',
            name='analysis_result',
            field=models.JSONField(blank=True, null=True, verbose_name='分析結果詳細'),
        ),
    ]
