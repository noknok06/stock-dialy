# analysis_template/apps.py
from django.apps import AppConfig


class AnalysisTemplateConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analysis_template'
    verbose_name = '分析テンプレート'