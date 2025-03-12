# analysis_template/urls.py
from django.urls import path
from . import views
from . import api  # APIモジュールをインポート

app_name = 'analysis_template'

urlpatterns = [
    path('', views.AnalysisTemplateListView.as_view(), name='list'),
    path('create/', views.AnalysisTemplateCreateView.as_view(), name='create'),
    path('<int:pk>/', views.AnalysisTemplateDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.AnalysisTemplateUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.AnalysisTemplateDeleteView.as_view(), name='delete'),
    path('<int:pk>/report/', views.AnalysisReportView.as_view(), name='report'),
    
    # API URLs
    path('api/items/', api.get_template_items, name='api_get_items'),
]