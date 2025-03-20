# subscriptions/context_processors.py
def subscription_status(request):
    """サブスクリプション情報をテンプレートに提供"""
    context = {
        'show_ads': True,  # デフォルトは広告表示
        'is_pro': False,
        'subscription_name': 'フリー'
    }
    
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return context
    
    try:
        subscription = request.user.subscription
        if subscription and subscription.is_valid():
            context['show_ads'] = subscription.plan.show_ads
            context['is_pro'] = subscription.plan.slug == 'pro'
            context['subscription_name'] = subscription.plan.name
    except (AttributeError, Exception):
        # エラーが発生した場合はデフォルト値を使用
        pass
    
    return context