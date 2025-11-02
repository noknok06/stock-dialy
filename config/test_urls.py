# config/test_urls.py
from django.contrib import admin
from django.urls import path, include
from config import views  # ← 追加
from django.http import HttpResponse


def dummy_ads_view(request):
    return HttpResponse("ads dummy")

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
    # 🩵 ads 名前空間だけダミーで登録
    path('ads/ad-preferences/', dummy_ads_view, name='ad_preferences'),
]


# 名前空間を手動登録
from django.urls import include
urlpatterns += [
    path('ads/', include(([
        path('ad-preferences/', dummy_ads_view, name='ad_preferences'),
    ], 'ads'), namespace='ads'))
]