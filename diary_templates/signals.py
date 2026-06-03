from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .defaults import ensure_sample_template


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_sample_template_for_new_user(sender, instance, created, **kwargs):
    if created:
        ensure_sample_template(instance)
