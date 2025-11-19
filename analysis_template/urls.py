# analysis_template/urls.py
from django.urls import path
from . import views

app_name = 'analysis_template'

urlpatterns = [
    # テンプレート管理
    path('', views.TemplateListView.as_view(), name='list'),
    path('create/', views.TemplateCreateView.as_view(), name='create'),
    path('<int:pk>/', views.template_detail, name='detail'),
    path('<int:pk>/update/', views.template_update, name='update'),
    path('<int:pk>/delete/', views.template_delete, name='delete'),
    path('<int:pk>/duplicate/', views.template_duplicate, name='duplicate'),  # ⭐ 複製
    path('<int:pk>/export/', views.template_export, name='export'),  # ⭐ エクスポート
    
    # 企業選択
    path('<int:pk>/company-select/', views.company_select, name='company_select'),
    
    # 指標管理
    path('<int:pk>/metrics/input/', views.metrics_input, name='metrics_input'),
    path('<int:pk>/metrics/', views.metrics_edit, name='metrics_edit'),
    path('<int:pk>/calculate/', views.calculate_scores, name='calculate_scores'),
    
    # 自動取得機能
    path('<int:pk>/metrics/auto-fetch/', views.metrics_auto_fetch, name='metrics_auto_fetch'),
    path('<int:pk>/api/check-availability/', views.check_api_availability, name='check_api_availability'),
    
    # API
    path('api/company/search/', views.company_search_ajax, name='company_search_ajax'),
    path('<int:pk>/api/company/<int:company_id>/metrics/', 
         views.company_metrics_ajax, name='company_metrics_ajax'),
    path('<int:pk>/api/company/remove/', 
         views.company_remove_api, name='company_remove_api'),
    
    # ⭐ 一括削除
    path('bulk-delete/', views.template_bulk_delete, name='bulk_delete'),
]