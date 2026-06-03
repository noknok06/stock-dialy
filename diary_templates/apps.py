from django.apps import AppConfig


class DiaryTemplatesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'diary_templates'
    verbose_name = '日記入力テンプレート'

    def ready(self):
        from . import signals  # noqa: F401
