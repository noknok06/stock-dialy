# subscriptions/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import UserSubscription, SubscriptionPlan

class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # サブスクリプションがなければフリープランを割り当て
            try:
                subscription = request.user.subscription
                if not subscription.is_valid():
                    # 期限切れの場合はフリープランに戻す
                    try:
                        free_plan = SubscriptionPlan.objects.get(slug='free')
                        subscription.plan = free_plan
                        subscription.is_active = True
                        subscription.end_date = None
                        subscription.save()
                    except SubscriptionPlan.DoesNotExist:
                        # フリープランが存在しない場合は何もしない（エラー防止）
                        pass
            except (UserSubscription.DoesNotExist, AttributeError):
                # サブスクリプションがなければ作成を試みる
                try:
                    free_plan = SubscriptionPlan.objects.get(slug='free')
                    UserSubscription.objects.create(user=request.user, plan=free_plan)
                except SubscriptionPlan.DoesNotExist:
                    # フリープランが存在しない場合は何もしない（エラー防止）
                    pass
                
            # サブスクリプション情報をリクエストに追加（エラー処理を追加）
            try:
                request.subscription = request.user.subscription
            except (UserSubscription.DoesNotExist, AttributeError):
                # サブスクリプションがない場合はNoneを設定
                request.subscription = None
        
        response = self.get_response(request)
        return response