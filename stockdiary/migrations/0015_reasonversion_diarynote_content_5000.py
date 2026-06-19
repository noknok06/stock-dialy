# 見立ての来歴(ReasonVersion)追加と DiaryNote.content の上限 5000 化。
# docs/diary_recording_redesign.md 段階9a（N + ReasonVersion）。

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stockdiary", "0014_merge_20260619_1128"),
    ]

    operations = [
        migrations.AlterField(
            model_name="diarynote",
            name="content",
            field=models.TextField(
                blank=True, max_length=5000, verbose_name="記録内容"
            ),
        ),
        migrations.CreateModel(
            name="ReasonVersion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "content",
                    models.TextField(blank=True, max_length=5000, verbose_name="内容"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "diary",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reason_versions",
                        to="stockdiary.stockdiary",
                        verbose_name="日記",
                    ),
                ),
            ],
            options={
                "verbose_name": "見立ての版",
                "verbose_name_plural": "見立ての版",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["diary", "-created_at"],
                        name="stockdiary__diary_i_16be1f_idx",
                    )
                ],
            },
        ),
    ]
