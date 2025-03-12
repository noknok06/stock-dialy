# company_master/apps.py
from django.apps import AppConfig


class CompanyMasterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'company_master'
    verbose_name = '企業マスタ'