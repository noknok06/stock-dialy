# stockdiary/api.py
import traceback
import requests
from decimal import Decimal

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from django.urls import reverse
from company_master.models import CompanyMaster
from .models import StockDiary
from tags.models import Tag

from django.core.exceptions import ValidationError

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
        print(f"Exception occurred: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# APIエンドポイントでの制限チェック機能を追加

@login_required
@require_POST
def api_create_diary(request):
    try:
        # 必須フィールドのチェック
        stock_name = request.POST.get('stock_name', '').strip()
        
        # 文字数制限のチェック
        if len(stock_name) > 100:
            return JsonResponse({
                'success': False,
                'message': '銘柄名は100文字以内で入力してください'
            }, status=400)
        
        if not stock_name:
            return JsonResponse({
                'success': False,
                'message': '銘柄名は必須です'
            }, status=400)
        
        # 新しい日記インスタンスを作成
        diary = StockDiary(
            user=request.user,
            stock_name=stock_name,
        )
        
        # オプションフィールドの設定と文字数制限チェック
        stock_symbol = request.POST.get('stock_symbol', '').strip()
        sector = request.POST.get('sector', '').strip()
        reason = request.POST.get('reason', '').strip()
        
        # 各フィールドの文字数制限チェック
        if len(stock_symbol) > 50:
            return JsonResponse({
                'success': False,
                'message': '銘柄コードは50文字以内で入力してください'
            }, status=400)
        
        if len(sector) > 50:
            return JsonResponse({
                'success': False,
                'message': '業種は50文字以内で入力してください'
            }, status=400)
        
        if len(reason) > 1000:
            return JsonResponse({
                'success': False,
                'message': '購入理由は1000文字以内で入力してください'
            }, status=400)
        
        diary.stock_symbol = stock_symbol
        diary.sector = sector
        diary.reason = reason
        
        # 数値フィールドの処理
        price = request.POST.get('purchase_price')
        quantity = request.POST.get('purchase_quantity')
        
        if price:
            try:
                diary.purchase_price = float(price)
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'message': '購入価格は有効な数値を入力してください'
                }, status=400)
                
        if quantity:
            try:
                diary.purchase_quantity = int(quantity)
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'message': '購入数量は有効な整数を入力してください'
                }, status=400)
        
        # 画像ファイルの処理
        if 'image' in request.FILES:
            image_file = request.FILES['image']
            
            # ファイルサイズのチェック（10MB以下）
            if image_file.size > 10 * 1024 * 1024:
                return JsonResponse({
                    'success': False,
                    'message': '画像ファイルのサイズは10MB以下にしてください'
                }, status=400)
            
            # ファイル形式のチェック
            valid_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(image_file, 'content_type') and image_file.content_type not in valid_formats:
                return JsonResponse({
                    'success': False,
                    'message': 'JPEG、PNG、GIF、WebP形式の画像ファイルのみアップロード可能です'
                }, status=400)
        
        # 日記を保存（モデルのvalidationが実行される）
        try:
            diary.save()
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'message': f'入力データにエラーがあります: {str(e)}'
            }, status=400)
        
        # 画像のアップロード（日記保存後）
        image_uploaded = False
        if 'image' in request.FILES:
            image_uploaded = diary.upload_image(request.FILES['image'])
        
        # タグの処理
        tags = request.POST.getlist('tags')
        if tags:
            for tag_id in tags:
                try:
                    tag = Tag.objects.get(id=tag_id, user=request.user)
                    diary.tags.add(tag)
                except Tag.DoesNotExist:
                    pass
        
        # 新しく作成した日記のHTMLを生成
        from django.template.loader import render_to_string
        diary_html = render_to_string('stockdiary/partials/diary_card.html', {
            'diary': diary,
            'request': request,
            'forloop': {'counter': 1}  # forloop.counter の代わり
        })

        return JsonResponse({
            'success': True,
            'message': '日記を作成しました',
            'diary_id': diary.id,
            'diary_html': diary_html,
            'image_url': diary.get_image_url(),  # 画像URLを追加
            'redirect_url': reverse('stockdiary:detail', kwargs={'pk': diary.id})
        })
        
    except Exception as e:
        # エラー処理
        return JsonResponse({
            'success': False,
            'message': f'エラーが発生しました: {str(e)}'
        }, status=500)


@login_required
@require_GET
def search_stock(request):
    """
    銘柄検索API（オートコンプリート用）
    銘柄コードまたは銘柄名で検索
    """
    query = request.GET.get('query', '').strip()
    limit = int(request.GET.get('limit', 20))

    if not query or len(query) < 2:
        return JsonResponse({
            'success': False,
            'message': '検索クエリは2文字以上入力してください'
        }, status=400)

    try:
        # 企業マスタから検索
        from django.db.models import Q

        companies = CompanyMaster.objects.filter(
            Q(code__icontains=query) |
            Q(name__icontains=query)
        ).order_by('code')[:limit]

        results = []
        for company in companies:
            results.append({
                'code': company.code,
                'name': company.name,
                'industry': company.industry_name_33 or company.industry_name_17 or '不明',
                'market': company.market or '東証'
            })

        return JsonResponse({
            'success': True,
            'companies': results,
            'count': len(results)
        })

    except Exception as e:
        print(f"Search error: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)