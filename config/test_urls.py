# config/test_urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', include('stockdiary.urls')),
    path('checklist/', include('checklist.urls')),
    path('tags/', include('tags.urls')),
    path('analysis/', include('analysis_template.urls')),
    path('portfolio/', include('portfolio.urls')),
    # subscriptionsを除外
]