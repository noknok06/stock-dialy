from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from config import views  # landing_page 用


# ---- ダミービュー定義 ----
def dummy_ads_view(request, *args, **kwargs):
    return HttpResponse("ads dummy")


# ---- ads 名前空間（ダミー） ----
ads_patterns = [
    path('privacy-policy/', dummy_ads_view, name='privacy_policy'),
    path('preferences/', dummy_ads_view, name='ad_preferences'),
    path('terms/', dummy_ads_view, name='terms'),
    path('faq/', dummy_ads_view, name='faq'),
    path('guide/', dummy_ads_view, name='guide'),
    path('api/preview/<int:ad_unit_id>/', dummy_ads_view, name='ad_preview_api'),
]


# ---- メインURL定義 ----
urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('users/', include('users.urls')),
    path('', include('stockdiary.urls')),
    path('checklist/', include('checklist.urls')),
    path('tags/', include('tags.urls')),
    path('analysis/', include('analysis_template.urls')),

    # ✅ landing_pageを個別登録
    path('', views.landing_page, name='landing_page'),

    # ✅ ads名前空間をダミーで登録
    path('ads/', include((ads_patterns, 'ads'), namespace='ads')),
]
