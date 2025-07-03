# earnings_analysis/urls.py
from django.urls import path
from . import views
from .views import ui

app_name = 'earnings_analysis'

urlpatterns = [
    # ======== ユーザー画面 ========
    # トップページ
    path('', ui.IndexView.as_view(), name='index'),
    
    # 企業検索API（AJAX用）
    path('companies/search/', ui.CompanySearchAPIView.as_view(), name='company-search-api'),
    
    # 書類関連
    path('documents/', ui.DocumentListView.as_view(), name='document-list-ui'),
    path('documents/<str:doc_id>/', ui.DocumentDetailView.as_view(), name='document-detail-ui'),
    
    # 統計情報
    path('stats/', ui.SystemStatsView.as_view(), name='stats-ui'),
    
    # ======== API エンドポイント ========
    # 企業検索API
    path('api/companies/search/', views.CompanySearchView.as_view(), name='api-company-search'),
    
    # 書類検索・詳細API
    path('api/documents/', views.DocumentListView.as_view(), name='api-document-list'),
    path('api/documents/<str:doc_id>/', views.DocumentDetailView.as_view(), name='api-document-detail'),
    
    # ダウンロードAPI
    path('documents/<str:doc_id>/download/', views.DocumentDownloadView.as_view(), name='document-download'),
    
    # システム統計API
    path('api/stats/', views.SystemStatsView.as_view(), name='api-system-stats'),
    
    # バッチ履歴API
    path('api/batch-history/', views.BatchHistoryView.as_view(), name='api-batch-history'),
]