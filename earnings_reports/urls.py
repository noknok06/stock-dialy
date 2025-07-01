"""
earnings_reports/urls.py
決算分析アプリのURL設定
"""

from django.urls import path
from . import views

app_name = 'earnings_reports'

urlpatterns = [
    # ============================================
    # メイン機能
    # ============================================
    
    # ホーム画面
    path('', views.home, name='home'),
    
    # 企業検索・選択
    path('search/', views.search_company, name='search_company'),
    path('api/companies/autocomplete/', views.company_autocomplete, name='company_autocomplete'),
    
    # 書類一覧・選択
    path('company/<str:stock_code>/documents/', views.document_list, name='document_list'),
    
    # 分析設定・実行
    path('company/<str:stock_code>/analysis/settings/', views.analysis_settings, name='analysis_settings'),
    path('analysis/status/<str:analysis_ids>/', views.analysis_status, name='analysis_status'),
    
    # 分析結果
    path('analysis/<int:pk>/', views.analysis_detail, name='analysis_detail'),
    path('analyses/', views.analysis_list, name='analysis_list'),
    
    # 企業ダッシュボード
    path('company/<str:stock_code>/', views.company_dashboard, name='company_dashboard'),
    
    # ============================================
    # 高度な機能
    # ============================================
    
    # 一括分析
    # path('bulk-analysis/', views.bulk_analysis, name='bulk_analysis'),
    # path('bulk-analysis/execute/', views.execute_bulk_analysis, name='execute_bulk_analysis'),
    
    # 比較分析
    # path('compare/', views.compare_companies, name='compare_companies'),
    # path('compare/result/', views.compare_result, name='compare_result'),
    
    # 業界分析
    # path('industry/<str:sector>/', views.industry_analysis, name='industry_analysis'),
    
    # ============================================
    # 管理・設定
    # ============================================
    
    # 通知設定
    # path('settings/notifications/', views.notification_settings, name='notification_settings'),
    
    # データエクスポート
    # path('export/company/<str:stock_code>/', views.export_company_data, name='export_company_data'),
    # path('export/analyses/', views.export_analysis_data, name='export_analysis_data'),
    
    # ============================================
    # API エンドポイント
    # ============================================
    
    # 分析進捗API
    # path('api/analysis/<int:analysis_id>/status/', views.api_analysis_status, name='api_analysis_status'),
    
    # チャートデータAPI
    # path('api/company/<str:stock_code>/chart-data/', views.api_company_chart_data, name='api_company_chart_data'),
    # path('api/analysis/<int:pk>/chart-data/', views.api_analysis_chart_data, name='api_analysis_chart_data'),
    
    # 統計データAPI
    # path('api/stats/user/', views.api_user_stats, name='api_user_stats'),
    # path('api/stats/industry/<str:sector>/', views.api_industry_stats, name='api_industry_stats'),
    
    # 決算カレンダーAPI
    # path('api/earnings-calendar/', views.api_earnings_calendar, name='api_earnings_calendar'),
    
    # ============================================
    # 管理機能（スタッフ用）
    # ============================================
    
    # システム統計
    # path('admin/stats/', views.admin_stats, name='admin_stats'),
    
    # # データ同期
    # path('admin/sync/companies/', views.admin_sync_companies, name='admin_sync_companies'),
    # path('admin/sync/documents/<str:stock_code>/', views.admin_sync_documents, name='admin_sync_documents'),
]