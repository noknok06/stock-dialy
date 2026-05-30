from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='diary_note_tag_limit',
            field=models.IntegerField(
                default=3,
                help_text='グラフの@タグ計算に使う継続記録の件数（直近N件）',
            ),
        ),
    ]
