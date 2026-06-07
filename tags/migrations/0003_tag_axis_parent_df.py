from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tags', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
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
                ],
                default='theme',
                max_length=20,
                verbose_name='軸',
            ),
        ),
        migrations.AddField(
            model_name='tag',
            name='parent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='children',
                to='tags.tag',
                verbose_name='親タグ',
            ),
        ),
        migrations.AddField(
            model_name='tag',
            name='df',
            field=models.PositiveIntegerField(default=0, verbose_name='出現銘柄数'),
        ),
        migrations.AlterModelOptions(
            name='tag',
            options={'ordering': ['axis', 'name']},
        ),
    ]
