# ads/views.py - 広告設定ビューの更新 - サブスクリプション対応
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from .models import UserAdPreference
from subscriptions.models import UserSubscription

def privacy_policy(request):
    """プライバシーポリシーのビュー"""
    return render(request, 'ads/privacy_policy.html')

@login_required
def ad_preferences(request):
    """ユーザーの広告設定ページ - サブスクリプション対応"""
    # ユーザーのサブスクリプション情報を取得
    is_premium = False
    premium_controls_ads = False
    is_free = False
    
    try:
        subscription = UserSubscription.objects.get(user=request.user)
        if subscription.is_valid():
            # プレミアムプラン（広告非表示プラン）の場合
            is_premium = not subscription.plan.show_ads
            premium_controls_ads = not subscription.plan.show_ads
            # フリープランの場合
            is_free = subscription.plan.slug == 'free'
    except UserSubscription.DoesNotExist:
        # サブスクリプションがない場合はフリープラン扱い
        is_free = True
    
    # 広告設定の取得または作成
    try:
        preference = UserAdPreference.objects.get(user=request.user)
    except UserAdPreference.DoesNotExist:
        preference = UserAdPreference.objects.create(user=request.user)
    
    # POSTリクエスト（設定更新）の処理
    if request.method == 'POST':
        # プレミアムプランで広告表示が制御される場合は設定変更を制限
        if premium_controls_ads:
            messages.info(request, "現在のプランでは広告表示は自動的に無効化されます。設定を変更する必要はありません。")
            return redirect('ads:ad_preferences')
        
        # フリープランの場合は広告表示をオフにできない
        if is_free:
            messages.info(request, "フリープランでは広告表示は必須です。広告を非表示にするにはプランのアップグレードが必要です。")
            return redirect('ads:ad_preferences')
        
        # フォームから値を取得
        allow_personalized_ads = request.POST.get('allow_personalized_ads') == 'on'
        
        # 設定を更新
        preference.allow_personalized_ads = allow_personalized_ads
        
        # フリープランでは強制的に広告表示をオン
        if is_free:
            preference.show_ads = True
        
        preference.save()
        
        messages.success(request, '広告設定を更新しました。')
        return redirect('ads:ad_preferences')
    
    # プレミアムプラン情報をテンプレートに渡す
    return render(request, 'ads/ad_preferences.html', {
        'preference': preference,
        'is_premium': is_premium,
        'premium_controls_ads': premium_controls_ads,
        'is_free': is_free
    })