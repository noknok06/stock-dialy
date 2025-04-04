# ads/apps.py - シグナルを登録するための設定
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class AdsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ads'
    verbose_name = _('広告管理')
    
    def ready(self):
        import ads.signals  # シグナルを読み込む