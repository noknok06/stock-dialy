# ads/views.py - 新しいサブスクリプションプラン構造に対応
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from .models import UserAdPreference
from subscriptions.models import UserSubscription, SubscriptionPlan

def privacy_policy(request):
    """プライバシーポリシーのビュー"""
    return render(request, 'ads/privacy_policy.html')

@login_required
def ad_preferences(request):
    """ユーザーの広告設定ページ - サブスクリプション新構造対応版"""
    # ユーザーのサブスクリプション情報を取得
    is_premium = False
    is_free = True  # デフォルトはフリープラン
    subscription_plan = None
    
    try:
        subscription = UserSubscription.objects.get(user=request.user)
        if subscription.is_valid():
            # 広告非表示プラン判定
            is_premium = not subscription.plan.show_ads
            # フリープラン判定
            is_free = subscription.plan.slug == 'free'
            # プラン情報
            subscription_plan = subscription.plan
    except UserSubscription.DoesNotExist:
        # サブスクリプションがない場合はフリープラン扱い
        try:
            subscription_plan = SubscriptionPlan.objects.get(slug='free')
        except SubscriptionPlan.DoesNotExist:
            # フリープランが存在しない場合はNoneのまま
            pass
    
    # 広告設定の取得または作成
    try:
        preference = UserAdPreference.objects.get(user=request.user)
    except UserAdPreference.DoesNotExist:
        preference = UserAdPreference.objects.create(
            user=request.user,
            show_ads=not is_premium,
            is_premium=is_premium,
            allow_personalized_ads=is_free
        )
    
    # プランに基づいて広告設定を自動的に更新
    update_needed = False
    
    if is_premium:
        # 有料プラン（basic/pro）の場合、広告を非表示
        if preference.show_ads or not preference.is_premium:
            preference.show_ads = False
            preference.is_premium = True
            update_needed = True
            
        # 有料プランの場合、パーソナライズ広告も無効化
        if preference.allow_personalized_ads:
            preference.allow_personalized_ads = False
            update_needed = True
    else:
        # フリープランの場合、広告を表示
        if not preference.show_ads or preference.is_premium:
            preference.show_ads = True
            preference.is_premium = False
            update_needed = True
        
        # フリープランの場合は、パーソナライズ広告も有効化
        if is_free and not preference.allow_personalized_ads:
            preference.allow_personalized_ads = True
            update_needed = True
    
    if update_needed:
        preference.save()
        print(f"Updated ad preferences in view for user {request.user.username}: "
              f"plan={subscription_plan.slug if subscription_plan else 'unknown'}, "
              f"show_ads={preference.show_ads}, is_premium={preference.is_premium}, "
              f"allow_personalized_ads={preference.allow_personalized_ads}")
    
    # 利用可能なすべてのプランを取得
    try:
        all_plans = SubscriptionPlan.objects.all().order_by('display_order')
    except:
        all_plans = []
    
    # テンプレートにコンテキストを渡す
    context = {
        'preference': preference,
        'is_premium': is_premium,
        'is_free': is_free,
        'subscription_plan': subscription_plan,
        'all_plans': all_plans,
    }
    
    return render(request, 'ads/ad_preferences.html', context)