# stockdiary/views_comparison.py
import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

logger = logging.getLogger(__name__)


class StockComparisonView(LoginRequiredMixin, TemplateView):
    """複数銘柄の財務データを横並びで比較するページ"""
    template_name = 'stockdiary/comparison.html'


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
        analyzer = GeminiStockAnalyzer()
        result = analyzer.analyze_stocks(stocks)
        return JsonResponse({'success': True, 'analysis': result})
    except Exception as e:
        logger.error(f"Gemini stock analysis API error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
