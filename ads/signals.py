# ads/signals.py - ユーザーモデル参照の修正
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import UserAdPreference
from subscriptions.models import UserSubscription

# settings.AUTH_USER_MODEL を使用
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_ad_preference(sender, instance, created, **kwargs):
    """ユーザー作成時に広告設定とサブスクリプションを自動作成"""
    if created:
        # 広告設定の作成
        UserAdPreference.objects.create(user=instance)
        
        # サブスクリプション情報を確認
        try:
            # サブスクリプションが既に存在するか確認
            subscription = UserSubscription.objects.filter(user=instance).first()
            
            # サブスクリプションがなければ何もしない（middleware側で処理される）
            if subscription and subscription.is_valid():
                # サブスクリプションに基づいて広告設定を調整
                ad_preference = UserAdPreference.objects.get(user=instance)
                
                # プランの広告表示設定に合わせて調整
                ad_preference.show_ads = subscription.plan.show_ads
                if not subscription.plan.show_ads:
                    # 有料プランの場合
                    ad_preference.is_premium = True
                
                ad_preference.save()
        except Exception:
            # エラーが発生した場合はデフォルト設定のまま
            pass


@receiver(post_save, sender=UserSubscription)
def update_user_ad_preference(sender, instance, **kwargs):
    """サブスクリプション変更時に広告設定を更新"""
    try:
        # ユーザーの広告設定を取得
        ad_preference, created = UserAdPreference.objects.get_or_create(
            user=instance.user,
            defaults={'show_ads': instance.plan.show_ads}
        )
        
        # プランの広告表示設定を反映
        ad_preference.show_ads = instance.plan.show_ads
        
        # プレミアム状態を設定（広告非表示プランの場合はプレミアム扱い）
        ad_preference.is_premium = not instance.plan.show_ads
        
        # プランに応じてパーソナライズ広告設定を更新
        if instance.plan.slug == 'free':
            # フリープランの場合はパーソナライズ広告を有効化
            ad_preference.allow_personalized_ads = True
        else:
            # 有料プラン（広告非表示プラン）の場合はパーソナライズ広告を無効化
            # 広告自体が表示されないため、この設定は実質的に意味がないが一貫性のために設定
            ad_preference.allow_personalized_ads = False
        
        ad_preference.save()
        
        # 変更後のログを出力（デバッグ用）
        print(f"Updated ad preferences for user {instance.user.username}: show_ads={ad_preference.show_ads}, is_premium={ad_preference.is_premium}, allow_personalized_ads={ad_preference.allow_personalized_ads}")
        
    except Exception as e:
        # エラーが発生した場合は処理をスキップ
        print(f"Error updating ad preferences: {str(e)}")