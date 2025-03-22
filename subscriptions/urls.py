# subscriptions/urls.py
from django.urls import path
from . import views

app_name = 'subscriptions'

urlpatterns = [
    path('upgrade/', views.UpgradeView.as_view(), name='upgrade'),
    path('checkout/<str:plan_id>/<str:type>/', views.CheckoutView.as_view(), name='checkout'),
    path('success/', views.SubscriptionSuccessView.as_view(), name='success'),
    path('downgrade/', views.DowngradeView.as_view(), name='downgrade'),
    path('usage/', views.SubscriptionUsageView.as_view(), name='usage'),
    path('plans/', views.PlanView.as_view(), name='plans'),
    # path('webhook/', views.StripeWebhookView.as_view(), name='webhook'),
]