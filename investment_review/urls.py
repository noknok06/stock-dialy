# investment_review/urls.py
from django.urls import path
from . import views

app_name = 'investment_review'

urlpatterns = [
    # ダッシュボード
    path('', views.InvestmentReviewDashboardView.as_view(), name='dashboard'),
    
    # レビュー管理
    path('list/', views.InvestmentReviewListView.as_view(), name='list'),
    path('<int:pk>/', views.InvestmentReviewDetailView.as_view(), name='detail'),
    
    # レビュー作成
    path('create/monthly/', views.CreateMonthlyReviewView.as_view(), name='create_monthly'),
    
    # レビュー操作
    path('<int:pk>/regenerate/', views.RegenerateReviewView.as_view(), name='regenerate'),
    path('<int:pk>/delete/', views.DeleteReviewView.as_view(), name='delete'),
    
    # AJAX API
    path('api/<int:pk>/status/', views.ReviewAnalysisStatusView.as_view(), name='analysis_status'),
]