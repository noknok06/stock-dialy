import logging

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.urls import reverse_lazy
from django.db.models import Q, Count, Avg, F, Sum, Min, Max, Case, When, Value, IntegerField, DecimalField
from django.db.models.functions import Coalesce
from django.db.models.functions import TruncMonth, ExtractWeekDay, Length
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.template.defaultfilters import truncatechars_html
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse, Http404
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.conf import settings
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core.cache import cache

from utils.mixins import ObjectNotFoundRedirectMixin
from .models import StockDiary, DiaryNote, DiaryNotification
from .models import Transaction, StockSplit
from .forms import TransactionForm, StockSplitForm, TradeUploadForm
from .forms import StockDiaryForm, DiaryNoteForm
from company_master.models import CompanyMaster
from tags.models import Tag
from django.views.generic import FormView


from django.db import transaction as db_transaction
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import calendar
import chardet
import mimetypes
import os
import csv
import io
import traceback
import html

logger = logging.getLogger(__name__)

# ページネーション定数
DIARY_LIST_PAGE_SIZE = 10        # 日記一覧 HTMX パーシャルおよびFBV
DIARY_LIST_INITIAL_SIZE = 4      # 日記一覧 CBV 初期表示
NOTIFICATION_LIST_PAGE_SIZE = 20 # 通知一覧
EXPLORE_PAGE_SIZE = 20           # Explore検索結果

import json
import re
import statistics

from PIL import Image

# ==========================================
# ユーティリティ関数
# ==========================================

def get_mention_map(user):
    """ユーザーのstock_symbol→diary_idマップ（LocMemCacheで5分キャッシュ）"""
    cache_key = f'mention_map_u{user.id}'
    mention_map = cache.get(cache_key)
    if mention_map is None:
        rows = StockDiary.objects.filter(
            user=user
        ).exclude(stock_symbol='').values('id', 'stock_symbol')
        mention_map = {r['stock_symbol']: r['id'] for r in rows}
        cache.set(cache_key, mention_map, 300)
    return mention_map


def calculate_margin_ratio(outstanding_purchases, outstanding_sales):
    """信用倍率を計算する共通関数"""
    if outstanding_sales > 0:
        return round(outstanding_purchases / outstanding_sales, 2)
    return 0


def render_error_html(icon, title, message, show_retry=False):
    """エラーメッセージHTMLを生成する共通関数"""
    retry_button = '''
        <button class="btn btn-sm btn-outline-primary" onclick="window.location.reload()">
            <i class="bi bi-arrow-clockwise me-1"></i>再試行
        </button>
    ''' if show_retry else ''
    
    return f'''
    <div class="text-center py-4">
        <div class="text-muted">
            <i class="bi bi-{icon}" style="font-size: 2rem;"></i>
            <h6 class="mt-3">{title}</h6>
            <p class="mb-0 small">{message}</p>
            {retry_button}
        </div>
    </div>
    '''


def get_note_badge_class(note_type):
    """ノートタイプに応じたバッジクラスを取得"""
    badge_classes = {
        'analysis': 'bg-primary',
        'news': 'bg-info',
        'earnings': 'bg-success',
        'insight': 'bg-warning',
        'risk': 'bg-danger'
    }
    return badge_classes.get(note_type, 'bg-secondary')


def get_note_type_display(note_type):
    """ノートタイプの表示名を取得"""
    type_displays = {
        'analysis': '分析更新',
        'news': 'ニュース',
        'earnings': '決算情報',
        'insight': '新たな気づき',
        'risk': 'リスク要因'
    }
    return type_displays.get(note_type, 'その他')


# ==========================================
# ビュークラス
# ==========================================

class StockDiaryListView(LoginRequiredMixin, ListView):
    model = StockDiary
    template_name = 'stockdiary/home.html'
    context_object_name = 'diaries'
    paginate_by = DIARY_LIST_INITIAL_SIZE
    
    def get_queryset(self):
        from .utils import search_diaries_by_hashtag

        queryset = StockDiary.objects.filter(user=self.request.user).order_by('-updated_at')
        queryset = queryset.select_related('user').prefetch_related('tags', 'notes')

        # 検索クエリ（銘柄名、コード、内容、メモ）
        query = self.request.GET.get('query', '').strip()
        if query:
            queryset = queryset.filter(
                Q(stock_name__icontains=query) |
                Q(stock_symbol__icontains=query) |
                Q(reason__icontains=query) |
                Q(memo__icontains=query) |
                Q(sector__icontains=query)
            )

        # ハッシュタグフィルター
        hashtag = self.request.GET.get('hashtag', '').strip()
        if hashtag:
            queryset = search_diaries_by_hashtag(queryset, hashtag)

        # タグフィルター
        tag_id = self.request.GET.get('tag', '')
        if tag_id:
            try:
                queryset = queryset.filter(tags__id=int(tag_id))
            except (ValueError, TypeError):
                pass
        
        # 業種フィルター
        sector = self.request.GET.get('sector', '').strip()
        if sector:
            queryset = queryset.filter(sector__iexact=sector)
        
        # 🔧 保有状態フィルター（デフォルトで保有中のみ表示）
        status = self.request.GET.get('status', 'active')  # デフォルト値を'active'に設定
        if status == 'active':
            # 保有中: 保有数が0より大きい
            queryset = queryset.filter(current_quantity__gt=0)
        elif status == 'sold':
            # 売却済み: 取引はあるが保有数が0または負数（空売り決済済み）
            queryset = queryset.filter(
                Q(current_quantity=0) | Q(current_quantity__lt=0),
                transaction_count__gt=0
            )
        elif status == 'memo':
            # メモのみ: 取引がない
            queryset = queryset.filter(transaction_count=0)
        elif status == 'all':
            # すべて表示（フィルターなし）
            pass
        
        # 🆕 トランザクション期間フィルター（created_at基準）
        transaction_date_range = self.request.GET.get('transaction_date_range', '')
        if transaction_date_range:
            from datetime import timedelta
            today = timezone.now()
            
            range_mapping = {
                '1w': 7,
                '1m': 30,
                '3m': 90,
                '6m': 180,
                '1y': 365
            }
            
            if transaction_date_range in range_mapping:
                start_datetime = today - timedelta(days=range_mapping[transaction_date_range])
                # トランザクションのcreated_atで絞り込み
                diary_ids = Transaction.objects.filter(
                    diary__user=self.request.user,
                    created_at__gte=start_datetime
                ).values_list('diary_id', flat=True).distinct()
                queryset = queryset.filter(id__in=diary_ids)
        
        # 開示書類更新フィルター
        disclosure_filter = self.request.GET.get('disclosure', '')
        if disclosure_filter == 'new':
            from datetime import timedelta
            cutoff = timezone.now().date() - timedelta(days=7)
            queryset = queryset.filter(latest_disclosure_date__gte=cutoff)
        elif disclosure_filter == 'recent':
            from datetime import timedelta
            cutoff = timezone.now().date() - timedelta(days=30)
            queryset = queryset.filter(latest_disclosure_date__gte=cutoff)

        # 既存の日付範囲フィルター（first_purchase_date基準）
        date_range = self.request.GET.get('date_range', '')
        if date_range:
            from datetime import timedelta
            today = timezone.now().date()
            
            range_mapping = {
                '1w': 7,
                '1m': 30,
                '3m': 90,
                '6m': 180,
                '1y': 365
            }
            
            if date_range in range_mapping:
                start_date = today - timedelta(days=range_mapping[date_range])
                queryset = queryset.filter(
                    Q(first_purchase_date__gte=start_date) |
                    Q(first_purchase_date__isnull=True, created_at__gte=start_date)
                )
        
        # 🆕 ソート順（取引回数・総取得原価を追加）
        sort = self.request.GET.get('sort', '')
        if sort == 'name':
            queryset = queryset.order_by('stock_name')
        elif sort == 'symbol':
            queryset = queryset.order_by('stock_symbol')
        elif sort == 'date_asc':
            queryset = queryset.order_by(
                F('first_purchase_date').asc(nulls_last=True),
                'created_at'
            )
        elif sort == 'date_desc':
            queryset = queryset.order_by(
                F('first_purchase_date').desc(nulls_last=True),
                '-created_at'
            )
        elif sort == 'profit_desc':
            queryset = queryset.order_by('-realized_profit')
        elif sort == 'profit_asc':
            queryset = queryset.order_by('realized_profit')
        # 🆕 取引回数順
        elif sort == 'transaction_count_desc':
            queryset = queryset.order_by('-transaction_count', '-updated_at')
        elif sort == 'transaction_count_asc':
            queryset = queryset.order_by('transaction_count', 'updated_at')
        # 🆕 総取得原価順
        elif sort == 'total_cost_desc':
            queryset = queryset.order_by('-total_cost', '-updated_at')
        elif sort == 'total_cost_asc':
            queryset = queryset.order_by('total_cost', 'updated_at')
        else:
            # デフォルト: 更新日時降順
            queryset = queryset.order_by('-updated_at')
        
        return queryset.distinct()

    # 🆕 diary_list 関数も同様に更新（views.py内の該当関数を以下で置き換え）
    def diary_list(request):
        """日記リストを表示するビュー（HTMX対応）"""
        is_htmx = request.headers.get('HX-Request') == 'true' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if not is_htmx:
            return redirect(f'/stockdiary/?{request.GET.urlencode()}')
        
        try:
            queryset = StockDiary.objects.filter(user=request.user).order_by('-updated_at')
            queryset = queryset.select_related('user').prefetch_related('tags', 'notes')
            
            # 検索クエリ
            query = request.GET.get('query', '').strip()
            if query:
                queryset = queryset.filter(
                    Q(stock_name__icontains=query) | 
                    Q(stock_symbol__icontains=query) |
                    Q(reason__icontains=query) |
                    Q(memo__icontains=query) |
                    Q(sector__icontains=query)
                )
            
            # タグフィルター
            tag_id = request.GET.get('tag', '')
            if tag_id:
                try:
                    queryset = queryset.filter(tags__id=int(tag_id))
                except (ValueError, TypeError):
                    pass
            
            # 業種フィルター
            sector = request.GET.get('sector', '').strip()
            if sector:
                queryset = queryset.filter(sector__iexact=sector)
            
            # 🆕 保有状態フィルター（デフォルトで保有中）
            status = request.GET.get('status', 'active')
            if status == 'active':
                queryset = queryset.filter(current_quantity__gt=0)
            elif status == 'sold':
                queryset = queryset.filter(
                    Q(current_quantity=0) | Q(current_quantity__lt=0),
                    transaction_count__gt=0
                )
            elif status == 'memo':
                queryset = queryset.filter(transaction_count=0)
            elif status == 'all':
                pass
            
            # 🆕 トランザクション期間フィルター
            transaction_date_range = request.GET.get('transaction_date_range', '')
            if transaction_date_range:
                from datetime import timedelta
                today = timezone.now()
                
                range_mapping = {
                    '1w': 7, '1m': 30, '3m': 90, '6m': 180, '1y': 365
                }
                
                if transaction_date_range in range_mapping:
                    start_datetime = today - timedelta(days=range_mapping[transaction_date_range])
                    diary_ids = Transaction.objects.filter(
                        diary__user=request.user,
                        created_at__gte=start_datetime
                    ).values_list('diary_id', flat=True).distinct()
                    queryset = queryset.filter(id__in=diary_ids)
            
            # 開示書類更新フィルター
            disclosure_filter = request.GET.get('disclosure', '')
            if disclosure_filter == 'new':
                from datetime import timedelta
                cutoff = timezone.now().date() - timedelta(days=7)
                queryset = queryset.filter(latest_disclosure_date__gte=cutoff)
            elif disclosure_filter == 'recent':
                from datetime import timedelta
                cutoff = timezone.now().date() - timedelta(days=30)
                queryset = queryset.filter(latest_disclosure_date__gte=cutoff)

            # 日付範囲フィルター
            date_range = request.GET.get('date_range', '')
            if date_range:
                from datetime import timedelta
                today = timezone.now().date()

                range_mapping = {
                    '1w': 7, '1m': 30, '3m': 90, '6m': 180, '1y': 365
                }

                if date_range in range_mapping:
                    start_date = today - timedelta(days=range_mapping[date_range])
                    queryset = queryset.filter(
                        Q(first_purchase_date__gte=start_date) |
                        Q(first_purchase_date__isnull=True, created_at__gte=start_date)
                    )

            # 🆕 ソート（取引回数・総取得原価を追加）
            sort = request.GET.get('sort', '')
            if sort == 'name':
                queryset = queryset.order_by('stock_name')
            elif sort == 'symbol':
                queryset = queryset.order_by('stock_symbol')
            elif sort == 'date_asc':
                queryset = queryset.order_by(
                    F('first_purchase_date').asc(nulls_last=True),
                    'created_at'
                )
            elif sort == 'date_desc':
                queryset = queryset.order_by(
                    F('first_purchase_date').desc(nulls_last=True),
                    '-created_at'
                )
            elif sort == 'profit_desc':
                queryset = queryset.order_by('-realized_profit')
            elif sort == 'profit_asc':
                queryset = queryset.order_by('realized_profit')
            elif sort == 'transaction_count_desc':
                queryset = queryset.order_by('-transaction_count', '-updated_at')
            elif sort == 'transaction_count_asc':
                queryset = queryset.order_by('transaction_count', 'updated_at')
            elif sort == 'total_cost_desc':
                queryset = queryset.order_by('-total_cost', '-updated_at')
            elif sort == 'total_cost_asc':
                queryset = queryset.order_by('total_cost', 'updated_at')
            else:
                queryset = queryset.order_by('-updated_at')
            
            queryset = queryset.distinct()
            
            # ページネーション
            current_params = request.GET.copy()
            current_params.pop('page', None)

            paginator = Paginator(queryset, DIARY_LIST_PAGE_SIZE)
            page = request.GET.get('page', 1)
            
            try:
                diaries = paginator.page(page)
            except (PageNotAnInteger, EmptyPage):
                diaries = paginator.page(1)
            
            tags = Tag.objects.filter(user=request.user)
            
            sectors = StockDiary.objects.filter(
                user=request.user,
                sector__isnull=False
            ).exclude(sector='').values_list('sector', flat=True).distinct().order_by('sector')
            
            context = {
                'diaries': diaries,
                'page_obj': diaries,
                'tags': tags,
                'sectors': list(sectors),
                'request': request,
                'current_params': current_params,
            }
            
            return render(request, 'stockdiary/partials/diary_list.html', context)
        
        except Exception as e:
            logger.error("Diary list error: %s", e, exc_info=True)

            return HttpResponse(
                '<div class="alert alert-danger">日記リストの読み込みに失敗しました。</div>',
                status=500
            )
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tags'] = Tag.objects.filter(user=self.request.user)
        
        # 業種リストを取得（重複なし）
        sectors = StockDiary.objects.filter(
            user=self.request.user,
            sector__isnull=False
        ).exclude(sector='').values_list('sector', flat=True).distinct().order_by('sector')
        context['sectors'] = list(sectors)
        
        # カレンダー表示用にすべての日記データを追加（統計も同一クエリで取得）
        all_diaries_qs = StockDiary.objects.filter(user=self.request.user)
        context['all_diaries'] = all_diaries_qs.defer(
            'reason', 'memo', 'created_at', 'updated_at',
        )

        # 統計情報を1クエリにまとめて取得
        stats = all_diaries_qs.aggregate(
            active_count=Count('id', filter=Q(current_quantity__gt=0)),
            sold_count=Count('id', filter=Q(current_quantity=0, transaction_count__gt=0)),
            memo_count=Count('id', filter=Q(transaction_count=0)),
            total_profit=Sum('realized_profit'),
        )
        context['active_holdings_count'] = stats['active_count'] or 0
        context['realized_profit'] = stats['total_profit'] or Decimal('0')
        context['sold_count'] = stats['sold_count'] or 0
        context['memo_count'] = stats['memo_count'] or 0
        
        # 検索パラメータを保持
        context['current_query'] = self.request.GET.urlencode()
        context['current_params'] = self.request.GET
        
        # フォーム用のスピードダイアルアクション
        context['form_actions'] = [
            {
                'id': 'quick-add',
                'type': 'quick-add',
                'url': '#',
                'icon': 'bi-lightning-charge-fill',
                'label': 'クイック記録',
                'aria_label': '素早く投資記録を作成',
                'condition': True
            },
            {
                'type': 'add',
                'url': reverse_lazy('stockdiary:create'),
                'icon': 'bi-plus-lg',
                'label': '新規登録',
                'aria_label': '新規登録'
            },
            {
                'type': 'template',
                'url': reverse_lazy('analysis_template:list'),
                'icon': 'bi-clipboard-data',
                'label': 'テンプレート',
                'aria_label': 'テンプレート',
            },
            {
                'type': 'tag',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-tags',
                'label': 'タグ管理',
                'aria_label': 'タグ管理'
            }
        ]

        # クイック記録用に今日の日付を追加
        context['today'] = timezone.now().date()
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                self.object_list = self.get_queryset()
                page_size = self.get_paginate_by(self.object_list)
                
                if page_size:
                    paginator = self.get_paginator(self.object_list, page_size)
                    page_number = request.GET.get('page', 1)
                    try:
                        page_obj = paginator.get_page(page_number)
                    except (EmptyPage, PageNotAnInteger):
                        page_obj = paginator.get_page(1)
                    
                    data = []
                    for diary in page_obj:
                        try:
                            diary_html = render_to_string('stockdiary/partials/diary_card.html', {
                                'diary': diary,
                                'request': request,
                                'forloop': {'counter': 1}
                            })
                            data.append(diary_html)
                        except Exception as e:
                            logger.warning("Error rendering diary %s: %s", diary.id, e, exc_info=True)
                            continue
                    
                    return JsonResponse({
                        'html': data,
                        'has_next': page_obj.has_next(),
                        'next_page': page_obj.next_page_number() if page_obj.has_next() else None
                    })
            except Exception as e:
                logger.error("AJAX request error: %s", e, exc_info=True)
                return JsonResponse({
                    'message': 'データの読み込み中にエラーが発生しました。'
                }, status=500)
        
        return super().get(request, *args, **kwargs)


class StockDiaryDetailView(ObjectNotFoundRedirectMixin, LoginRequiredMixin, DetailView):
    model = StockDiary
    template_name = 'stockdiary/detail.html'
    context_object_name = 'diary'
    redirect_url = 'stockdiary:home'
    not_found_message = "日記エントリーが見つかりません。削除された可能性があります。"
    
    def get_queryset(self):
        return StockDiary.objects.filter(user=self.request.user).select_related('user').prefetch_related(
            'notes', 'tags',
            'transactions', 'stock_splits', 'linked_diaries'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # ✅ 現物取引のみの統計を追加
        context['cash_only_stats'] = self.object.calculate_cash_only_stats()
        
        # 取引履歴を取得
        transactions = self.object.transactions.all().order_by('-transaction_date', '-created_at')
        context['transactions'] = transactions
        
        # 株式分割履歴を取得
        stock_splits = self.object.stock_splits.all().order_by('-split_date')
        context['stock_splits'] = stock_splits
        
        # 取引と分割を時系列で統合
        combined = []
        for transaction in transactions:
            combined.append({
                'type': 'transaction',
                'date': transaction.transaction_date,
                'data': transaction
            })
        
        for split in stock_splits:
            combined.append({
                'type': 'split',
                'date': split.split_date,
                'data': split
            })
        
        # 日付でソート（降順）
        combined.sort(key=lambda x: x['date'], reverse=True)
        context['combined_history'] = combined
        
        # 継続記録
        context['note_form'] = DiaryNoteForm(initial={'date': timezone.now().date()})
        context['notes'] = self.object.notes.all().order_by('-date')
        
        # 関連日記
        # 銘柄コードが空の場合は同一銘柄グループとして扱わない（空同士がまとめられるのを防ぐ）
        if self.object.stock_symbol:
            all_related_diaries = StockDiary.objects.filter(
                user=self.request.user,
                stock_symbol=self.object.stock_symbol
            ).order_by('first_purchase_date', 'created_at')
        else:
            all_related_diaries = StockDiary.objects.filter(
                id=self.object.id
            )

        context['related_diaries'] = all_related_diaries.exclude(id=self.object.id)
        context['timeline_diaries'] = all_related_diaries

        # 手動リンク + 自動リンク（メモ・投資理由に記載された4桁銘柄コード言及）を統合した関連日記リスト
        manual_linked_ids = set(self.object.linked_diaries.values_list('id', flat=True))
        combined_related = []
        for d in self.object.linked_diaries.select_related():
            combined_related.append({'diary': d, 'is_auto': False})
        # メモ・投資理由から4桁銘柄コードを抽出し、一致する日記を自動リンク
        search_text = ' '.join(filter(None, [self.object.memo, self.object.reason]))
        mentioned_codes = set(re.findall(r'\b\d{4}\b', search_text))
        if mentioned_codes:
            auto_diaries = StockDiary.objects.filter(
                user=self.request.user,
                stock_symbol__in=mentioned_codes
            ).exclude(id=self.object.id)
            for d in auto_diaries:
                if d.id not in manual_linked_ids:
                    combined_related.append({'diary': d, 'is_auto': True})
        context['combined_related_diaries'] = combined_related
        
        # スピードダイアルアクション
        context['diary_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'modal',  # 🆕 モーダル専用タイプ
                'modal_target': '#notificationModal',  # 🆕 モーダルのID
                'icon': 'bi-bell',
                'label': '通知設定'
            },
            {
                'type': 'edit',
                'url': reverse_lazy('stockdiary:update', kwargs={'pk': self.object.id}),
                'icon': 'bi-pencil',
                'label': '編集'
            },
            {
                'type': 'delete',
                'url': reverse_lazy('stockdiary:delete', kwargs={'pk': self.object.id}),
                'icon': 'bi-trash',
                'label': '削除'
            }
        ]

        # クイック記録用に今日の日付を追加
        context['today'] = timezone.now().date()

        # テキスト内銘柄コードリンク用マッピング {stock_symbol: diary_pk}
        context['mention_map'] = get_mention_map(self.request.user)

        return context

class StockDiaryCreateView(LoginRequiredMixin, CreateView):
    model = StockDiary
    form_class = StockDiaryForm
    template_name = 'stockdiary/diary_form.html'
    success_url = reverse_lazy('stockdiary:home')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        
        # 画像ファイルの処理
        image_file = form.cleaned_data.get('image')
        if image_file:
            success = self.object.process_and_save_image(image_file)
            if not success:
                messages.warning(self.request, '日記は作成されましたが、画像の処理に失敗しました。')
                
        # 初回購入情報の処理
        if form.cleaned_data.get('add_initial_purchase'):
            try:
                initial_transaction = Transaction(
                    diary=self.object,
                    transaction_type='buy',
                    transaction_date=form.cleaned_data['initial_purchase_date'],
                    price=form.cleaned_data['initial_purchase_price'],
                    quantity=form.cleaned_data['initial_purchase_quantity'],
                    memo='初回購入'
                )
                initial_transaction.save()
                
                # 取引後の状態を記録
                initial_transaction.quantity_after = self.object.current_quantity
                initial_transaction.average_price_after = self.object.average_purchase_price
                initial_transaction.save(update_fields=['quantity_after', 'average_price_after'])
                
                messages.success(self.request, '日記を作成し、初回購入取引を記録しました')
            except Exception as e:
                messages.warning(
                    self.request,
                    f'日記は作成されましたが、初回購入取引の記録に失敗しました: {str(e)}'
                )
        else:
            messages.success(self.request, '日記を作成しました')

        cache.delete(f'mention_map_u{self.request.user.id}')
        return response


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # スピードダイアルアクション
        context['form_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        
        
        
        return context
    

class StockDiaryUpdateView(ObjectNotFoundRedirectMixin, LoginRequiredMixin, UpdateView):
    model = StockDiary
    form_class = StockDiaryForm
    template_name = 'stockdiary/diary_form.html'
    redirect_url = 'stockdiary:home'
    not_found_message = "日記エントリーが見つかりません。削除された可能性があります。"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:detail', kwargs={'pk': self.object.pk}),
                'icon': 'bi-arrow-left',
                'label': '戻る',
                'aria_label': '戻る' 
            },
            {
                'type': 'template',
                'url': reverse_lazy('analysis_template:list'),
                'icon': 'bi-clipboard-data',
                'label': 'テンプレート',
                'aria_label': 'テンプレート' 
            },
            {
                'type': 'tag',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-tags',
                'label': 'タグ管理',
                'aria_label': 'タグ管理' 
            }
        ]
        return context

    def get_queryset(self):
        return StockDiary.objects.filter(user=self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        if request.POST.get('clear_image'):
            success = self.object.delete_image()
            if not success:
                messages.warning(request, '画像の削除に失敗しました。')
        
        return super().post(request, *args, **kwargs)
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        image_file = form.cleaned_data.get('image')
        if image_file:
            success = self.object.process_and_save_image(image_file)
            if not success:
                messages.warning(self.request, '日記は更新されましたが、画像の処理に失敗しました。')

        cache.delete(f'mention_map_u{self.request.user.id}')
        return response

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        return form
    
    def get_success_url(self):
        return reverse_lazy('stockdiary:detail', kwargs={'pk': self.object.pk})


class StockDiaryDeleteView(LoginRequiredMixin, DeleteView):
    model = StockDiary
    template_name = 'stockdiary/diary_confirm_delete.html'
    success_url = reverse_lazy('stockdiary:home')
    
    def get_queryset(self):
        return StockDiary.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        cache.delete(f'mention_map_u{request.user.id}')
        return response


class AddDiaryNoteView(LoginRequiredMixin, CreateView):
    """日記エントリーへの継続記録追加"""
    model = DiaryNote
    form_class = DiaryNoteForm
    http_method_names = ['post']
    
    def form_valid(self, form):
        diary_id = self.kwargs.get('pk')
        diary = get_object_or_404(StockDiary, id=diary_id, user=self.request.user)
        form.instance.diary = diary
        
        response = super().form_valid(form)

        # 参照書類IDを保存
        source_doc_id = self.request.POST.get('source_doc_id', '').strip()[:8]
        if source_doc_id:
            self.object.source_doc_id = source_doc_id
            self.object.save(update_fields=['source_doc_id'])

        image_file = self.request.FILES.get('image')
        if image_file:
            if image_file.size > 10 * 1024 * 1024:
                messages.error(self.request, '画像ファイルのサイズは10MB以下にしてください')
                return self.form_invalid(form)

            valid_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(image_file, 'content_type') and image_file.content_type not in valid_formats:
                messages.error(self.request, 'JPEG、PNG、GIF、WebP形式の画像ファイルのみアップロード可能です')
                return self.form_invalid(form)

            success = self.object.process_and_save_image(image_file)
            if not success:
                messages.warning(self.request, '継続記録は追加されましたが、画像の処理に失敗しました。')

        messages.success(self.request, "継続記録を追加しました")
        return response
    
    def get_success_url(self):
        return reverse_lazy('stockdiary:detail', kwargs={'pk': self.kwargs.get('pk')})
    
    def form_invalid(self, form):
        diary_id = self.kwargs.get('pk')
        return redirect('stockdiary:detail', pk=diary_id)


class DeleteDiaryNoteView(LoginRequiredMixin, DeleteView):
    """継続記録を削除するビュー"""
    model = DiaryNote
    template_name = 'stockdiary/note_confirm_delete.html'
    
    def get_queryset(self):
        return DiaryNote.objects.filter(diary__user=self.request.user)
    
    def get_success_url(self):
        diary_pk = self.kwargs.get('diary_pk')
        return reverse_lazy('stockdiary:detail', kwargs={'pk': diary_pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['diary_pk'] = self.kwargs.get('diary_pk')
        return context


class DiaryTabContentView(LoginRequiredMixin, View):
    def get(self, request, diary_id, tab_type):
        try:
            diary = StockDiary.objects.get(id=diary_id, user=request.user)
            
            context = {
                'diary': diary,
                'diary_id': diary.id,
            }
            
            if tab_type == 'notes':
                html = self._render_notes_tab(diary)
            elif tab_type == 'analysis':
                html = self._render_analysis_tab(diary)
            elif tab_type == 'details':
                html = self._render_details_tab(context)
            else:
                return JsonResponse({'error': '無効なタブタイプです'}, status=400)
            
            return JsonResponse({'html': html})
            
        except StockDiary.DoesNotExist:
            return JsonResponse({'error': '日記が見つかりません'}, status=404)
        except Exception as e:
            logger.error("Tab content error: %s", e, exc_info=True)
            return JsonResponse({'error': 'タブコンテンツの読み込みに失敗しました'}, status=500)

    def _render_notes_tab(self, diary):
        """継続記録タブのHTMLを直接生成"""
        notes = diary.notes.all().order_by('-date')[:3]
        html = '<div class="px-1 py-2"><div class="notes-timeline">'
        
        if notes.exists():
            for note in notes:
                date_str = note.date.strftime('%Y年%m月%d日')
                badge_class = get_note_badge_class(note.note_type)
                badge_text = get_note_type_display(note.note_type)
                
                html += f'''
                <div class="note-item mb-3" data-importance="{note.importance}">
                  <div class="d-flex justify-content-between align-items-start mb-1">
                    <div class="note-date">
                      <i class="bi bi-calendar-date text-muted"></i>
                      <span class="text-muted small">{date_str}</span>
                    </div>
                    <span class="badge {badge_class} small">{badge_text}</span>
                  </div>
                '''
                
                if note.current_price:
                    price_formatted = f"{float(note.current_price):,.2f}円"
                    html += f'<div class="note-price small mb-1"><span class="text-muted">記録時価格:</span><span class="fw-medium">{price_formatted}</span>'
                    
                    if diary.purchase_price:
                        price_change = ((float(note.current_price) / float(diary.purchase_price)) - 1) * 100
                        price_change_class = "text-success" if price_change > 0 else "text-danger"
                        price_change_sign = "+" if price_change > 0 else ""
                        html += f'<span class="{price_change_class} ms-2">({price_change_sign}{price_change:.2f}%)</span>'
                    
                    html += '</div>'
                                
                formatted_content = note.content.replace('\n', '<br>')
                html += f'''
                <div class="note-content bg-light p-2 rounded">
                    {formatted_content}
                </div>
                </div>
                '''
            
            notes_count = diary.notes.count()
            if notes_count > 3:
                html += f'''
                <div class="text-end mt-2">
                  <a href="/stockdiary/{diary.id}/" class="text-primary text-decoration-none small">
                    すべての記録を見る ({notes_count}件) <i class="bi bi-arrow-right"></i>
                  </a>
                </div>
                '''
        else:
            html += '<p class="text-muted">継続記録はまだありません</p>'
        
        html += '</div></div>'
        return html
            
    
    def _render_details_tab(self, context):
        """取引タブのHTMLを直接生成"""
        diary = context['diary']
        html = '<div class="px-1 py-2">'
        
        # 🔧 修正: 購入情報の表示
        # 取引履歴があり、平均取得単価と保有数が設定されている場合
        if diary.transaction_count > 0 and diary.average_purchase_price is not None:
            # 現在の総投資額を計算
            if diary.current_quantity > 0:
                total_investment = float(diary.average_purchase_price) * float(diary.current_quantity)
            else:
                # 売却済みの場合は総購入額を表示
                total_investment = float(diary.total_buy_amount) if diary.total_buy_amount else 0
            
            html += '''
            <div class="info-block mb-3">
            <div class="info-row">
                <div class="info-item">
                <div class="info-icon">
                    <i class="bi bi-currency-yen"></i>
                </div>
                <div class="info-content">
                    <span class="info-label">平均取得単価</span>
                    <span class="info-value">{:,.2f}円</span>
                </div>
                </div>
                
                <div class="info-item">
                <div class="info-icon">
                    <i class="bi bi-graph-up"></i>
                </div>
                <div class="info-content">
                    <span class="info-label">現在保有数</span>
                    <span class="info-value">{:.2f}株</span>
                </div>
                </div>
                
                <div class="info-item">
                <div class="info-icon">
                    <i class="bi bi-calendar-date"></i>
                </div>
                <div class="info-content">
                    <span class="info-label">初回購入日</span>
                    <span class="info-value">{}</span>
                </div>
                </div>
                
                <div class="info-item">
                <div class="info-icon">
                    <i class="bi bi-cash-stack"></i>
                </div>
                <div class="info-content">
                    <span class="info-label">総投資額</span>
                    <span class="info-value">{:,.0f}円</span>
                </div>
                </div>
            </div>
            </div>
            '''.format(
                float(diary.average_purchase_price),
                float(diary.current_quantity) if diary.current_quantity else 0,
                diary.first_purchase_date.strftime('%Y年%m月%d日') if diary.first_purchase_date else '未設定',
                total_investment
            )
        
        # 🔧 修正: 売却情報の表示
        # 売却済み（保有数0、取引あり）かつ実現損益がある場合
        if diary.is_sold_out and diary.realized_profit is not None:
            profit = float(diary.realized_profit)
            # 損益率を計算（総売却額 ÷ 総購入額）
            profit_rate = 0
            if diary.total_buy_amount and float(diary.total_buy_amount) > 0:
                profit_rate = (profit / float(diary.total_buy_amount)) * 100
            
            profit_class = "profit" if profit > 0 else ("loss" if profit < 0 else "text-muted")
            profit_sign = "+" if profit > 0 else ""
            
            html += '''
            <div class="sell-info">
            <div class="info-row">
                <div class="info-item">
                <div class="info-icon">
                    <i class="bi bi-calendar-check"></i>
                </div>
                <div class="info-content">
                    <span class="info-label">最終取引日</span>
                    <span class="info-value">{}</span>
                </div>
                </div>
                
                <div class="info-item">
                <div class="info-icon">
                    <i class="bi bi-graph-up-arrow"></i>
                </div>
                <div class="info-content">
                    <span class="info-label">実現損益</span>
                    <span class="info-value {}">{}{:,.0f}円</span>
                </div>
                </div>
                
                <div class="info-item">
                <div class="info-icon">
                    <i class="bi bi-percent"></i>
                </div>
                <div class="info-content">
                    <span class="info-label">損益率</span>
                    <span class="info-value {}">{}{:.2f}%</span>
                </div>
                </div>
                
                <div class="info-item">
                <div class="info-icon">
                    <i class="bi bi-cash-stack"></i>
                </div>
                <div class="info-content">
                    <span class="info-label">総売却額</span>
                    <span class="info-value">{:,.0f}円</span>
                </div>
                </div>
            </div>
            </div>
            '''.format(
                diary.last_transaction_date.strftime('%Y年%m月%d日') if diary.last_transaction_date else '未設定',
                profit_class,
                profit_sign,
                profit,
                profit_class,
                profit_sign,
                profit_rate,
                float(diary.total_sell_amount) if diary.total_sell_amount else 0
            )
        elif diary.is_memo:
            # メモのみの場合
            html += '''
            <div class="alert alert-info">
            <i class="bi bi-info-circle me-2"></i>
            この日記はメモとして記録されています。取引情報が設定されていません。
            </div>
            '''
        
        html += '</div>'
        return html


class StockListView(LoginRequiredMixin, TemplateView):
    """登録株式一覧を表示するビュー"""
    template_name = 'stockdiary/stock_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        search_query = self.request.GET.get('q', '').strip()
        sort_by = self.request.GET.get('sort', 'symbol')
        sector_filter = self.request.GET.get('sector', '')
        
        # 単一クエリで銘柄ごとに集計（N+1防止）
        diary_agg = (
            StockDiary.objects.filter(user=user, stock_symbol__isnull=False)
            .exclude(stock_symbol='')
            .values('stock_symbol')
            .annotate(
                stock_name=Max('stock_name'),
                sector=Max('sector'),
                diary_count=Count('id'),
                active_count=Count('id', filter=Q(current_quantity__gt=0)),
                sold_count=Count(
                    'id',
                    filter=Q(current_quantity=0, transaction_count__gt=0)
                ),
            )
            .order_by('stock_symbol')
        )

        # CompanyMasterを一括取得して業種補完用辞書を作成
        symbols = [row['stock_symbol'] for row in diary_agg]
        company_sector_map = {
            c.code: c.industry_name_33 or c.industry_name_17 or '未分類'
            for c in CompanyMaster.objects.filter(code__in=symbols)
        }

        stock_list = []

        for row in diary_agg:
            sector = row['sector'] or '未分類'
            if sector == '未分類':
                sector = company_sector_map.get(row['stock_symbol'], '未分類')

            stock_list.append({
                'symbol': row['stock_symbol'],
                'name': row['stock_name'],
                'sector': sector,
                'current_ratio': 0,
                'previous_ratio': 0,
                'ratio_change': 0,
                'latest_date': None,
                'diary_count': row['diary_count'],
                'has_active_holdings': row['active_count'] > 0,
                'has_completed_sales': row['sold_count'] > 0,
                'margin_data_available': False,
            })
        
        # 検索フィルター
        if search_query:
            stock_list = [
                stock for stock in stock_list
                if search_query.lower() in stock['name'].lower() or 
                   search_query.lower() in stock['symbol'].lower() or
                   search_query.lower() in stock['sector'].lower()
            ]
        
        # 業種フィルター
        if sector_filter:
            stock_list = [stock for stock in stock_list if stock['sector'] == sector_filter]
        
        # ソート処理
        sort_mapping = {
            'name': lambda x: x['name'],
            'sector': lambda x: x['sector'],
            'current_ratio_desc': lambda x: x['current_ratio'],
            'current_ratio_asc': lambda x: x['current_ratio'],
            'ratio_change_desc': lambda x: x['ratio_change'],
            'ratio_change_asc': lambda x: x['ratio_change'],
            'diary_count_desc': lambda x: x['diary_count'],
        }
        
        if sort_by in sort_mapping:
            reverse = sort_by.endswith('_desc')
            stock_list.sort(key=sort_mapping[sort_by], reverse=reverse)
        else:
            stock_list.sort(key=lambda x: x['symbol'])
        
        # 業種リストの作成
        sectors = sorted(list(set([stock['sector'] for stock in stock_list])))
        
        # 統計情報の作成
        stats = {
            'total_stocks': len(stock_list),
            'active_holdings': len([s for s in stock_list if s['has_active_holdings']]),
            'margin_data_available': len([s for s in stock_list if s['margin_data_available']]),
            'sectors_count': len(sectors)
        }
        
        # ページアクション
        context['page_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'add',
                'url': reverse_lazy('stockdiary:create'),
                'icon': 'bi-plus-lg',
                'label': '新規作成'
            }
        ]
        
        context.update({
            'stock_list': stock_list,
            'sectors': sectors,
            'stats': stats,
            'search_query': search_query,
            'sort_by': sort_by,
            'sector_filter': sector_filter,
        })
        
        return context

class ServeImageView(LoginRequiredMixin, View):
    """ユーザー認証付きの画像配信ビュー"""
    
    def get(self, request, diary_id, image_type, note_id=None):
        try:
            diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
            
            if image_type == 'diary':
                if not diary.image:
                    raise Http404("画像が見つかりません")
                image_field = diary.image
                
            elif image_type == 'note':
                if not note_id:
                    raise Http404("ノートIDが指定されていません")
                note = get_object_or_404(DiaryNote, id=note_id, diary=diary)
                if not note.image:
                    raise Http404("画像が見つかりません")
                image_field = note.image
            else:
                raise Http404("無効な画像タイプです")
            
            is_thumbnail = request.GET.get('thumbnail') == '1'
            if is_thumbnail:
                return self._serve_thumbnail(image_field, request)
            
            return self._serve_image(image_field)
            
        except Exception as e:
            logger.error("Image serving error: %s", e, exc_info=True)
            raise Http404("画像の配信中にエラーが発生しました")
    
    def _serve_image(self, image_field):
        """通常の画像を配信"""
        try:
            image_file = image_field.open('rb')
            file_path = image_field.name
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = 'image/jpeg'
            
            response = HttpResponse(image_file.read(), content_type=content_type)
            response['Cache-Control'] = 'private, max-age=3600'
            
            filename = os.path.basename(file_path)
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            
            image_file.close()
            return response
            
        except Exception as e:
            logger.error("Error serving image: %s", e, exc_info=True)
            raise Http404("画像ファイルが見つかりません")
    
    def _serve_thumbnail(self, image_field, request):
        """サムネイル画像を生成して配信"""
        try:
            width = int(request.GET.get('w', 300))
            height = int(request.GET.get('h', 200))
            
            width = min(max(width, 50), 800)
            height = min(max(height, 50), 600)
            
            image_file = image_field.open('rb')
            img = Image.open(image_file)
            
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            img_ratio = img.width / img.height
            thumb_ratio = width / height
            
            if img_ratio > thumb_ratio:
                new_height = height
                new_width = int(height * img_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                left = (new_width - width) // 2
                img = img.crop((left, 0, left + width, height))
            else:
                new_width = width
                new_height = int(width / img_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                top = (new_height - height) // 2
                img = img.crop((0, top, width, top + height))
            
            output = io.BytesIO()
            
            try:
                img.save(output, format='WebP', quality=80, optimize=True)
                content_type = 'image/webp'
            except Exception:
                img.save(output, format='JPEG', quality=80, optimize=True)
                content_type = 'image/jpeg'
            
            output.seek(0)
            
            response = HttpResponse(output.getvalue(), content_type=content_type)
            response['Cache-Control'] = 'private, max-age=7200'
            
            image_file.close()
            return response
            
        except Exception as e:
            logger.warning("Error creating thumbnail: %s", e, exc_info=True)
            return self._serve_image(image_field)


# ==========================================
# ファンクションベースビュー
# ==========================================
def diary_list(request):
    """日記リストを表示するビュー（HTMX対応）"""
    from .utils import search_diaries_by_hashtag

    is_htmx = request.headers.get('HX-Request') == 'true' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not is_htmx:
        return redirect(f'/stockdiary/?{request.GET.urlencode()}')

    try:
        queryset = StockDiary.objects.filter(user=request.user).order_by('-updated_at')
        queryset = queryset.select_related('user').prefetch_related('tags', 'notes')

        # 検索クエリ
        query = request.GET.get('query', '').strip()
        if query:
            queryset = queryset.filter(
                Q(stock_name__icontains=query) |
                Q(stock_symbol__icontains=query) |
                Q(reason__icontains=query) |
                Q(memo__icontains=query) |
                Q(sector__icontains=query)
            )

        # ハッシュタグフィルター
        hashtag = request.GET.get('hashtag', '').strip()
        if hashtag:
            queryset = search_diaries_by_hashtag(queryset, hashtag)

        # タグフィルター
        tag_id = request.GET.get('tag', '')
        if tag_id:
            try:
                queryset = queryset.filter(tags__id=int(tag_id))
            except (ValueError, TypeError):
                pass
        
        # 業種フィルター
        sector = request.GET.get('sector', '').strip()
        if sector:
            queryset = queryset.filter(sector__iexact=sector)
        
        # 保有状態フィルター
        status = request.GET.get('status', '')
        if status == 'active':
            queryset = queryset.filter(current_quantity__gt=0)
        elif status == 'sold':
            queryset = queryset.filter(
                Q(current_quantity=0) | Q(current_quantity__lt=0),
                transaction_count__gt=0
            )
        elif status == 'memo':
            queryset = queryset.filter(transaction_count=0)
        
        # 日付範囲フィルター
        date_range = request.GET.get('date_range', '')
        if date_range:
            from datetime import timedelta
            today = timezone.now().date()
            
            range_mapping = {
                '1w': 7, '1m': 30, '3m': 90, '6m': 180, '1y': 365
            }
            
            if date_range in range_mapping:
                start_date = today - timedelta(days=range_mapping[date_range])
                queryset = queryset.filter(
                    Q(first_purchase_date__gte=start_date) |
                    Q(first_purchase_date__isnull=True, created_at__gte=start_date)
                )
        
        # トランザクション期間フィルター（created_at基準）
        transaction_date_range = request.GET.get('transaction_date_range', '')
        if transaction_date_range:
            from datetime import timedelta
            today = timezone.now()
            range_mapping = {
                '1w': 7, '1m': 30, '3m': 90, '6m': 180, '1y': 365
            }
            if transaction_date_range in range_mapping:
                start_datetime = today - timedelta(days=range_mapping[transaction_date_range])
                diary_ids = Transaction.objects.filter(
                    diary__user=request.user,
                    created_at__gte=start_datetime
                ).values_list('diary_id', flat=True).distinct()
                queryset = queryset.filter(id__in=diary_ids)

        # 開示書類更新フィルター
        disclosure_filter = request.GET.get('disclosure', '')
        if disclosure_filter == 'new':
            from datetime import timedelta
            cutoff = timezone.now().date() - timedelta(days=7)
            queryset = queryset.filter(latest_disclosure_date__gte=cutoff)
        elif disclosure_filter == 'recent':
            from datetime import timedelta
            cutoff = timezone.now().date() - timedelta(days=30)
            queryset = queryset.filter(latest_disclosure_date__gte=cutoff)

        # ソート
        sort = request.GET.get('sort', '')
        if sort == 'name':
            queryset = queryset.order_by('stock_name')
        elif sort == 'symbol':
            queryset = queryset.order_by('stock_symbol')
        elif sort == 'date_asc':
            queryset = queryset.order_by(
                F('first_purchase_date').asc(nulls_last=True),
                'created_at'
            )
        elif sort == 'date_desc':
            queryset = queryset.order_by(
                F('first_purchase_date').desc(nulls_last=True),
                '-created_at'
            )
        elif sort == 'profit_desc':
            queryset = queryset.order_by('-realized_profit')
        elif sort == 'profit_asc':
            queryset = queryset.order_by('realized_profit')
        elif sort == 'transaction_count_desc':
            queryset = queryset.order_by('-transaction_count', '-updated_at')
        elif sort == 'transaction_count_asc':
            queryset = queryset.order_by('transaction_count', 'updated_at')
        elif sort == 'total_cost_desc':
            queryset = queryset.order_by('-total_cost', '-updated_at')
        elif sort == 'total_cost_asc':
            queryset = queryset.order_by('total_cost', 'updated_at')
        else:
            queryset = queryset.order_by('-updated_at')
        
        queryset = queryset.distinct()
        
        # ページネーション
        current_params = request.GET.copy()
        current_params.pop('page', None)

        paginator = Paginator(queryset, DIARY_LIST_PAGE_SIZE)
        page = request.GET.get('page', 1)
        
        try:
            diaries = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            diaries = paginator.page(1)
        
        tags = Tag.objects.filter(user=request.user)
        
        # 業種リスト
        sectors = StockDiary.objects.filter(
            user=request.user,
            sector__isnull=False
        ).exclude(sector='').values_list('sector', flat=True).distinct().order_by('sector')
        
        context = {
            'diaries': diaries,
            'page_obj': diaries,
            'tags': tags,
            'sectors': list(sectors),
            'request': request,
            'current_params': current_params,
        }
        
        return render(request, 'stockdiary/partials/diary_list.html', context)
    
    except Exception as e:
        logger.error("Diary list error: %s", e, exc_info=True)

        return HttpResponse(
            '<div class="alert alert-danger">日記リストの読み込みに失敗しました。</div>',
            status=500
        )

def tab_content(request, diary_id, tab_type):
    """日記カードのタブコンテンツを表示するビュー"""
    try:
        try:
            diary = StockDiary.objects.prefetch_related(
                'notes', 'transactions'
            ).get(id=diary_id, user=request.user)
        except StockDiary.DoesNotExist:
            return HttpResponse(
                '<div class="alert alert-warning">指定された日記が見つかりません。</div>', 
                status=404
            )

        context = {
            'diary': diary,
            'is_detail_view': False,  # ホーム画面からの呼び出し
        }
        
        try:
            if tab_type == 'notes':
                notes = diary.notes.all().order_by('-date')[:3]
                context['notes'] = notes
                context['mention_map'] = get_mention_map(request.user)
                template_name = 'stockdiary/partials/tab_notes.html'

            elif tab_type == 'details':
                # 取引タブの処理を追加
                transactions = diary.transactions.all().order_by('-transaction_date', '-created_at')[:5]
                context['transactions'] = transactions
                context['transaction_count'] = diary.transaction_count
                template_name = 'stockdiary/partials/tab_details.html'
                        
            else:
                return HttpResponse(
                    '<div class="alert alert-warning">無効なタブタイプです。</div>', 
                    status=400
                )

            return render(request, template_name, context)

        except Exception as render_error:
            logger.error("タブレンダリングエラー: %s", render_error, exc_info=True)
            return HttpResponse(
                '<div class="alert alert-danger">タブコンテンツの読み込み中にエラーが発生しました。</div>',
                status=500
            )

    except Exception as e:
        logger.error("想定外のエラー: %s", e, exc_info=True)
        return HttpResponse(
            '<div class="alert alert-danger">予期せぬエラーが発生しました。</div>',
            status=500
        )

def calendar_view(request):
    """カレンダー全体ビュー"""
    today = timezone.now().date()
    month = today.month
    year = today.year
    
    user_diaries = StockDiary.objects.filter(user=request.user)
    
    return render(request, 'stockdiary/calendar.html', {
        'today': today,
        'month': month,
        'year': year,
        'diaries': user_diaries
    })


@login_required
@require_GET
def search_suggestion(request):
    """検索キーワードに基づいて提案を返す"""
    query = request.GET.get('query', '').strip()
    
    if len(query) < 2:
        return HttpResponse('')
    
    stock_matches = StockDiary.objects.filter(
        user=request.user
    ).filter(
        Q(stock_name__icontains=query) | 
        Q(stock_symbol__icontains=query)
    ).distinct().values('stock_name', 'stock_symbol')[:5]
    
    tag_matches = Tag.objects.filter(
        user=request.user, 
        name__icontains=query
    ).values('id', 'name')[:3]
    
    if not stock_matches and not tag_matches:
        return HttpResponse('')
    
    html = '<div class="search-suggestions mt-2">'
    
    if stock_matches:
        html += '<div class="search-suggestion-title"><small>銘柄:</small></div>'
        html += '<div class="search-suggestion-items">'
        for match in stock_matches:
            html += f'<div class="search-suggestion-item" hx-get="/stockdiary/diary-list/?query={match["stock_name"]}" hx-target="#diary-container" hx-push-url="true">'
            html += f'<i class="bi bi-building me-1"></i> {match["stock_name"]} ({match["stock_symbol"]})'
            html += '</div>'
        html += '</div>'
    
    if tag_matches:
        html += '<div class="search-suggestion-title"><small>タグ:</small></div>'
        html += '<div class="search-suggestion-items">'
        for match in tag_matches:
            html += f'<div class="search-suggestion-item" hx-get="/stockdiary/diary-list/?tag={match["id"]}" hx-target="#diary-container" hx-push-url="true">'
            html += f'<i class="bi bi-tag me-1"></i> {match["name"]}'
            html += '</div>'
        html += '</div>'
    
    html += '</div>'
    
    return HttpResponse(html)


def csrf_failure_view(request, reason=""):
    """CSRF失敗時のカスタムハンドラー"""
    if (hasattr(request, 'user') and 
        request.user.is_authenticated and 
        request.user.username in getattr(settings, 'TEST_ACCOUNT_SETTINGS', {}).get('USERNAMES', [])):
        
        messages.warning(
            request, 
            "テストアカウントの同時利用により一時的なエラーが発生しました。"
            "ページを更新するか、別のテストアカウント（test1, test2, demo1等）をお試しください。"
        )
        return redirect('stockdiary:home')
    
    return render(request, 'errors/csrf_failure.html', {
        'reason': reason,
        'test_accounts': settings.TEST_ACCOUNT_SETTINGS.get('USERNAMES', [])
    }, status=403)


@login_required
def api_stock_diaries(request, symbol):
    """特定の銘柄の日記一覧をJSON形式で返すAPI"""
    try:
        diaries = StockDiary.objects.filter(
            user=request.user,
            stock_symbol=symbol
        ).order_by('-created_at')
        
        diary_data = []
        for diary in diaries:
            tags = [tag.name for tag in diary.tags.all()]
            
            # ✅ 現物取引のみの統計を取得
            cash_stats = diary.calculate_cash_only_stats()
            
            diary_data.append({
                'id': diary.id,
                'first_purchase_date': diary.first_purchase_date.strftime('%Y年%m月%d日') if diary.first_purchase_date else None,
                'created_at': diary.created_at.strftime('%Y年%m月%d日'),
                'reason': diary.reason,
                'memo': diary.memo,
                'tags': tags,
                # 状態フラグ
                'is_memo': diary.is_memo,
                'is_holding': diary.is_holding,
                'is_sold_out': diary.is_sold_out,
                # 現物取引の統計
                'average_purchase_price': float(cash_stats['average_purchase_price']) if cash_stats['average_purchase_price'] else None,
                'current_quantity': float(cash_stats['current_quantity']) if cash_stats['current_quantity'] else None,
                'total_buy_amount': float(cash_stats['total_buy_amount']) if cash_stats['total_buy_amount'] else None,
                'total_sell_amount': float(cash_stats['total_sell_amount']) if cash_stats['total_sell_amount'] else None,
                'realized_profit': float(cash_stats['realized_profit']) if cash_stats['realized_profit'] else None,
                'transaction_count': diary.transaction_count,
            })
        
        return JsonResponse({
            'diaries': diary_data,
            'count': len(diary_data),
            'stock_symbol': symbol,
            'success': True
        })
        
    except Exception as e:
        # エラーハンドリング
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)
        
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

class TradeUploadView(LoginRequiredMixin, FormView):
    """取引履歴アップロードビュー"""
    template_name = 'stockdiary/trade_upload.html'
    form_class = TradeUploadForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        return context
    
    def form_valid(self, form):
        broker = form.cleaned_data['broker']
        csv_file = form.cleaned_data['csv_file']
        
        # セッションにブローカー情報を保存
        self.request.session['upload_broker'] = broker
        
        # 🔧 ファイル名を保存
        self.request.session['upload_filename'] = csv_file.name
        
        # CSVファイルを読み込んで処理
        try:
            # バイト列を読み込み
            csv_bytes = csv_file.read()
            
            # エンコーディングを検出
            detected = chardet.detect(csv_bytes)
            encoding = detected['encoding']
            
            # 検出されたエンコーディングで文字列に変換
            try:
                csv_content = csv_bytes.decode(encoding)
            except (UnicodeDecodeError, AttributeError):
                # 検出に失敗した場合は一般的なエンコーディングを試す
                for enc in ['shift-jis', 'cp932', 'utf-8-sig', 'utf-8', 'euc-jp']:
                    try:
                        csv_content = csv_bytes.decode(enc)
                        encoding = enc
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise ValueError('CSVファイルのエンコーディングを判別できませんでした')
            
            # セッションにCSVコンテンツとエンコーディング情報を保存
            self.request.session['csv_content'] = csv_content
            self.request.session['csv_encoding'] = encoding
            
            messages.info(
                self.request, 
                f'CSVファイルを読み込みました（エンコーディング: {encoding}）'
            )
            
            # プレビュー画面に遷移
            return redirect('stockdiary:process_trade_upload')
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(
                self.request, 
                f'CSVファイルの読み込みに失敗しました: {str(e)}'
            )
            return self.form_invalid(form)


@login_required
def process_trade_upload(request):
    """取引履歴処理ビュー"""
    if request.method != 'POST':
        # GET時はプレビュー表示
        broker = request.session.get('upload_broker')
        csv_content = request.session.get('csv_content')
        filename = request.session.get('upload_filename', '不明')
        
        if not broker or not csv_content:
            messages.error(request, 'アップロードデータが見つかりません')
            return redirect('stockdiary:trade_upload')
        
        # CSVをパースしてプレビュー
        try:
            # ✅ ブローカーに応じて処理を分岐
            if broker == 'rakuten':
                preview_data = parse_rakuten_csv_preview(csv_content)
            elif broker == 'sbi':
                preview_data = parse_sbi_csv_preview(csv_content)
            else:
                raise ValueError(f'未対応の証券会社です: {broker}')
            
            context = {
                'broker': broker,
                'filename': filename,
                'preview_data': preview_data,
                'total_count': len(preview_data),
            }
            
            return render(request, 'stockdiary/trade_upload_preview.html', context)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f'CSVの解析に失敗しました: {str(e)}')
            return redirect('stockdiary:trade_upload')
    
    else:
        # POST時は実際にデータ登録
        broker = request.session.get('upload_broker')
        csv_content = request.session.get('csv_content')
        filename = request.session.get('upload_filename', '不明')
        
        if not broker or not csv_content:
            messages.error(request, 'アップロードデータが見つかりません')
            return redirect('stockdiary:trade_upload')
        
        try:
            # ✅ ブローカーに応じて処理を分岐
            if broker == 'rakuten':
                result = process_rakuten_csv(request.user, csv_content, filename)
            elif broker == 'sbi':
                result = process_sbi_csv(request.user, csv_content, filename)
            else:
                raise ValueError(f'未対応の証券会社です: {broker}')
            
            # セッションデータをクリア
            del request.session['upload_broker']
            del request.session['csv_content']
            if 'upload_filename' in request.session:
                del request.session['upload_filename']
            
            messages.success(
                request,
                f'取引履歴の登録が完了しました。'
                f'成功: {result["success_count"]}件、'
                f'上書き: {result["overwrite_count"]}件、'
                f'スキップ: {result["skip_count"]}件、'
                f'エラー: {result["error_count"]}件'
            )
            
            # エラーがあれば詳細を表示
            if result['errors']:
                for error in result['errors'][:5]:  # 最初の5件まで
                    messages.warning(request, error)
            
            return redirect('stockdiary:home')
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f'取引履歴の登録中にエラーが発生しました: {str(e)}')
            return redirect('stockdiary:trade_upload')
        

def process_rakuten_csv(user, csv_content, filename):
    """
    楽天証券CSVを処理してStockDiaryとTransactionを作成
    
    処理ルール:
    - 1ファイル内の同一キー: 数量を合算
    - 既存データと同一キーがある場合: 常に上書き（重複取り込み防止）
    """
    csv_file = io.StringIO(csv_content)
    reader = csv.DictReader(csv_file)
    
    success_count = 0
    skip_count = 0
    error_count = 0
    overwrite_count = 0
    errors = []
    
    # まず全データを読み込んで日付順にソート
    all_rows = []
    for original_row_num, row in enumerate(reader, start=2):
        trade_date_str = row.get('受渡日', '').strip()
        if trade_date_str:
            all_rows.append({
                'data': row,
                'original_row': original_row_num
            })
    
    # 受渡日でソート（古い順）
    def parse_date(date_str):
        for date_format in ['%Y/%m/%d', '%Y-%m-%d', '%Y年%m月%d日']:
            try:
                return datetime.strptime(date_str, date_format)
            except ValueError:
                continue
        return datetime.max
    
    all_rows.sort(key=lambda r: parse_date(r['data'].get('受渡日', '')))
    
    for idx, row_data in enumerate(all_rows, start=1):
        row = row_data['data']
        original_row_num = row_data['original_row']
        
        try:
            # 受渡日を取得
            trade_date_str = row.get('受渡日', '').strip()
            if not trade_date_str:
                skip_count += 1
                continue
            
            # 日付をパース
            try:
                trade_date = None
                for date_format in ['%Y/%m/%d', '%Y-%m-%d', '%Y年%m月%d日']:
                    try:
                        trade_date = datetime.strptime(trade_date_str, date_format).date()
                        break
                    except ValueError:
                        continue
                
                if trade_date is None:
                    raise ValueError(f'日付形式が不正です: {trade_date_str}')
            except ValueError as e:
                errors.append(f'行{original_row_num}: {str(e)}')
                error_count += 1
                continue
            
            # 銘柄情報
            stock_code = row.get('銘柄コード', '').strip()
            stock_name = row.get('銘柄名', '').strip()
            
            if not stock_code or not stock_name:
                errors.append(f'行{original_row_num}: 銘柄コードまたは銘柄名が空です')
                skip_count += 1
                continue
            
            # 売買区分を取得
            trade_type_raw = row.get('売買区分', '').strip()
            trade_category = row.get('取引区分', '').strip()
            
            # ✅ 信用取引かどうかを判定
            is_margin_trade = '信用' in trade_category
            
            # 売買区分を変換
            if '買' in trade_type_raw or '積立' in trade_type_raw:
                transaction_type = 'buy'
            elif '売' in trade_type_raw:
                transaction_type = 'sell'
            else:
                errors.append(f'行{original_row_num}: 不明な売買区分: "{trade_type_raw}" ({stock_name})')
                error_count += 1
                continue
            
            # 数量と単価を取得
            quantity_str = row.get('数量［株］', '')
            price_str = row.get('単価［円］', '')
            
            # カンマを除去
            quantity_str = quantity_str.replace(',', '').strip()
            price_str = price_str.replace(',', '').strip()
            
            if not quantity_str or not price_str:
                errors.append(f'行{original_row_num}: 数量または単価が空です ({stock_name})')
                skip_count += 1
                continue
            
            # 数値に変換
            try:
                quantity = Decimal(quantity_str)
                price = Decimal(price_str)
            except (ValueError, InvalidOperation) as e:
                errors.append(f'行{original_row_num}: 数値の解析エラー: {stock_name} - 数量:{quantity_str}, 単価:{price_str}')
                error_count += 1
                continue
            
            if quantity <= 0 or price <= 0:
                errors.append(f'行{original_row_num}: 数量または単価が0以下です ({stock_name})')
                skip_count += 1
                continue
            
            # StockDiaryを取得または作成
            with db_transaction.atomic():
                # 既存のStockDiaryを取得（複数ある場合は最初のものを使用）
                diary = StockDiary.objects.filter(
                    user=user,
                    stock_symbol=stock_code
                ).order_by('created_at').first()
                
                if not diary:
                    # 存在しない場合は新規作成
                    diary = StockDiary.objects.create(
                        user=user,
                        stock_symbol=stock_code,
                        stock_name=stock_name,
                        reason=f'楽天証券からインポート（{trade_date}）',
                    )
                
                # メモ内容を作成
                memo_content = f'楽天証券からインポート({trade_category} {trade_type_raw}) [ファイル: {filename} 行: {original_row_num}]'
                
                # 同一キー（日付・銘柄・価格・取引種別）の取引を検索
                price_tolerance = Decimal('0.01')
                
                existing_transaction = Transaction.objects.filter(
                    diary=diary,
                    transaction_type=transaction_type,
                    transaction_date=trade_date,
                    price__gte=price - price_tolerance,
                    price__lte=price + price_tolerance
                ).first()
                
                if existing_transaction:
                    # ✅ 既存の同一キーがある場合は常に上書き（重複取り込み防止）
                    existing_transaction.quantity = quantity
                    existing_transaction.price = price
                    existing_transaction.memo = memo_content
                    existing_transaction.is_margin = is_margin_trade  # ✅ 信用取引フラグを更新
                    existing_transaction.save()
                    overwrite_count += 1
                    
                else:
                    # ✅ 新規取引として作成
                    transaction_obj = Transaction(
                        diary=diary,
                        transaction_type=transaction_type,
                        transaction_date=trade_date,
                        price=price,
                        quantity=quantity,
                        memo=memo_content,
                        is_margin=is_margin_trade  # ✅ 信用取引フラグを設定
                    )
                    
                    transaction_obj.save()
                    success_count += 1
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            stock_name_for_error = locals().get('stock_name', '不明')
            errors.append(f'行{original_row_num} ({stock_name_for_error}): {str(e)}')
            error_count += 1
            continue
    
    # 最後に各Diaryの集計を更新
    processed_diaries = StockDiary.objects.filter(
        user=user,
        transactions__memo__contains='楽天証券からインポート'
    ).distinct()
    
    for diary in processed_diaries:
        diary.update_aggregates()
    
    return {
        'success_count': success_count,
        'skip_count': skip_count,
        'error_count': error_count,
        'overwrite_count': overwrite_count,
        'errors': errors
    }

# ✅ プレビュー表示：1ファイル内の同一キー取引をグループ化
def parse_rakuten_csv_preview(csv_content):
    """楽天CSVをパースしてプレビュー用データを返す（1ファイル内の同一キーは合算表示）"""
    csv_file = io.StringIO(csv_content)
    reader = csv.DictReader(csv_file)
    
    # 同一キーごとにデータを集約
    grouped_data = defaultdict(lambda: {
        'quantity': 0,
        'amount': 0,
        'count': 0,
        'first_row': None
    })
    
    for row_num, row in enumerate(reader, 1):
        try:
            trade_date = row.get('受渡日', '').strip()
            stock_code = row.get('銘柄コード', '').strip()
            stock_name = row.get('銘柄名', '').strip()
            
            trade_category = row.get('取引区分', '').strip()
            trade_type = row.get('区分', '').strip()
            
            quantity_str = row.get('数量［株］', '') or row.get('数量[株]', '') or row.get('数量', '')
            price_str = row.get('単価［円］', '') or row.get('単価[円]', '') or row.get('単価', '')
            
            quantity_str = quantity_str.replace(',', '').strip()
            price_str = price_str.replace(',', '').strip()
            
            if not quantity_str or not price_str:
                continue
                
            try:
                quantity = float(quantity_str)
                price = float(price_str)
            except ValueError:
                continue
            
            # ✅ キーを生成（日付・銘柄コード・価格・取引種別）
            key = (trade_date, stock_code, f'{price:.2f}', trade_type)
            
            # ✅ 同一キーのデータを集約
            if grouped_data[key]['first_row'] is None:
                grouped_data[key]['first_row'] = {
                    'date': trade_date,
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'trade_category': trade_category,
                    'trade_type': trade_type,
                    'price': price
                }
            
            grouped_data[key]['quantity'] += quantity
            grouped_data[key]['amount'] += quantity * price
            grouped_data[key]['count'] += 1
            
        except Exception as e:
            logger.warning("Row %s parsing error: %s", row_num, e, exc_info=True)
            continue
    
    # ✅ 集約されたデータをプレビュー用に整形
    preview_data = []
    for key, data in grouped_data.items():
        row_data = data['first_row']
        total_quantity = data['quantity']
        total_amount = data['amount']
        merge_count = data['count']
        
        display_trade_type = f"{row_data['trade_category']} {row_data['trade_type']}" if row_data['trade_category'] else row_data['trade_type']
        
        # ✅ 合算される場合は注釈を追加
        quantity_display = f'{total_quantity:,.0f}'
        if merge_count > 1:
            quantity_display += f' ※{merge_count}件を合算'
        
        preview_data.append({
            'date': row_data['date'],
            'stock_code': row_data['stock_code'],
            'stock_name': row_data['stock_name'],
            'trade_type': display_trade_type,
            'trade_category': row_data['trade_category'],
            'buy_or_sell': row_data['trade_type'],
            'quantity': quantity_display,
            'price': f'{row_data["price"]:,.2f}',
            'amount': f'{total_amount:,.0f}',
            'is_merged': merge_count > 1  # ✅ 合算フラグ
        })
    
    # 日付順にソート
    preview_data.sort(key=lambda x: x['date'])
    
    return preview_data

class NotificationListView(LoginRequiredMixin, TemplateView):
    """通知管理ページ - 予定の表示"""
    template_name = 'stockdiary/notification_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        notifications = DiaryNotification.objects.filter(
            diary__user=self.request.user,
            is_active=True
        ).select_related('diary').order_by('remind_at')
        
        # Get filter parameter from GET request
        filter_type = self.request.GET.get('filter', 'all')
        today = timezone.now()
        today_start = timezone.make_aware(timezone.datetime.combine(today.date(), timezone.datetime.min.time()))
        today_end = timezone.make_aware(timezone.datetime.combine(today.date(), timezone.datetime.max.time()))
        
        # Apply date filters
        if filter_type == 'today':
            notifications = notifications.filter(remind_at__gte=today_start, remind_at__lte=today_end)
        elif filter_type == 'upcoming':
            notifications = notifications.filter(remind_at__gte=today_start)
        
        # Paginate results
        paginator = Paginator(notifications, NOTIFICATION_LIST_PAGE_SIZE)
        page_number = self.request.GET.get('page', 1)
        
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)
        
        # Add preview information for each notification
        for notification in page_obj:
            notification.title = notification.diary.stock_name
            notification.sent_at = notification.remind_at
            notification.is_read = False  # 予定は未読状態
            notification.message_preview = notification.message[:100] if notification.message else '通知予定'
            if notification.message and len(notification.message) > 100:
                notification.message_preview += '...'
            notification.diary_url = reverse('stockdiary:detail', kwargs={'pk': notification.diary.pk})
        
        context.update({
            'notifications': page_obj,
            'filter_type': filter_type,
            'unread_count': DiaryNotification.objects.filter(
                diary__user=self.request.user,
                is_active=True,
                remind_at__gte=today_start
            ).count(),
        })
        
        
        context['page_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]    
        return context

# stockdiary/views.py に以下の関数を追加

def parse_sbi_csv_preview(csv_content):
    """SBI証券CSVをパースしてプレビュー用データを返す"""
    lines = csv_content.strip().split('\n')
    
    # 9行目（インデックス8）からがデータ
    if len(lines) < 7:
        raise ValueError('CSVファイルの形式が不正です（データ行が見つかりません）')
    
    # ヘッダー行を取得（9行目）
    header_line = lines[7]
    
    # データ行を取得（10行目以降）
    data_lines = lines[8:]
    
    csv_file = io.StringIO('\n'.join([header_line] + data_lines))
    reader = csv.DictReader(csv_file)
    
    # 同一キーごとにデータを集約
    grouped_data = defaultdict(lambda: {
        'quantity': 0,
        'amount': 0,
        'count': 0,
        'first_row': None
    })
    
    for row_num, row in enumerate(reader, 1):
        try:
            # 受渡日を取得（約定日ではなく受渡日を使用）
            trade_date = row.get('受渡日', '').strip()
            if not trade_date:
                continue
            
            stock_code = row.get('銘柄コード', '').strip()
            stock_name = row.get('銘柄', '').strip()
            
            # 銘柄コードがない場合はスキップ（投資信託など）
            if not stock_code:
                continue
            
            # 取引種別を取得
            trade_type_raw = row.get('取引', '').strip()
            
            # 売買区分を判定
            if '買' in trade_type_raw:
                trade_type = '買'
            elif '売' in trade_type_raw:
                trade_type = '売'
            else:
                continue
            
            # 数量と単価を取得
            quantity_str = row.get('約定数量', '').strip()
            price_str = row.get('約定単価', '').strip()
            
            # カンマを除去
            quantity_str = quantity_str.replace(',', '').strip()
            price_str = price_str.replace(',', '').strip()
            
            if not quantity_str or not price_str or quantity_str == '--' or price_str == '--':
                continue
            
            try:
                quantity = float(quantity_str)
                price = float(price_str)
            except ValueError:
                continue
            
            # キーを生成（日付・銘柄コード・価格・取引種別）
            key = (trade_date, stock_code, f'{price:.2f}', trade_type)
            
            # 同一キーのデータを集約
            if grouped_data[key]['first_row'] is None:
                grouped_data[key]['first_row'] = {
                    'date': trade_date,
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'trade_type_raw': trade_type_raw,
                    'trade_type': trade_type,
                    'price': price,
                    'market': row.get('市場', '').strip()
                }
            
            grouped_data[key]['quantity'] += quantity
            grouped_data[key]['amount'] += quantity * price
            grouped_data[key]['count'] += 1
            
        except Exception as e:
            logger.warning("Row %s parsing error: %s", row_num, e, exc_info=True)
            continue
    
    # 集約されたデータをプレビュー用に整形
    preview_data = []
    for key, data in grouped_data.items():
        row_data = data['first_row']
        total_quantity = data['quantity']
        total_amount = data['amount']
        merge_count = data['count']
        
        quantity_display = f'{total_quantity:,.0f}'
        if merge_count > 1:
            quantity_display += f' ※{merge_count}件を合算'
        
        preview_data.append({
            'date': row_data['date'],
            'stock_code': row_data['stock_code'],
            'stock_name': row_data['stock_name'],
            'trade_type': row_data['trade_type_raw'],
            'buy_or_sell': row_data['trade_type'],
            'quantity': quantity_display,
            'price': f'{row_data["price"]:,.2f}',
            'amount': f'{total_amount:,.0f}',
            'is_merged': merge_count > 1
        })
    
    # 日付順にソート
    preview_data.sort(key=lambda x: x['date'])
    
    return preview_data


def process_sbi_csv(user, csv_content, filename):
    """
    SBI証券CSVを処理してStockDiaryとTransactionを作成
    """
    lines = csv_content.strip().split('\n')
    
    if len(lines) < 9:
        raise ValueError('CSVファイルの形式が不正です')
    
    # ヘッダー行とデータ行を取得
    header_line = lines[7]
    data_lines = lines[8:]
    
    csv_file = io.StringIO('\n'.join([header_line] + data_lines))
    reader = csv.DictReader(csv_file)
    
    success_count = 0
    skip_count = 0
    error_count = 0
    overwrite_count = 0
    errors = []
    
    # 全データを読み込んで日付順にソート
    all_rows = []
    for original_row_num, row in enumerate(reader, start=10):  # 実際のデータは10行目から
        trade_date_str = row.get('受渡日', '').strip()
        if trade_date_str:
            all_rows.append({
                'data': row,
                'original_row': original_row_num
            })
    
    # 受渡日でソート（古い順）
    def parse_date(date_str):
        for date_format in ['%Y/%m/%d', '%Y-%m-%d', '%Y年%m月%d日']:
            try:
                return datetime.strptime(date_str, date_format)
            except ValueError:
                continue
        return datetime.max
    
    all_rows.sort(key=lambda r: parse_date(r['data'].get('受渡日', '')))
    
    for idx, row_data in enumerate(all_rows, start=1):
        row = row_data['data']
        original_row_num = row_data['original_row']
        
        try:
            # 受渡日を取得
            trade_date_str = row.get('受渡日', '').strip()
            if not trade_date_str:
                skip_count += 1
                continue
            
            # 日付をパース
            try:
                trade_date = None
                for date_format in ['%Y/%m/%d', '%Y-%m-%d', '%Y年%m月%d日']:
                    try:
                        trade_date = datetime.strptime(trade_date_str, date_format).date()
                        break
                    except ValueError:
                        continue
                
                if trade_date is None:
                    raise ValueError(f'日付形式が不正です: {trade_date_str}')
            except ValueError as e:
                errors.append(f'行{original_row_num}: {str(e)}')
                error_count += 1
                continue
            
            # 銘柄情報
            stock_code = row.get('銘柄コード', '').strip()
            stock_name = row.get('銘柄', '').strip()
            
            # 銘柄コードがない場合はスキップ（投資信託など）
            if not stock_code or not stock_name:
                skip_count += 1
                continue
            
            # 取引種別を取得
            trade_type_raw = row.get('取引', '').strip()
            market = row.get('市場', '').strip()
            
            # ✅ 信用取引かどうかを判定
            is_margin_trade = '信用' in trade_type_raw
            
            # 売買区分を変換
            if '買' in trade_type_raw:
                transaction_type = 'buy'
            elif '売' in trade_type_raw:
                transaction_type = 'sell'
            else:
                skip_count += 1
                continue
            
            # 数量と単価を取得
            quantity_str = row.get('約定数量', '').strip()
            price_str = row.get('約定単価', '').strip()
            
            # カンマを除去
            quantity_str = quantity_str.replace(',', '').strip()
            price_str = price_str.replace(',', '').strip()
            
            if not quantity_str or not price_str or quantity_str == '--' or price_str == '--':
                skip_count += 1
                continue
            
            # 数値に変換
            try:
                quantity = Decimal(quantity_str)
                price = Decimal(price_str)
            except (ValueError, InvalidOperation) as e:
                errors.append(f'行{original_row_num}: 数値の解析エラー: {stock_name} - 数量:{quantity_str}, 単価:{price_str}')
                error_count += 1
                continue
            
            if quantity <= 0 or price <= 0:
                errors.append(f'行{original_row_num}: 数量または単価が0以下です ({stock_name})')
                skip_count += 1
                continue
            
            # StockDiaryを取得または作成
            with db_transaction.atomic():
                diary = StockDiary.objects.filter(
                    user=user,
                    stock_symbol=stock_code
                ).order_by('created_at').first()
                
                if not diary:
                    diary = StockDiary.objects.create(
                        user=user,
                        stock_symbol=stock_code,
                        stock_name=stock_name,
                        reason=f'SBI証券からインポート（{trade_date}）',
                    )
                
                # メモ内容を作成
                memo_content = f'SBI証券からインポート({trade_type_raw}'
                if market:
                    memo_content += f' {market}'
                memo_content += f') [ファイル: {filename} 行: {original_row_num}]'
                
                # 同一キーの取引を検索
                price_tolerance = Decimal('0.01')
                
                existing_transaction = Transaction.objects.filter(
                    diary=diary,
                    transaction_type=transaction_type,
                    transaction_date=trade_date,
                    price__gte=price - price_tolerance,
                    price__lte=price + price_tolerance
                ).first()
                
                if existing_transaction:
                    # 既存の同一キーがある場合は上書き
                    existing_transaction.quantity = quantity
                    existing_transaction.price = price
                    existing_transaction.memo = memo_content
                    existing_transaction.is_margin = is_margin_trade  # ✅ 信用取引フラグを更新
                    existing_transaction.save()
                    overwrite_count += 1
                else:
                    # 新規取引として作成
                    transaction_obj = Transaction(
                        diary=diary,
                        transaction_type=transaction_type,
                        transaction_date=trade_date,
                        price=price,
                        quantity=quantity,
                        memo=memo_content,
                        is_margin=is_margin_trade  # ✅ 信用取引フラグを設定
                    )
                    transaction_obj.save()
                    success_count += 1
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            stock_name_for_error = locals().get('stock_name', '不明')
            errors.append(f'行{original_row_num} ({stock_name_for_error}): {str(e)}')
            error_count += 1
            continue
    
    # 各Diaryの集計を更新
    processed_diaries = StockDiary.objects.filter(
        user=user,
        transactions__memo__contains='SBI証券からインポート'
    ).distinct()
    
    for diary in processed_diaries:
        diary.update_aggregates()
    
    return {
        'success_count': success_count,
        'skip_count': skip_count,
        'error_count': error_count,
        'overwrite_count': overwrite_count,
        'errors': errors
    }
    
class TradingDashboardView(LoginRequiredMixin, TemplateView):
    """取引分析ダッシュボード（現物取引のみ・ROI改善版）"""
    template_name = 'stockdiary/trading_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # ========== 期間フィルター ==========
        period = self.request.GET.get('period', '6m')
        today = timezone.now().date()

        period_mapping = {
            '1m': 30,
            '3m': 90,
            '6m': 180,
            '1y': 365,
            'all': None
        }

        days = period_mapping.get(period)

        # ✅ 現物取引のみを取得
        if days:
            start_date = today - timedelta(days=days)
            period_transactions = Transaction.objects.filter(
                diary__user=user,
                transaction_date__gte=start_date,
                is_margin=False  # ✅ 信用取引を除外
            )
        else:
            period_transactions = Transaction.objects.filter(
                diary__user=user,
                is_margin=False  # ✅ 信用取引を除外
            )

        # 期間内に取引があった日記を取得
        diary_ids_in_period = period_transactions.values_list('diary_id', flat=True).distinct()
        diaries_in_period = StockDiary.objects.filter(
            id__in=diary_ids_in_period
        ).select_related('user')

        # 全日記
        all_diaries = StockDiary.objects.filter(user=user)

        # ========== CompanyMasterから業種情報を取得 ==========
        from company_master.models import CompanyMaster

        company_codes = list(
            diaries_in_period.values_list('stock_symbol', flat=True).distinct()
        )

        company_industries = {}
        if company_codes:
            companies = CompanyMaster.objects.filter(
                code__in=company_codes
            ).values('code', 'industry_name_33')

            for company in companies:
                code = company['code'].split('.')[0]
                industry = company['industry_name_33']
                if industry:
                    industry = industry.strip()
                industry = industry if industry else '未分類'
                company_industries[code] = industry

        # ========== メトリクス集計（現物のみ） ==========
        total_transactions = 0
        total_cash_invested = Decimal('0')  # 総投資額（現物のみ）
        total_cash_sell_amount = Decimal('0')  # 総売却額（現物のみ）
        total_current_value = Decimal('0')  # 現在の評価額
        
        for diary in diaries_in_period:
            # ✅ 現物取引のみの統計を取得
            cash_stats = diary.calculate_cash_only_stats()
            
            # 現物取引の数をカウント
            cash_transaction_count = period_transactions.filter(diary=diary).count()
            total_transactions += cash_transaction_count
            
            # 総投資額（購入総額）
            total_cash_invested += cash_stats['total_buy_amount']
            
            # 総売却額
            total_cash_sell_amount += cash_stats['total_sell_amount']
            
            # 現在の評価額（保有数 × 平均取得単価）
            if cash_stats['current_quantity'] > 0 and cash_stats['average_purchase_price']:
                current_value = cash_stats['current_quantity'] * cash_stats['average_purchase_price']
                total_current_value += current_value

        # ✅ ROI = (売却総額 + 評価額 - 総投資額) / 総投資額 × 100
        if total_cash_invested > 0:
            total_roi = ((total_cash_sell_amount + total_current_value - total_cash_invested) 
                        / total_cash_invested * 100)
        else:
            total_roi = Decimal('0')

        # 実現損益
        total_realized_profit = total_cash_sell_amount - (total_cash_invested - total_current_value)

        # 保有中銘柄数（現物のみ）
        holding_count = 0
        for diary in all_diaries:
            cash_stats = diary.calculate_cash_only_stats()
            if cash_stats['current_quantity'] > 0:
                holding_count += 1

        # 平均利益率（売却ベース）
        profitable_rates = []
        for diary in diaries_in_period:
            cash_stats = diary.calculate_cash_only_stats()
            if cash_stats['total_sell_amount'] and cash_stats['total_sell_amount'] > 0:
                buy_cost = cash_stats['total_buy_amount'] - cash_stats['total_cost']
                if buy_cost > 0:
                    profit_rate = ((cash_stats['total_sell_amount'] - buy_cost) 
                                  / buy_cost) * 100
                    profitable_rates.append(profit_rate)

        avg_profit_rate = (sum(profitable_rates) / len(profitable_rates) 
                          if profitable_rates else 0)

        # ========== 取引回数ランキング（銘柄別・現物のみ） ==========
        stock_ranking = {}
        for diary in diaries_in_period:
            stock_code = diary.stock_symbol
            if stock_code not in stock_ranking:
                stock_ranking[stock_code] = {
                    'stock_code': stock_code,
                    'stock_name': diary.stock_name,
                    'transaction_count': 0,
                    'diaries': []
                }
            
            # ✅ 現物取引のみカウント
            cash_transaction_count = period_transactions.filter(diary=diary).count()
            stock_ranking[stock_code]['transaction_count'] += cash_transaction_count
            
            # ✅ 日記ごとの詳細情報（現物のみ）
            cash_stats = diary.calculate_cash_only_stats()
            
            last_transaction = period_transactions.filter(diary=diary).order_by('-transaction_date').first()
            last_trade = last_transaction.transaction_date if last_transaction else None
            
            if last_trade:
                delta = today - last_trade
                if delta.days == 0:
                    last_trade_display = '今日'
                elif delta.days == 1:
                    last_trade_display = '1日前'
                elif delta.days < 7:
                    last_trade_display = f'{delta.days}日前'
                elif delta.days < 30:
                    weeks = delta.days // 7
                    last_trade_display = f'{weeks}週間前'
                else:
                    months = delta.days // 30
                    last_trade_display = f'{months}ヶ月前'
            else:
                last_trade_display = '不明'
            
            # ✅ ROI計算：(売却総額 + 評価額 - 総投資額) / 総投資額 × 100
            total_invested = cash_stats['total_buy_amount']
            total_sell = cash_stats['total_sell_amount']
            current_value = Decimal('0')
            if cash_stats['current_quantity'] > 0 and cash_stats['average_purchase_price']:
                current_value = cash_stats['current_quantity'] * cash_stats['average_purchase_price']
            
            roi = Decimal('0')
            if total_invested > 0:
                roi = ((total_sell + current_value - total_invested) / total_invested * 100)
            
            stock_ranking[stock_code]['diaries'].append({
                'id': diary.id,
                'transaction_count': cash_transaction_count,
                'realized_profit': float(cash_stats['realized_profit'] or 0),
                'current_quantity': float(cash_stats['current_quantity'] or 0),
                'total_invested': float(total_invested),
                'total_sell_amount': float(total_sell),
                'current_value': float(current_value),
                'roi': float(roi),
                'last_trade_display': last_trade_display,
                'created_at': diary.created_at.strftime('%Y年%m月%d日'),
            })

        # ソートして上位10件
        transaction_ranking = sorted(
            stock_ranking.values(),
            key=lambda x: x['transaction_count'],
            reverse=True
        )[:10]

        # ========== 業種別分析（現物のみ） ==========
        sector_stats = {}
        sector_companies = {}

        for diary in diaries_in_period:
            stock_code = diary.stock_symbol.split('.')[0] if diary.stock_symbol else None
            sector = company_industries.get(stock_code, '未分類')
            sector = sector.strip() if sector else '未分類'

            if sector not in sector_stats:
                sector_stats[sector] = {
                    'sector': sector,
                    'transaction_count': 0,
                    'total_invested': Decimal('0'),
                    'total_sell_amount': Decimal('0'),
                    'total_current_value': Decimal('0'),
                    'diary_ids': set(),
                }
                sector_companies[sector] = []

            # ✅ 現物取引のみカウント
            cash_transaction_count = period_transactions.filter(diary=diary).count()
            sector_stats[sector]['transaction_count'] += cash_transaction_count
            sector_stats[sector]['diary_ids'].add(diary.id)
            
            # ✅ 現物取引の統計を集計
            cash_stats = diary.calculate_cash_only_stats()
            
            total_invested = cash_stats['total_buy_amount']
            total_sell = cash_stats['total_sell_amount']
            current_value = Decimal('0')
            if cash_stats['current_quantity'] > 0 and cash_stats['average_purchase_price']:
                current_value = cash_stats['current_quantity'] * cash_stats['average_purchase_price']
            
            sector_stats[sector]['total_invested'] += total_invested
            sector_stats[sector]['total_sell_amount'] += total_sell
            sector_stats[sector]['total_current_value'] += current_value

            # ✅ ROI計算
            roi = Decimal('0')
            if total_invested > 0:
                roi = ((total_sell + current_value - total_invested) / total_invested * 100)
            
            # ✅ 日記別に企業情報を保存
            sector_companies[sector].append({
                'id': diary.id,
                'name': diary.stock_name,
                'code': diary.stock_symbol,
                'transaction_count': cash_transaction_count,
                'realized_profit': float(cash_stats['realized_profit'] or 0),
                'total_invested': float(total_invested),
                'total_sell_amount': float(total_sell),
                'current_value': float(current_value),
                'current_quantity': float(cash_stats['current_quantity'] or 0),
                'roi': float(roi),
                'created_at': diary.created_at.strftime('%Y年%m月%d日'),
            })

        # ROIを計算
        sector_analysis = []
        for sector, data in sector_stats.items():
            diary_count = len(data['diary_ids'])
            total_invested = data['total_invested']
            total_sell = data['total_sell_amount']
            total_current_value = data['total_current_value']

            # ✅ ROI = (売却総額 + 評価額 - 総投資額) / 総投資額 × 100
            roi = Decimal('0')
            if total_invested > 0:
                roi = ((total_sell + total_current_value - total_invested) / total_invested * 100)

            # 実現損益
            realized_profit = total_sell - (total_invested - total_current_value)

            sector_analysis.append({
                'sector': sector.strip(),
                'transaction_count': data['transaction_count'],
                'realized_profit': float(realized_profit),
                'total_invested': float(total_invested),
                'total_sell_amount': float(total_sell),
                'current_value': float(total_current_value),
                'roi': float(round(roi, 1)),
                'diary_count': diary_count,
            })

        # ソート & 幅パーセント計算
        sector_analysis.sort(key=lambda x: x['transaction_count'], reverse=True)
        sector_analysis = sector_analysis[:10]

        max_transaction_count = sector_analysis[0]['transaction_count'] if sector_analysis else 1
        total_all_transactions = sum(s['transaction_count'] for s in sector_analysis)
        
        for sector in sector_analysis:
            sector['width_percent'] = (sector['transaction_count'] / max_transaction_count) * 100
            sector['transaction_ratio'] = round((sector['transaction_count'] / total_all_transactions) * 100, 1) if total_all_transactions > 0 else 0

        # ========== 業種別企業明細データ（日記別） ==========
        sector_details = {}
        for sector, companies in sector_companies.items():
            company_list = []
            for c in companies:
                company_list.append({
                    'id': c['id'],
                    'name': c['name'],
                    'code': c['code'],
                    'transaction_count': c['transaction_count'],
                    'realized_profit': round(c['realized_profit'], 0),
                    'total_invested': round(c['total_invested'], 0),
                    'total_sell_amount': round(c['total_sell_amount'], 0),
                    'current_value': round(c['current_value'], 0),
                    'roi': c['roi'],
                    'current_quantity': c['current_quantity'],
                    'created_at': c['created_at'],
                })

            company_list.sort(key=lambda x: x['roi'], reverse=True)
            sector_details[sector.strip()] = company_list

        # ========== 利益/損失業種（ROIベース） ==========
        seen_sectors = set()
        unique_sector_analysis = []
        for s in sector_analysis:
            sector_key = s['sector'].strip()
            if sector_key not in seen_sectors:
                seen_sectors.add(sector_key)
                unique_sector_analysis.append(s)

        profitable_sectors = [s for s in unique_sector_analysis if s['roi'] > 0]
        profitable_sectors.sort(key=lambda x: x['roi'], reverse=True)
        profitable_sectors = profitable_sectors[:3]

        loss_sectors = [s for s in unique_sector_analysis if s['roi'] < 0]
        loss_sectors.sort(key=lambda x: x['roi'])
        loss_sectors = loss_sectors[:3]

        # ========== ROIランキングデータ（業種別） ==========
        sector_roi_list = []
        for sector in unique_sector_analysis:
            sector_roi_list.append({
                'label': sector['sector'],
                'roi': sector['roi'],
                'transaction_count': sector['transaction_count'],
                'diary_count': sector['diary_count']
            })
        
        sector_roi_list.sort(key=lambda x: x['roi'], reverse=True)
        
        # ========== ROIランキングデータ（銘柄別） ==========
        stock_roi_list = []
        for stock_code, stock_data in stock_ranking.items():
            # 日記全体のROIを計算
            total_invested = sum(d['total_invested'] for d in stock_data['diaries'])
            total_sell = sum(d['total_sell_amount'] for d in stock_data['diaries'])
            total_current_value = sum(d['current_value'] for d in stock_data['diaries'])
            
            roi = 0
            if total_invested > 0:
                roi = ((total_sell + total_current_value - total_invested) / total_invested * 100)
            
            stock_roi_list.append({
                'label': f"{stock_data['stock_name']} ({stock_code})",
                'roi': round(roi, 1),
                'transaction_count': stock_data['transaction_count'],
                'diary_count': len(stock_data['diaries'])
            })
        
        stock_roi_list.sort(key=lambda x: x['roi'], reverse=True)

        # ========== コンテキスト ==========
        context.update({
            'total_transactions': total_transactions,
            'holding_count': holding_count,
            'total_realized_profit': float(total_realized_profit),
            'total_invested': float(total_cash_invested),
            'total_roi': round(float(total_roi), 1),
            'avg_profit_rate': round(avg_profit_rate, 1),
            'transaction_ranking': transaction_ranking,
            'sector_analysis': sector_analysis,
            'profitable_sectors': profitable_sectors,
            'loss_sectors': loss_sectors,
            'current_period': period,
            'has_data': total_transactions > 0,
            'sector_details': json.dumps(sector_details, ensure_ascii=False),
            'stock_ranking': json.dumps({s['stock_code']: s for s in transaction_ranking}, ensure_ascii=False),
            'sector_roi_data': json.dumps(sector_roi_list, ensure_ascii=False),
            'stock_roi_data': json.dumps(stock_roi_list, ensure_ascii=False),
        })

        context['page_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]

        return context


class DiaryGraphView(LoginRequiredMixin, TemplateView):
    """日記関連グラフ表示ページ"""
    template_name = 'stockdiary/diary_graph.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['diary_count'] = StockDiary.objects.filter(user=user).count()
        # ユーザーの日記に実際に使われているタグのみ取得
        context['tags'] = (
            Tag.objects.filter(user=user, stockdiary__user=user)
            .distinct()
            .order_by('name')
        )
        return context


class ExploreView(LoginRequiredMixin, ListView):
    """
    全文検索ページ（Obsidian風）
    日記の投資理由・メモ・継続記録・@ハッシュタグを横断検索する。
    """
    model = StockDiary
    template_name = 'stockdiary/explore.html'
    context_object_name = 'diaries'
    paginate_by = EXPLORE_PAGE_SIZE

    def get_queryset(self):
        from .utils import search_diaries_by_hashtag

        qs = StockDiary.objects.filter(user=self.request.user).order_by('-updated_at')
        qs = qs.prefetch_related('tags', 'notes')

        q = self.request.GET.get('q', '').strip()
        if q:
            search_type = self.request.GET.get('search_type', 'all')
            if search_type == 'reason':
                qs = qs.filter(Q(reason__icontains=q) | Q(memo__icontains=q))
            elif search_type == 'note':
                qs = qs.filter(notes__content__icontains=q).distinct()
            elif search_type == 'hashtag':
                qs = search_diaries_by_hashtag(qs, q)
            else:  # all
                qs = qs.filter(
                    Q(stock_name__icontains=q) |
                    Q(stock_symbol__icontains=q) |
                    Q(reason__icontains=q) |
                    Q(memo__icontains=q) |
                    Q(notes__content__icontains=q)
                ).distinct()

        # ステータスフィルター
        status = self.request.GET.get('status', '')
        if status == 'holding':
            qs = qs.filter(current_quantity__gt=0)
        elif status == 'sold':
            qs = qs.filter(transaction_count__gt=0, current_quantity=0)
        elif status == 'memo':
            qs = qs.filter(transaction_count=0)

        # 業種フィルター
        sector = self.request.GET.get('sector', '').strip()
        if sector:
            qs = qs.filter(sector=sector)

        # タグフィルター
        tag_id = self.request.GET.get('tag', '').strip()
        if tag_id:
            try:
                qs = qs.filter(tags__id=int(tag_id))
            except (ValueError, TypeError):
                pass

        return qs

    def get_context_data(self, **kwargs):
        from .utils import get_all_hashtags_from_queryset

        context = super().get_context_data(**kwargs)
        user = self.request.user

        q           = self.request.GET.get('q', '').strip()
        search_type = self.request.GET.get('search_type', 'all')
        status      = self.request.GET.get('status', '')
        sector      = self.request.GET.get('sector', '').strip()
        tag_id      = self.request.GET.get('tag', '').strip()

        context['q']           = q
        context['search_type'] = search_type
        context['status']      = status
        context['sector']      = sector
        context['tag_id']      = tag_id

        # 全ユーザー日記からハッシュタグ一覧を取得（上位20件）
        all_diaries = StockDiary.objects.filter(user=user).only('reason')
        context['top_hashtags'] = get_all_hashtags_from_queryset(all_diaries)[:20]

        # タグ一覧
        context['tags'] = Tag.objects.filter(user=user).order_by('name')

        # 業種一覧
        context['sectors'] = (
            StockDiary.objects.filter(user=user)
            .exclude(sector='')
            .values_list('sector', flat=True)
            .distinct()
            .order_by('sector')
        )

        # 総日記数
        context['total_diary_count'] = StockDiary.objects.filter(user=user).count()

        return context

# ============================================================
# EDINET連携: 開示書類パネル（HTMXパーシャル）
# ============================================================

def _get_securities_code(stock_symbol):
    """銘柄コード（4桁）からEDINET用5桁証券コードに変換"""
    if stock_symbol and stock_symbol.isdigit() and len(stock_symbol) == 4:
        return stock_symbol + '0'
    return None


@login_required
@require_GET
def edinet_panel(request, diary_id):
    """
    EDINET関連開示書類パネル（HTMXで遅延ロード）
    日本株4桁コードにマッチする直近の開示書類と分析結果を返す
    """
    diary = get_object_or_404(StockDiary, pk=diary_id, user=request.user)
    documents = []
    error = None

    try:
        from earnings_analysis.models.company import Company
        from earnings_analysis.models.document import DocumentMetadata
        from earnings_analysis.models.financial import CompanyFinancialData
        from earnings_analysis.models.sentiment import SentimentAnalysisSession, SentimentAnalysisHistory

        sec_code = _get_securities_code(diary.stock_symbol)
        if not sec_code:
            return render(request, 'stockdiary/partials/edinet_panel.html', {
                'diary': diary,
                'documents': [],
                'not_supported': True,
            })

        # EDINETの Company マスタから edinet_code を解決する
        company = Company.objects.filter(securities_code=sec_code, is_active=True).first()
        if company:
            doc_filter = {'edinet_code': company.edinet_code, 'legal_status': '1'}
        else:
            # Company マスタに存在しない場合は securities_code で代替（EDINET制約は維持）
            doc_filter = {'securities_code': sec_code, 'legal_status': '1'}

        # 直近10件の開示書類を取得（legal_status='1'＝閲覧中のみ）
        docs = (
            DocumentMetadata.objects
            .filter(**doc_filter)
            .order_by('-submit_date_time')[:10]
        )

        for doc in docs:
            # 感情分析: セッション → 永続履歴にフォールバック
            sent_session = (
                SentimentAnalysisSession.objects
                .filter(document=doc, processing_status='COMPLETED')
                .order_by('-created_at')
                .first()
            )
            sent_history = None
            if not sent_session:
                try:
                    sent_history = (
                        SentimentAnalysisHistory.objects
                        .filter(document=doc)
                        .order_by('-analysis_date')
                        .first()
                    )
                except Exception:
                    pass
            sent = sent_session or sent_history

            pdf_url = None
            if doc.pdf_flag:
                try:
                    pdf_url = reverse('copomo:document-download', args=[doc.doc_id]) + '?type=pdf'
                except Exception:
                    pass

            # 感情分析データをJSON化（モーダル表示用）
            sent_json = None
            if sent:
                try:
                    analysis_result = getattr(sent, 'analysis_result', None) or {}
                    kw = analysis_result.get('keyword_analysis', {})
                    stats_raw = analysis_result.get('statistics', {})
                    ai_expert = analysis_result.get('ai_expert_analysis') or {}

                    # キーワードは {'word': ..., 'count': ...} のdict配列なので文字列に変換
                    def _kw_word(k):
                        return k.get('word', '') if isinstance(k, dict) else str(k)

                    # センテンスは {'text': ..., 'score': ...} のdict配列なので文字列に変換
                    def _sent_text(s):
                        return s.get('text', '') if isinstance(s, dict) else str(s)

                    raw_sp = (analysis_result.get('sample_sentences') or {}).get('positive', [])
                    raw_sn = (analysis_result.get('sample_sentences') or {}).get('negative', [])

                    sent_json = json.dumps({
                        'overall_score': float(sent.overall_score) if sent.overall_score is not None else 0,
                        'ai_overall_score': ai_expert.get('overall_score'),
                        'sentiment_label': sent.sentiment_label or '',
                        'label_display': {
                            'positive': 'ポジティブ', 'negative': 'ネガティブ', 'neutral': '中立',
                        }.get(sent.sentiment_label, sent.sentiment_label or '—'),
                        'sample_sentences': {
                            'positive': [_sent_text(s) for s in raw_sp[:3]],
                            'negative': [_sent_text(s) for s in raw_sn[:3]],
                        },
                        'keyword_pos': [_kw_word(k) for k in kw.get('positive', [])[:10]],
                        'keyword_neg': [_kw_word(k) for k in kw.get('negative', [])[:10]],
                        'stats': {k: stats_raw[k] for k in (
                            'sentences_analyzed', 'positive_words_count', 'negative_words_count'
                        ) if k in stats_raw},
                        'ai_insights': ai_expert.get('investment_points', []),
                    }, ensure_ascii=False)
                except Exception:
                    pass

            # 財務データ（XBRL 分析済みの場合）
            fin_data = (
                CompanyFinancialData.objects
                .filter(document=doc)
                .order_by('-updated_at')
                .first()
            )

            # 財務分析レポート JSON（fin_data がある場合に構築）
            report_json = None
            if fin_data:
                try:
                    from earnings_analysis.services.financial_analyzer import FinancialAnalyzer
                    from decimal import Decimal
                    _risk_labels = {'low': '低リスク', 'medium': '中リスク', 'high': '高リスク', 'very_high': '非常に高リスク'}

                    cf_data = {}
                    if all(getattr(fin_data, f) is not None for f in ('operating_cf', 'investing_cf', 'financing_cf')):
                        cf_result = FinancialAnalyzer().analyze_cashflow_pattern({
                            'operating_cf': Decimal(str(fin_data.operating_cf)),
                            'investing_cf': Decimal(str(fin_data.investing_cf)),
                            'financing_cf': Decimal(str(fin_data.financing_cf)),
                        })
                        ptn = cf_result.get('pattern', {})
                        amt = cf_result.get('amounts', {})
                        ana = cf_result.get('analysis', {})
                        cf_data = {
                            'name': ptn.get('name', ''),
                            'description': ptn.get('description', ''),
                            'risk_level': ptn.get('risk_level', 'medium'),
                            'risk_label': _risk_labels.get(ptn.get('risk_level', 'medium'), '中リスク'),
                            'interpretation': ptn.get('interpretation', ''),
                            'operating_cf': amt.get('operating_cf', 0),
                            'investing_cf': amt.get('investing_cf', 0),
                            'financing_cf': amt.get('financing_cf', 0),
                            'strengths': ana.get('strengths', [])[:3],
                            'concerns': ana.get('concerns', [])[:3],
                            'key_insights': ana.get('key_insights', [])[:3],
                        }

                    def _f(v):
                        return round(float(v), 2) if v is not None else None

                    # 比率フィールドが null の場合は元データから直接計算（_calculate_ratios の条件が厳しいため）
                    def _ratio_or_calc(stored, numerator, denominator):
                        if stored is not None:
                            return _f(stored)
                        try:
                            n = getattr(fin_data, numerator)
                            d = getattr(fin_data, denominator)
                            if n is not None and d is not None and Decimal(str(d)) != 0:
                                return round(float(Decimal(str(n)) / Decimal(str(d)) * 100), 2)
                        except Exception:
                            pass
                        return None

                    report_json = json.dumps({
                        'company_name': doc.company_name,
                        'doc_type': doc.doc_type_display_name or doc.doc_type_code,
                        'file_date': str(doc.file_date) if doc.file_date else '',
                        # 財務安全性（DBの計算済み値 → なければ元データから直接計算）
                        'equity_ratio': _ratio_or_calc(fin_data.equity_ratio, 'net_assets', 'total_assets'),
                        # CF 数値
                        'operating_cf': _f(fin_data.operating_cf),
                        'investing_cf': _f(fin_data.investing_cf),
                        'financing_cf': _f(fin_data.financing_cf),
                        # CFパターン詳細
                        'cf': cf_data,
                    }, ensure_ascii=False)
                except Exception:
                    pass

            documents.append({
                'doc': doc,
                'sent': sent,
                'fin_data': fin_data,
                'report_json': report_json,
                'pdf_url': pdf_url,
                'sent_json': sent_json,
            })

    except ImportError:
        error = 'earnings_analysis アプリが利用できません'
    except Exception as e:
        error = str(e)

    return render(request, 'stockdiary/partials/edinet_panel.html', {
        'diary': diary,
        'documents': documents,
        'error': error,
        'not_supported': False,
    })


@login_required
@require_GET
def edinet_note_prefill(request, diary_id):
    """
    EDINET開示書類の分析結果をDiaryNoteのプリセット内容としてJSON返却
    新規Gemini呼び出しは行わず、保存済みanalysis_resultを使用
    """
    doc_id = request.GET.get('doc_id', '')
    if not doc_id:
        return JsonResponse({'error': 'doc_id required'}, status=400)

    diary = get_object_or_404(StockDiary, pk=diary_id, user=request.user)

    try:
        from earnings_analysis.models.document import DocumentMetadata
        from earnings_analysis.models.sentiment import SentimentAnalysisSession, SentimentAnalysisHistory

        doc = get_object_or_404(DocumentMetadata, doc_id=doc_id, legal_status='1')

        # 感情分析: セッション → 永続履歴にフォールバック
        sent_session = (
            SentimentAnalysisSession.objects
            .filter(document=doc, processing_status='COMPLETED')
            .order_by('-created_at')
            .first()
        )
        sent = sent_session
        if not sent:
            try:
                sent = (
                    SentimentAnalysisHistory.objects
                    .filter(document=doc)
                    .order_by('-analysis_date')
                    .first()
                )
            except Exception:
                pass

        content_parts = []
        content_parts.append(f'## EDINET開示: {doc.company_name}')
        content_parts.append(f'書類種別: {doc.doc_type_display_name}')
        content_parts.append(f'提出日: {doc.file_date}')
        content_parts.append('')

        if sent:
            analysis_result = getattr(sent, 'analysis_result', None) or {}
            _label_map = {'positive': 'ポジティブ', 'negative': 'ネガティブ', 'neutral': '中立'}
            label_display = _label_map.get(sent.sentiment_label, sent.sentiment_label or '—')
            score = float(sent.overall_score) if sent.overall_score is not None else None

            content_parts.append('### 感情分析')
            score_str = f'{score:.1f}' if score is not None else '—'
            content_parts.append(f'- センチメント: **{label_display}** （スコア: {score_str}）')

            # AIインサイトの投資ポイント
            points = (analysis_result.get('ai_expert_analysis') or {}).get('investment_points', [])
            if points:
                content_parts.append('')
                content_parts.append('### 投資ポイント（AI分析）')
                for p in points:
                    title = p.get('title', '')
                    desc = p.get('description', p.get('content', ''))
                    if title:
                        content_parts.append(f'- **{title}**: {desc}')
                    else:
                        content_parts.append(f'- {desc}')
            content_parts.append('')

        content_parts.append('---')
        content_parts.append(f'*書類参照: {doc.doc_type_display_name} / {doc.file_date} [#{doc.doc_id}]*')

        prefill_content = '\n'.join(content_parts)
        return JsonResponse({
            'content': prefill_content,
            'doc_id': doc.doc_id,
            'note_type': 'earnings',
            'importance': 'medium',
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================
# EDINET連携: XBRL 財務分析トリガー（非AI・ルールベース）
# ============================================================

@login_required
@require_POST
def edinet_xbrl_analyze(request, diary_id):
    """
    EDINET XBRL から財務指標を抽出・算出して CompanyFinancialData に保存。
    AI（Gemini）は一切使用しない。
    """
    diary = get_object_or_404(StockDiary, pk=diary_id, user=request.user)
    doc_id = request.POST.get('doc_id', '')
    if not doc_id:
        return JsonResponse({'error': 'doc_id required'}, status=400)

    try:
        from earnings_analysis.models.document import DocumentMetadata
        from earnings_analysis.services.xbrl_analysis_service import XBRLAnalysisService

        doc = get_object_or_404(DocumentMetadata, doc_id=doc_id, legal_status='1')

        if not doc.xbrl_flag:
            return JsonResponse({'error': 'この書類には XBRL データがありません'}, status=400)

        result = XBRLAnalysisService().analyze_document(doc)

        if not result.get('ok'):
            return JsonResponse({'error': result.get('error', '分析に失敗しました')}, status=500)

        return JsonResponse({'ok': True, 'result': result})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
