# earnings_analysis/views/forecast.py
"""
業績予想信頼性スコア API ビュー

企業の予想達成率・信頼性スコアを提供するAPIエンドポイント。
"""

import json
import logging

from django.http import JsonResponse
from django.views import View
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from ..models.forecast import EarningsForecast, ForecastReliabilityScore
from ..services.forecast_reliability_service import ForecastReliabilityService

logger = logging.getLogger('earnings_analysis.forecast')


class ForecastReliabilityAPIView(View):
    """
    GET /api/forecast/reliability/<company_code>/
    指定企業の予想信頼性スコアを返す（キャッシュあり）。
    """

    def get(self, request, company_code):
        service = ForecastReliabilityService()
        data = service.get_or_calculate(company_code)

        if data is None:
            return JsonResponse({
                'success': False,
                'company_code': company_code,
                'message': '業績予想データが登録されていません。',
                'reliability': None,
            }, status=200)

        return JsonResponse({
            'success': True,
            'company_code': company_code,
            'reliability': data,
        })


class ForecastReliabilityRecalcView(View):
    """
    POST /api/forecast/reliability/<company_code>/recalc/
    指定企業のスコアを強制再計算する。
    """

    def post(self, request, company_code):
        service = ForecastReliabilityService()
        data = service.calculate_reliability(company_code)

        if data is None:
            return JsonResponse({
                'success': False,
                'message': '業績予想（実績確定済み）データが不足しています。',
            }, status=200)

        return JsonResponse({'success': True, 'reliability': data})


class EarningsForecastListAPIView(View):
    """
    GET  /api/forecast/<company_code>/          企業の予想実績一覧
    POST /api/forecast/<company_code>/          予想レコードを登録・更新
    """

    def get(self, request, company_code):
        records = EarningsForecast.objects.filter(
            company_code=company_code,
        ).order_by('-fiscal_year', 'period_type')

        items = []
        for rec in records:
            items.append({
                'id': rec.pk,
                'fiscal_year': rec.fiscal_year,
                'period_type': rec.period_type,
                'period_type_display': rec.get_period_type_display(),
                'has_actual': rec.has_actual,
                # 予想値
                'forecast': {
                    'net_sales': str(rec.forecast_net_sales) if rec.forecast_net_sales is not None else None,
                    'operating_income': str(rec.forecast_operating_income) if rec.forecast_operating_income is not None else None,
                    'ordinary_income': str(rec.forecast_ordinary_income) if rec.forecast_ordinary_income is not None else None,
                    'net_income': str(rec.forecast_net_income) if rec.forecast_net_income is not None else None,
                    'eps': str(rec.forecast_eps) if rec.forecast_eps is not None else None,
                    'revision_count': rec.forecast_revision_count,
                    'announced_date': str(rec.forecast_announced_date) if rec.forecast_announced_date else None,
                },
                # 実績値
                'actual': {
                    'net_sales': str(rec.actual_net_sales) if rec.actual_net_sales is not None else None,
                    'operating_income': str(rec.actual_operating_income) if rec.actual_operating_income is not None else None,
                    'ordinary_income': str(rec.actual_ordinary_income) if rec.actual_ordinary_income is not None else None,
                    'net_income': str(rec.actual_net_income) if rec.actual_net_income is not None else None,
                    'eps': str(rec.actual_eps) if rec.actual_eps is not None else None,
                    'announced_date': str(rec.actual_announced_date) if rec.actual_announced_date else None,
                },
                # 達成率
                'achievement_rates': {
                    'net_sales': str(rec.achievement_rate_net_sales) if rec.achievement_rate_net_sales is not None else None,
                    'operating_income': str(rec.achievement_rate_operating_income) if rec.achievement_rate_operating_income is not None else None,
                    'ordinary_income': str(rec.achievement_rate_ordinary_income) if rec.achievement_rate_ordinary_income is not None else None,
                    'net_income': str(rec.achievement_rate_net_income) if rec.achievement_rate_net_income is not None else None,
                    'composite': rec.composite_achievement_rate,
                },
                'achievement_label': rec.achievement_label,
                'source': rec.source,
            })

        return JsonResponse({
            'success': True,
            'company_code': company_code,
            'count': len(items),
            'records': items,
        })

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, company_code):
        """
        予想 or 実績値を登録・更新する。
        リクエストボディ例:
        {
            "fiscal_year": 2024,
            "period_type": "annual",
            "forecast_net_sales": 100000,
            "forecast_operating_income": 8000,
            "forecast_net_income": 5000,
            "forecast_eps": 150.0,
            "actual_net_sales": 102000,       // 実績が確定した場合
            "actual_operating_income": 8500,
            "actual_net_income": 5200,
            "source": "manual",
            "company_name": "テスト株式会社"   // 任意
        }
        """
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

        fiscal_year = body.get('fiscal_year')
        period_type = body.get('period_type', 'annual')

        if not fiscal_year:
            return JsonResponse({'success': False, 'error': 'fiscal_year は必須です'}, status=400)

        def _dec(val):
            from decimal import Decimal
            if val is None:
                return None
            try:
                return Decimal(str(val))
            except Exception:
                return None

        defaults = {
            'company_name': body.get('company_name', ''),
            'forecast_net_sales': _dec(body.get('forecast_net_sales')),
            'forecast_operating_income': _dec(body.get('forecast_operating_income')),
            'forecast_ordinary_income': _dec(body.get('forecast_ordinary_income')),
            'forecast_net_income': _dec(body.get('forecast_net_income')),
            'forecast_eps': _dec(body.get('forecast_eps')),
            'forecast_revision_count': body.get('forecast_revision_count', 0),
            'forecast_announced_date': body.get('forecast_announced_date'),
            'actual_net_sales': _dec(body.get('actual_net_sales')),
            'actual_operating_income': _dec(body.get('actual_operating_income')),
            'actual_ordinary_income': _dec(body.get('actual_ordinary_income')),
            'actual_net_income': _dec(body.get('actual_net_income')),
            'actual_eps': _dec(body.get('actual_eps')),
            'actual_announced_date': body.get('actual_announced_date'),
            'source': body.get('source', 'manual'),
        }

        rec, created = EarningsForecast.objects.update_or_create(
            company_code=company_code,
            fiscal_year=fiscal_year,
            period_type=period_type,
            defaults=defaults,
        )

        # 実績が入った場合は信頼性スコアも再計算
        if rec.has_actual:
            try:
                ForecastReliabilityService().calculate_reliability(company_code)
            except Exception as e:
                logger.warning(f"信頼性スコア再計算エラー: {e}")

        return JsonResponse({
            'success': True,
            'created': created,
            'id': rec.pk,
            'has_actual': rec.has_actual,
            'achievement_rates': {
                'operating_income': str(rec.achievement_rate_operating_income) if rec.achievement_rate_operating_income else None,
                'net_income': str(rec.achievement_rate_net_income) if rec.achievement_rate_net_income else None,
            },
        }, status=201 if created else 200)
