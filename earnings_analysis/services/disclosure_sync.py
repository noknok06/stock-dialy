# earnings_analysis/services/disclosure_sync.py
"""
株式日記の開示書類インジケーター更新サービス

EDINETの DocumentMetadata から各銘柄の最新開示日を取得し、
StockDiary.latest_disclosure_date / latest_disclosure_doc_type_name を一括更新する。

設計方針:
- 日記一覧表示時の追加クエリは不要（事前計算フィールドに保存）
- 日次バッチ（daily_update）完了後に呼び出される
"""
import logging
from django.db import models

logger = logging.getLogger(__name__)


def update_diary_disclosure_status() -> int:
    """
    全ユーザーの StockDiary に最新開示日と書類種別を一括更新する。

    Returns:
        int: 更新した StockDiary レコード数
    """
    from stockdiary.models import StockDiary
    from earnings_analysis.models import DocumentMetadata

    # 4桁数字の銘柄コードを持つ日記を対象（日本株のみ）
    diaries = list(
        StockDiary.objects.filter(
            stock_symbol__regex=r'^\d{4}$'
        ).only('id', 'stock_symbol', 'latest_disclosure_date', 'latest_disclosure_doc_type_name')
    )

    if not diaries:
        logger.info('開示インジケーター更新: 対象日記なし')
        return 0

    # 4桁コード → 5桁コード（末尾に '0' を付加）
    symbol_to_securities = {d.stock_symbol: d.stock_symbol + '0' for d in diaries}
    securities_codes = list(symbol_to_securities.values())

    # EDINETの書類種別表示名マッピング
    doc_type_names = DocumentMetadata.DOC_TYPE_DISPLAY_NAMES

    # 銘柄ごとに最新の開示書類を取得
    # DISTINCT ON を使い、securities_code ごとに最新の file_date のレコードを1件取得
    latest_docs = (
        DocumentMetadata.objects
        .filter(
            securities_code__in=securities_codes,
            legal_status__in=['1', '2'],     # '1'=縦覧中, '2'=延長期間中
            withdrawal_status='0',            # 取り下げられていない
        )
        .order_by('securities_code', '-file_date', '-submit_date_time')
        .distinct('securities_code')
        .values('securities_code', 'file_date', 'doc_type_code')
    )

    # securities_code（5桁）→ (file_date, doc_type_name) のマップを構築
    disclosure_map: dict[str, tuple] = {
        row['securities_code']: (
            row['file_date'],
            doc_type_names.get(row['doc_type_code'], f"書類種別{row['doc_type_code']}")
        )
        for row in latest_docs
    }

    # StockDiary を更新
    to_update = []
    for diary in diaries:
        sec_code = symbol_to_securities[diary.stock_symbol]
        info = disclosure_map.get(sec_code)
        new_date = info[0] if info else None
        new_name = info[1] if info else ''

        if diary.latest_disclosure_date != new_date or diary.latest_disclosure_doc_type_name != new_name:
            diary.latest_disclosure_date = new_date
            diary.latest_disclosure_doc_type_name = new_name
            to_update.append(diary)

    if to_update:
        StockDiary.objects.bulk_update(
            to_update,
            ['latest_disclosure_date', 'latest_disclosure_doc_type_name'],
            batch_size=500,
        )

    updated_count = len(to_update)
    logger.info(f'開示インジケーター更新完了: {updated_count}/{len(diaries)} 件更新')
    return updated_count
