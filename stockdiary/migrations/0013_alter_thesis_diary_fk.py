import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Thesis.diary を OneToOneField から ForeignKey に変更し、
    1 つの日記に複数の仮説を記録できるようにする。"""

    dependencies = [
        ("stockdiary", "0012_remove_stockdiary_memo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="thesis",
            name="diary",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="theses",
                to="stockdiary.stockdiary",
            ),
        ),
        migrations.AlterModelOptions(
            name="thesis",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "仮説",
                "verbose_name_plural": "仮説",
            },
        ),
    ]
