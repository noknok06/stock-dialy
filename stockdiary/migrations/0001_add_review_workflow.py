"""
Migration: Add periodic review workflow fields and model.

Changes:
- DiaryNote: add is_review (BooleanField), review_verdict (CharField)
- New model: ReviewSchedule
"""
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('stockdiary', '__first__'),
    ]

    operations = [
        # DiaryNote.is_review フィールド追加
        migrations.AddField(
            model_name='diarynote',
            name='is_review',
            field=models.BooleanField(default=False, verbose_name='定期レビュー'),
        ),
        # DiaryNote.review_verdict フィールド追加
        migrations.AddField(
            model_name='diarynote',
            name='review_verdict',
            field=models.CharField(
                blank=True,
                choices=[
                    ('valid',     '✅ 仮説は有効'),
                    ('partially', '⚠️ 部分的に有効'),
                    ('invalid',   '❌ 仮説は無効'),
                ],
                max_length=20,
                null=True,
                verbose_name='レビュー判定',
            ),
        ),
        # ReviewSchedule モデル追加
        migrations.CreateModel(
            name='ReviewSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('interval_days', models.PositiveIntegerField(
                    choices=[(30, '1ヶ月'), (60, '2ヶ月'), (90, '3ヶ月（推奨）'), (180, '6ヶ月')],
                    default=90,
                    verbose_name='レビュー間隔（日）',
                )),
                ('next_review_date', models.DateField(verbose_name='次回レビュー日')),
                ('is_active', models.BooleanField(default=True, verbose_name='有効')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('diary', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='review_schedules',
                    to='stockdiary.stockdiary',
                    verbose_name='対象日記',
                )),
            ],
            options={
                'verbose_name': '定期レビュースケジュール',
                'verbose_name_plural': '定期レビュースケジュール',
                'ordering': ['next_review_date'],
                'indexes': [
                    models.Index(fields=['next_review_date', 'is_active'], name='stockdiary_review_next_date_idx'),
                ],
            },
        ),
    ]
