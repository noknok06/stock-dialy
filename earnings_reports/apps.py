"""
earnings_reports/apps.py
決算分析アプリ設定
"""

from django.apps import AppConfig


class EarningsReportsConfig(AppConfig):
    """決算分析アプリ設定"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'earnings_reports'
    verbose_name = '決算分析システム'
    
    def ready(self):
        """アプリ準備完了時の処理"""
        # シグナルハンドラーの登録
        import earnings_reports.signals