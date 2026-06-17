"""日記データ移行（エクスポート/インポート）のテスト。

ラウンドトリップ（export → import）で、別ユーザーへデータが正しくコピーされ、
集計値が再計算で一致すること、タグが統合されること等を検証する。
"""
import io
import json
import zipfile
from datetime import date
from decimal import Decimal

import pytest

from stockdiary.models import StockDiary, DiaryTagDirection
from stockdiary.services.migration_export_service import ExportService
from stockdiary.services.migration_import_service import (
    ImportService, ImportError as MigrationImportError,
)
from tags.models import Tag


class _FakeUpload:
    """ImportService.parse に渡すアップロードファイルの簡易モック。"""

    def __init__(self, name, content: bytes):
        self.name = name
        self._content = content

    def read(self):
        return self._content


def _export_json_upload(user, filename='migration.json'):
    _, content = ExportService(user).to_json()
    return _FakeUpload(filename, content)


def _export_zip_upload(user, filename='migration.zip'):
    _, content = ExportService(user).to_csv_zip()
    return _FakeUpload(filename, content)


@pytest.mark.django_db
class TestExportPayload:
    def test_build_payload_structure(self, complex_diary_with_multiple_transactions, sample_tags):
        user = complex_diary_with_multiple_transactions.user
        payload = ExportService(user).build_payload()

        assert payload['meta']['format'] == 'stockdiary-migration'
        assert payload['meta']['version'] == 2
        assert payload['meta']['counts']['diaries'] == 1
        assert payload['meta']['counts']['transactions'] == 5
        diary = payload['diaries'][0]
        assert diary['stock_name'] == '信越化学工業'
        # Decimal は文字列で出力される
        assert isinstance(diary['transactions'][0]['price'], str)

    def test_linked_diaries_excluded(self, sample_diary, sample_memo_diary):
        # リンクを張ってもエクスポートには出力されない
        sample_diary.linked_diaries.add(sample_memo_diary)
        payload = ExportService(sample_diary.user).build_payload()
        for d in payload['diaries']:
            assert 'linked_diaries' not in d


@pytest.mark.django_db
class TestJsonRoundTrip:
    def test_aggregates_recalculated_and_user_reassigned(
        self, complex_diary_with_multiple_transactions, another_user
    ):
        original = complex_diary_with_multiple_transactions
        original.refresh_from_db()

        upload = _export_json_upload(original.user)
        service = ImportService(another_user)
        payload = service.parse(upload)
        result = service.import_payload(payload)

        assert result['created_diaries'] == 1
        assert result['transactions'] == 5

        imported = StockDiary.objects.get(user=another_user, stock_symbol='4063')
        # user が付け替わっている（元ユーザーのデータは増えていない）
        assert imported.user == another_user
        assert StockDiary.objects.filter(user=original.user).count() == 1

        # 集計値が再計算で元と一致
        assert imported.current_quantity == original.current_quantity
        assert imported.total_cost == original.total_cost
        assert imported.realized_profit == original.realized_profit
        assert imported.cash_only_current_quantity == original.cash_only_current_quantity
        assert imported.transaction_count == original.transaction_count

    def test_notes_round_trip(self, diary_with_notes, another_user):
        upload = _export_json_upload(diary_with_notes.user)
        service = ImportService(another_user)
        result = service.import_payload(service.parse(upload))

        assert result['notes'] == 2
        imported = StockDiary.objects.get(user=another_user, stock_symbol='7203')
        assert imported.notes.count() == 2
        assert imported.notes.filter(note_type='earnings', importance='high').exists()

    def test_image_not_imported(self, sample_diary_with_transaction, another_user):
        upload = _export_json_upload(sample_diary_with_transaction.user)
        service = ImportService(another_user)
        service.import_payload(service.parse(upload))
        imported = StockDiary.objects.get(user=another_user, stock_symbol='7203')
        assert not imported.image


@pytest.mark.django_db
class TestCsvZipRoundTrip:
    def test_zip_round_trip_matches_json(
        self, complex_diary_with_multiple_transactions, another_user
    ):
        original = complex_diary_with_multiple_transactions
        original.refresh_from_db()

        upload = _export_zip_upload(original.user)
        service = ImportService(another_user)
        payload = service.parse(upload)
        result = service.import_payload(payload)

        assert result['created_diaries'] == 1
        imported = StockDiary.objects.get(user=another_user, stock_symbol='4063')
        assert imported.current_quantity == original.current_quantity
        assert imported.realized_profit == original.realized_profit

    def test_zip_uses_utf8_sig_bom(self, sample_diary, another_user):
        _, content = ExportService(sample_diary.user).to_csv_zip()
        zf = zipfile.ZipFile(io.BytesIO(content))
        raw = zf.read('diaries.csv')
        assert raw.startswith(b'\xef\xbb\xbf')  # BOM

    def test_zip_tags_pipe_separated(self, sample_diary, sample_tags, another_user):
        sample_diary.tags.set(sample_tags)
        upload = _export_zip_upload(sample_diary.user)
        service = ImportService(another_user)
        service.import_payload(service.parse(upload))
        imported = StockDiary.objects.get(user=another_user, stock_symbol='7203')
        assert imported.tags.count() == 3


@pytest.mark.django_db
class TestTagMerge:
    def test_existing_tag_reused_not_duplicated(self, sample_diary, sample_tags, another_user):
        sample_diary.tags.set(sample_tags)
        # 取り込み先に同名タグを事前作成
        Tag.objects.create(user=another_user, name='長期投資', axis=Tag.AXIS_RISK)

        upload = _export_json_upload(sample_diary.user)
        service = ImportService(another_user)
        result = service.import_payload(service.parse(upload))

        # 同名タグは統合され、重複作成されない
        assert Tag.objects.filter(user=another_user, name='長期投資').count() == 1
        assert result['tags_reused'] >= 1
        # 既存タグの axis は上書きされない
        assert Tag.objects.get(user=another_user, name='長期投資').axis == Tag.AXIS_RISK

    def test_parent_tag_resolved(self, sample_diary, another_user):
        parent = Tag.objects.create(user=sample_diary.user, name='マクロ', axis=Tag.AXIS_MACRO)
        child = Tag.objects.create(
            user=sample_diary.user, name='金利感応', axis=Tag.AXIS_MACRO, parent=parent
        )
        sample_diary.tags.set([child])

        upload = _export_json_upload(sample_diary.user)
        service = ImportService(another_user)
        service.import_payload(service.parse(upload))

        imported_child = Tag.objects.get(user=another_user, name='金利感応')
        assert imported_child.parent is not None
        assert imported_child.parent.name == 'マクロ'


@pytest.mark.django_db
class TestTagDirections:
    def test_tag_direction_preserved(self, sample_diary, another_user):
        tag = Tag.objects.create(user=sample_diary.user, name='金利感応', axis=Tag.AXIS_MACRO)
        sample_diary.tags.set([tag])
        DiaryTagDirection.objects.create(diary=sample_diary, tag=tag, direction='up')

        upload = _export_json_upload(sample_diary.user)
        service = ImportService(another_user)
        service.import_payload(service.parse(upload))

        imported = StockDiary.objects.get(user=another_user, stock_symbol='7203')
        td = imported.tag_directions.get()
        assert td.direction == 'up'
        assert td.tag.name == '金利感応'


@pytest.mark.django_db
class TestStockSplit:
    def test_split_imported_unapplied_and_not_double_applied(
        self, diary_with_stock_split, another_user
    ):
        original = diary_with_stock_split
        original.refresh_from_db()
        original_qty = original.current_quantity  # 100株（分割未適用）

        upload = _export_json_upload(original.user)
        service = ImportService(another_user)
        result = service.import_payload(service.parse(upload))

        assert result['stock_splits'] == 1
        imported = StockDiary.objects.get(user=another_user, stock_symbol='7974')
        split = imported.stock_splits.get()
        # 未適用で取り込まれる（再適用されないので数量は変わらない）
        assert split.is_applied is False
        assert split.applied_at is None
        assert imported.current_quantity == original_qty


@pytest.mark.django_db
class TestValidation:
    def test_invalid_json_raises(self, another_user):
        upload = _FakeUpload('bad.json', b'{not valid json')
        service = ImportService(another_user)
        with pytest.raises(MigrationImportError):
            service.parse(upload)

    def test_unsupported_extension_raises(self, another_user):
        upload = _FakeUpload('data.txt', b'{}')
        service = ImportService(another_user)
        with pytest.raises(MigrationImportError):
            service.parse(upload)

    def test_wrong_format_meta_raises(self, another_user):
        bad = json.dumps({'meta': {'format': 'something-else'}, 'diaries': []})
        upload = _FakeUpload('data.json', bad.encode('utf-8'))
        service = ImportService(another_user)
        with pytest.raises(MigrationImportError):
            service.parse(upload)

    def test_empty_stock_name_skipped(self, another_user):
        payload = {
            'meta': {'format': 'stockdiary-migration', 'version': 1},
            'tags': [],
            'diaries': [
                {'export_key': 'd1', 'stock_symbol': '0001', 'stock_name': '',
                 'currency': 'JPY', 'tags': [], 'tag_directions': [],
                 'transactions': [], 'stock_splits': [], 'notes': []},
            ],
        }
        service = ImportService(another_user)
        result = service.import_payload(payload)
        assert result['created_diaries'] == 0
        assert result['skipped_diaries'] == 1

    def test_invalid_transaction_skipped(self, another_user):
        payload = {
            'meta': {'format': 'stockdiary-migration', 'version': 1},
            'tags': [],
            'diaries': [
                {'export_key': 'd1', 'stock_symbol': '0002', 'stock_name': 'テスト',
                 'currency': 'JPY', 'tags': [], 'tag_directions': [],
                 'transactions': [
                     {'transaction_type': 'buy', 'transaction_date': '2024-01-01',
                      'price': '-100', 'quantity': '10', 'is_margin': False},
                     {'transaction_type': 'buy', 'transaction_date': '2024-01-02',
                      'price': '100', 'quantity': '10', 'is_margin': False},
                 ],
                 'stock_splits': [], 'notes': []},
            ],
        }
        service = ImportService(another_user)
        result = service.import_payload(payload)
        # 価格<=0 の取引はスキップ、正常な1件のみ登録
        assert result['transactions'] == 1

    def test_summarize_detects_duplicates(self, sample_diary, another_user):
        # 取り込み先に同じ銘柄コードの日記を作成
        StockDiary.objects.create(
            user=another_user, stock_symbol='7203', stock_name='トヨタ自動車'
        )
        upload = _export_json_upload(sample_diary.user)
        service = ImportService(another_user)
        payload = service.parse(upload)
        summary = service.summarize(payload)
        assert len(summary['duplicates']) == 1
        assert summary['duplicates'][0]['existing_count'] == 1


def _make_thesis_with_verdict(diary, tags=None):
    """diary に仮説＋検証（的中×利益＝再現すべき勝ち）を付ける。"""
    from stockdiary.models import Thesis, Verdict
    thesis = Thesis.objects.create(
        diary=diary, claim='円安継続で輸出採算が改善する',
        horizon='6m', worst_case='円高反転', review_due_date=date(2025, 1, 1),
        status=Thesis.STATUS_VERIFIED,
    )
    if tags:
        thesis.basis_tags.set(tags)
    Verdict.objects.create(
        thesis=thesis, hypothesis_result=Verdict.HYP_HIT, pnl_result=Verdict.PNL_PROFIT,
        decision_quality=4, missed_factor='', is_repeatable=True,
        learning='テーマが効くなら握り続ける',
    )
    return thesis


@pytest.mark.django_db
class TestThesisVerdictRoundTrip:
    """Phase 8a の仮説・検証が export → import で保持されること。"""

    def test_thesis_in_payload(self, sample_diary, sample_tags):
        _make_thesis_with_verdict(sample_diary, tags=sample_tags[:2])
        payload = ExportService(sample_diary.user).build_payload()
        th = payload['diaries'][0]['thesis']
        assert th['claim'] == '円安継続で輸出採算が改善する'
        assert th['status'] == 'verified'
        assert set(th['basis_tags']) == {sample_tags[0].name, sample_tags[1].name}
        assert th['verdict']['hypothesis_result'] == 'hit'
        assert th['verdict']['learning'] == 'テーマが効くなら握り続ける'
        assert payload['meta']['counts']['theses'] == 1
        assert payload['meta']['counts']['verdicts'] == 1

    def test_no_thesis_is_none(self, sample_diary):
        payload = ExportService(sample_diary.user).build_payload()
        assert payload['diaries'][0]['thesis'] is None
        assert payload['meta']['counts']['theses'] == 0

    def test_json_round_trip(self, sample_diary, sample_tags, another_user):
        _make_thesis_with_verdict(sample_diary, tags=sample_tags[:2])
        upload = _export_json_upload(sample_diary.user)
        service = ImportService(another_user)
        result = service.import_payload(service.parse(upload))

        assert result['theses'] == 1
        assert result['verdicts'] == 1
        imported = StockDiary.objects.get(user=another_user, stock_symbol='7203')
        thesis = imported.thesis
        assert thesis.claim == '円安継続で輸出採算が改善する'
        assert thesis.status == 'verified'
        assert thesis.review_due_date == date(2025, 1, 1)
        # 根拠タグが別ユーザー側で名前統合されて復元される
        assert set(thesis.basis_tags.values_list('name', flat=True)) == {
            sample_tags[0].name, sample_tags[1].name,
        }
        verdict = thesis.verdict
        assert verdict.hypothesis_result == 'hit'
        assert verdict.pnl_result == 'profit'
        assert verdict.quadrant == 'skill'
        assert verdict.is_repeatable is True

    def test_zip_round_trip(self, sample_diary, sample_tags, another_user):
        _make_thesis_with_verdict(sample_diary, tags=sample_tags[:1])
        upload = _export_zip_upload(sample_diary.user)
        service = ImportService(another_user)
        result = service.import_payload(service.parse(upload))

        assert result['theses'] == 1
        assert result['verdicts'] == 1
        imported = StockDiary.objects.get(user=another_user, stock_symbol='7203')
        assert imported.thesis.verdict.learning == 'テーマが効くなら握り続ける'

    def test_open_thesis_without_verdict(self, sample_diary, another_user):
        from stockdiary.models import Thesis
        Thesis.objects.create(
            diary=sample_diary, claim='検証待ちの仮説',
            review_due_date=date(2099, 1, 1), status=Thesis.STATUS_OPEN,
        )
        upload = _export_json_upload(sample_diary.user)
        service = ImportService(another_user)
        result = service.import_payload(service.parse(upload))

        assert result['theses'] == 1
        assert result['verdicts'] == 0
        imported = StockDiary.objects.get(user=another_user, stock_symbol='7203')
        assert imported.thesis.status == 'open'
        from stockdiary.models import Verdict
        assert not Verdict.objects.filter(thesis=imported.thesis).exists()

    def test_legacy_v1_payload_without_thesis(self, another_user):
        # 旧 v1 ファイル（thesis キー無し）でも落ちない
        payload = {
            'meta': {'format': 'stockdiary-migration', 'version': 1},
            'tags': [],
            'diaries': [
                {'export_key': 'd1', 'stock_symbol': '0003', 'stock_name': '旧データ',
                 'currency': 'JPY', 'tags': [], 'tag_directions': [],
                 'transactions': [], 'stock_splits': [], 'notes': []},
            ],
        }
        service = ImportService(another_user)
        result = service.import_payload(payload)
        assert result['created_diaries'] == 1
        assert result['theses'] == 0
