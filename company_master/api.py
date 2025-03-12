# company_master/api.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import CompanyMaster

@login_required
@require_GET
def search_company(request):
    """
    企業情報を検索するAPIエンドポイント
    
    クエリパラメータ:
    - query: 検索キーワード (証券コードまたは企業名)
    - limit: 結果の最大件数 (デフォルト: 10)
    """
    try:
        query = request.GET.get('query', '')
        limit = int(request.GET.get('limit', 10))
        
        if not query:
            return JsonResponse({
                'success': True,
                'companies': []
            })
        
        # 証券コードまたは企業名で検索
        companies = CompanyMaster.objects.filter(
            Q(code__istartswith=query) | 
            Q(name__icontains=query)
        ).values('code', 'name', 'market', 'industry')[:limit]
        
        return JsonResponse({
            'success': True,
            'companies': list(companies)
        })
        
    except Exception as e:
        import traceback
        print(f"Error in search_company API: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_GET
def get_company_info(request, code):
    """
    証券コードから企業情報を取得するAPIエンドポイント
    
    パスパラメータ:
    - code: 証券コード
    """
    try:
        company = CompanyMaster.objects.filter(code=code).first()
        
        if not company:
            return JsonResponse({
                'success': False,
                'error': '企業情報が見つかりません'
            }, status=404)
        
        return JsonResponse({
            'success': True,
            'company': {
                'code': company.code,
                'name': company.name,
                'market': company.market,
                'industry': company.industry,
                'sector': company.sector,
                'unit': company.unit
            }
        })
        
    except Exception as e:
        import traceback
        print(f"Error in get_company_info API: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)