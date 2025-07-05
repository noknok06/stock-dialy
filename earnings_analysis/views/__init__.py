# earnings_analysis/views/__init__.py
"""
ビューモジュールの初期化
UIビューとAPIビューを適切に分離
"""

# APIビューのインポート（既存のもの）
from .search import (
    CompanySearchView,
    DocumentListView, 
    DocumentDetailView,
    SystemStatsView,
    BatchHistoryView, 
)

from .download import DocumentDownloadView
from .sentiment import (
    SentimentAnalysisStartView,
    SentimentAnalysisProgressView,
    SentimentAnalysisResultView,
    SentimentAnalysisExportView,
    SentimentAnalysisStatsView,
    SentimentAnalysisCleanupView    
)   


# UIビューは ui.py から直接インポートされる

__all__ = [
    # APIビュー
    'CompanySearchView',
    'DocumentListView', 
    'DocumentDetailView',
    'DocumentDownloadView',
    'SystemStatsView',
    'BatchHistoryView',
    'SentimentAnalysisStartView',
    'SentimentAnalysisProgressView',
    'SentimentAnalysisResultView',
    'SentimentAnalysisExportView',
    'SentimentAnalysisStatsView',
    'SentimentAnalysisCleanupView'
]