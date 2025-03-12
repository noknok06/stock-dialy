# company_master/urls.py
from django.urls import path
from . import api

app_name = 'company_master'

urlpatterns = [
    # APIエンドポイント
    path('api/search/', api.search_company, name='api_search_company'),
    path('api/company/<str:code>/', api.get_company_info, name='api_get_company_info'),
]