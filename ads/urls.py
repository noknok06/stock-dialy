# ads/urls.py
from django.urls import path
from . import views

app_name = 'ads'

urlpatterns = [
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('preferences/', views.ad_preferences, name='ad_preferences'),
]