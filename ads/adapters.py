# ads/adapters.py
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from .models import UserAdPreference
from subscriptions.models import UserSubscription, SubscriptionPlan

class AdsEnabledSocialAccountAdapter(DefaultSocialAccountAdapter):
    """広告設定に対応したソーシャルアカウントアダプター"""
    
    def pre_social_login(self, request, sociallogin):
        """ソーシャルログイン前の処理 - 既存のadaptersを継承"""
        # 既存の処理を実行（users/adapters.pyのCustomSocialAccountAdapterに定義されたもの）
        super().pre_social_login(request, sociallogin)
        
    def save_user(self, request, sociallogin, form=None):
        """ユーザー保存時に広告設定も初期化"""
        # 通常のユーザー保存処理
        user = super().save_user(request, sociallogin, form)
        
        # Google認証で初めてのログインの場合
        if sociallogin.account.provider == 'google':
            # 広告設定の取得または作成
            ad_preference, created = UserAdPreference.objects.get_or_create(
                user=user,
                defaults={
                    'show_ads': True,
                    'is_premium': False,
                    'allow_personalized_ads': True
                }
            )
            
            # サブスクリプションを確認
            try:
                subscription = UserSubscription.objects.filter(user=user).first()
                
                # サブスクリプションがなければフリープランを設定
                if not subscription:
                    try:
                        free_plan = SubscriptionPlan.objects.get(slug='free')
                        UserSubscription.objects.create(
                            user=user,
                            plan=free_plan,
                            is_active=True
                        )
                    except SubscriptionPlan.DoesNotExist:
                        # フリープランが見つからない場合はスキップ
                        pass
            except Exception:
                # エラーが発生した場合は処理をスキップ
                pass
        
        return user