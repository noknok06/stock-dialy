# users/urls.py
from django.urls import path, include
from . import views

app_name = 'users'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('account/delete/confirm/', views.AccountDeleteConfirmView.as_view(), name='account_delete_confirm'),
    path('account/delete/', views.AccountDeleteView.as_view(), name='account_delete'),
    # django-allauthのURLを含める
    path('google-login/', views.GoogleLoginView.as_view(), name='google_login'),
    path('', include('allauth.urls')),
]