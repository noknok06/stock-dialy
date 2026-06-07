from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("stockdiary", "0006_add_is_excluded_to_stockdiary"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="stockdiary",
            new_name="stockdiary__user_id_c5ff1c_idx",
            old_name="stockdiary__user_id_is_excl_idx",
        ),
    ]
