from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class MarginTrackingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'margin_tracking'
    verbose_name = '信用倍率管理'

    def ready(self):
        # Django-Q スケジュール登録（マイグレーション適用後のみ実行）
        try:
            from margin_tracking.tasks import setup_margin_fetch_schedule
            setup_margin_fetch_schedule()
        except Exception:
            # マイグレーション未適用時など DB が存在しない場合はスキップ
            pass
