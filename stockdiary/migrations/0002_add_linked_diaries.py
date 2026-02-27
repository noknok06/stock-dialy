from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stockdiary", "0001_add_linked_diaries"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockdiary",
            name="linked_diaries",
            field=models.ManyToManyField(
                blank=True, to="stockdiary.stockdiary", verbose_name="関連日記"
            ),
        ),
    ]
