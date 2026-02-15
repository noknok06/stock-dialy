# stockdiary/views_mobile_ux.py
"""
モバイルUX向上のためのビュー
クイック記録、ボトムシート対応

🆕 修正内容:
- 銘柄コード（stock_code）と銘柄名（stock_name_hidden）を分けて取得・保存
- 業種・市場情報も自動設定
"""

from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.urls import reverse
from django.shortcuts import get_object_or_404
from decimal import Decimal, InvalidOperation

from .models import StockDiary, Transaction, DiaryNote
from tags.models import Tag
import logging

logger = logging.getLogger(__name__)


@login_required
@require_POST
def quick_create_diary(request):
    """
    クイック記録API（Ajax対応）
    最小限の入力で日記を作成
    
    🆕 修正内容:
    - 銘柄コード（stock_code）と銘柄名（stock_name_hidden）を分けて取得
    - 業種・市場情報も自動設定
    """
    try:
        # 🆕 銘柄コードと名称を分けて取得
        stock_code = request.POST.get('stock_code', '').strip()
        stock_name = request.POST.get('stock_name_hidden', '').strip()
        
        # 🔧 後方互換性: stock_nameフィールドから取得を試みる（手動入力の場合）
        if not stock_name:
            stock_name_input = request.POST.get('stock_name', '').strip()
            # "コード 名称" 形式で入力されている場合はパース
            if stock_name_input:
                parts = stock_name_input.split(None, 1)  # 最初の空白で分割
                if len(parts) == 2:
                    stock_code = parts[0]
                    stock_name = parts[1]
                elif len(parts) == 1:
                    # コードのみの場合
                    stock_name = parts[0]

        # 銘柄名がない場合は「メモ」として扱う
        if not stock_name:
            stock_name = f"メモ - {timezone.now().strftime('%Y/%m/%d %H:%M')}"

        # 文字数制限チェック
        if len(stock_name) > 100:
            return JsonResponse({
                'success': False,
                'message': '銘柄名は100文字以内で入力してください'
            }, status=400)
        
        if stock_code and len(stock_code) > 50:
            return JsonResponse({
                'success': False,
                'message': '銘柄コードは50文字以内で入力してください'
            }, status=400)

        # 🆕 購入情報を取得
        purchase_price = request.POST.get('purchase_price', '').strip()
        purchase_quantity = request.POST.get('purchase_quantity', '').strip()
        purchase_date_str = request.POST.get('purchase_date', '').strip()

        # 🆕 購入価格のバリデーション
        purchase_price_decimal = None
        if purchase_price:
            try:
                purchase_price_decimal = Decimal(purchase_price)
                if purchase_price_decimal < 0:
                    return JsonResponse({
                        'success': False,
                        'message': '購入単価は0以上の数値を入力してください'
                    }, status=400)
            except (ValueError, InvalidOperation):
                return JsonResponse({
                    'success': False,
                    'message': '購入単価は有効な数値を入力してください'
                }, status=400)

        # 🆕 購入数量のバリデーション
        purchase_quantity_int = None
        if purchase_quantity:
            try:
                purchase_quantity_int = int(purchase_quantity)
                if purchase_quantity_int < 1:
                    return JsonResponse({
                        'success': False,
                        'message': '購入数量は1以上の整数を入力してください'
                    }, status=400)
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'message': '購入数量は有効な整数を入力してください'
                }, status=400)

        # 🆕 購入日のバリデーション
        purchase_date = None
        if purchase_date_str:
            try:
                from datetime import datetime
                purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'message': '購入日の形式が正しくありません'
                }, status=400)

        # 日記作成
        diary = StockDiary(
            user=request.user,
            stock_name=stock_name,
            stock_symbol=stock_code if stock_code else '',  # 🆕 銘柄コードを設定
        )

        # 🆕 業種・市場情報を設定
        industry = request.POST.get('industry', '').strip()
        market = request.POST.get('market', '').strip()

        if industry:
            diary.sector = industry[:50]  # 最大50文字

        # 市場情報はメモに追記（必要に応じて）
        if market and not diary.memo:
            diary.memo = f"市場: {market}"

        # 任意項目: 投資理由
        reason = request.POST.get('reason', '').strip()
        if reason:
            if len(reason) > 2000:
                return JsonResponse({
                    'success': False,
                    'message': '投資理由は2000文字以内で入力してください'
                }, status=400)
            diary.reason = reason

        # 保存
        diary.save()

        # 🆕 銘柄コードが設定されているが購入価格が未入力の場合、株価APIから自動取得
        if stock_code and not purchase_price_decimal:
            try:
                from .api import get_stock_price
                from django.http import HttpRequest

                # 株価取得APIを内部的に呼び出し
                api_request = HttpRequest()
                api_request.user = request.user
                api_request.method = 'GET'

                stock_price_response = get_stock_price(api_request, stock_code)

                if stock_price_response.status_code == 200:
                    import json
                    price_data = json.loads(stock_price_response.content)

                    if price_data.get('success') and price_data.get('price'):
                        # 株価を取得できた場合、purchase_price_decimalに設定
                        purchase_price_decimal = Decimal(str(price_data['price']))

                        logger.info(
                            f"[quick_create_diary] Auto-fetched stock price: "
                            f"code={stock_code}, price={purchase_price_decimal}"
                        )
            except Exception as e:
                # 株価取得に失敗してもエラーにはせず、ログ出力のみ
                logger.warning(
                    f"[quick_create_diary] Failed to auto-fetch stock price: "
                    f"code={stock_code}, error={str(e)}"
                )

        # 🆕 購入情報があれば、Transactionを作成
        transaction_created = False
        if purchase_price_decimal is not None and purchase_quantity_int is not None:
            # 購入日が未指定の場合は今日の日付
            if not purchase_date:
                purchase_date = timezone.now().date()

            # Transaction作成
            transaction = Transaction.objects.create(
                diary=diary,
                transaction_type='buy',
                transaction_date=purchase_date,
                price=purchase_price_decimal,
                quantity=purchase_quantity_int,
                is_margin=False
            )

            # 日記の集計情報を更新
            diary.update_aggregates()

            transaction_created = True

            logger.info(
                f"[quick_create_diary] Created transaction: "
                f"price={purchase_price_decimal}, quantity={purchase_quantity_int}, date={purchase_date}"
            )

        # 🆕 ログ出力（デバッグ用）
        logger.info(
            f"[quick_create_diary] Created diary: "
            f"code={stock_code}, name={stock_name}, "
            f"industry={industry}, market={market}, transaction_created={transaction_created}"
        )

        return JsonResponse({
            'success': True,
            'message': f'クイック記録を作成しました: {stock_name}',
            'diary_id': diary.id,
            'stock_code': stock_code,
            'stock_name': stock_name,
            'transaction_created': transaction_created,
            'purchase_price': float(purchase_price_decimal) if purchase_price_decimal else None,
            'purchase_quantity': purchase_quantity_int,
            'purchase_date': purchase_date.strftime('%Y-%m-%d') if purchase_date else None,
            'redirect_url': reverse('stockdiary:detail', kwargs={'pk': diary.id})
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'エラーが発生しました: {str(e)}'
        }, status=500)


@login_required
@require_POST
def quick_add_note(request, diary_id):
    """
    クイック継続記録追加API（Ajax対応）
    ボトムシートから素早く継続記録を追加
    """
    try:
        diary = get_object_or_404(StockDiary, pk=diary_id, user=request.user)

        content = request.POST.get('content', '').strip()
        if not content:
            return JsonResponse({
                'success': False,
                'message': '記録内容を入力してください'
            }, status=400)

        if len(content) > 1000:
            return JsonResponse({
                'success': False,
                'message': '記録内容は1000文字以内で入力してください'
            }, status=400)

        # 継続記録作成
        note = DiaryNote.objects.create(
            diary=diary,
            date=timezone.now().date(),
            content=content,
            note_type=request.POST.get('note_type', 'other'),
            importance=request.POST.get('importance', 'medium')
        )

        return JsonResponse({
            'success': True,
            'message': '継続記録を追加しました',
            'note_id': note.id,
            'note_date': note.date.strftime('%Y-%m-%d'),
            'note_content': note.content
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'エラーが発生しました: {str(e)}'
        }, status=500)


@login_required
@require_POST
def quick_add_transaction(request, diary_id):
    """
    クイック取引記録API（Ajax対応）
    ボトムシートから素早く取引を記録
    """
    try:
        diary = get_object_or_404(StockDiary, pk=diary_id, user=request.user)

        # 必須項目チェック
        transaction_type = request.POST.get('transaction_type', '').strip()
        price = request.POST.get('price', '').strip()
        quantity = request.POST.get('quantity', '').strip()

        if not transaction_type or transaction_type not in ['buy', 'sell', 'buy_margin', 'sell_margin']:
            return JsonResponse({
                'success': False,
                'message': '取引種別を選択してください'
            }, status=400)

        if not price or not quantity:
            return JsonResponse({
                'success': False,
                'message': '単価と数量を入力してください'
            }, status=400)

        try:
            price_decimal = Decimal(price)
            quantity_decimal = Decimal(quantity)
        except (ValueError, InvalidOperation):
            return JsonResponse({
                'success': False,
                'message': '単価と数量は数値で入力してください'
            }, status=400)

        # 取引日
        transaction_date = request.POST.get('transaction_date', '').strip()
        if transaction_date:
            try:
                from datetime import datetime
                transaction_date = datetime.strptime(transaction_date, '%Y-%m-%d').date()
            except ValueError:
                transaction_date = timezone.now().date()
        else:
            transaction_date = timezone.now().date()

        # 取引作成
        transaction = Transaction.objects.create(
            diary=diary,
            transaction_type=transaction_type,
            transaction_date=transaction_date,
            price=price_decimal,
            quantity=quantity_decimal
        )

        return JsonResponse({
            'success': True,
            'message': '取引を記録しました',
            'transaction_id': transaction.id,
            'transaction_type_display': transaction.get_transaction_type_display(),
            'amount': float(transaction.amount)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'エラーが発生しました: {str(e)}'
        }, status=500)


@login_required
@require_GET
def get_template_suggestions(request):
    """
    投資スタイルテンプレート取得API
    """
    templates = {
        'growth': {
            'name': '成長株投資',
            'icon': '🚀',
            'template': """## 注目理由
- 業績の成長性が高い
- 市場シェア拡大中

## リスク
- 割高感に注意"""
        },
        'dividend': {
            'name': '配当投資',
            'icon': '💰',
            'template': """## 配当情報
- 配当利回り: %
- 配当性向: %

## 安定性
- 業績安定"""
        },
        'value': {
            'name': 'バリュー投資',
            'icon': '📊',
            'template': """## バリュエーション
- PER:
- PBR:
- 割安と判断した理由: """
        },
        'swing': {
            'name': 'スイングトレード',
            'icon': '📈',
            'template': """## エントリー条件
- テクニカル指標:
- 目標価格:
- 損切りライン: """
        },
    }

    template_key = request.GET.get('template')

    if template_key and template_key in templates:
        return JsonResponse({
            'success': True,
            'template': templates[template_key]
        })
    else:
        return JsonResponse({
            'success': True,
            'templates': templates
        })