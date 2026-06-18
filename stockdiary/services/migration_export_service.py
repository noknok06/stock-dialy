"""日記データ移行：エクスポートサービス。

StockDiary とその関連（継続記録・取引・株式分割・タグ・タグ方向・仮説・検証）を
ポータブルな中間dict（payload）に変換し、JSON または CSV(ZIP) として出力する。

JSON と CSV は同じ payload を経由するため、シリアライズ本体はここに集約される。
インポート側（migration_import_service.ImportService）も同じ payload 構造を受け取る。

対象外: linked_diaries（関連日記リンク）、画像バイナリ（ファイル名のみメタ記録）。
"""

import csv
import io
import json
import zipfile
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from ..models import StockDiary

# payload スキーマのバージョン。将来の構造変更時に分岐するためのキー。
# v2: 仮説（Thesis）・検証（Verdict）を追加。
PAYLOAD_VERSION = 2
PAYLOAD_FORMAT = 'stockdiary-migration'

# CSV(ZIP) 内のファイル名
CSV_FILES = {
    'tags': 'tags.csv',
    'diaries': 'diaries.csv',
    'transactions': 'transactions.csv',
    'stock_splits': 'stock_splits.csv',
    'notes': 'notes.csv',
    'tag_directions': 'tag_directions.csv',
    'theses': 'theses.csv',
    'verdicts': 'verdicts.csv',
}

# diaries.csv のタグ列で使う区切り文字
TAG_SEPARATOR = '|'


def _dec(value):
    """Decimal/数値を文字列に。None はそのまま None。"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _date(value):
    """date を 'YYYY-MM-DD' 文字列に。None はそのまま None。"""
    if value is None:
        return None
    return value.isoformat()


class ExportService:
    """指定ユーザーの日記データをエクスポートする。"""

    def __init__(self, user):
        self.user = user

    # ------------------------------------------------------------------
    # payload 構築
    # ------------------------------------------------------------------
    def build_payload(self) -> dict:
        """DB から中間dict（payload）を構築する。"""
        diaries_qs = (
            StockDiary.objects.filter(user=self.user)
            .prefetch_related(
                'theses__verdict',
                'theses__basis_tags',
                'tags',
                'transactions',
                'stock_splits',
                'notes',
                'tag_directions__tag',
            )
            .order_by('id')
        )

        # タグマスタ（このユーザーの全タグ）を収集。parent は名前で参照する。
        from tags.models import Tag
        tags_payload = []
        for tag in Tag.objects.filter(user=self.user).select_related('parent').order_by('id'):
            tags_payload.append({
                'name': tag.name,
                'axis': tag.axis,
                'parent': tag.parent.name if tag.parent else None,
                'df': tag.df,
            })

        diaries_payload = []
        for index, diary in enumerate(diaries_qs, start=1):
            export_key = f'd{index}'
            diaries_payload.append({
                'export_key': export_key,
                'stock_symbol': diary.stock_symbol,
                'stock_name': diary.stock_name,
                'currency': diary.currency,
                'reason': diary.reason,
                'sector': diary.sector,
                'is_excluded': diary.is_excluded,
                'latest_disclosure_date': _date(diary.latest_disclosure_date),
                'latest_disclosure_doc_type_name': diary.latest_disclosure_doc_type_name,
                'image_filename': diary.image.name if diary.image else None,
                'tags': [t.name for t in diary.tags.all()],
                'tag_directions': [
                    {'tag': td.tag.name, 'direction': td.direction}
                    for td in diary.tag_directions.all()
                ],
                'transactions': [
                    {
                        'transaction_type': tx.transaction_type,
                        'transaction_date': _date(tx.transaction_date),
                        'price': _dec(tx.price),
                        'quantity': _dec(tx.quantity),
                        'memo': tx.memo,
                        'is_margin': tx.is_margin,
                    }
                    # 行順＝挿入順を維持するため日付・id順で並べる
                    for tx in sorted(
                        diary.transactions.all(),
                        key=lambda t: (t.transaction_date, t.id),
                    )
                ],
                'stock_splits': [
                    {
                        'split_date': _date(sp.split_date),
                        'split_ratio': _dec(sp.split_ratio),
                        'memo': sp.memo,
                        'is_applied': sp.is_applied,
                    }
                    for sp in sorted(
                        diary.stock_splits.all(),
                        key=lambda s: (s.split_date, s.id),
                    )
                ],
                'notes': [
                    {
                        'date': _date(note.date),
                        'content': note.content,
                        'current_price': _dec(note.current_price),
                        'note_type': note.note_type,
                        'importance': note.importance,
                        'topic': note.topic,
                        'source_doc_id': note.source_doc_id,
                        'image_filename': note.image.name if note.image else None,
                    }
                    for note in sorted(
                        diary.notes.all(),
                        key=lambda n: (n.date, n.id),
                    )
                ],
                # 仮説（Thesis）と検証（Verdict）。無ければ None。
                'thesis': self._thesis_payload(diary),
            })

        return {
            'meta': {
                'format': PAYLOAD_FORMAT,
                'version': PAYLOAD_VERSION,
                'exported_at': timezone.localtime(timezone.now()).isoformat(),
                'source_username': self.user.get_username(),
                'includes_images': False,
                'counts': {
                    'diaries': len(diaries_payload),
                    'tags': len(tags_payload),
                    'transactions': sum(len(d['transactions']) for d in diaries_payload),
                    'stock_splits': sum(len(d['stock_splits']) for d in diaries_payload),
                    'notes': sum(len(d['notes']) for d in diaries_payload),
                    'tag_directions': sum(len(d['tag_directions']) for d in diaries_payload),
                    'theses': sum(1 for d in diaries_payload if d['thesis']),
                    'verdicts': sum(1 for d in diaries_payload if d['thesis'] and d['thesis']['verdict']),
                },
            },
            'tags': tags_payload,
            'diaries': diaries_payload,
        }

    @staticmethod
    def _thesis_payload(diary):
        """diary に紐づく仮説（と検証）を dict 化する。無ければ None。最新の1件を返す。"""
        theses = list(diary.theses.all())  # prefetch キャッシュを使用
        if not theses:
            return None
        thesis = theses[0]
        verdict = getattr(thesis, 'verdict', None)
        verdict_payload = None
        if verdict is not None:
            verdict_payload = {
                'hypothesis_result': verdict.hypothesis_result,
                'pnl_result': verdict.pnl_result,
                'decision_quality': verdict.decision_quality,
                'missed_factor': verdict.missed_factor,
                'is_repeatable': verdict.is_repeatable,
                'learning': verdict.learning,
            }
        return {
            'claim': thesis.claim,
            'basis_tags': [t.name for t in thesis.basis_tags.all()],
            'horizon': thesis.horizon,
            'worst_case': thesis.worst_case,
            'review_due_date': _date(thesis.review_due_date),
            'status': thesis.status,
            'verdict': verdict_payload,
        }

    # ------------------------------------------------------------------
    # JSON 出力
    # ------------------------------------------------------------------
    def to_json(self):
        """(filename, bytes) を返す。"""
        payload = self.build_payload()
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        filename = f'stockdiary_migration_{datetime.now().strftime("%Y%m%d")}.json'
        return filename, content.encode('utf-8')

    # ------------------------------------------------------------------
    # CSV(ZIP) 出力
    # ------------------------------------------------------------------
    def to_csv_zip(self):
        """(filename, bytes) を返す。各CSVは utf-8-sig(BOM)。"""
        payload = self.build_payload()
        rows = self._payload_to_rows(payload)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # meta は JSON で同梱
            zf.writestr('meta.json', json.dumps(payload['meta'], ensure_ascii=False, indent=2))
            for key, filename in CSV_FILES.items():
                zf.writestr(filename, self._rows_to_csv_bytes(rows[key]['header'], rows[key]['rows']))

        filename = f'stockdiary_migration_{datetime.now().strftime("%Y%m%d")}.zip'
        return filename, buffer.getvalue()

    @staticmethod
    def _rows_to_csv_bytes(header, data_rows):
        """ヘッダーと行リストを utf-8-sig CSV のバイト列に変換。"""
        text_buffer = io.StringIO()
        writer = csv.writer(text_buffer)
        writer.writerow(header)
        for row in data_rows:
            writer.writerow(row)
        # utf-8-sig で BOM を付け Excel での文字化けを防ぐ
        return text_buffer.getvalue().encode('utf-8-sig')

    @staticmethod
    def _payload_to_rows(payload) -> dict:
        """payload をテーブルごとの {header, rows} に平坦化する。"""
        tags_rows = [
            [t['name'], t['axis'], t['parent'] or '', t['df']]
            for t in payload['tags']
        ]

        diaries_rows = []
        transactions_rows = []
        stock_splits_rows = []
        notes_rows = []
        tag_directions_rows = []
        theses_rows = []
        verdicts_rows = []

        for d in payload['diaries']:
            key = d['export_key']
            diaries_rows.append([
                key,
                d['stock_symbol'],
                d['stock_name'],
                d['currency'],
                d['reason'],
                d['sector'],
                d['is_excluded'],
                d['latest_disclosure_date'] or '',
                d['latest_disclosure_doc_type_name'],
                TAG_SEPARATOR.join(d['tags']),
            ])
            for tx in d['transactions']:
                transactions_rows.append([
                    key, tx['transaction_type'], tx['transaction_date'],
                    tx['price'], tx['quantity'], tx['memo'], tx['is_margin'],
                ])
            for sp in d['stock_splits']:
                stock_splits_rows.append([
                    key, sp['split_date'], sp['split_ratio'], sp['memo'], sp['is_applied'],
                ])
            for note in d['notes']:
                notes_rows.append([
                    key, note['date'], note['content'],
                    note['current_price'] if note['current_price'] is not None else '',
                    note['note_type'], note['importance'], note['topic'],
                    note['source_doc_id'] or '',
                ])
            for td in d['tag_directions']:
                tag_directions_rows.append([key, td['tag'], td['direction']])
            th = d.get('thesis')
            if th:
                theses_rows.append([
                    key, th['claim'], TAG_SEPARATOR.join(th['basis_tags']),
                    th['horizon'], th['worst_case'], th['review_due_date'] or '', th['status'],
                ])
                v = th.get('verdict')
                if v:
                    verdicts_rows.append([
                        key, v['hypothesis_result'], v['pnl_result'], v['decision_quality'],
                        v['missed_factor'], v['is_repeatable'], v['learning'],
                    ])

        return {
            'tags': {
                'header': ['name', 'axis', 'parent', 'df'],
                'rows': tags_rows,
            },
            'diaries': {
                'header': [
                    'export_key', 'stock_symbol', 'stock_name', 'currency', 'reason',
                    'sector', 'is_excluded', 'latest_disclosure_date',
                    'latest_disclosure_doc_type_name', 'tags',
                ],
                'rows': diaries_rows,
            },
            'transactions': {
                'header': [
                    'diary_export_key', 'transaction_type', 'transaction_date',
                    'price', 'quantity', 'memo', 'is_margin',
                ],
                'rows': transactions_rows,
            },
            'stock_splits': {
                'header': ['diary_export_key', 'split_date', 'split_ratio', 'memo', 'is_applied'],
                'rows': stock_splits_rows,
            },
            'notes': {
                'header': [
                    'diary_export_key', 'date', 'content', 'current_price',
                    'note_type', 'importance', 'topic', 'source_doc_id',
                ],
                'rows': notes_rows,
            },
            'tag_directions': {
                'header': ['diary_export_key', 'tag', 'direction'],
                'rows': tag_directions_rows,
            },
            'theses': {
                'header': [
                    'diary_export_key', 'claim', 'basis_tags', 'horizon',
                    'worst_case', 'review_due_date', 'status',
                ],
                'rows': theses_rows,
            },
            'verdicts': {
                'header': [
                    'diary_export_key', 'hypothesis_result', 'pnl_result',
                    'decision_quality', 'missed_factor', 'is_repeatable', 'learning',
                ],
                'rows': verdicts_rows,
            },
        }
