from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stockdiary', '0006_add_is_excluded_to_stockdiary'),
        ('tags', '0003_tag_axis_parent_df'),
    ]

    operations = [
        migrations.CreateModel(
            name='DiaryTagDirection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('direction', models.CharField(
                    choices=[
                        ('up', '↑ プラス影響'),
                        ('down', '↓ マイナス影響'),
                        ('neutral', '→ 中立'),
                    ],
                    default='neutral',
                    max_length=10,
                    verbose_name='影響方向',
                )),
                ('diary', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tag_directions',
                    to='stockdiary.stockdiary',
                )),
                ('tag', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='diary_directions',
                    to='tags.tag',
                )),
            ],
            options={
                'verbose_name': 'タグ方向属性',
                'verbose_name_plural': 'タグ方向属性',
                'unique_together': {('diary', 'tag')},
            },
        ),
    ]
