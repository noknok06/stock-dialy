# Phase 8a: 検証ループ（Thesis / Verdict）の追加。純粋な追加のみ。
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stockdiary", "0010_notificationlog_disclosure_event_and_more"),
        ("tags", "0006_master_tag"),
    ]

    operations = [
        migrations.CreateModel(
            name="Thesis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("claim", models.CharField(help_text="この投資の主張を一文で（例: 円安継続で輸出採算が改善する）", max_length=200, verbose_name="主張")),
                ("horizon", models.CharField(choices=[("next_earnings", "次の決算まで"), ("3m", "3ヶ月"), ("6m", "6ヶ月"), ("1y", "1年"), ("long", "長期（1年超）")], default="6m", max_length=20, verbose_name="想定検証期間")),
                ("worst_case", models.CharField(blank=True, help_text="この仮説が崩れるとしたら何が起きたときか", max_length=300, verbose_name="最悪のケース")),
                ("review_due_date", models.DateField(blank=True, db_index=True, null=True, verbose_name="検証予定日")),
                ("status", models.CharField(choices=[("open", "未検証"), ("verified", "検証済み"), ("abandoned", "取り下げ")], db_index=True, default="open", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("basis_tags", models.ManyToManyField(blank=True, related_name="theses", to="tags.tag", verbose_name="根拠の軸")),
                ("diary", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="thesis", to="stockdiary.stockdiary")),
            ],
            options={"verbose_name": "仮説", "verbose_name_plural": "仮説"},
        ),
        migrations.CreateModel(
            name="Verdict",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("hypothesis_result", models.CharField(choices=[("hit", "的中"), ("partial", "部分的中"), ("miss", "外れ"), ("unknown", "判定不能")], max_length=10, verbose_name="仮説の当否")),
                ("pnl_result", models.CharField(choices=[("profit", "利益"), ("loss", "損失"), ("flat", "ほぼ変わらず"), ("holding", "保有中")], max_length=10, verbose_name="損益の結果")),
                ("decision_quality", models.PositiveSmallIntegerField(default=3, help_text="1〜5。再現したい判断ほど高い", verbose_name="判断の質")),
                ("missed_factor", models.CharField(blank=True, max_length=300, verbose_name="見落とした要因")),
                ("is_repeatable", models.BooleanField(default=False, verbose_name="再現したい判断")),
                ("learning", models.CharField(blank=True, help_text="次に活かす一文（引用される学びの原子）", max_length=200, verbose_name="学び")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("thesis", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="verdict", to="stockdiary.thesis")),
            ],
            options={"verbose_name": "検証", "verbose_name_plural": "検証"},
        ),
    ]
