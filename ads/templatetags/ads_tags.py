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

# ads/templatetags/ads_tags.py に追加

@register.simple_tag(takes_context=True)
def show_template_ad(context, template_type):
    """指定されたテンプレートタイプの広告を表示する"""
    # 広告表示が無効の場合は何も表示しない
    if not context.get('show_ads', True):
        return ''
    
    # テンプレートタイプに一致する広告ユニットを取得
    try:
        ad_unit = AdUnit.objects.filter(
            is_active=True,
            template_type=template_type
        ).first()
        
        if not ad_unit:
            return ''
        
        # パーソナライズ広告の設定を取得
        personalized_ads = context.get('personalized_ads', True)
        
        # スタイル属性を構築
        style = ad_unit.custom_style if ad_unit.custom_style else "display:block;"
        
        # 広告コードを構築
        ad_code = f"""
        <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ad_unit.ad_client}"
             crossorigin="anonymous"></script>
        <ins class="adsbygoogle"
             style="{style}"
             data-ad-client="{ad_unit.ad_client}"
             data-ad-slot="{ad_unit.ad_slot}"
        """
        
        # オプション属性を追加
        if ad_unit.ad_format:
            ad_code += f'data-ad-format="{ad_unit.ad_format}"\n'
        if ad_unit.ad_layout:
            ad_code += f'data-ad-layout="{ad_unit.ad_layout}"\n'
        if ad_unit.ad_layout_key:
            ad_code += f'data-ad-layout-key="{ad_unit.ad_layout_key}"\n'
        if ad_unit.is_fluid:
            ad_code += 'data-ad-format="fluid"\n'
        if not personalized_ads:
            ad_code += 'data-adtest="on" data-ad-channel="non-personalized"\n'
            
        # 広告コードを完成させる
        ad_code += """></ins>
        <script>
             (adsbygoogle = window.adsbygoogle || []).push({});
        </script>
        """
        
        # カスタムJSがあれば追加
        if ad_unit.custom_js:
            ad_code += f"<script>{ad_unit.custom_js}</script>"
            
        return mark_safe(ad_code)
        
    except Exception as e:
        # エラー時は何も表示しない（開発時のみログ出力）
        if settings.DEBUG:
            print(f"広告表示エラー: {e}")
        return ''