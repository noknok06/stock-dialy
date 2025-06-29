# earnings_analysis/urls.py（簡略化版）
"""
オンデマンド決算分析用URLパターン

特定企業の個別分析に特化したエンドポイント
"""

from django.urls import path
from . import api

app_name = 'earnings_analysis'

urlpatterns = [
    # メイン分析API
    path('api/analyze/<str:company_code>/', api.analyze_company, name='api_analyze_company'),
    
    # 分析状況確認API
    path('api/status/<str:company_code>/', api.get_analysis_status, name='api_analysis_status'),
    
    # 企業検索API
    path('api/search/', api.search_companies, name='api_search_companies'),
    
    # アラート管理API
    path('api/alerts/setup/', api.setup_earnings_alert, name='api_setup_alert'),
    path('api/alerts/', api.get_user_alerts, name='api_user_alerts'),
    
    # ポートフォリオ分析API（stockdiaryアプリとの連携）
    path('api/portfolio/', api.get_portfolio_analysis, name='api_portfolio_analysis'),
    
    # 分析サマリーAPI
    path('api/summary/', api.get_analysis_summary, name='api_analysis_summary'),
    
    # クイック分析API（開発・テスト用）
    path('api/quick-analyze/', api.QuickAnalysisView.as_view(), name='api_quick_analyze'),
]

# レガシーエンドポイント（互換性のため）
urlpatterns += [
    # 旧形式のAPIエンドポイント（リダイレクト用）
    path('api/company/<str:company_code>/', api.analyze_company, name='api_company_analysis_legacy'),
]