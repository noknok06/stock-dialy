from django.db import migrations, models


def seed_master_tags(apps, schema_editor):
    """厳選コア標準タグを MasterTag に投入する。

    種データは stockdiary.tag_axis_config.CORE_MASTER_TAGS。
    重複（既存 name）はスキップする（再実行・手動編集後の安全性確保）。
    """
    MasterTag = apps.get_model('tags', 'MasterTag')
    try:
        from stockdiary.tag_axis_config import CORE_MASTER_TAGS
    except Exception:
        CORE_MASTER_TAGS = {}

    existing = set(MasterTag.objects.values_list('name', flat=True))
    to_create = [
        MasterTag(name=name, axis=axis, is_active=True, sort_order=idx)
        for idx, (name, axis) in enumerate(CORE_MASTER_TAGS.items())
        if name not in existing
    ]
    if to_create:
        MasterTag.objects.bulk_create(to_create)


def unseed_master_tags(apps, schema_editor):
    # CreateModel の逆操作でテーブルごと削除されるため、データ削除は不要。
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tags', '0005_add_custom_axis'),
    ]

    operations = [
        migrations.CreateModel(
            name='MasterTag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True, verbose_name='タグ名')),
                ('axis', models.CharField(
                    choices=[
                        ('theme', 'テーマ'),
                        ('business_model', 'ビジネスモデル'),
                        ('risk', 'リスク'),
                        ('capital_policy', '資本政策'),
                        ('macro', 'マクロ感応'),
                        ('event', 'イベント'),
                        ('custom', 'ラベル'),
                    ],
                    default='theme',
                    max_length=20,
                    verbose_name='軸',
                )),
                ('is_active', models.BooleanField(default=True, verbose_name='有効')),
                ('sort_order', models.IntegerField(default=0, verbose_name='表示順')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '標準タグ',
                'verbose_name_plural': '標準タグ',
                'ordering': ['sort_order', 'axis', 'name'],
            },
        ),
        migrations.RunPython(seed_master_tags, unseed_master_tags),
    ]
