# stockdiary/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class StockdiaryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'stockdiary'
    
    def ready(self):
        """アプリ起動時に実行"""
        # マイグレーション中はスキップ
        import sys
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return
        
        try:
            # 通知スケジュールを設定
            from .tasks import setup_notification_schedule
            setup_notification_schedule()
            logger.info("✅ stockdiaryアプリ準備完了")
        except Exception as e:
            logger.warning(f"⚠️ 通知スケジュール設定スキップ: {e}")