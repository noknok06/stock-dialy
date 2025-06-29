# earnings_analysis/urls.py（更新版）
"""
決算分析用URLパターン（フロントエンド対応版）
"""

from django.urls import path
from . import api, views

app_name = 'earnings_analysis'

urlpatterns = [
    # === フロントエンド画面 ===
    # メイン画面
    path('', views.EarningsMainView.as_view(), name='main'),
    
    # 企業比較画面（将来実装）
    path('compare/', views.EarningsCompareView.as_view(), name='compare'),
    
    # 業界分析画面（将来実装）
    path('industry/', views.industry_analysis_view, name='industry'),
    
    # === HTML パーシャル ===
    # 企業検索結果
    path('search/', views.search_companies_view, name='search_companies'),
    
    # 分析詳細（HTML）
    path('detail/<str:company_code>/', views.analysis_detail_view, name='analysis_detail'),
    
    # ポートフォリオ分析（HTML）
    path('portfolio/', views.portfolio_analysis_view, name='portfolio_analysis'),
    
    # 最新分析結果パーシャル
    path('recent/', views.recent_analyses_partial, name='recent_analyses'),
    
    # === JSON API エンドポイント ===
    # メイン分析API
    path('api/analyze/<str:company_code>/', api.analyze_company, name='api_analyze_company'),
    
    # 分析状況確認API
    path('api/status/<str:company_code>/', api.get_analysis_status, name='api_analysis_status'),
    
    # 企業検索API（JSON）
    path('api/search/', api.search_companies, name='api_search_companies'),
    
    # 分析再実行API
    path('api/refresh/<str:company_code>/', views.refresh_analysis_view, name='api_refresh_analysis'),
    
    # 企業状況API
    path('api/company-status/<str:company_code>/', views.company_status_view, name='api_company_status'),
    
    # アラート管理API
    path('api/alerts/setup/', api.setup_earnings_alert, name='api_setup_alert'),
    path('api/alerts/', api.get_user_alerts, name='api_user_alerts'),
    
    # ポートフォリオ分析API（JSON）
    path('api/portfolio/', api.get_portfolio_analysis, name='api_portfolio_analysis'),
    
    # 分析サマリーAPI
    path('api/summary/', api.get_analysis_summary, name='api_analysis_summary'),
    
    # クイック分析API（開発・テスト用）
    path('api/quick-analyze/', api.QuickAnalysisView.as_view(), name='api_quick_analyze'),
    
    # === レガシーエンドポイント（互換性のため） ===
    # 旧形式のAPIエンドポイント（リダイレクト用）
    path('api/company/<str:company_code>/', api.analyze_company, name='api_company_analysis_legacy'),
]

# デバッグ用のURLパターン（開発時のみ有効）
from django.conf import settings
if settings.DEBUG:
    urlpatterns += [
        # テスト用のAPIエンドポイント
        # path('debug/edinet/', views.debug_edinet_view, name='debug_edinet'),
        # path('debug/analysis/<str:company_code>/', views.debug_analysis_view, name='debug_analysis'),
    ]