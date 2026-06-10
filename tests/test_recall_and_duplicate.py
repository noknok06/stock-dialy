"""リクエスト時想起カード（RecallService）と重複日記チェックのテスト"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse

from stockdiary.models import StockDiary, Transaction, DiaryNote
from stockdiary.services.recall_service import RecallService
from stockdiary.utils import find_duplicate_diaries
from stockdiary.forms import StockDiaryForm

pytestmark = pytest.mark.django_db(transaction=True)


class TestRecallService:
    """RecallService.build の各セクション"""

    def test_empty_user_has_no_content(self, user):
        recall = RecallService.build(user)
        assert recall['has_content'] is False
        assert recall['anniversary'] == []
        assert recall['unreviewed'] == []
        assert recall['disclosures'] == []

    def test_anniversary_note_found(self, sample_diary):
        """約1年前の継続記録が「1年前の今日」に出る"""
        DiaryNote.objects.create(
            diary=sample_diary,
            date=date.today() - timedelta(days=365),
            content='1年前の考察',
        )
        recall = RecallService.build(sample_diary.user)
        assert recall['has_content'] is True
        assert len(recall['anniversary']) == 1
        assert recall['anniversary'][0]['diary'].id == sample_diary.id
        assert recall['anniversary'][0]['kind'] == 'note'

    def test_anniversary_outside_window_excluded(self, sample_diary):
        """ウィンドウ外（±3日超）の記録は出ない"""
        DiaryNote.objects.create(
            diary=sample_diary,
            date=date.today() - timedelta(days=365 + 10),
            content='ウィンドウ外',
        )
        recall = RecallService.build(sample_diary.user)
        assert recall['anniversary'] == []

    def test_unreviewed_sold_diary_listed(self, sample_sold_diary):
        """売却完結済みで振り返りがない日記が出る"""
        recall = RecallService.build(sample_sold_diary.user)
        assert sample_sold_diary in recall['unreviewed']
        assert recall['unreviewed_count'] == 1

    def test_sold_diary_with_retrospective_excluded(self, sample_sold_diary):
        """retrospective ノートを書いた日記は出ない"""
        DiaryNote.objects.create(
            diary=sample_sold_diary,
            date=date.today(),
            content='高値掴みだった。次はエントリー根拠を数値で残す',
            note_type='retrospective',
        )
        recall = RecallService.build(sample_sold_diary.user)
        assert sample_sold_diary not in recall['unreviewed']
        assert recall['unreviewed_count'] == 0

    def test_holding_diary_not_in_unreviewed(self, sample_diary_with_transaction):
        """保有中の日記は振り返り対象外"""
        recall = RecallService.build(sample_diary_with_transaction.user)
        assert sample_diary_with_transaction not in recall['unreviewed']

    def test_recent_disclosure_listed(self, sample_diary):
        """直近7日以内の開示がある日記が出る"""
        sample_diary.latest_disclosure_date = date.today() - timedelta(days=2)
        sample_diary.save(update_fields=['latest_disclosure_date'])
        recall = RecallService.build(sample_diary.user)
        assert sample_diary in recall['disclosures']

    def test_old_disclosure_excluded(self, sample_diary):
        """8日以上前の開示は出ない"""
        sample_diary.latest_disclosure_date = date.today() - timedelta(days=20)
        sample_diary.save(update_fields=['latest_disclosure_date'])
        recall = RecallService.build(sample_diary.user)
        assert sample_diary not in recall['disclosures']

    def test_other_users_data_not_leaked(self, sample_sold_diary, another_user):
        """他ユーザーの日記は想起に出ない"""
        recall = RecallService.build(another_user)
        assert recall['has_content'] is False


class TestFindDuplicateDiaries:
    """重複日記検出ヘルパー"""

    def test_same_symbol_found(self, sample_diary):
        dup = find_duplicate_diaries(sample_diary.user, stock_symbol='7203')
        assert sample_diary in dup

    def test_other_user_not_found(self, sample_diary, another_user):
        dup = find_duplicate_diaries(another_user, stock_symbol='7203')
        assert sample_diary not in dup

    def test_name_match_only_when_symbol_empty(self, user):
        """コードなしメモはコード空同士の名前一致のみ"""
        memo = StockDiary.objects.create(user=user, stock_symbol='', stock_name='投資アイデア')
        assert memo in find_duplicate_diaries(user, stock_name='投資アイデア')
        # コード付き日記は名前では引っかからない
        StockDiary.objects.create(user=user, stock_symbol='7203', stock_name='トヨタ自動車')
        assert list(find_duplicate_diaries(user, stock_name='トヨタ自動車')) == []

    def test_empty_input_returns_none(self, user):
        assert list(find_duplicate_diaries(user)) == []


class TestCheckDuplicateAPI:
    """重複チェックAPIエンドポイント"""

    def test_duplicate_found(self, authenticated_client, sample_diary):
        url = reverse('stockdiary:api_check_duplicate')
        response = authenticated_client.get(url, {'symbol': '7203'})
        assert response.status_code == 200
        data = response.json()
        assert data['exists'] is True
        assert data['diaries'][0]['id'] == sample_diary.id
        assert data['diaries'][0]['status'] == 'メモ'

    def test_no_duplicate(self, authenticated_client, sample_diary):
        url = reverse('stockdiary:api_check_duplicate')
        response = authenticated_client.get(url, {'symbol': '9999'})
        assert response.json()['exists'] is False

    def test_requires_login(self, client):
        url = reverse('stockdiary:api_check_duplicate')
        response = client.get(url, {'symbol': '7203'})
        assert response.status_code == 302


class TestStockDiaryFormDuplicate:
    """フォームの重複チェック（新規作成時のみ・allow_duplicate で許可）"""

    def _form_data(self, **overrides):
        data = {
            'stock_symbol': '7203',
            'stock_name': 'トヨタ自動車',
            'reason': '再エントリー検討',
            'memo': '',
            'sector': '',
            'currency': 'JPY',
        }
        data.update(overrides)
        return data

    def test_duplicate_blocked_without_allow(self, sample_diary):
        form = StockDiaryForm(data=self._form_data(), user=sample_diary.user)
        assert not form.is_valid()
        assert 'stock_symbol' in form.errors
        assert form.duplicate_diary == sample_diary

    def test_duplicate_allowed_with_flag(self, sample_diary):
        form = StockDiaryForm(
            data=self._form_data(allow_duplicate='on'),
            user=sample_diary.user,
        )
        assert form.is_valid(), form.errors

    def test_no_duplicate_passes(self, user):
        form = StockDiaryForm(data=self._form_data(), user=user)
        assert form.is_valid(), form.errors

    def test_update_not_blocked(self, sample_diary):
        """既存日記の編集は重複チェック対象外"""
        form = StockDiaryForm(
            data=self._form_data(reason=sample_diary.reason),
            instance=sample_diary,
            user=sample_diary.user,
        )
        assert form.is_valid(), form.errors


class TestRetrospectiveNoteType:
    """note_type に retrospective が追加されている"""

    def test_retrospective_choice_exists(self):
        assert 'retrospective' in dict(DiaryNote.TYPE_CHOICES)

    def test_create_retrospective_note(self, sample_sold_diary):
        note = DiaryNote.objects.create(
            diary=sample_sold_diary,
            date=date.today(),
            content='振り返り',
            note_type='retrospective',
        )
        assert note.get_note_type_display() == '振り返り'
