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
)

from .download import DocumentDownloadView
from .sentiment import (
    SentimentAnalysisStartView,
    SentimentAnalysisProgressView,
    SentimentAnalysisResultView,
)   


# UIビューは ui.py から直接インポートされる

__all__ = [
    # APIビュー
    'CompanySearchView',
    'DocumentListView', 
    'DocumentDetailView',
    'DocumentDownloadView',
    'SentimentAnalysisStartView',
    'SentimentAnalysisProgressView',
    'SentimentAnalysisResultView',
]