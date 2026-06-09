from django.conf import settings
from django.db import migrations

from diary_templates.defaults import BASIC_TEMPLATE_BODY, BASIC_TEMPLATE_TITLE


def seed_basic_template(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    DiaryTemplate = apps.get_model('diary_templates', 'DiaryTemplate')

    for user_id in User.objects.values_list('id', flat=True):
        DiaryTemplate.objects.get_or_create(
            user_id=user_id,
            title=BASIC_TEMPLATE_TITLE,
            defaults={'body': BASIC_TEMPLATE_BODY},
        )


def remove_basic_template(apps, schema_editor):
    DiaryTemplate = apps.get_model('diary_templates', 'DiaryTemplate')
    DiaryTemplate.objects.filter(
        title=BASIC_TEMPLATE_TITLE,
        body=BASIC_TEMPLATE_BODY,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('diary_templates', '0002_seed_sample_template'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(seed_basic_template, remove_basic_template),
    ]
