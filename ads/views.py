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
    """ユーザーの広告設定ページ - サブスクリプション遷移なし版"""
    # 広告設定の取得または作成
    try:
        preference = UserAdPreference.objects.get(user=request.user)
    except UserAdPreference.DoesNotExist:
        preference = UserAdPreference.objects.create(
            user=request.user,
            show_ads=True,
            is_premium=False,
            allow_personalized_ads=True
        )
    
    # テンプレートにコンテキストを渡す
    context = {
        'preference': preference,
    }
    
    return render(request, 'ads/ad_preferences.html', context)


class TermsView(TemplateView):
    template_name = 'ads/terms.html'
    
class FAQView(TemplateView):
    template_name = 'ads/faq.html'

class InvestmentGuideView(TemplateView):
    """投資記録ガイドページを表示するビュー"""
    template_name = 'ads/guide.html'