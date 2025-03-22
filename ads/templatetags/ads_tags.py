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
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX"
         crossorigin="anonymous"></script>
    """
    return mark_safe(ad_code)

@register.simple_tag
def display_ad(ad_slot, format='auto'):
    """
    指定されたスロットIDの広告を表示する
    例: {% display_ad "1234567890" %}
    """
    ad_code = """
    <ins class="adsbygoogle"
         style="display:block"
         data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
         data-ad-slot="{slot}"
         data-ad-format="{format}"></ins>
    <script>
         (adsbygoogle = window.adsbygoogle || []).push({});
    </script>
    """.format(slot=ad_slot, format=format)
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
    
    ad_code = """
    <div class="ad-container ad-{position}">
        <ins class="adsbygoogle"
             style="{style}"
             data-ad-client="ca-pub-{client}"
             data-ad-slot="{slot}"
             data-ad-format="{format}"></ins>
        <script>
             (adsbygoogle = window.adsbygoogle || []).push({});
        </script>
    </div>
    """.format(
        position=position,
        style=style,
        client=ad_unit.ad_client,
        slot=ad_unit.ad_slot,
        format=ad_unit.ad_format
    )
    
    return mark_safe(ad_code)