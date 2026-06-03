from django.conf import settings
from django.db import migrations

from diary_templates.defaults import SAMPLE_TEMPLATE_BODY, SAMPLE_TEMPLATE_TITLE


def seed_sample_template(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    DiaryTemplate = apps.get_model('diary_templates', 'DiaryTemplate')

    for user_id in User.objects.values_list('id', flat=True):
        DiaryTemplate.objects.get_or_create(
            user_id=user_id,
            title=SAMPLE_TEMPLATE_TITLE,
            defaults={'body': SAMPLE_TEMPLATE_BODY},
        )


def remove_sample_template(apps, schema_editor):
    DiaryTemplate = apps.get_model('diary_templates', 'DiaryTemplate')
    DiaryTemplate.objects.filter(
        title=SAMPLE_TEMPLATE_TITLE,
        body=SAMPLE_TEMPLATE_BODY,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('diary_templates', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(seed_sample_template, remove_sample_template),
    ]
