# ads/views.py - 新しいサブスクリプションプラン構造に対応
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import TemplateView


from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import user_passes_test
from django.utils.html import escape
from .models import AdUnit

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


@require_GET
@user_passes_test(lambda u: u.is_staff)  # 管理者のみアクセス可能
def ad_preview_api(request, ad_unit_id):
    """広告プレビュー用のAPIビュー"""
    try:
        ad_unit = AdUnit.objects.get(id=ad_unit_id)
        
        # 広告コードの生成（実際のタグを生成するが、エスケープして文字列として返す）
        style = ad_unit.custom_style if ad_unit.custom_style else "display:block;"
        html_code = f"""<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ad_unit.ad_client}" crossorigin="anonymous"></script>
<ins class="adsbygoogle"
     style="{style}"
     data-ad-client="{ad_unit.ad_client}"
     data-ad-slot="{ad_unit.ad_slot}"
"""
        
        if ad_unit.ad_format and ad_unit.ad_format != 'auto':
            html_code += f'     data-ad-format="{ad_unit.ad_format}"\n'
        
        if ad_unit.is_fluid:
            html_code += '     data-ad-format="fluid"\n'
            
        if ad_unit.ad_layout:
            html_code += f'     data-ad-layout="{ad_unit.ad_layout}"\n'
            
        if ad_unit.ad_layout_key:
            html_code += f'     data-ad-layout-key="{ad_unit.ad_layout_key}"\n'
        
        html_code += """></ins>
<script>
     (adsbygoogle = window.adsbygoogle || []).push({});
</script>"""
        
        # HTMLコードをエスケープ
        html_code_escaped = escape(html_code)
        
        return JsonResponse({
            'id': ad_unit.id,
            'name': ad_unit.name,
            'placement': str(ad_unit.placement),
            'ad_client': ad_unit.ad_client,
            'ad_slot': ad_unit.ad_slot,
            'ad_format': ad_unit.ad_format,
            'is_fluid': ad_unit.is_fluid,
            'width': ad_unit.width,
            'height': ad_unit.height,
            'template_type': ad_unit.template_type,
            'ad_layout': ad_unit.ad_layout,
            'ad_layout_key': ad_unit.ad_layout_key,
            'html_code': html_code_escaped
        })
    except AdUnit.DoesNotExist:
        return JsonResponse({'error': '広告ユニットが見つかりません'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)    