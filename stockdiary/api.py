# stockdiary/api.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
import requests
from company_master.models import CompanyMaster

# 銘柄リストをキャッシュするための変数
STOCK_DATA_CACHE = None

def load_stock_data():
    """企業マスタから銘柄情報を読み込む"""
    global STOCK_DATA_CACHE
    
    # すでにキャッシュされている場合はそれを返す
    if STOCK_DATA_CACHE is not None:
        return STOCK_DATA_CACHE
    
    try:
        # 企業マスタからデータを取得
        companies = CompanyMaster.objects.all()
        
        # 銘柄情報をディクショナリに変換
        stock_dict = {}
        for company in companies:
            stock_dict[company.code] = {
                'name': company.name,
                'industry': company.industry_name_33 or company.industry_name_17 or "不明",
                'market': company.market or "東証"
            }
        
        # キャッシュに保存
        STOCK_DATA_CACHE = stock_dict
        return stock_dict
    except Exception as e:
        import traceback
        print(f"Error loading stock data: {str(e)}")
        print(traceback.format_exc())
        return {}

@login_required
@require_GET
def get_stock_info(request, stock_code):
    """銘柄コードから会社情報と株価情報を取得するAPIエンドポイント"""
    try:
        # 銘柄リストを読み込む
        stock_dict = load_stock_data()
        
        # 銘柄コードから会社情報を取得
        stock_info = stock_dict.get(stock_code, {})
        company_name = stock_info.get('name') if stock_info else None
        industry_from_master = stock_info.get('industry') if stock_info else None
        market_from_master = stock_info.get('market') if stock_info else None
        
        # Yahoo Finance APIから詳細情報を取得
        try:
            # 日本株と米国株で分岐
            is_us_stock = not stock_code.isdigit() or len(stock_code) > 4
            ticker_symbol = stock_code if is_us_stock else f"{stock_code}.T"

            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            data = response.json()
            
            # デフォルト値の設定
            price = None
            change_percent = None
            market = market_from_master or ("米国市場" if is_us_stock else "東証")  # 市場情報
            industry = industry_from_master or "不明"  # 企業マスタからの情報を優先
            
            if 'chart' in data and 'result' in data['chart'] and len(data['chart']['result']) > 0:
                meta = data['chart']['result'][0]['meta']
                
                # 現在価格を取得
                price = meta.get('regularMarketPrice')
                
                # 前日比を計算 (%)
                prev_close = meta.get('previousClose')
                if price is not None and prev_close is not None and prev_close > 0:
                    change_percent = ((price - prev_close) / prev_close) * 100
                
                # 会社名がローカルデータになければYahooから取得
                if not company_name:
                    company_name = meta.get('shortName') or meta.get('longName')
                    if not company_name:
                        company_name = meta.get('symbol', '').replace('.T', '')
                
                # 取引所情報（企業マスタからの情報がない場合のみ）
                if not market_from_master:
                    if meta.get('exchangeName'):
                        market = meta.get('exchangeName')
                    elif meta.get('fullExchangeName'):
                        market = meta.get('fullExchangeName')
            
            # レスポンスの作成
            response_data = {
                'success': True,
                'company_name': company_name,
                'price': price,
                'change_percent': change_percent,
                'market': market,
                'industry': industry  # 業種情報
            }
            
            return JsonResponse(response_data)
                
        except Exception as e:
            # Yahoo APIでエラーが発生した場合でも、会社名だけは返す
            if company_name:
                return JsonResponse({
                    'success': True,
                    'company_name': company_name,
                    'market': market_from_master or "東証",
                    'industry': industry_from_master or "不明",
                    'source': 'company_master'
                })
            else:
                raise Exception(f"株価情報の取得に失敗しました: {str(e)}")
            
    except Exception as e:
        import traceback
        print(f"Exception occurred: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_GET
def get_stock_price(request, stock_code):
    """銘柄コードから現在株価を取得するAPIエンドポイント"""
    try:
        # 日本株と米国株で分岐
        is_us_stock = not stock_code.isdigit() or len(stock_code) > 4
        ticker_symbol = stock_code if is_us_stock else f"{stock_code}.T"

        # Yahoo Finance Chart APIを使用
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        
        # 現在株価を取得
        if 'chart' in data and 'result' in data['chart'] and len(data['chart']['result']) > 0:
            meta = data['chart']['result'][0]['meta']
            
            # 現在価格を取得
            price = meta.get('regularMarketPrice', 0)
            
            return JsonResponse({
                'success': True,
                'price': price,
                'currency': meta.get('currency', 'JPY')
            })
        else:
            return JsonResponse({
                'success': False,
                'error': '株価情報が見つかりませんでした'
            }, status=404)
            
    except Exception as e:
        import traceback
        print(f"Exception occurred: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)