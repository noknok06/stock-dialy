# subscriptions/urls.py
from django.urls import path
from . import views
from . import webhooks

app_name = 'subscriptions'

urlpatterns = [
    path('upgrade/', views.UpgradeView.as_view(), name='upgrade'),
    path('checkout/<str:plan_id>/<str:type>/', views.CheckoutView.as_view(), name='checkout'),
    path('success/', views.SubscriptionSuccessView.as_view(), name='success'),
    path('downgrade/', views.DowngradeView.as_view(), name='downgrade'),
    path('usage/', views.SubscriptionUsageView.as_view(), name='usage'),
    path('plans/', views.PlanView.as_view(), name='plans'),
    
    # Stripe関連のURL
    path('webhook/', webhooks.stripe_webhook, name='webhook'),
    path('stripe-test/', views.StripeTestView.as_view(), name='stripe_test'),
    path('create-checkout-session/', views.CreateCheckoutSessionView.as_view(), name='create_checkout_session'),
    
    # リダイレクト用のヘルパー
    path('upgrade-to-plan/<str:slug>/', views.plan_redirect_view, name='upgrade_to_plan'),
    path('downgrade-to-plan/<str:slug>/', views.plan_redirect_view, name='downgrade_to_plan'),
]