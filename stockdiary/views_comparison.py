# stockdiary/views_comparison.py
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from django.urls import reverse_lazy

logger = logging.getLogger(__name__)


class StockComparisonView(LoginRequiredMixin, RedirectView):
    """旧銘柄比較ページ → investment-hub へ恒久リダイレクト"""
    permanent = True
    url = reverse_lazy('stockdiary:investment_hub')


class InvestmentHubView(LoginRequiredMixin, TemplateView):
    """投資判断サポートハブ（比較 + 分析テンプレート + AI見解）"""
    template_name = 'stockdiary/investment_hub.html'


@login_required
@require_POST
def api_gemini_stock_analysis(request):
    """
    複数銘柄の財務データを受け取りGemini AIで比較分析するAPIエンドポイント
    POST body: { "stocks": [ { code, stock_name, revenue[], roe[], per, pbr, ... }, ... ] }
    SuperUser のみ利用可能
    """
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': '権限がありません（管理者のみ利用可能）'}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'リクエスト形式エラー'}, status=400)

    stocks = body.get('stocks', [])
    if not stocks:
        return JsonResponse({'success': False, 'error': '銘柄データがありません'}, status=400)
    if len(stocks) > 5:
        stocks = stocks[:5]

    try:
        from stockdiary.services.gemini_stock_analysis import GeminiStockAnalyzer
        from common.services.yahoo_finance_service import YahooFinanceService

        # 銘柄ごとにニュースを並列取得（最大5秒でタイムアウト）
        news_map: dict = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_code = {
                executor.submit(
                    YahooFinanceService.fetch_stock_news,
                    s['code'],
                    s.get('stock_name', ''),
                    5,
                ): s['code']
                for s in stocks
            }
            for future in as_completed(future_to_code, timeout=10):
                code = future_to_code[future]
                try:
                    news_map[code] = future.result(timeout=5)
                except Exception:
                    news_map[code] = []

        analyzer = GeminiStockAnalyzer()
        result = analyzer.analyze_stocks(stocks, news_map=news_map)
        return JsonResponse({'success': True, 'analysis': result, 'news_map': news_map})
    except Exception as e:
        logger.error(f"Gemini stock analysis API error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
