# earnings_analysis/urls.py （財務分析URL追加版）
from django.urls import path
from . import views
from .views import ui, sentiment_ui, sentiment, financial_ui, financial

app_name = 'earnings_analysis'

urlpatterns = [
    # ======== ユーザー画面 ========
    # トップページ
    path('', ui.IndexView.as_view(), name='index'),
    
    path('company/<str:edinet_code>/', ui.CompanyDetailView.as_view(), name='company-detail-ui'), 
    
    # 企業検索API（AJAX用）
    path('companies/search/', ui.CompanySearchAPIView.as_view(), name='company-search-api'),
    
    # 書類関連
    path('documents/', ui.DocumentListView.as_view(), name='document-list-ui'),
    path('documents/<str:doc_id>/', ui.DocumentDetailView.as_view(), name='document-detail-ui'),

    
    # ======== 感情分析機能 ========
    # 感情分析UI
    path('sentiment/<str:doc_id>/', sentiment_ui.SentimentAnalysisView.as_view(), name='sentiment-analysis'),
    path('sentiment/result/<str:session_id>/', sentiment_ui.SentimentResultView.as_view(), name='sentiment-result'),
    
    # 感情分析API
    path('api/sentiment/analyze/', sentiment.SentimentAnalysisStartView.as_view(), name='sentiment-start'),
    path('api/sentiment/progress/', sentiment.SentimentAnalysisProgressView.as_view(), name='sentiment-progress'),
    path('api/sentiment/result/', sentiment.SentimentAnalysisResultView.as_view(), name='sentiment-result-api'),
    
    # ======== 財務分析機能 ========
    # 財務分析UI
    path('financial/<str:doc_id>/', financial_ui.FinancialAnalysisView.as_view(), name='financial-analysis'),
    path('financial/result/<str:session_id>/', financial_ui.FinancialResultView.as_view(), name='financial-result'),
    path('financial/data/', financial_ui.FinancialDataView.as_view(), name='financial-data-list'),
    path('financial/stats/', financial_ui.FinancialStatsView.as_view(), name='financial-stats'),
    path('financial/comparison/', financial_ui.CompanyFinancialComparisonView.as_view(), name='financial-comparison'),
    
    # 財務分析API
    path('api/financial/analyze/', financial.FinancialAnalysisStartView.as_view(), name='financial-start'),
    path('api/financial/progress/', financial.FinancialAnalysisProgressView.as_view(), name='financial-progress'),
    path('api/financial/result/', financial.FinancialAnalysisResultView.as_view(), name='financial-result-api'),
    path('api/financial/data/', financial.FinancialDataAPIView.as_view(), name='api-financial-data'),
    path('api/financial/history/', financial.FinancialAnalysisHistoryView.as_view(), name='api-financial-history'),
    path('api/financial/stats/', financial.FinancialStatsAPIView.as_view(), name='api-financial-stats'),
    
    # ======== API エンドポイント ========
    # 企業検索API
    path('api/companies/search/', views.CompanySearchView.as_view(), name='api-company-search'),
    
    # 書類検索・詳細API
    path('api/documents/', views.DocumentListView.as_view(), name='api-document-list'),
    path('api/documents/<str:doc_id>/', views.DocumentDetailView.as_view(), name='api-document-detail'),
    
    # ダウンロードAPI
    path('documents/<str:doc_id>/download/', views.DocumentDownloadView.as_view(), name='document-download'),
]