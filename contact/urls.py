# contact/urls.py
from django.urls import path
from . import views

app_name = 'contact'

urlpatterns = [
    path('', views.contact_view, name='contact'),
    path('verify/<uuid:token>/', views.verify_email, name='verify_email'),
    path('verification-sent/', views.verification_sent_view, name='verification_sent'),
    path('verification-expired/', views.verification_expired_view, name='verification_expired'),
    path('verification-failed/', views.verification_failed_view, name='verification_failed'),
    path('already-verified/', views.already_verified_view, name='already_verified'),
    path('success/', views.contact_success_view, name='success'),
]