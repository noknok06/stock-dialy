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
def get_stock_metrics(request, stock_code):
    """
    銘柄コードからリアルタイム株価・PER・PBR・配当利回りを返す
    日本株4桁コードは自動的に .T サフィックスを付与
    """
    import yfinance as yf
    import pandas as pd
    from datetime import datetime

    try:
        ticker_symbol = f"{stock_code}.T" if (stock_code.isdigit() and len(stock_code) <= 4) else stock_code
        ticker = yf.Ticker(ticker_symbol)

        # --- 株価・時価総額: fast_info を優先（ticker.info より高速・正確）
        fi = ticker.fast_info
        price      = getattr(fi, 'last_price',   None) or getattr(fi, 'lastPrice',   None)
        market_cap = getattr(fi, 'market_cap',   None) or getattr(fi, 'marketCap',   None)
        shares     = getattr(fi, 'shares',       None) or getattr(fi, 'sharesOutstanding', None)

        per = pbr = dividend_yield = None

        # --- PER / PBR: 年次損益計算書 + 直近四半期BSから計算
        # quarterly_income_stmt は日本企業で累計値になることがあるため年次を使用
        try:
            income_stmt   = ticker.income_stmt            # 年次
            balance_sheet = ticker.quarterly_balance_sheet

            latest_i_col = sorted(income_stmt.columns,   reverse=True)[0]
            b_col        = sorted(balance_sheet.columns, reverse=True)[0]

            def annual_val(label):
                if label not in income_stmt.index:
                    return None
                v = income_stmt.loc[label, latest_i_col]
                return float(v) if not pd.isna(v) else None

            def bs(label):
                if label not in balance_sheet.index:
                    return None
                v = balance_sheet.loc[label, b_col]
                return float(v) if not pd.isna(v) else None

            annual_net = annual_val('Net Income')
            equity     = bs('Stockholders Equity')

            if price and shares and shares > 0:
                if annual_net and annual_net > 0:
                    per = round(price / (annual_net / shares), 2)
                if equity and equity > 0:
                    pbr = round(price / (equity / shares), 2)
        except Exception:
            pass

        # 財務諸表で取得できなかった場合は ticker.info にフォールバック
        if per is None or pbr is None:
            try:
                info = ticker.info
                if per is None:
                    raw = info.get('trailingPE') or info.get('forwardPE')
                    per = round(raw, 2) if raw else None
                if pbr is None:
                    raw = info.get('priceToBook')
                    pbr = round(raw, 2) if raw else None
            except Exception:
                pass

        # --- 配当利回り: ticker.dividends から直近1年合計で計算
        try:
            divs = ticker.dividends
            if divs is not None and len(divs) > 0:
                one_year_ago = pd.Timestamp.now(tz=divs.index.tz) - pd.DateOffset(years=1)
                annual_div   = float(divs[divs.index >= one_year_ago].sum())
                if annual_div > 0 and price and price > 0:
                    dividend_yield = round(annual_div / price * 100, 2)
        except Exception:
            pass

        # 配当が取得できなかった場合は ticker.info にフォールバック
        if dividend_yield is None:
            try:
                raw = ticker.info.get('dividendYield')
                dividend_yield = round(raw * 100, 2) if raw else None
            except Exception:
                pass

        return JsonResponse({
            'success': True,
            'price': price,
            'per': per,
            'pbr': pbr,
            'dividend_yield': dividend_yield,
            'market_cap_oku': round(market_cap / 100_000_000, 0) if market_cap else None,
            'fetched_at': datetime.now().strftime('%Y/%m/%d %H:%M'),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_GET
def get_stock_historical(request, stock_code):
    """
    銘柄コードから5年分の財務履歴データを返す（株比較機能用）
    売上高・営業利益・EPS・営業CF・自己資本比率・ROEを年次で取得
    """
    import yfinance as yf
    import pandas as pd
    from datetime import datetime

    try:
        ticker_symbol = f"{stock_code}.T" if (stock_code.isdigit() and len(stock_code) <= 4) else stock_code
        ticker = yf.Ticker(ticker_symbol)

        # 会社名取得
        stock_dict = load_stock_data()
        stock_info = stock_dict.get(stock_code, {})
        stock_name = stock_info.get('name') if stock_info else None

        def safe_float(val):
            try:
                f = float(val)
                return None if pd.isna(f) else f
            except Exception:
                return None

        def to_oku(val):
            """円 → 億円"""
            v = safe_float(val)
            return round(v / 1e8, 1) if v is not None else None

        years = []
        revenue_list = []
        operating_income_list = []
        eps_list = []
        operating_cf_list = []
        equity_ratio_list = []
        roe_list = []
        dividend_yield_history = []

        try:
            income_stmt = ticker.income_stmt      # 年次: columns=決算年(降順)
            balance_sheet = ticker.balance_sheet  # 年次
            cash_flow = ticker.cash_flow          # 年次

            # 利用可能な年を古い順に並べる（最大4年）
            cols = sorted(income_stmt.columns, reverse=False)[-4:]

            for col in cols:
                year_str = str(col.year)
                years.append(year_str)

                # 売上高
                rev = to_oku(income_stmt.loc['Total Revenue', col]) if 'Total Revenue' in income_stmt.index else None
                revenue_list.append(rev)

                # 営業利益
                oi = to_oku(income_stmt.loc['Operating Income', col]) if 'Operating Income' in income_stmt.index else None
                operating_income_list.append(oi)

                # EPS
                eps_val = safe_float(income_stmt.loc['Basic EPS', col]) if 'Basic EPS' in income_stmt.index else None
                eps_list.append(round(eps_val, 1) if eps_val is not None else None)

                # 営業CF
                if cash_flow is not None and not cash_flow.empty and col in cash_flow.columns:
                    ocf = to_oku(cash_flow.loc['Operating Cash Flow', col]) if 'Operating Cash Flow' in cash_flow.index else None
                else:
                    ocf = None
                operating_cf_list.append(ocf)

                # 自己資本比率・ROE（バランスシート）
                eq_ratio = None
                roe_val = None
                if balance_sheet is not None and not balance_sheet.empty and col in balance_sheet.columns:
                    equity = safe_float(balance_sheet.loc['Stockholders Equity', col]) if 'Stockholders Equity' in balance_sheet.index else None
                    total_assets = safe_float(balance_sheet.loc['Total Assets', col]) if 'Total Assets' in balance_sheet.index else None
                    if equity and total_assets and total_assets > 0:
                        eq_ratio = round(equity / total_assets * 100, 1)

                    net_income = safe_float(income_stmt.loc['Net Income', col]) if 'Net Income' in income_stmt.index else None
                    if net_income and equity and equity > 0:
                        roe_val = round(net_income / equity * 100, 1)

                equity_ratio_list.append(eq_ratio)
                roe_list.append(roe_val)

        except Exception as e:
            print(f"Historical data error for {stock_code}: {e}")

        # 年別配当利回り計算
        try:
            divs = ticker.dividends
            price_hist = ticker.history(period="5y", interval="1mo")
            for year_str in years:
                year_int = int(year_str)
                try:
                    annual_div = float(divs[divs.index.year == year_int].sum()) if divs is not None and len(divs) > 0 else 0.0
                    year_prices = price_hist[price_hist.index.year == year_int]['Close']
                    year_end_price = float(year_prices.iloc[-1]) if len(year_prices) > 0 else None
                    dy = round(annual_div / year_end_price * 100, 2) if annual_div > 0 and year_end_price and year_end_price > 0 else None
                except Exception:
                    dy = None
                dividend_yield_history.append(dy)
        except Exception:
            dividend_yield_history = [None] * len(years)

        # 最新指標（PER/PBR/配当利回り）は既存 get_stock_metrics と同じロジック
        fi = ticker.fast_info
        price = getattr(fi, 'last_price', None) or getattr(fi, 'lastPrice', None)
        shares = getattr(fi, 'shares', None) or getattr(fi, 'sharesOutstanding', None)
        per = pbr = dividend_yield = None

        try:
            inc = ticker.income_stmt
            bs_q = ticker.quarterly_balance_sheet
            if inc is not None and not inc.empty and bs_q is not None and not bs_q.empty:
                latest_i = sorted(inc.columns, reverse=True)[0]
                latest_b = sorted(bs_q.columns, reverse=True)[0]
                annual_net = safe_float(inc.loc['Net Income', latest_i]) if 'Net Income' in inc.index else None
                equity_latest = safe_float(bs_q.loc['Stockholders Equity', latest_b]) if 'Stockholders Equity' in bs_q.index else None
                if price and shares and shares > 0:
                    if annual_net and annual_net > 0:
                        per = round(price / (annual_net / shares), 2)
                    if equity_latest and equity_latest > 0:
                        pbr = round(price / (equity_latest / shares), 2)
        except Exception:
            pass

        if per is None or pbr is None:
            try:
                info = ticker.info
                if per is None:
                    raw = info.get('trailingPE') or info.get('forwardPE')
                    per = round(raw, 2) if raw else None
                if pbr is None:
                    raw = info.get('priceToBook')
                    pbr = round(raw, 2) if raw else None
            except Exception:
                pass

        try:
            divs = ticker.dividends
            if divs is not None and len(divs) > 0:
                one_year_ago = pd.Timestamp.now(tz=divs.index.tz) - pd.DateOffset(years=1)
                annual_div = float(divs[divs.index >= one_year_ago].sum())
                if annual_div > 0 and price and price > 0:
                    dividend_yield = round(annual_div / price * 100, 2)
        except Exception:
            pass

        if dividend_yield is None:
            try:
                raw = ticker.info.get('dividendYield')
                dividend_yield = round(raw * 100, 2) if raw else None
            except Exception:
                pass

        if not stock_name:
            try:
                stock_name = ticker.info.get('shortName') or ticker.info.get('longName') or stock_code
            except Exception:
                stock_name = stock_code

        return JsonResponse({
            'success': True,
            'stock_code': stock_code,
            'stock_name': stock_name,
            'years': years,
            'revenue': revenue_list,
            'operating_income': operating_income_list,
            'eps': eps_list,
            'operating_cf': operating_cf_list,
            'equity_ratio': equity_ratio_list,
            'roe': roe_list,
            'per': per,
            'pbr': pbr,
            'dividend_yield': dividend_yield,
            'dividend_yield_history': dividend_yield_history,
            'price': price,
        })

    except Exception as e:
        print(f"get_stock_historical error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


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