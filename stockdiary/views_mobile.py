# stockdiary/views_mobile.py
# モバイル向け機能のビュー

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.db.models import Q
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required

from .models import StockDiary
from tags.models import Tag

import json
import re

@login_required
@require_GET
def search_suggestion(request):
    """
    検索キーワードに基づいて提案を返す
    hx-get="/stockdiary/search-suggestion/" で使用
    """
    query = request.GET.get('query', '').strip()
    
    # 3文字未満はサジェストを出さない
    if len(query) < 2:
        return HttpResponse('')
    
    # ユーザーの日記から検索
    stock_matches = StockDiary.objects.filter(
        user=request.user
    ).filter(
        Q(stock_name__icontains=query) | 
        Q(stock_symbol__icontains=query)
    ).distinct().values('stock_name', 'stock_symbol')[:5]
    
    # タグ検索
    tag_matches = Tag.objects.filter(
        user=request.user, 
        name__icontains=query
    ).values('name')[:3]
    
    if not stock_matches and not tag_matches:
        return HttpResponse('')
    
    # レスポンスを構築
    html = '<div class="search-suggestions mt-2">'
    
    if stock_matches:
        html += '<div class="search-suggestion-title"><small>銘柄:</small></div>'
        html += '<div class="search-suggestion-items">'
        for match in stock_matches:
            html += f'<div class="search-suggestion-item" hx-get="{% url \'stockdiary:diary_list\' %}?query={match["stock_name"]}" hx-target="#diary-container" hx-push-url="true">'
            html += f'<i class="bi bi-building me-1"></i> {match["stock_name"]} ({match["stock_symbol"]})'
            html += '</div>'
        html += '</div>'
    
    if tag_matches:
        html += '<div class="search-suggestion-title"><small>タグ:</small></div>'
        html += '<div class="search-suggestion-items">'
        for match in tag_matches:
            html += f'<div class="search-suggestion-item" hx-get="{% url \'stockdiary:diary_list\' %}?tag={match["name"]}" hx-target="#diary-container" hx-push-url="true">'
            html += f'<i class="bi bi-tag me-1"></i> {match["name"]}'
            html += '</div>'
        html += '</div>'
    
    html += '</div>'
    
    return HttpResponse(html)

@login_required
@require_GET
def context_actions(request, pk):
    """
    特定の日記に対するコンテキストアクション
    モバイルで長押し時に表示する
    """
    try:
        diary = StockDiary.objects.get(id=pk, user=request.user)
    except StockDiary.DoesNotExist:
        return JsonResponse({'error': '日記が見つかりません'}, status=404)
    
    # 日記の種類に応じたアクションを決定
    is_memo = diary.is_memo or diary.purchase_price is None or diary.purchase_quantity is None
    is_sold = diary.sell_date is not None
    
    context = {
        'diary': diary,
        'is_memo': is_memo,
        'is_sold': is_sold
    }
    
    html = render_to_string('stockdiary/partials/context_actions.html', context)
    return HttpResponse(html)

@login_required
@require_GET
def validate_field(request, field_type):
    """
    フィールドの入力バリデーション
    インラインで即時フィードバックを提供
    """
    if field_type == 'symbol':
        symbol = request.GET.get('value', '').strip()
        
        # 空の場合
        if not symbol:
            return JsonResponse({
                'valid': False,
                'message': '銘柄コードを入力してください'
            })
        
        # 形式チェック（数字4桁など）
        if not re.match(r'^\d{4}$', symbol):
            return JsonResponse({
                'valid': False,
                'message': '通常、日本株の銘柄コードは4桁の数字です'
            })
        
        # 既存レコードとの照合
        exists = StockDiary.objects.filter(
            user=request.user,
            stock_symbol=symbol
        ).exists()
        
        if exists:
            return JsonResponse({
                'valid': True,
                'message': '過去にこの銘柄の記録があります',
                'exists': True
            })
        
        return JsonResponse({
            'valid': True,
            'message': '有効な銘柄コードの形式です',
            'exists': False
        })
    
    elif field_type == 'stock_name':
        name = request.GET.get('value', '').strip()
        
        if not name:
            return JsonResponse({
                'valid': False,
                'message': '銘柄名を入力してください'
            })
        
        if len(name) < 2:
            return JsonResponse({
                'valid': False,
                'message': '銘柄名は2文字以上で入力してください'
            })
        
        return JsonResponse({
            'valid': True,
            'message': '有効な銘柄名です'
        })
    
    else:
        return JsonResponse({
            'valid': False,
            'message': '不明なフィールドタイプです'
        }, status=400)