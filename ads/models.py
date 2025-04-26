# ads/models.py の修正 - ユーザーモデル参照の修正

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings  # settings.AUTH_USER_MODEL を使用するため

class AdPlacement(models.Model):
    """広告の配置場所を定義するモデル"""
    POSITION_CHOICES = [
        ('header', 'ヘッダー'),
        ('sidebar', 'サイドバー'),
        ('content_top', 'コンテンツ上部'),
        ('content_bottom', 'コンテンツ下部'),
        ('footer', 'フッター'),
    ]
    
    name = models.CharField(_('配置名'), max_length=100)
    position = models.CharField(_('配置位置'), max_length=50, choices=POSITION_CHOICES)
    description = models.TextField(_('説明'), blank=True)
    is_active = models.BooleanField(_('有効'), default=True)
    
    class Meta:
        verbose_name = _('広告配置')
        verbose_name_plural = _('広告配置')
        
    def __str__(self):
        return f"{self.name} ({self.get_position_display()})"


class AdUnit(models.Model):
    """GoogleアドセンスのAd Unitを管理するモデル"""
    name = models.CharField(_('ユニット名'), max_length=100)
    ad_client = models.CharField(_('ad-client ID'), max_length=100, help_text=_('例: ca-pub-3954701883136363'))
    ad_slot = models.CharField(_('ad-slot ID'), max_length=100)
    
    template_type = models.CharField(
        _('テンプレートタイプ'), 
        max_length=50, 
        blank=True, 
        help_text=_('特定のテンプレート用（例：diary_tab、diary_list）')
    )
    ad_layout = models.CharField(
        _('広告レイアウト'), 
        max_length=100, 
        blank=True, 
        help_text=_('data-ad-layout値（例：in-article）')
    )
    ad_layout_key = models.CharField(
        _('広告レイアウトキー'), 
        max_length=100, 
        blank=True, 
        help_text=_('data-ad-layout-key値（例：-h2+d+5c-9-3e）')
    )
    custom_style = models.TextField(
        _('カスタムスタイル'), 
        blank=True, 
        help_text=_('カスタムCSSスタイル（例：display:block; text-align:center;）')
    )
    custom_js = models.TextField(
        _('カスタムJS'), 
        blank=True, 
        help_text=_('追加のJavaScriptコード')
    )
    is_fluid = models.BooleanField(
        _('Fluid広告'), 
        default=False,
        help_text=_('Fluid型広告の場合はチェック')
    )

    # 広告フォーマット
    FORMAT_CHOICES = [
        ('auto', '自動'),
        ('horizontal', '水平バナー'),
        ('vertical', '垂直バナー'),
        ('rectangle', 'レクタングル'),
        ('responsive', 'レスポンシブ'),
        ('fluid', '流体'),
    ]
    ad_format = models.CharField(_('広告フォーマット'), max_length=20, choices=FORMAT_CHOICES, default='auto')
    
    # サイズ（レスポンシブの場合は空白可）
    width = models.PositiveIntegerField(_('幅'), null=True, blank=True)
    height = models.PositiveIntegerField(_('高さ'), null=True, blank=True)
    
    # 配置場所
    placement = models.ForeignKey(AdPlacement, on_delete=models.CASCADE, related_name='ad_units')
    
    # 管理フラグ
    is_active = models.BooleanField(_('有効'), default=True)
    
    class Meta:
        verbose_name = _('広告ユニット')
        verbose_name_plural = _('広告ユニット')
        
    def __str__(self):
        return f"{self.name} - {self.placement.name}"


class UserAdPreference(models.Model):
    """ユーザーごとの広告表示設定"""
    # ここを修正: auth.User への直接参照から settings.AUTH_USER_MODEL への参照に変更
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ad_preference')
    show_ads = models.BooleanField(_('広告を表示する'), default=True)
    is_premium = models.BooleanField(_('プレミアムユーザー'), default=False, help_text=_('プレミアムユーザーは広告が表示されません'))
    allow_personalized_ads = models.BooleanField(_('パーソナライズ広告を許可'), default=True)
    
    class Meta:
        verbose_name = _('ユーザー広告設定')
        verbose_name_plural = _('ユーザー広告設定')
        
    def __str__(self):
        return f"{self.user.username}の広告設定"
    
    def should_show_ads(self):
        """広告を表示すべきかどうかを判定"""
        return self.show_ads and not self.is_premium