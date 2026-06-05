from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stockdiary", "0005_stockdiary_currency"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockdiary",
            name="is_excluded",
            field=models.BooleanField(
                default=False,
                verbose_name="除外フラグ",
                db_index=True,
            ),
        ),
        migrations.AddIndex(
            model_name="stockdiary",
            index=models.Index(fields=["user", "is_excluded"], name="stockdiary__user_id_is_excl_idx"),
        ),
    ]
