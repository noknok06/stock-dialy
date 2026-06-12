# earnings_analysis/services/disclosure_sync.py
"""
株式日記の開示書類インジケーター更新・開示イベント生成サービス

EDINETの DocumentMetadata から各銘柄の最新開示日を取得し、
StockDiary.latest_disclosure_date / latest_disclosure_doc_type_name を更新する。
あわせて新規開示を DisclosureEvent として記録し、該当銘柄を記録中の
ユーザーへアプリ内通知（NotificationLog）をファンアウトする。

設計方針（docs/improvement_plan.md 論点2）:
- 日記一覧表示時の追加クエリは不要（事前計算フィールドに保存）
- 日次バッチ（daily_update）完了後に呼び出される
- 負荷はユーザー数・日記数ではなくユニーク銘柄数（上場銘柄数で飽和）に比例させる
  - Stage 1: 銘柄単位の差分検知（全日記を list() でメモリに載せない）
  - Stage 2: DB内バルクINSERTでのファンアウト（Pythonループでユーザーを回さない設計を
    崩さないよう、銘柄ごとに values + bulk_create のみで処理する）
"""
import logging
from datetime import timedelta

from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)

# 想起・バッジ・通知の対象とする「重要開示」書類種別。
# EDINET は速報フィードではなく「年2回の確定決算による仮説見直しトリガー」として使う方針
# （docs/improvement_plan.md 論点2改定）のため、有報・半報のみに絞る。
# 140(四半期報告書)は2024年4月の制度廃止で新規提出なし、180(臨時報告書)は
# 大半が議決権行使結果等のノイズのため対象外。
IMPORTANT_DOC_TYPE_CODES = {
    '120',  # 有価証券報告書
    '160',  # 半期報告書
}

# これより古い開示はイベント化しない（初回実行時の過去分一斉通知を防ぐ）
EVENT_MAX_AGE_DAYS = 7

# ファンアウト時の bulk_create バッチサイズ
FANOUT_BATCH_SIZE = 500


def update_diary_disclosure_status() -> int:
    """
    全ユーザーの StockDiary に最新開示日と書類種別を更新し、
    新規開示のイベント記録とアプリ内通知ファンアウトを行う。

    Returns:
        int: 更新した StockDiary レコード数
    """
    from stockdiary.models import StockDiary

    # ユニーク銘柄コードのみ取得（4桁数字 = 日本株。日記数に依存しない）
    symbols = list(
        StockDiary.objects
        .filter(stock_symbol__regex=r'^\d{4}$')
        .values_list('stock_symbol', flat=True)
        .distinct()
    )

    if not symbols:
        logger.info('開示インジケーター更新: 対象銘柄なし')
        return 0

    # 4桁コード → 5桁証券コード（末尾に '0' を付加）
    securities_codes = [s + '0' for s in symbols]

    # 銘柄ごとの最新開示（securities_code → row dict）
    disclosure_map = _fetch_latest_disclosures(securities_codes)

    # Stage 1a: StockDiary を銘柄単位で更新（変更がある行のみ UPDATE）
    updated_count = 0
    for symbol in symbols:
        info = disclosure_map.get(symbol + '0')
        new_date = info['file_date'] if info else None
        new_name = info['doc_type_name'] if info else ''

        updated_count += (
            StockDiary.objects
            .filter(stock_symbol=symbol)
            .exclude(
                latest_disclosure_date=new_date,
                latest_disclosure_doc_type_name=new_name,
            )
            .update(
                latest_disclosure_date=new_date,
                latest_disclosure_doc_type_name=new_name,
            )
        )

    # Stage 1b: 新規開示をイベント化（銘柄×書類で一意、再実行しても重複しない）
    new_events = _record_disclosure_events(disclosure_map)

    # Stage 2: 該当銘柄を記録中のユーザーへアプリ内通知をファンアウト
    notified_count = fan_out_disclosure_notifications(new_events)

    logger.info(
        f'開示インジケーター更新完了: 日記更新={updated_count}件, '
        f'新規イベント={len(new_events)}件, 通知={notified_count}件'
    )
    return updated_count


def _fetch_latest_disclosures(securities_codes) -> dict:
    """銘柄ごとの最新の重要開示書類（有報・半報）を取得する。

    Returns:
        dict: securities_code(5桁) → {'doc_id', 'file_date', 'doc_type_code', 'doc_type_name'}
    """
    from earnings_analysis.models import DocumentMetadata

    doc_type_names = DocumentMetadata.DOC_TYPE_DISPLAY_NAMES

    base_qs = (
        DocumentMetadata.objects
        .filter(
            securities_code__in=securities_codes,
            doc_type_code__in=IMPORTANT_DOC_TYPE_CODES,
            legal_status__in=['1', '2'],     # '1'=縦覧中, '2'=延長期間中
            withdrawal_status='0',            # 取り下げられていない
        )
        .order_by('securities_code', '-file_date', '-submit_date_time')
        .values('securities_code', 'doc_id', 'file_date', 'doc_type_code')
    )

    if connection.vendor == 'postgresql':
        # DISTINCT ON で銘柄ごとに最新1件をDB側で絞る（本番環境）
        rows = base_qs.distinct('securities_code')
    else:
        # SQLite 等（テスト環境）: ソート済み行を順に読み、銘柄ごとの先頭のみ採用
        def first_per_code(qs):
            seen = set()
            for row in qs.iterator(chunk_size=2000):
                code = row['securities_code']
                if code in seen:
                    continue
                seen.add(code)
                yield row
        rows = first_per_code(base_qs)

    disclosure_map = {}
    for row in rows:
        disclosure_map[row['securities_code']] = {
            'doc_id': row['doc_id'],
            'file_date': row['file_date'],
            'doc_type_code': row['doc_type_code'],
            'doc_type_name': doc_type_names.get(
                row['doc_type_code'], f"書類種別{row['doc_type_code']}"
            ),
        }
    return disclosure_map


def _record_disclosure_events(disclosure_map: dict) -> list:
    """通知対象の新規開示を DisclosureEvent として記録し、新規作成分を返す。

    - 重要書類種別（IMPORTANT_DOC_TYPE_CODES）かつ EVENT_MAX_AGE_DAYS 以内のみ対象
    - (securities_code, doc_id) の一意制約により再実行しても重複しない
    """
    from earnings_analysis.models import DisclosureEvent

    cutoff = timezone.now().date() - timedelta(days=EVENT_MAX_AGE_DAYS)

    candidates = {
        code: info for code, info in disclosure_map.items()
        if info['doc_type_code'] in IMPORTANT_DOC_TYPE_CODES and info['file_date'] >= cutoff
    }
    if not candidates:
        return []

    # 既存イベントを除外（doc_id で十分絞れるため pair 照合は Python 側で行う）
    doc_ids = [info['doc_id'] for info in candidates.values()]
    existing_pairs = set(
        DisclosureEvent.objects
        .filter(doc_id__in=doc_ids)
        .values_list('securities_code', 'doc_id')
    )

    to_create = [
        DisclosureEvent(
            securities_code=code,
            doc_id=info['doc_id'],
            file_date=info['file_date'],
            doc_type_code=info['doc_type_code'],
            doc_type_name=info['doc_type_name'],
        )
        for code, info in candidates.items()
        if (code, info['doc_id']) not in existing_pairs
    ]
    if not to_create:
        return []

    DisclosureEvent.objects.bulk_create(to_create, ignore_conflicts=True)

    # ignore_conflicts では PK が確定しないため、確実に再取得して返す
    new_pairs = {(e.securities_code, e.doc_id) for e in to_create}
    return [
        e for e in DisclosureEvent.objects.filter(doc_id__in=doc_ids)
        if (e.securities_code, e.doc_id) in new_pairs
    ]


def fan_out_disclosure_notifications(events) -> int:
    """新規開示イベントを該当銘柄の記録ユーザーへアプリ内通知として展開する。

    - ユーザーごとに1通（同一銘柄の日記が複数あっても最新更新の日記に誘導）
    - (user, disclosure_event) の一意制約 + ignore_conflicts で重複送信を防ぐ
    - プッシュ配信はここでは行わない（Stage 3 のダイジェスト配信で対応予定）

    Returns:
        int: 作成したアプリ内通知数
    """
    from stockdiary.models import StockDiary, NotificationLog

    total = 0
    for event in events:
        symbol = event.securities_code[:-1]  # 5桁 → 4桁

        rows = (
            StockDiary.objects
            .filter(stock_symbol=symbol, is_excluded=False)
            .order_by('user_id', '-updated_at')
            .values('id', 'user_id', 'stock_name')
            .iterator(chunk_size=1000)
        )

        logs = []
        seen_users = set()
        for row in rows:
            if row['user_id'] in seen_users:
                continue
            seen_users.add(row['user_id'])
            logs.append(NotificationLog(
                user_id=row['user_id'],
                disclosure_event=event,
                title=f"📄 {row['stock_name']} の確定決算が出ました",
                message=(
                    f"{event.file_date.strftime('%Y/%m/%d')} に「{event.doc_type_name}」"
                    "が提出されました。仮説を見直して決算レビューを記録しませんか？"
                ),
                url=f"/stockdiary/{row['id']}/",
            ))
            if len(logs) >= FANOUT_BATCH_SIZE:
                NotificationLog.objects.bulk_create(logs, ignore_conflicts=True)
                total += len(logs)
                logs = []

        if logs:
            NotificationLog.objects.bulk_create(logs, ignore_conflicts=True)
            total += len(logs)

    return total
