# ads/templatetags/ads_tags.py
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def google_adsense():
    ad_code = """
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX"
         crossorigin="anonymous"></script>
    """
    return mark_safe(ad_code)

@register.simple_tag
def display_ad(ad_slot, format='auto'):
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