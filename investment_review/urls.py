# investment_review/urls.py
from django.urls import path
from . import views

app_name = 'investment_review'

urlpatterns = [
    # 既存のURL（そのまま保持）
    path('', views.InvestmentReviewListView.as_view(), name='list'),
    path('dashboard/', views.InvestmentReviewDashboardView.as_view(), name='dashboard'),
    path('create-monthly/', views.CreateMonthlyReviewView.as_view(), name='create_monthly'),
    path('<int:pk>/', views.InvestmentReviewDetailView.as_view(), name='detail'),
    path('<int:pk>/regenerate/', views.RegenerateReviewView.as_view(), name='regenerate'),
    path('<int:pk>/delete/', views.DeleteReviewView.as_view(), name='delete'),
    path('<int:pk>/status/', views.ReviewAnalysisStatusView.as_view(), name='analysis_status'),
    
    # ポートフォリオ評価機能（新規追加）
    path('portfolio/', views.PortfolioEvaluationView.as_view(), name='portfolio_evaluation'),
    path('portfolio/history/', views.PortfolioEvaluationHistoryView.as_view(), name='portfolio_history'),
    path('portfolio/<int:pk>/', views.PortfolioEvaluationDetailView.as_view(), name='portfolio_evaluation_detail'),
    path('portfolio/<int:pk>/status/', views.PortfolioEvaluationStatusAPIView.as_view(), name='portfolio_evaluation_api_status'),
    path('portfolio/<int:pk>/delete/', views.PortfolioEvaluationDeleteView.as_view(), name='portfolio_evaluation_delete'),
    path('portfolio/comparison/', views.PortfolioComparisonView.as_view(), name='portfolio_comparison'),
]