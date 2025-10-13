# subscriptions/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import UserSubscription, SubscriptionPlan

# subscriptions/middleware.py - 修正版
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import UserSubscription, SubscriptionPlan

class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # すべてのユーザーに無制限機能のプランを割り当て（広告表示あり）
            try:
                subscription = request.user.subscription
                
                # 無料プランを取得（または広告あり機能制限なしの特別プランを作成）
                try:
                    # 'free_unlimited' という新しいスラグで広告あり・制限なしのプランを作成/取得
                    free_unlimited_plan = SubscriptionPlan.objects.get(slug='free_unlimited')
                    
                    # 現在のプランが無制限プランでなければ更新
                    if subscription.plan.slug != 'free_unlimited':
                        subscription.plan = free_unlimited_plan
                        subscription.is_active = True
                        subscription.end_date = None
                        subscription.save()
                        
                        # 広告設定は表示するように設定
                        self.update_ad_preferences(request.user, show_ads=True)
                except SubscriptionPlan.DoesNotExist:
                    # 無制限プランがなければ作成
                    free_unlimited_plan = SubscriptionPlan.objects.create(
                        name='フリープラン（制限なし）',
                        slug='free_unlimited',
                        max_tags=-1,  # 無制限
                        max_templates=-1,  # 無制限
                        max_records=-1,  # 無制限
                        show_ads=True,  # 広告表示あり
                        export_enabled=True,
                        advanced_analytics=True,
                        price_monthly=0,  # 無料
                        price_yearly=0,   # 無料
                        display_order=5
                    )
                    subscription.plan = free_unlimited_plan
                    subscription.save()
            except (UserSubscription.DoesNotExist, AttributeError):
                # サブスクリプションがなければ作成
                try:
                    # 無制限プランを取得または作成
                    try:
                        free_unlimited_plan = SubscriptionPlan.objects.get(slug='free_unlimited')
                    except SubscriptionPlan.DoesNotExist:
                        free_unlimited_plan = SubscriptionPlan.objects.create(
                            name='フリープラン（制限なし）',
                            slug='free_unlimited',
                            max_tags=-1,  # 無制限
                            max_templates=-1,  # 無制限
                            max_records=-1,  # 無制限
                            show_ads=True,  # 広告表示あり
                            export_enabled=True,
                            advanced_analytics=True,
                            price_monthly=0,  # 無料
                            price_yearly=0,   # 無料
                            display_order=5
                        )
                    
                    # ユーザーに無制限プランのサブスクリプションを作成
                    UserSubscription.objects.create(user=request.user, plan=free_unlimited_plan)
                    
                    # 広告設定は表示に設定
                    self.update_ad_preferences(request.user, show_ads=True)
                except Exception as e:
                    # エラーは記録するが処理は続行
                    print(f"Error creating subscription: {str(e)}")
                
            # サブスクリプション情報をリクエストに追加
            try:
                request.subscription = request.user.subscription
            except (UserSubscription.DoesNotExist, AttributeError):
                request.subscription = None
        
        response = self.get_response(request)
        return response
    
    def update_ad_preferences(self, user, show_ads=True):
        """ユーザーの広告設定を更新（広告表示に設定）"""
        try:
            from ads.models import UserAdPreference
            ad_preference, _ = UserAdPreference.objects.get_or_create(
                user=user,
                defaults={
                    'show_ads': True,
                    'is_premium': False,
                    'allow_personalized_ads': True
                }
            )
            
            ad_preference.show_ads = True
            ad_preference.is_premium = False
            ad_preference.allow_personalized_ads = True
            ad_preference.save()
            return True
        except Exception as e:
            print(f"Error updating ad preferences: {str(e)}")
            return False

    # リソース警告チェックを無効化
    def check_resource_warnings(self, request):
        """リソース使用量の警告チェック（無効化）"""
        pass  # 制限なしのため警告表示不要