# stockdiary/services/recall_service.py
"""
リクエスト時想起サービス

ホーム表示時にユーザー単位の軽量クエリで「想起のきっかけ」を組み立てる。
常駐バッチを持たず、アクセスがあったユーザーの分しか計算しない設計
（docs/improvement_plan.md 論点2「リクエスト時想起」を参照）。

提供する想起:
- 1年前の今日: 約1年前(±数日)の継続記録・日記作成
- 振り返り未記入: 売却完結したが retrospective ノートがない日記
- 新着開示: 直近に開示書類が出た日記（DisclosureSync が更新する
  latest_disclosure_date を読むだけ。追加の外部アクセスなし）
"""
from datetime import timedelta

from django.utils import timezone


# 「1年前の今日」の許容ウィンドウ（±日数）
ANNIVERSARY_WINDOW_DAYS = 3
# 新着開示とみなす日数
DISCLOSURE_RECENT_DAYS = 7
# 各セクションの最大表示件数
SECTION_LIMIT = 3


class RecallService:
    """ホーム上部「今日の想起」カードのデータ組み立て"""

    @classmethod
    def build(cls, user, today=None):
        """
        想起カード用データを構築する。

        Returns:
            dict: {
                'anniversary': [{'diary', 'date', 'kind', 'snippet'}, ...],
                'unreviewed': [StockDiary, ...],
                'unreviewed_count': int,
                'disclosures': [StockDiary, ...],
                'has_content': bool,
            }
        """
        today = today or timezone.now().date()

        anniversary = cls._build_anniversary(user, today)
        unreviewed, unreviewed_count = cls._build_unreviewed(user)
        disclosures = cls._build_disclosures(user, today)

        return {
            'anniversary': anniversary,
            'unreviewed': unreviewed,
            'unreviewed_count': unreviewed_count,
            'disclosures': disclosures,
            'has_content': bool(anniversary or unreviewed or disclosures),
            # 折りたたみ時の見出しバッジ用の総件数
            'total_count': len(anniversary) + unreviewed_count + len(disclosures),
        }

    @classmethod
    def _build_anniversary(cls, user, today):
        """約1年前(±ウィンドウ)の継続記録・日記作成を新しい順に返す"""
        from ..models import DiaryNote, StockDiary

        target = today - timedelta(days=365)
        start = target - timedelta(days=ANNIVERSARY_WINDOW_DAYS)
        end = target + timedelta(days=ANNIVERSARY_WINDOW_DAYS)

        items = []

        notes = (
            DiaryNote.objects
            .filter(diary__user=user, diary__is_excluded=False, date__range=(start, end))
            .select_related('diary')
            .order_by('-date')[:SECTION_LIMIT]
        )
        for note in notes:
            # 振り返りは topic が固定テーマのため、中身が伝わる本文を優先する
            if note.note_type == 'retrospective':
                snippet = (note.content or '')[:60]
            else:
                snippet = (note.topic or note.content or '')[:60]
            items.append({
                'diary': note.diary,
                'date': note.date,
                'kind': 'note',
                'snippet': snippet,
            })

        if len(items) < SECTION_LIMIT:
            diaries = (
                StockDiary.objects
                .filter(user=user, is_excluded=False, created_at__date__range=(start, end))
                .order_by('-created_at')[:SECTION_LIMIT - len(items)]
            )
            for diary in diaries:
                items.append({
                    'diary': diary,
                    'date': diary.created_at.date(),
                    'kind': 'diary',
                    'snippet': (diary.reason or '')[:60],
                })

        return items[:SECTION_LIMIT]

    @classmethod
    def _build_unreviewed(cls, user):
        """売却完結済みで振り返り(retrospective)未記入の日記。

        複数売買ラウンド対応: 「最後の売り取引以降に書かれた振り返り」が
        ある日記だけを記入済みとみなす（再売却したら再び未記入扱いに戻る）。
        """
        from django.db.models import Exists, OuterRef, Subquery
        from ..models import StockDiary, DiaryNote, Transaction

        # DiaryNote から見た親日記の最終売り日（DiaryNote.diary_id 経由で相関）
        last_sell = (
            Transaction.objects
            .filter(diary=OuterRef('diary_id'), transaction_type='sell')
            .order_by('-transaction_date')
            .values('transaction_date')[:1]
        )
        reviewed = DiaryNote.objects.filter(
            diary=OuterRef('pk'),
            note_type='retrospective',
            date__gte=Subquery(last_sell),
        )

        qs = (
            StockDiary.objects
            .filter(
                user=user,
                is_excluded=False,
                transaction_count__gt=0,
                current_quantity=0,
            )
            .annotate(_reviewed=Exists(reviewed))
            .filter(_reviewed=False)
            .order_by('-updated_at')
        )
        count = qs.count()
        return list(qs[:SECTION_LIMIT]), count

    @classmethod
    def _build_disclosures(cls, user, today):
        """直近に開示書類が出た日記（latest_disclosure_date を参照）"""
        from ..models import StockDiary

        cutoff = today - timedelta(days=DISCLOSURE_RECENT_DAYS)
        return list(
            StockDiary.objects
            .filter(user=user, is_excluded=False, latest_disclosure_date__gte=cutoff)
            .order_by('-latest_disclosure_date')[:SECTION_LIMIT]
        )
