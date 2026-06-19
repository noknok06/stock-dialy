# stockdiary/views_mobile_ux.py
"""
モバイルUX向上のためのビュー
クイック記録、ボトムシート対応

🆕 修正内容:
- 銘柄コード（stock_code）と銘柄名（stock_name_hidden）を分けて取得・保存
- 業種・市場情報も自動設定
"""

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.urls import reverse
from django.shortcuts import get_object_or_404
from decimal import Decimal, InvalidOperation

from .models import StockDiary, DiaryNote, Transaction, sanitize_text_content
from tags.models import Tag
import logging

logger = logging.getLogger(__name__)


@login_required
@require_POST
def quick_create_diary(request):
    """
    クイック記録API（Ajax対応）
    銘柄名とメモのみで日記を作成
    """
    try:
        # 銘柄コードと名称を取得
        stock_code = request.POST.get('stock_code', '').strip()
        stock_name = request.POST.get('stock_name_hidden', '').strip()

        # stock_nameフィールドから取得（手動入力の場合）
        if not stock_name:
            stock_name_input = request.POST.get('stock_name', '').strip()
            if stock_name_input:
                parts = stock_name_input.split(None, 1)
                if len(parts) == 2:
                    stock_code = parts[0]
                    stock_name = parts[1]
                elif len(parts) == 1:
                    stock_name = parts[0]

        # 銘柄名がない場合は「メモ」として扱う
        if not stock_name:
            stock_name = f"メモ - {timezone.now().strftime('%Y/%m/%d %H:%M')}"

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

        # メモ（投資理由フィールドを使用）
        reason = request.POST.get('reason', '').strip()
        if reason and len(reason) > 5000:
            return JsonResponse({
                'success': False,
                'message': 'メモは5000文字以内で入力してください'
            }, status=400)

        # 日記作成
        diary = StockDiary(
            user=request.user,
            stock_name=stock_name,
            stock_symbol=stock_code if stock_code else '',
        )

        # 業種・市場情報を設定（オートコンプリート経由の場合）
        industry = request.POST.get('industry', '').strip()
        market = request.POST.get('market', '').strip()

        if industry:
            diary.sector = industry[:50]

        if reason:
            diary.reason = reason

        diary.save()

        logger.info(
            f"[quick_create_diary] Created diary: code={stock_code}, name={stock_name}"
        )

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

        content = sanitize_text_content(request.POST.get('content', '')).strip()
        topic = request.POST.get('topic', '').strip()
        importance = request.POST.get('importance', 'medium')

        logger.info(f'[quick_add_note] Received - content: {bool(content)}, topic: {repr(topic)}, importance: {importance}')

        if not content:
            return JsonResponse({
                'success': False,
                'message': '記録内容を入力してください'
            }, status=400)

        if len(content) > 5000:
            return JsonResponse({
                'success': False,
                'message': '記録内容は5000文字以内で入力してください'
            }, status=400)

        # 継続記録作成
        note = DiaryNote.objects.create(
            diary=diary,
            date=timezone.now().date(),
            content=content,
            topic=topic,
            note_type=request.POST.get('note_type', 'other'),
            importance=importance
        )
        logger.info(f'[quick_add_note] Created note - id: {note.id}, topic: {repr(note.topic)}')

        # 継続記録本文の @タグを日記のタグへ同期（本文＋全継続記録が正）
        from .views import _sync_hashtag_tags
        _sync_hashtag_tags(diary, request.user)

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


