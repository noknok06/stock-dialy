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
    path('', include('allauth.urls')),
    path('google-login/', views.GoogleLoginView.as_view(), name='google_login'),
    path('profile/edit/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    path('profile/password/', views.CustomPasswordChangeView.as_view(), name='password_change'),

    # パスワードリセット関連のURL
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),    
]