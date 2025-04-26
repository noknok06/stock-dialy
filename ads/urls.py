# ads/urls.py
from django.urls import path
from . import views

app_name = 'ads'

urlpatterns = [
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('preferences/', views.ad_preferences, name='ad_preferences'),
    
    path('terms/', views.TermsView.as_view(), name='terms'),
    path('faq/', views.FAQView.as_view(), name='faq'),
    path('guide/', views.InvestmentGuideView.as_view(), name='guide'),

    path('api/preview/<int:ad_unit_id>/', views.ad_preview_api, name='ad_preview_api'),
]