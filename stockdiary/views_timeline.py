# stockdiary/views_timeline.py
"""
全銘柄横断の思考タイムライン

継続記録・取引・日記作成・振り返りを日付降順の1本の時系列で表示する。
「あの時期の自分は何を考えていたか」を見返す想起の中核画面
（docs/improvement_plan.md 論点6）。

リクエスト時のユーザー単位クエリのみで構成し、常駐バッチを持たない。
各ソースの取得件数に上限を設けてメモリを抑える。
"""
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView

from .models import StockDiary, DiaryNote, Transaction
from .utils import extract_lead
from tags.models import Tag

PAGE_SIZE = 50
# 1ソースあたりの最大取得件数（期間フィルターと併用するメモリ上限）
SOURCE_CAP = 500

PERIOD_DAYS = {'1m': 30, '3m': 90, '1y': 365}

TYPE_CHOICES = [
    ('all', 'すべて'),
    ('note', '継続記録'),
    ('retrospective', '振り返り'),
    ('transaction', '取引'),
    ('diary', '日記作成'),
]

PERIOD_CHOICES = [
    ('1m', '1ヶ月'),
    ('3m', '3ヶ月'),
    ('1y', '1年'),
    ('all', 'すべて'),
]


class TimelineView(LoginRequiredMixin, TemplateView):
    template_name = 'stockdiary/timeline.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        period = self.request.GET.get('period', '3m')
        if period not in dict(PERIOD_CHOICES):
            period = '3m'
        etype = self.request.GET.get('type', 'all')
        if etype not in dict(TYPE_CHOICES):
            etype = 'all'
        try:
            tag_id = int(self.request.GET.get('tag', '') or 0) or None
        except (ValueError, TypeError):
            tag_id = None

        since = None
        if period in PERIOD_DAYS:
            since = timezone.now().date() - timedelta(days=PERIOD_DAYS[period])

        events = self._collect_events(user, since, etype, tag_id)

        paginator = Paginator(events, PAGE_SIZE)
        page_obj = paginator.get_page(self.request.GET.get('page', 1))

        context.update({
            'page_obj': page_obj,
            'events': page_obj.object_list,
            'period': period,
            'etype': etype,
            'tag_id': tag_id,
            'period_choices': PERIOD_CHOICES,
            'type_choices': TYPE_CHOICES,
            'tags': Tag.objects.filter(user=user).order_by('name'),
            # 振り返り中にそのまま記録できるよう、他の主要ページと同じスピードダイアルを置く
            'page_actions': [
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
            ],
        })
        return context

    @staticmethod
    def _collect_events(user, since, etype, tag_id):
        """3ソース（継続記録・取引・日記作成）を統合して日付降順で返す"""
        events = []

        # 継続記録（振り返り含む）
        if etype in ('all', 'note', 'retrospective'):
            notes = DiaryNote.objects.filter(
                diary__user=user, diary__is_excluded=False,
            ).select_related('diary')
            if etype == 'retrospective':
                notes = notes.filter(note_type='retrospective')
            elif etype == 'note':
                notes = notes.exclude(note_type='retrospective')
            if since:
                notes = notes.filter(date__gte=since)
            if tag_id:
                notes = notes.filter(diary__tags__id=tag_id)
            for n in notes.order_by('-date', '-created_at')[:SOURCE_CAP]:
                events.append({
                    'kind': 'retrospective' if n.note_type == 'retrospective' else 'note',
                    'date': n.date,
                    'sort_key': (n.date, n.created_at),
                    'diary': n.diary,
                    'note': n,
                    'lead': extract_lead(n.content or '', max_len=120),
                })

        # 取引
        if etype in ('all', 'transaction'):
            txs = Transaction.objects.filter(
                diary__user=user, diary__is_excluded=False,
            ).select_related('diary')
            if since:
                txs = txs.filter(transaction_date__gte=since)
            if tag_id:
                txs = txs.filter(diary__tags__id=tag_id)
            for t in txs.order_by('-transaction_date', '-created_at')[:SOURCE_CAP]:
                events.append({
                    'kind': 'transaction',
                    'date': t.transaction_date,
                    'sort_key': (t.transaction_date, t.created_at),
                    'diary': t.diary,
                    'transaction': t,
                })

        # 日記作成
        if etype in ('all', 'diary'):
            diaries = StockDiary.objects.filter(user=user, is_excluded=False)
            if since:
                diaries = diaries.filter(created_at__date__gte=since)
            if tag_id:
                diaries = diaries.filter(tags__id=tag_id)
            for d in diaries.order_by('-created_at')[:SOURCE_CAP]:
                events.append({
                    'kind': 'diary',
                    'date': d.created_at.date(),
                    'sort_key': (d.created_at.date(), d.created_at),
                    'diary': d,
                    'lead': extract_lead(d.reason or '', max_len=120),
                })

        events.sort(key=lambda e: e['sort_key'], reverse=True)
        return events
