"""決算予定（決算カレンダー）機能のテスト。

なぜこのテストがあるか:
  決算予定API（EDINET DB /v1/calendar）から日次取得した決算予定を、保有銘柄・
  ウォッチリスト・決算カレンダーに表示し、決算前日に通知する一連の流れを固定する。
  外部APIはモックし、画面表示時にAPIを叩かない（ローカルDB参照のみ）ことも担保する。

  検証する主な不変条件:
  - APIクライアントはフィールド名の揺れを吸収して正規化する
  - limit到達時は offset でページングして全件取得する
  - 同期は未来分を洗い替えし、過去分は履歴として残す
  - next_earnings_date が日記へ事前計算される（4桁/5桁コードの両方に対応）
  - 決算前日（翌日決算）の通知が記録ユーザーへ1通だけ届く（重複しない）
  - カレンダー画面は GET のみで描画でき、scope で記録銘柄/全銘柄を切り替えられる
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from stockdiary.models import StockDiary, NotificationLog
from earnings_analysis.models import EarningsSchedule
from earnings_analysis.services.earnings_calendar_api import (
    EarningsCalendarAPIService,
)
from earnings_analysis.services import earnings_calendar_sync as sync

User = get_user_model()
pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# APIクライアント（正規化・ページング）
# ---------------------------------------------------------------------------

def test_normalize_item_handles_field_name_variants():
    """提供元によるキー名の揺れ（secCode / announcement_date 等）を吸収する。"""
    raw = {
        'secCode': '7203',
        'companyName': 'トヨタ自動車',
        'announcement_date': '2026-08-05',
        'period_type': '第1四半期',
        'market': 'プライム',
    }
    item = EarningsCalendarAPIService._normalize_item(raw)
    assert item['securities_code'] == '7203'
    assert item['company_name'] == 'トヨタ自動車'
    assert item['earnings_date'] == date(2026, 8, 5)
    assert item['earnings_type'] == '第1四半期'
    assert item['market_segment'] == 'プライム'


def test_normalize_item_rejects_missing_code_or_date():
    """必須項目（コード・日付）が欠けたら捨てる（不完全データで落とさない）。"""
    assert EarningsCalendarAPIService._normalize_item({'name': 'x'}) is None
    assert EarningsCalendarAPIService._normalize_item(
        {'secCode': '7203'}  # 日付なし
    ) is None


def test_fetch_window_paginates_with_offset(settings):
    """返却件数が limit と等しい間は offset を進めて続きを取得する。"""
    settings.EARNINGS_CALENDAR_API_SETTINGS = {
        'API_KEY': 'k', 'BASE_URL': 'https://example.test',
        'CALENDAR_PATH': '/v1/calendar', 'AUTH_HEADER': 'X-API-Key',
        'AUTH_SCHEME': '', 'PAGE_LIMIT': 2, 'TIMEOUT': 5,
    }
    service = EarningsCalendarAPIService()

    pages = [
        # 1ページ目: limit(2)と同数 → 続きあり
        [{'secCode': '1111', 'date': '2026-07-01'},
         {'secCode': '2222', 'date': '2026-07-02'}],
        # 2ページ目: limit未満 → 終了
        [{'secCode': '3333', 'date': '2026-07-03'}],
    ]
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params['offset'])

        class Resp:
            status_code = 200

            def json(self_inner):
                idx = params['offset'] // 2
                return {'results': pages[idx] if idx < len(pages) else []}
        return Resp()

    with patch.object(service.session, 'get', side_effect=fake_get):
        items = service.fetch_window(days=90)

    assert calls == [0, 2]  # offset が 2 つ進んだ
    assert [i['securities_code'] for i in items] == ['1111', '2222', '3333']


# ---------------------------------------------------------------------------
# 同期（洗い替え・事前計算）
# ---------------------------------------------------------------------------

def test_sync_skips_when_unconfigured(settings):
    """APIキー未設定なら外部を叩かず0件で終わる（誤って公開APIを叩かない）。"""
    settings.EARNINGS_CALENDAR_API_SETTINGS = {'API_KEY': ''}
    assert sync.sync_earnings_calendar() == 0
    assert EarningsSchedule.objects.count() == 0


def test_sync_replaces_future_keeps_past(settings):
    """同期は未来分を洗い替えし、過去分（履歴）は残す。"""
    settings.EARNINGS_CALENDAR_API_SETTINGS = {'API_KEY': 'k'}
    today = date.today()

    # 既存: 過去1件 + 未来1件（未来分は洗い替え対象）
    EarningsSchedule.objects.create(
        securities_code='0001', earnings_date=today - timedelta(days=10),
    )
    EarningsSchedule.objects.create(
        securities_code='0002', earnings_date=today + timedelta(days=5),
    )

    new_items = [{
        'securities_code': '7203', 'company_name': 'トヨタ',
        'earnings_date': today + timedelta(days=20),
        'earnings_type': '本決算', 'market_segment': 'プライム',
        'source_updated_at': '',
    }]
    with patch.object(EarningsCalendarAPIService, 'fetch_window', return_value=new_items):
        saved = sync.sync_earnings_calendar(days=90)

    assert saved == 1
    codes = set(EarningsSchedule.objects.values_list('securities_code', flat=True))
    assert '0001' in codes          # 過去分は残る
    assert '0002' not in codes      # 未来分は洗い替えで消える
    assert '7203' in codes          # 新規が入る


def test_update_diary_next_earnings_matches_4_and_5_digit(settings):
    """4桁の日記コードに対し、4桁/末尾0付き5桁どちらの予定も照合できる。"""
    user = User.objects.create_user('u1', 'u1@e.com', 'p')
    d1 = StockDiary.objects.create(user=user, stock_name='A', stock_symbol='7203')
    d2 = StockDiary.objects.create(user=user, stock_name='B', stock_symbol='6758')
    today = date.today()

    # 7203 は4桁コードで、6758 は末尾0付き5桁コードで提供されるケース
    EarningsSchedule.objects.create(
        securities_code='7203', earnings_date=today + timedelta(days=10),
        earnings_type='第1四半期',
    )
    EarningsSchedule.objects.create(
        securities_code='67580', earnings_date=today + timedelta(days=3),
        earnings_type='本決算',
    )

    updated = sync.update_diary_next_earnings()
    assert updated == 2

    d1.refresh_from_db()
    d2.refresh_from_db()
    assert d1.next_earnings_date == today + timedelta(days=10)
    assert d1.next_earnings_type == '第1四半期'
    assert d2.next_earnings_date == today + timedelta(days=3)


def test_update_diary_next_earnings_picks_nearest_future(settings):
    """過去の予定は無視し、当日以降で最も近い予定を採用する。"""
    user = User.objects.create_user('u2', 'u2@e.com', 'p')
    d = StockDiary.objects.create(user=user, stock_name='A', stock_symbol='7203')
    today = date.today()
    EarningsSchedule.objects.create(
        securities_code='7203', earnings_date=today - timedelta(days=5))
    EarningsSchedule.objects.create(
        securities_code='7203', earnings_date=today + timedelta(days=40))
    EarningsSchedule.objects.create(
        securities_code='7203', earnings_date=today + timedelta(days=12))

    sync.update_diary_next_earnings()
    d.refresh_from_db()
    assert d.next_earnings_date == today + timedelta(days=12)


# ---------------------------------------------------------------------------
# 決算前日通知（ファンアウト・重複防止）
# ---------------------------------------------------------------------------

def test_fan_out_earnings_reminders_one_per_user_no_duplicate():
    """翌日決算の銘柄を記録するユーザーへ1通だけ通知し、再実行で重複しない。"""
    user = User.objects.create_user('u3', 'u3@e.com', 'p')
    # 同一銘柄の日記が2件あってもユーザーへの通知は1通
    StockDiary.objects.create(user=user, stock_name='A', stock_symbol='7203')
    StockDiary.objects.create(user=user, stock_name='A(別記録)', stock_symbol='7203')
    tomorrow = date.today() + timedelta(days=1)
    EarningsSchedule.objects.create(
        securities_code='7203', earnings_date=tomorrow, earnings_type='本決算')

    created = sync.fan_out_earnings_reminders()
    assert created == 1
    log = NotificationLog.objects.get(user=user)
    assert log.earnings_schedule is not None
    assert '明日が決算予定' in log.title

    # 再実行しても重複しない（(user, earnings_schedule) 一意制約 + ignore_conflicts）
    again = sync.fan_out_earnings_reminders()
    assert again == 0
    assert NotificationLog.objects.filter(user=user).count() == 1


def test_reminder_survives_schedule_wash_replace():
    """日次同期が未来の決算予定を洗い替えしても、送信済み通知は消えない。

    なぜこのテストがあるか:
      EarningsSchedule は毎日「当日以降」を delete→再投入で洗い替えする。通知の
      FK が CASCADE だと、決算前日に出した通知が翌日の同期で巻き添え削除され、
      ちょうど決算当日に履歴が消える。SET_NULL でそれを防ぐことを固定する。
    """
    user = User.objects.create_user('u_wash', 'uw@e.com', 'p')
    StockDiary.objects.create(user=user, stock_name='A', stock_symbol='7203')
    tomorrow = date.today() + timedelta(days=1)
    schedule = EarningsSchedule.objects.create(
        securities_code='7203', earnings_date=tomorrow)

    sync.fan_out_earnings_reminders()
    assert NotificationLog.objects.filter(user=user).count() == 1

    # 洗い替え（未来分の削除）
    schedule.delete()

    log = NotificationLog.objects.get(user=user)  # 残っている
    assert log.earnings_schedule is None           # FK は NULL に


def test_fan_out_excludes_excluded_diary():
    """除外フラグの日記しか持たないユーザーには通知しない。"""
    user = User.objects.create_user('u4', 'u4@e.com', 'p')
    StockDiary.objects.create(
        user=user, stock_name='A', stock_symbol='7203', is_excluded=True)
    tomorrow = date.today() + timedelta(days=1)
    EarningsSchedule.objects.create(securities_code='7203', earnings_date=tomorrow)

    assert sync.fan_out_earnings_reminders() == 0


# ---------------------------------------------------------------------------
# StockDiary プロパティ
# ---------------------------------------------------------------------------

def test_days_until_earnings_and_proximity():
    """残り日数と近さ区分が境界値で正しく分類される。"""
    user = User.objects.create_user('u5', 'u5@e.com', 'p')
    today = date.today()
    d = StockDiary.objects.create(user=user, stock_name='A', stock_symbol='7203')

    d.next_earnings_date = today + timedelta(days=2)
    assert d.days_until_earnings == 2
    assert d.earnings_proximity == 'imminent'

    d.next_earnings_date = today + timedelta(days=10)
    assert d.earnings_proximity == 'soon'

    d.next_earnings_date = today + timedelta(days=30)
    assert d.earnings_proximity == 'scheduled'

    # 過去日・未設定は None
    d.next_earnings_date = today - timedelta(days=1)
    assert d.days_until_earnings is None
    assert d.earnings_proximity is None
    d.next_earnings_date = None
    assert d.days_until_earnings is None


# ---------------------------------------------------------------------------
# カレンダー画面（GETのみ・APIを叩かない・scope切替）
# ---------------------------------------------------------------------------

def test_calendar_view_renders_without_calling_api(client):
    """画面表示は外部APIを一切叩かず、ローカルDBのみで描画する。"""
    user = User.objects.create_user('v1', 'v1@e.com', 'p')
    client.force_login(user)
    today = date.today()

    # 保有銘柄（取引あり想定の current_quantity>0 を直接設定）
    holding = StockDiary.objects.create(
        user=user, stock_name='保有株', stock_symbol='7203',
        current_quantity=100, transaction_count=2,
        next_earnings_date=today + timedelta(days=5), next_earnings_type='本決算',
    )
    # ウォッチ（メモ＝取引なし）
    watch = StockDiary.objects.create(
        user=user, stock_name='監視株', stock_symbol='6758',
        next_earnings_date=today + timedelta(days=9),
    )
    EarningsSchedule.objects.create(
        securities_code='7203', earnings_date=today + timedelta(days=5),
        company_name='保有株', earnings_type='本決算')

    url = reverse('stockdiary:earnings_calendar')
    with patch.object(EarningsCalendarAPIService, 'fetch_window') as mocked:
        resp = client.get(url)
        assert mocked.call_count == 0  # 表示でAPIは呼ばれない

    assert resp.status_code == 200
    assert holding.stock_name.encode() in resp.content
    assert watch.stock_name.encode() in resp.content


def test_calendar_scope_mine_filters_to_recorded_symbols(client):
    """scope=mine は記録銘柄のみ、scope=all は全銘柄を一覧する。"""
    user = User.objects.create_user('v2', 'v2@e.com', 'p')
    client.force_login(user)
    today = date.today()
    StockDiary.objects.create(
        user=user, stock_name='保有株', stock_symbol='7203',
        next_earnings_date=today + timedelta(days=5))

    EarningsSchedule.objects.create(
        securities_code='7203', earnings_date=today + timedelta(days=5),
        company_name='記録銘柄')
    EarningsSchedule.objects.create(
        securities_code='9999', earnings_date=today + timedelta(days=6),
        company_name='無関係銘柄')

    url = reverse('stockdiary:earnings_calendar')
    mine = client.get(url, {'scope': 'mine'}, HTTP_HX_REQUEST='true')
    assert '記録銘柄'.encode() in mine.content
    assert '無関係銘柄'.encode() not in mine.content

    everything = client.get(url, {'scope': 'all'}, HTTP_HX_REQUEST='true')
    assert '無関係銘柄'.encode() in everything.content


def test_calendar_view_requires_login(client):
    """未ログインはログインへリダイレクトする。"""
    resp = client.get(reverse('stockdiary:earnings_calendar'))
    assert resp.status_code in (301, 302)
