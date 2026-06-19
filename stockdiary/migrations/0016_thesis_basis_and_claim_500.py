# 仮説(Thesis)の主張を複数行・長文可(500字)にし、根拠・理由(basis)の自由文を追加。
# docs/diary_recording_redesign.md 段階H（銘柄のまとめ）/ 仮説UX改善。

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stockdiary", "0015_reasonversion_diarynote_content_5000"),
    ]

    operations = [
        migrations.AlterField(
            model_name="thesis",
            name="claim",
            field=models.CharField(
                help_text="この投資の主張（複数行可）。例: 円安継続で輸出採算が改善する",
                max_length=500,
                verbose_name="主張",
            ),
        ),
        migrations.AddField(
            model_name="thesis",
            name="basis",
            field=models.TextField(
                blank=True,
                help_text="なぜこの主張が成り立つと考えるか（文章）",
                max_length=1000,
                verbose_name="根拠・理由",
            ),
        ),
    ]
