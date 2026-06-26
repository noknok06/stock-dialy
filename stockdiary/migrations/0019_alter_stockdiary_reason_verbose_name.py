# reason フィールドの役割再定義（投資理由 → 背景）に伴う verbose_name 変更。
# DB スキーマには影響しない（表示名のみ）。docs/diary_recording_redesign.md 改訂2 を参照。
#
# 注: makemigrations は memo 削除・thesis.diary などの既存ドリフトも検出するが、
# それらは本変更とは無関係の別件のため、この migration には含めない（reason のみ）。
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stockdiary", "0018_merge_20260620_2115"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stockdiary",
            name="reason",
            field=models.TextField(blank=True, max_length=5000, verbose_name="背景"),
        ),
    ]
