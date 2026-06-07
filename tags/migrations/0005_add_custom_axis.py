from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tags', '0004_auto_assign_tag_axis'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tag',
            name='axis',
            field=models.CharField(
                choices=[
                    ('theme', 'テーマ'),
                    ('business_model', 'ビジネスモデル'),
                    ('risk', 'リスク'),
                    ('capital_policy', '資本政策'),
                    ('macro', 'マクロ感応'),
                    ('event', 'イベント'),
                    ('custom', 'ラベル'),
                ],
                default='theme',
                max_length=20,
                verbose_name='軸',
            ),
        ),
    ]
