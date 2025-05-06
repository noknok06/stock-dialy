# financial_reports/urls.py
from django.urls import path
from . import views

app_name = 'financial_reports'

urlpatterns = [
    # 公開ビュー
    path('', views.ReportListView.as_view(), name='report_list'),
    path('company/<int:pk>/', views.CompanyDetailView.as_view(), name='company_detail'),
    path('report/<int:pk>/', views.ReportDetailView.as_view(), name='report_detail'),
    
    # 管理者ビュー
    path('admin/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('admin/company/create/', views.CompanyCreateView.as_view(), name='company_create'),
    path('admin/company/<int:pk>/update/', views.CompanyUpdateView.as_view(), name='company_update'),
    path('admin/report/create/', views.ReportCreateView.as_view(), name='report_create'),
    path('admin/report/<int:pk>/update/', views.ReportUpdateView.as_view(), name='report_update'),
    path('admin/report/<int:pk>/toggle-publish/', views.ReportTogglePublishView.as_view(), name='report_toggle_publish'),
]