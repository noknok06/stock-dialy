# earnings_analysis/urls.py （バッチ履歴URL追加版）
from django.urls import path
from . import views
from .views import ui, sentiment_ui, sentiment

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

    
    # ======== 感情分析機能 ========
    # 感情分析UI
    path('documents/<str:doc_id>/sentiment/', sentiment_ui.SentimentAnalysisView.as_view(), name='sentiment-analysis'),
    path('sentiment/result/<str:session_id>/', sentiment_ui.SentimentResultView.as_view(), name='sentiment-result'),
    
    # 感情分析API
    path('api/sentiment/analyze/', sentiment.SentimentAnalysisStartView.as_view(), name='sentiment-start'),
    path('api/sentiment/progress/', sentiment.SentimentAnalysisProgressView.as_view(), name='sentiment-progress'),
    path('api/sentiment/analyze/', sentiment.SentimentAnalysisResultView.as_view(), name='sentiment-result-api'),
    
    # ======== API エンドポイント ========
    # 企業検索API
    path('api/companies/search/', views.CompanySearchView.as_view(), name='api-company-search'),
    
    # 書類検索・詳細API
    path('api/documents/', views.DocumentListView.as_view(), name='api-document-list'),
    path('api/documents/<str:doc_id>/', views.DocumentDetailView.as_view(), name='api-document-detail'),
    
    # ダウンロードAPI
    path('documents/<str:doc_id>/download/', views.DocumentDownloadView.as_view(), name='document-download'),
]