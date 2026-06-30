# Generated for the earnings calendar feature.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("earnings_analysis", "0004_earningsschedule"),
        ("stockdiary", "0019_alter_stockdiary_reason_verbose_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="stockdiary",
            name="next_earnings_date",
            field=models.DateField(
                blank=True, db_index=True, null=True, verbose_name="次回決算予定日"
            ),
        ),
        migrations.AddField(
            model_name="stockdiary",
            name="next_earnings_type",
            field=models.CharField(
                blank=True, max_length=50, verbose_name="次回決算種別"
            ),
        ),
        migrations.AddField(
            model_name="notificationlog",
            name="earnings_schedule",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="notification_logs",
                to="earnings_analysis.earningsschedule",
            ),
        ),
        migrations.AddConstraint(
            model_name="notificationlog",
            constraint=models.UniqueConstraint(
                condition=models.Q(("earnings_schedule__isnull", False)),
                fields=("user", "earnings_schedule"),
                name="uniq_user_earnings_schedule",
            ),
        ),
    ]
