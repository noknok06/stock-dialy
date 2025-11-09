# analysis_template/urls.py
from django.urls import path
from . import views

app_name = 'analysis_template'

urlpatterns = [
    # テンプレート管理
    path('', views.template_list, name='list'),
    path('create/', views.template_create, name='create'),
    path('<int:pk>/', views.template_detail, name='detail'),
    path('<int:pk>/update/', views.template_update, name='update'),
    path('<int:pk>/delete/', views.template_delete, name='delete'),
    
    # 企業選択
    path('<int:pk>/company-select/', views.company_select, name='company_select'),
    
    # 指標管理
    path('<int:pk>/metrics/input/', views.metrics_input, name='metrics_input'),
    path('<int:pk>/metrics/', views.metrics_edit, name='metrics_edit'),
    path('<int:pk>/calculate/', views.calculate_scores, name='calculate_scores'),
    
    # API
    path('api/company/search/', views.company_search_ajax, name='company_search_ajax'),
    path('<int:pk>/api/company/<int:company_id>/metrics/', 
         views.company_metrics_ajax, name='company_metrics_ajax'),
]