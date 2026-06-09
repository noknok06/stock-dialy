from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .defaults import ensure_basic_template


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_default_template_for_new_user(sender, instance, created, **kwargs):
    # 新規ユーザーには「基本テンプレート」のみ配布する。
    # 重厚版「サンプルテンプレート」はテンプレート一覧から任意で追加できる。
    if created:
        ensure_basic_template(instance)
