# ads/signals.py - サブスクリプション関連の参照を削除
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import UserAdPreference

# settings.AUTH_USER_MODEL を使用
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_ad_preference(sender, instance, created, **kwargs):
    """ユーザー作成時に広告設定を自動作成"""
    if created:
        # 広告設定の作成
        UserAdPreference.objects.create(
            user=instance,
            show_ads=True,
            is_premium=False, 
            allow_personalized_ads=True
        )