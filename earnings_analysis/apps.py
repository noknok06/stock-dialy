from django.apps import AppConfig

class EarningsAnalysisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'earnings_analysis'
    verbose_name = '決算分析・書類管理'
    
    def ready(self):
        # シグナル等の初期化処理
        try:
            import earnings_analysis.signals
        except ImportError:
            pass