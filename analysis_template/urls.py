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
    path('<int:pk>/companies/', views.company_select, name='company_select'),
    path('<int:pk>/companies/add/', views.company_add, name='company_add'),
    path('<int:pk>/companies/<str:company_code>/remove/', views.company_remove, name='company_remove'),
    
    # 指標入力
    path('<int:pk>/metrics/', views.metrics_input, name='metrics_input'),
    
    # データ取得（API）
    path('<int:pk>/chart-data/', views.chart_data, name='chart_data'),
    path('api/company-autocomplete/', views.company_autocomplete, name='company_autocomplete'),
]