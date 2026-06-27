"""取引（Transaction）と株式分割（StockSplit）の CRUD ビュー。

views.py から責務分割（原則: 小さく分離）。add/update/delete/get_transaction と
add/apply/delete_stock_split。集計は Transaction.save()/delete() と
StockSplit.apply_split() 側で自動更新される（AggregateService の不変条件）。
urls.py は `from . import views_transactions` で参照する。
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods

from .models import StockDiary, StockSplit, Transaction
from .forms import StockSplitForm, TransactionForm

logger = logging.getLogger(__name__)



@login_required
@require_http_methods(["POST"])
def add_transaction(request, diary_id):
    """取引を追加"""
    diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
    
    form = TransactionForm(request.POST, diary=diary)
    
    if form.is_valid():
        transaction = form.save(commit=False)
        transaction.diary = diary  # diary を設定
        
        try:
            # diary が設定された状態で full_clean を実行
            transaction.full_clean()
            
            # 保存（models.py の save メソッドで update_aggregates が呼ばれる）
            transaction.save()
            
            # 取引後の状態を記録
            diary.refresh_from_db()  # 最新の状態を取得
            transaction.quantity_after = diary.current_quantity
            transaction.average_price_after = diary.average_purchase_price
            transaction.save(update_fields=['quantity_after', 'average_price_after'])
            
            messages.success(
                request, 
                f'{transaction.get_transaction_type_display()}取引を記録しました'
            )
            
        except ValidationError as e:
            # ValidationError の処理
            if hasattr(e, 'message_dict'):
                for field, errors in e.message_dict.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
            else:
                messages.error(request, str(e))
        except Exception as e:
            logger.error("Transaction add error: %s", e, exc_info=True)
            messages.error(request, '取引の記録中にエラーが発生しました。')
    else:
        # フォームのエラーを表示
        for field, errors in form.errors.items():
            field_label = form.fields[field].label if field in form.fields else field
            for error in errors:
                messages.error(request, f'{field_label}: {error}')
    
    return redirect('stockdiary:detail', pk=diary_id)


@login_required
@require_http_methods(["POST"])
def update_transaction(request, transaction_id):
    """取引を更新"""
    transaction = get_object_or_404(
        Transaction, 
        id=transaction_id, 
        diary__user=request.user
    )
    
    diary = transaction.diary
    
    form = TransactionForm(request.POST, instance=transaction, diary=diary)
    
    if form.is_valid():
        try:
            transaction = form.save(commit=False)
            # diary は既に設定されているはず
            
            # full_clean を実行
            transaction.full_clean()
            
            # 保存
            transaction.save()
            
            # 取引後の状態を更新
            diary.refresh_from_db()
            transaction.quantity_after = diary.current_quantity
            transaction.average_price_after = diary.average_purchase_price
            transaction.save(update_fields=['quantity_after', 'average_price_after'])
            
            messages.success(request, '取引を更新しました')
            
        except ValidationError as e:
            if hasattr(e, 'message_dict'):
                for field, errors in e.message_dict.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
            else:
                messages.error(request, str(e))
        except Exception as e:
            logger.error("Transaction update error: %s", e, exc_info=True)
            messages.error(request, '取引の更新中にエラーが発生しました。')
    else:
        for field, errors in form.errors.items():
            field_label = form.fields[field].label if field in form.fields else field
            for error in errors:
                messages.error(request, f'{field_label}: {error}')
    
    return redirect('stockdiary:detail', pk=diary.id)


@login_required
@require_http_methods(["POST"])
def delete_transaction(request, transaction_id):
    """取引を削除"""
    transaction = get_object_or_404(
        Transaction, 
        id=transaction_id, 
        diary__user=request.user
    )
    
    diary_id = transaction.diary.id
    transaction_date = transaction.transaction_date
    transaction_type = transaction.get_transaction_type_display()
    
    try:
        transaction.delete()
        messages.success(
            request, 
            f'{transaction_date.strftime("%Y年%m月%d日")}の{transaction_type}取引を削除しました'
        )
    except Exception as e:
        messages.error(request, f'取引の削除中にエラーが発生しました: {str(e)}')
    
    return redirect('stockdiary:detail', pk=diary_id)


@login_required
@require_http_methods(["GET"])
def get_transaction(request, transaction_id):
    """取引データを取得（AJAX用）"""
    try:
        transaction = get_object_or_404(
            Transaction, 
            id=transaction_id, 
            diary__user=request.user
        )
        
        return JsonResponse({
            'id': transaction.id,
            'transaction_type': transaction.transaction_type,
            'transaction_date': transaction.transaction_date.strftime('%Y-%m-%d'),
            'price': str(transaction.price),
            'quantity': str(transaction.quantity),
            'memo': transaction.memo or '',
            'success': True
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=404)

# ==========================================
# 株式分割管理ビュー
# ==========================================

@login_required
@require_http_methods(["POST"])
def add_stock_split(request, diary_id):
    """株式分割を追加"""
    diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
    
    form = StockSplitForm(request.POST)
    
    if form.is_valid():
        split = form.save(commit=False)
        split.diary = diary
        
        try:
            split.save()
            messages.success(
                request, 
                f'株式分割情報を追加しました（{split.split_date} / {split.split_ratio}倍）'
            )
            messages.info(
                request,
                '取引履歴で「適用」ボタンをクリックすると、過去の取引が自動調整されます'
            )
        except Exception as e:
            messages.error(request, f'株式分割の追加中にエラーが発生しました: {str(e)}')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
    
    return redirect('stockdiary:detail', pk=diary_id)


@login_required
@require_http_methods(["POST"])
def apply_stock_split(request, split_id):
    """株式分割を適用"""
    split = get_object_or_404(
        StockSplit, 
        id=split_id, 
        diary__user=request.user
    )
    
    if split.is_applied:
        messages.warning(request, 'この株式分割はすでに適用済みです')
        return redirect('stockdiary:detail', pk=split.diary.id)
    
    try:
        split.apply_split()
        messages.success(
            request,
            f'株式分割を適用しました（{split.split_date} / {split.split_ratio}倍）'
        )
        messages.info(
            request,
            f'{split.split_date}以前の取引データが自動調整されました'
        )
    except Exception as e:
        messages.error(request, f'株式分割の適用中にエラーが発生しました: {str(e)}')
    
    return redirect('stockdiary:detail', pk=split.diary.id)


@login_required
@require_http_methods(["POST"])
def delete_stock_split(request, split_id):
    """株式分割を削除"""
    split = get_object_or_404(
        StockSplit, 
        id=split_id, 
        diary__user=request.user
    )
    
    if split.is_applied:
        messages.error(request, '適用済みの株式分割は削除できません')
        return redirect('stockdiary:detail', pk=split.diary.id)
    
    diary_id = split.diary.id
    split_date = split.split_date
    split_ratio = split.split_ratio
    
    try:
        split.delete()
        messages.success(
            request,
            f'株式分割情報を削除しました（{split_date} / {split_ratio}倍）'
        )
    except Exception as e:
        messages.error(request, f'株式分割の削除中にエラーが発生しました: {str(e)}')
    
    return redirect('stockdiary:detail', pk=diary_id)

