"""0011_merge_memo_into_reason と 0011_thesis_verdict を統合するマージマイグレーション。"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stockdiary', '0011_merge_memo_into_reason'),
        ('stockdiary', '0011_thesis_verdict'),
    ]

    operations = [
    ]
