# subscriptions/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class SubscriptionPlan(models.Model):
    """サブスクリプションプランの定義"""
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    max_tags = models.IntegerField(default=5)
    max_templates = models.IntegerField(default=3)
    max_snapshots = models.IntegerField(default=3)
    max_records = models.IntegerField(default=30)
    show_ads = models.BooleanField(default=True)
    export_enabled = models.BooleanField(default=False)
    advanced_analytics = models.BooleanField(default=False)
    price_monthly = models.DecimalField(max_digits=6, decimal_places=0, default=0)
    price_yearly = models.DecimalField(max_digits=8, decimal_places=0, default=0)
    
    def __str__(self):
        return self.name

class UserSubscription(models.Model):
    """ユーザーのサブスクリプション状態"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"
    
    def is_valid(self):
        """サブスクリプションが有効かどうかを確認"""
        if not self.is_active:
            return False
        if self.end_date and timezone.now() > self.end_date:
            self.is_active = False
            self.save()
            return False
        return True

class StripeCustomer(models.Model):
    """ユーザーとStripe顧客IDの関連付け"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stripe_customer')
    stripe_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.stripe_id}"