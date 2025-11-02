# config/test_urls.py
from django.contrib import admin
from django.urls import path, include
from config import views  # ← 追加

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('users/', include('users.urls')),
    path('', include('stockdiary.urls')),
    path('checklist/', include('checklist.urls')),
    path('tags/', include('tags.urls')),
    path('analysis/', include('analysis_template.urls')),

    # ↓ landing_pageだけ個別登録
    path('', views.landing_page, name='landing_page'),
]
