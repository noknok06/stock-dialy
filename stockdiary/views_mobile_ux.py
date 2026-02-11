# stockdiary/views_mobile_ux.py
"""
モバイルUX向上のためのビュー
クイック記録、ボトムシート対応
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


@login_required
@require_POST
def quick_create_diary(request):
    """
    クイック記録API（Ajax対応）
    最小限の入力で日記を作成
    """
    try:
        # 銘柄名（任意）
        stock_name = request.POST.get('stock_name', '').strip()

        # 銘柄名がない場合は「メモ」として扱う
        if not stock_name:
            stock_name = f"メモ - {timezone.now().strftime('%Y/%m/%d %H:%M')}"

        # 文字数制限チェック
        if len(stock_name) > 100:
            return JsonResponse({
                'success': False,
                'message': '銘柄名は100文字以内で入力してください'
            }, status=400)

        # 日記作成
        diary = StockDiary(
            user=request.user,
            stock_name=stock_name,
        )

        # 任意項目: 購入情報
        purchase_price = request.POST.get('purchase_price', '').strip()
        purchase_quantity = request.POST.get('purchase_quantity', '').strip()
        purchase_date = request.POST.get('purchase_date', '').strip()

        if purchase_price:
            try:
                diary.purchase_price = Decimal(purchase_price)
            except (ValueError, InvalidOperation):
                return JsonResponse({
                    'success': False,
                    'message': '購入単価は数値で入力してください'
                }, status=400)

        if purchase_quantity:
            try:
                diary.purchase_quantity = Decimal(purchase_quantity)
            except (ValueError, InvalidOperation):
                return JsonResponse({
                    'success': False,
                    'message': '購入数量は数値で入力してください'
                }, status=400)

        if purchase_date:
            try:
                from datetime import datetime
                diary.purchase_date = datetime.strptime(purchase_date, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'message': '購入日の形式が正しくありません'
                }, status=400)

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

        return JsonResponse({
            'success': True,
            'message': f'クイック記録を作成しました: {stock_name}',
            'diary_id': diary.id,
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
