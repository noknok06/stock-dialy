from django.urls import path
from . import views

app_name = 'earnings_analysis'

urlpatterns = [
    # 企業検索
    path('companies/search/', views.CompanySearchView.as_view(), name='company-search'),
    
    # 書類検索・詳細
    path('documents/', views.DocumentListView.as_view(), name='document-list'),
    path('documents/<str:doc_id>/', views.DocumentDetailView.as_view(), name='document-detail'),
    
    # ダウンロード
    path('documents/<str:doc_id>/download/', views.DocumentDownloadView.as_view(), name='document-download'),
    
    # 統計情報
    path('stats/', views.SystemStatsView.as_view(), name='system-stats'),
    
    # バッチ履歴
    path('batch-history/', views.BatchHistoryView.as_view(), name='batch-history'),
]