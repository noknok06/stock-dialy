"""memo フィールドのデータを reason に統合したマイグレーション。
本番環境ではローカルで適用済みのため、ここでは no-op として記録のみ行う。
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stockdiary', '0010_notificationlog_disclosure_event_and_more'),
    ]

    operations = [
    ]
