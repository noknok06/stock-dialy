# ads/templatetags/ads_tags.py - テンプレートタグの修正

from django import template
from django.utils.safestring import mark_safe
from ..models import AdUnit, AdPlacement

register = template.Library()

@register.simple_tag
def google_adsense():
    """
    GoogleアドセンスのJavaScriptライブラリをロードするタグ
    例: {% google_adsense %}
    """
    ad_code = """
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-3954701883136363"
         crossorigin="anonymous"></script>
    """
    return mark_safe(ad_code)

@register.simple_tag(takes_context=True)
def display_ad(context, ad_slot, format='auto'):
    # パーソナライズ広告の設定を取得
    personalized_ads = context.get('personalized_ads', True)
    
    ad_code = """
    <ins class="adsbygoogle"
         style="display:block"
         data-ad-client="ca-pub-3954701883136363"
         data-ad-slot="{slot}"
         data-ad-format="{format}"
         {personalized}></ins>
    <script>
         (adsbygoogle = window.adsbygoogle || []).push({});
    </script>
    """.format(
        slot=ad_slot,
        format=format,
        personalized='' if personalized_ads else 'data-adtest="on" data-ad-channel="non-personalized"'
    )
    return mark_safe(ad_code)
    
@register.simple_tag(takes_context=True)
def show_placement_ad(context, position):
    """指定された配置位置の広告を表示する"""
    # 広告表示が無効の場合は何も表示しない
    if not context.get('show_ads', True):
        return ''
    
    # コンテキストプロセッサで設定された広告配置を取得
    ad_placements = context.get('ad_placements', {})
    placement_data = ad_placements.get(position)
    
    if not placement_data:
        return ''
    
    ad_unit = placement_data.get('ad_unit')
    if not ad_unit:
        return ''
    
    # シンプルな形式の広告コード
    ad_code = f"""
    <div class="ad-container ad-{position}">
        <ins class="adsbygoogle"
             style="display:block"
             data-ad-client="{ad_unit.ad_client}"
             data-ad-slot="{ad_unit.ad_slot}"
             data-ad-format="auto"
             data-full-width-responsive="true"></ins>
        <script>
             (adsbygoogle = window.adsbygoogle || []).push({{}});
        </script>
    </div>
    """
    
    return mark_safe(ad_code)