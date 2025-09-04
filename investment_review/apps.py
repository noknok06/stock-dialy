# investment_review/apps.py
from django.apps import AppConfig


class InvestmentReviewConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'investment_review'
    verbose_name = '投資振り返り'