# config/urls.py
"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import os
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from . import views
from django.contrib.staticfiles.storage import staticfiles_storage
from django.views.generic.base import RedirectView

urlpatterns = [
    # ランディングページ
    path('', views.landing_page, name='landing_page'),
    
    # 管理画面
    path("admin/", admin.site.urls),
    
    # ユーザー認証関連
    path("users/", include("users.urls")),
    path('accounts/', include('allauth.urls')),  # allauthのURLを追加
    
    # メインアプリケーション
    path('stockdiary/', include('stockdiary.urls')),  # stockdiary アプリのURL
    path('checklist/', include('checklist.urls')),  # checklistアプリのURL
    path('tags/', include('tags.urls')),
    path('analysis_template/', include('analysis_template.urls')),
    path('company_master/', include('company_master.urls')),
    path('portfolio/', include('portfolio.urls')),
    path('financial_reports/', include('financial_reports.urls')),
    
    #コーポマインドリーダー（新機能）
    path('copomo/', include('earnings_analysis.urls', namespace='copomo')),
    
    # サポート・サービス系
    path('subscriptions/', include('subscriptions.urls')),
    path('ads/', include('ads.urls')),
    path('security/', include('security.urls')),
    path('contact/', include('contact.urls')),
    
    # APIエンドポイント（将来的な拡張用）
    # path('api/v1/earnings/', include('earnings_analysis.urls')),  # API専用
]

# 静的ファイル関連
urlpatterns += [
    path('ads.txt', RedirectView.as_view(url=staticfiles_storage.url('ads.txt'))),
]

# 開発環境でのスタティックファイル配信
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# カスタムエラーページ（本番環境用）
#if not settings.DEBUG:
    # 404, 500エラーページのハンドラー
    #handler404 = 'config.views.custom_404'
    #handler500 = 'config.views.custom_500'