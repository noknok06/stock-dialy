# subscriptions/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class SubscriptionPlan(models.Model):
    """サブスクリプションプランの定義"""
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    max_tags = models.IntegerField(default=5)
    max_templates = models.IntegerField(default=3)
    max_records = models.IntegerField(default=30)
    show_ads = models.BooleanField(default=True)
    export_enabled = models.BooleanField(default=False)
    advanced_analytics = models.BooleanField(default=False)
    price_monthly = models.DecimalField(max_digits=6, decimal_places=0, default=0)
    price_yearly = models.DecimalField(max_digits=8, decimal_places=0, default=0)
    # Stripeとの連携用ID
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True, help_text="Stripeの価格ID")
    display_order = models.PositiveIntegerField(default=0, help_text="表示順序")
    
    class Meta:
        ordering = ['display_order', 'price_monthly']
    
    def __str__(self):
        return self.name


class UserSubscription(models.Model):
    """ユーザーのサブスクリプション状態"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Stripeとの連携用フィールド
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    
    # ダウングレード予定の保存
    scheduled_downgrade_to = models.ForeignKey(
        SubscriptionPlan, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='scheduled_downgrades'
    )
    
    # キャンセル状態
    canceled_at = models.DateTimeField(null=True, blank=True)
    
    # メタデータ
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "ユーザーサブスクリプション"
        verbose_name_plural = "ユーザーサブスクリプション"
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"
    
    def is_valid(self):
        """サブスクリプションが有効かどうかを確認"""
        if not self.is_active:
            return False
        if self.end_date and timezone.now() > self.end_date:
            # サブスクリプションの期限切れを自動的に処理
            if self.scheduled_downgrade_to:
                self.apply_scheduled_downgrade()
            else:
                self.is_active = False
                self.save()
            return False
        return True
    
    def apply_scheduled_downgrade(self):
        """予定されたダウングレードを適用する"""
        if self.scheduled_downgrade_to:
            self.plan = self.scheduled_downgrade_to
            self.scheduled_downgrade_to = None
            self.save()
            
            # 広告設定も更新
            try:
                from ads.models import UserAdPreference
                ad_pref, _ = UserAdPreference.objects.get_or_create(
                    user=self.user,
                    defaults={
                        'show_ads': self.plan.show_ads,
                        'is_premium': not self.plan.show_ads,
                        'allow_personalized_ads': self.plan.show_ads
                    }
                )
                
                ad_pref.show_ads = self.plan.show_ads
                ad_pref.is_premium = not self.plan.show_ads
                ad_pref.allow_personalized_ads = self.plan.show_ads
                ad_pref.save()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error updating ad preferences during downgrade: {str(e)}")
            
            return True
        return False
    
    def schedule_downgrade(self, target_plan):
        """次の請求日時にダウングレードするようにスケジュール"""
        if self.current_period_end:
            self.scheduled_downgrade_to = target_plan
            self.save()
            return True
        # 期間情報がない場合は即時ダウングレード
        self.plan = target_plan
        self.save()
        return False
    
    def cancel(self):
        """サブスクリプションをキャンセルする（次の請求日に終了）"""
        # Stripeサブスクリプションがある場合
        if self.stripe_subscription_id:
            import stripe
            from django.conf import settings
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            try:
                # Stripeでのサブスクリプションキャンセル
                stripe_sub = stripe.Subscription.modify(
                    self.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                
                # キャンセル日時を記録
                self.canceled_at = timezone.now()
                
                # フリープランをスケジュール
                try:
                    free_plan = SubscriptionPlan.objects.get(slug='free')
                    self.schedule_downgrade(free_plan)
                except SubscriptionPlan.DoesNotExist:
                    pass
                
                self.save()
                return True
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error cancelling Stripe subscription: {str(e)}")
                return False
        else:
            # フリープランに変更
            try:
                free_plan = SubscriptionPlan.objects.get(slug='free')
                self.plan = free_plan
                self.canceled_at = timezone.now()
                self.save()
                return True
            except SubscriptionPlan.DoesNotExist:
                return False


class StripeCustomer(models.Model):
    """ユーザーとStripe顧客IDの関連付け"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stripe_customer')
    stripe_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['stripe_id']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.stripe_id}"


class SubscriptionEvent(models.Model):
    """サブスクリプションの変更履歴を保存するモデル"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, null=True)
    
    # イベントタイプの選択肢
    EVENT_TYPES = (
        ('created', '作成'),
        ('updated', '更新'),
        ('downgraded', 'ダウングレード'),
        ('upgraded', 'アップグレード'),
        ('canceled', 'キャンセル'),
        ('payment_succeeded', '支払い成功'),
        ('payment_failed', '支払い失敗'),
        ('trial_started', 'トライアル開始'),
        ('trial_ended', 'トライアル終了'),
    )
    
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    from_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='from_events')
    to_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='to_events')
    stripe_event_id = models.CharField(max_length=100, blank=True, null=True)
    
    # メタデータ
    created_at = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['stripe_event_id']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.event_type} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"