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
    """
    指定された配置位置の広告を表示する
    例: {% show_placement_ad "header" %}
    """
    # 広告表示が無効の場合は何も表示しない
    if not context.get('show_ads', True):
        return ''
    
    # パーソナライズ広告の設定を取得
    personalized_ads = context.get('personalized_ads', True)
    
    # コンテキストプロセッサで設定された広告配置を取得
    ad_placements = context.get('ad_placements', {})
    placement_data = ad_placements.get(position)
    
    if not placement_data:
        return ''  # 指定された位置に有効な広告が見つからない
    
    ad_unit = placement_data.get('ad_unit')
    if not ad_unit:
        return ''
    
    # 広告サイズの設定
    style = "display:block;"
    if ad_unit.width and ad_unit.height and ad_unit.ad_format != 'responsive':
        style += f"width:{ad_unit.width}px;height:{ad_unit.height}px;"
    
    # JavaScript部分のために波括弧をエスケープ
    personalized_attr = '' if personalized_ads else 'data-adtest="on" data-ad-channel="non-personalized"'
    
    # 修正：data-full-width-responsive の値を "true" に変更（文字列として）
    ad_code = f"""
    <div class="ad-container ad-{position}">
        <span class="ad-label">広告</span>
        <ins class="adsbygoogle"
            style="{style}"
            data-ad-client="{ad_unit.ad_client}"
            data-ad-slot="{ad_unit.ad_slot}"
            data-ad-format="{ad_unit.ad_format}"
            data-full-width-responsive="true"
            {personalized_attr}></ins>
        <script>
            (adsbygoogle = window.adsbygoogle || []).push({{}});
        </script>
    </div>
    """
    
    return mark_safe(ad_code)