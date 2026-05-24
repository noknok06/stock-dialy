from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stockdiary', '0003_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='diarynote',
            name='topic',
            field=models.CharField(blank=True, db_index=True, default='', help_text='分析テーマ（例: ナフサの影響）。空欄可', max_length=50, verbose_name='トピック'),
        ),
    ]
