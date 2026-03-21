# stockdiary/views_comparison.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class StockComparisonView(LoginRequiredMixin, TemplateView):
    """複数銘柄の財務データを横並びで比較するページ"""
    template_name = 'stockdiary/comparison.html'
