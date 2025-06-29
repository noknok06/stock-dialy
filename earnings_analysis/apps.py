# earnings_analysis/apps.py
from django.apps import AppConfig


class EarningsAnalysisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'earnings_analysis'
    verbose_name = '決算分析'
    
    def ready(self):
        """アプリケーション起動時の初期化処理"""
        # シグナルハンドラーの登録などがある場合はここに記述
        pass