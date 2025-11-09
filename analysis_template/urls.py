# analysis_template/urls.py
from django.urls import path
from . import views

app_name = 'analysis_template'

urlpatterns = [
    # テンプレート管理
    path('', views.template_list, name='list'),
    path('create/', views.template_create, name='create'),
    path('<int:pk>/', views.template_detail, name='detail'),
    path('<int:pk>/edit/', views.template_edit, name='edit'),
    path('<int:pk>/delete/', views.template_delete, name='delete'),
    
    # 指標管理
    path('<int:pk>/metrics/', views.metrics_edit, name='metrics_edit'),
    path('<int:pk>/calculate/', views.calculate_scores, name='calculate_scores'),
    
    # API
    path('api/company/search/', views.company_search_ajax, name='company_search_ajax'),
    path('<int:pk>/api/company/<int:company_id>/metrics/', 
         views.company_metrics_ajax, name='company_metrics_ajax'),
]