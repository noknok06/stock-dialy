# earnings_analysis/services/earnings_calendar_api.py
"""決算予定API（EDINET DB /v1/calendar）クライアント

商用利用可能な無料プラン（100リクエスト/日）の決算予定APIから、当日〜90日後の
決算発表予定を取得する。バッチ処理（日次1回）からのみ呼び出し、画面表示時は
このクライアントを使わない（ローカルDB参照）。

設計方針:
- エンドポイントURL・認証ヘッダーは settings.EARNINGS_CALENDAR_API_SETTINGS で
  差し替え可能にする（提供元の仕様変更や別プロバイダへの切り替えに耐える）。
- レスポンスのフィールド名は提供元により揺れがあるため、複数の候補キーから
  defensive に取り出して正規化する（_normalize_item）。
- limit=2000 で取得し、返却件数が limit と等しい間は offset を進めて続きを取得する。
"""
import logging
from datetime import date, timedelta

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# レスポンスの揺れに備えた候補キー（先勝ち）
_CODE_KEYS = ('securities_code', 'secCode', 'sec_code', 'code', 'ticker', 'stock_code')
_NAME_KEYS = ('company_name', 'companyName', 'name', 'filer_name', 'filerName')
_DATE_KEYS = (
    'earnings_date', 'announcement_date', 'scheduled_date', 'disclosed_date',
    'forecast_date', 'date',
)
_TYPE_KEYS = ('earnings_type', 'type', 'period_type', 'fiscal_period', 'quarter')
_MARKET_KEYS = ('market_segment', 'market', 'segment', 'market_division', 'market_code')
_UPDATED_KEYS = ('updated_at', 'updatedAt', 'modified', 'last_updated')


def _first(d: dict, keys) -> str:
    """候補キーのうち最初に見つかった非空の値を文字列で返す。"""
    for key in keys:
        if key in d and d[key] not in (None, ''):
            return str(d[key]).strip()
    return ''


class EarningsCalendarAPIError(Exception):
    """決算予定APIの呼び出し失敗。"""


class EarningsCalendarAPIService:
    """決算予定APIクライアント。"""

    def __init__(self):
        conf = getattr(settings, 'EARNINGS_CALENDAR_API_SETTINGS', {}) or {}
        self.api_key = conf.get('API_KEY', '')
        self.base_url = conf.get('BASE_URL', 'https://edinetdb.com').rstrip('/')
        self.calendar_path = conf.get('CALENDAR_PATH', '/v1/calendar')
        self.auth_header = conf.get('AUTH_HEADER', 'X-API-Key')
        self.auth_scheme = conf.get('AUTH_SCHEME', '')  # 例: 'Bearer'。空ならキーをそのまま
        self.page_limit = int(conf.get('PAGE_LIMIT', 2000))
        self.timeout = int(conf.get('TIMEOUT', 60))
        self.user_agent = conf.get(
            'USER_AGENT', 'KabulogEarningsCalendarBot/1.0 (https://kabu-log.net)'
        )

        self.session = requests.Session()
        headers = {'User-Agent': self.user_agent, 'Accept': 'application/json'}
        if self.api_key:
            value = f'{self.auth_scheme} {self.api_key}'.strip() if self.auth_scheme else self.api_key
            headers[self.auth_header] = value
        self.session.headers.update(headers)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}{self.calendar_path}"

    def fetch_window(self, days: int = 90) -> list:
        """当日〜days日後の決算予定を全件取得して正規化済みのリストで返す。

        Returns:
            list[dict]: {securities_code, company_name, earnings_date(date),
                         earnings_type, market_segment, source_updated_at(str)}
        """
        today = date.today()
        date_from = today.isoformat()
        date_to = (today + timedelta(days=days)).isoformat()

        items = []
        offset = 0
        while True:
            page = self._fetch_page(date_from, date_to, offset)
            if not page:
                break
            items.extend(page)
            # 返却件数が limit 未満なら最終ページ
            if len(page) < self.page_limit:
                break
            offset += self.page_limit
            # 無料枠保護のための安全弁（90日で2000件超×n回は通常あり得ない）
            if offset > self.page_limit * 20:
                logger.warning('決算予定API: offset上限に達したため打ち切り（offset=%s）', offset)
                break

        normalized = []
        for raw in items:
            item = self._normalize_item(raw)
            if item:
                normalized.append(item)
        logger.info('決算予定API取得: 生%s件 → 正規化%s件', len(items), len(normalized))
        return normalized

    def _fetch_page(self, date_from: str, date_to: str, offset: int) -> list:
        params = {
            'from': date_from,
            'to': date_to,
            'limit': self.page_limit,
            'offset': offset,
        }
        try:
            resp = self.session.get(self.endpoint, params=params, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise EarningsCalendarAPIError(f'決算予定API通信エラー: {e}') from e

        if resp.status_code != 200:
            raise EarningsCalendarAPIError(
                f'決算予定API HTTPエラー: status={resp.status_code} body={resp.text[:300]}'
            )
        try:
            data = resp.json()
        except ValueError as e:
            raise EarningsCalendarAPIError(f'決算予定API JSONパース失敗: {e}') from e

        return self._extract_results(data)

    @staticmethod
    def _extract_results(data) -> list:
        """レスポンスのトップレベルから結果リストを取り出す。"""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ('results', 'data', 'items', 'calendar', 'records'):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    @staticmethod
    def _normalize_item(raw: dict):
        """1件の生データを正規化する。必須項目（コード・日付）が欠けたら None。"""
        if not isinstance(raw, dict):
            return None

        code = _first(raw, _CODE_KEYS)
        date_str = _first(raw, _DATE_KEYS)
        if not code or not date_str:
            return None

        parsed = EarningsCalendarAPIService._parse_date(date_str)
        if parsed is None:
            return None

        return {
            'securities_code': code,
            'company_name': _first(raw, _NAME_KEYS),
            'earnings_date': parsed,
            'earnings_type': _first(raw, _TYPE_KEYS),
            'market_segment': _first(raw, _MARKET_KEYS),
            'source_updated_at': _first(raw, _UPDATED_KEYS),
        }

    @staticmethod
    def _parse_date(value: str):
        """ISO（YYYY-MM-DD）/ スラッシュ区切りの日付を date に変換。"""
        from datetime import datetime

        value = value.strip()[:10]
        for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None
