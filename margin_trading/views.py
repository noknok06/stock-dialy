from django.shortcuts import render
from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from .models import MarketIssue, MarginTradingData, DataImportLog

class MarginDataListView(LoginRequiredMixin, ListView):
    """信用取引データ一覧表示"""
    model = MarginTradingData
    template_name = 'margin_trading/data_list.html'
    context_object_name = 'margin_data'
    paginate_by = 50
    
    def get_queryset(self):
        return MarginTradingData.objects.select_related('issue').order_by('-date', 'issue__code')

class ImportLogListView(LoginRequiredMixin, ListView):
    """データ取得ログ一覧"""
    model = DataImportLog
    template_name = 'margin_trading/import_logs.html'
    context_object_name = 'logs'
    paginate_by = 30

class ImportDataView(LoginRequiredMixin, TemplateView):
    """手動データ取得画面"""
    template_name = 'margin_trading/import_data.html'

@login_required
@require_GET
def get_stock_margin_data(request, stock_code):
    """特定銘柄の信用取引データを取得"""
    try:
        issue = MarketIssue.objects.filter(code=stock_code).first()
        if not issue:
            return JsonResponse({'error': '銘柄が見つかりません'}, status=404)
        
        latest_data = MarginTradingData.objects.filter(
            issue=issue
        ).order_by('-date').first()
        
        if not latest_data:
            return JsonResponse({'error': 'データが見つかりません'}, status=404)
        
        margin_ratio = None
        if latest_data.outstanding_purchases > 0:
            margin_ratio = latest_data.outstanding_sales / latest_data.outstanding_purchases
        
        return JsonResponse({
            'stock_code': stock_code,
            'stock_name': issue.name,
            'date': latest_data.date.strftime('%Y-%m-%d'),
            'outstanding_sales': latest_data.outstanding_sales,
            'outstanding_purchases': latest_data.outstanding_purchases,
            'margin_ratio': round(margin_ratio, 3) if margin_ratio else None,
            'sales_change': latest_data.outstanding_sales_change,
            'purchases_change': latest_data.outstanding_purchases_change
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_GET 
def get_latest_data(request):
    """最新の信用取引データを取得"""
    try:
        latest_data = MarginTradingData.objects.select_related('issue').order_by('-date')[:20]
        
        data = []
        for item in latest_data:
            margin_ratio = None
            if item.outstanding_purchases > 0:
                margin_ratio = item.outstanding_sales / item.outstanding_purchases
            
            data.append({
                'stock_code': item.issue.code,
                'stock_name': item.issue.name,
                'date': item.date.strftime('%Y-%m-%d'),
                'outstanding_sales': item.outstanding_sales,
                'outstanding_purchases': item.outstanding_purchases,
                'margin_ratio': round(margin_ratio, 3) if margin_ratio else None
            })
        
        return JsonResponse({'data': data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)