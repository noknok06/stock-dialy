"""
earnings_reports/urls.py
決算分析アプリの完全なURLパターン
"""

from django.urls import path, include
from . import views
from . import views_api

app_name = 'earnings_reports'

# メインURLパターン
urlpatterns = [
    # ===== メインページ =====
    path('', views.home, name='home'),
    
    # ===== 企業検索・書類選択・分析実行 =====
    path('search/', views.search_company, name='search_company'),
    path('company/<str:stock_code>/documents/', views.document_list, name='document_list'),
    
    # ===== 分析結果・状況確認 =====
    path('analysis/status/<str:analysis_ids>/', views.analysis_status, name='analysis_status'),
    path('analysis/<int:pk>/', views.analysis_detail, name='analysis_detail'),
    path('analysis/', views.analysis_list, name='analysis_list'),
    
    # ===== 企業ダッシュボード =====
    path('company/<str:stock_code>/', views.company_dashboard, name='company_dashboard'),
    
    # ===== エクスポート機能 =====
    path('export/company/<str:stock_code>/', views_api.export_company_data, name='export_company_data'),
    path('export/all/', views_api.export_all_data_api, name='export_all_data'),
    
    # ===== API エンドポイント =====
    path('api/', include([
        # 企業関連API
        path('companies/autocomplete/', views.company_autocomplete, name='company_autocomplete'),
        path('companies/search/', views_api.company_search_api, name='company_search_api'),
        path('company/<str:stock_code>/stats/', views_api.company_stats_api, name='company_stats_api'),
        
        # 分析関連API
        path('analysis/<int:analysis_id>/status/', views_api.analysis_status_api, name='analysis_status_api'),
        path('analysis/<int:analysis_id>/retry/', views_api.retry_analysis_api, name='retry_analysis_api'),
        path('analysis/trends/', views_api.analysis_trends_api, name='analysis_trends_api'),
        
        # ユーザー統計API
        path('stats/user/', views_api.user_stats_api, name='user_stats_api'),
        path('stats/industry-benchmark/', views_api.industry_benchmark_api, name='industry_benchmark_api'),
    ])),
    
    # ===== 管理機能（将来拡張用） =====
    path('management/', include([
        # path('bulk-analysis/', views.bulk_analysis, name='bulk_analysis'),
        # path('notifications/', views.notification_settings, name='notification_settings'),
        # path('company-comparison/', views.company_comparison, name='company_comparison'),
    ])),
    
    # ===== 互換性のための旧URL =====
    path('search-company/', views.search_company, name='search_company_old'),
    path('analysis-settings/<str:stock_code>/', views.document_list, name='analysis_settings_old'),
]