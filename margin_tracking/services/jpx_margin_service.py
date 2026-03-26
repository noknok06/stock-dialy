"""
JPX 信用取引残高 PDF 取得・解析サービス

データソース:
  https://www.jpx.co.jp/markets/statistics-equities/margin/
  URL形式: syumatsu{YYYYMMDD}00.pdf
  例: syumatsu2026031900.pdf (2026年3月19日申込分)

PDFの実際の構造（横向きA3 / 1値1行形式）:
  各ページは横向きで、銘柄ごとにデータが縦に並ぶ。
  get_text("text") で取得すると以下の順序で1行ずつ出力される:

    B                         ← 市場区分（B=東証等）
    大和ハウス工業　普通株式    ← 銘柄名
    19250                     ← 5桁コード（先頭4桁が証券コード）
    JP3505000004              ← ISINコード
    70,200                    ← [0] 合計 売残高  ← 取得
    15,200                    ← [1] 合計 売前週比
    265,000                   ← [2] 合計 買残高  ← 取得
    15,900                    ← [3] 合計 買前週比
    48,000                    ← [4] 一般信用 売残高
    ...（残り8値）

取得するデータ:
  - 銘柄コード（4桁）
  - 銘柄名
  - 合計の売り残高（nums[0]）
  - 合計の買い残高（nums[2]）
"""

import re
import logging
import requests
import os
import tempfile
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple

try:
    import pymupdf as fitz
except ImportError:
    import fitz

logger = logging.getLogger(__name__)

# JPX信用残高PDFのURLパターン
JPX_MARGIN_PDF_BASE_URL = (
    'https://www.jpx.co.jp/markets/statistics-equities/margin/'
    'tvdivq0000001rnl-att/syumatsu{date}00.pdf'
)


def build_jpx_pdf_url(record_date: date) -> str:
    """指定日付のJPX信用残高PDFのURLを生成"""
    date_str = record_date.strftime('%Y%m%d')
    return JPX_MARGIN_PDF_BASE_URL.format(date=date_str)


def get_recent_dates(days: int = 40) -> List[date]:
    """
    直近N日分の日付リストを返す（古い順）。
    JPXの公開日は木曜が多いが固定ではないため、毎日総当たりで確認する。
    """
    today = date.today()
    return [today - timedelta(days=i) for i in range(days - 1, -1, -1)]


class JPXMarginPDFParser:
    """
    JPX 信用取引残高PDFのパーサー。

    PDFは横向き（landscape）で、各銘柄のデータが縦方向に1値1行で格納されている。
    PyMuPDF の get_text("text") でページ全体のテキストを取得し、
    5桁コードを起点にして前後の行から銘柄名・残高を抽出する。
    """

    # 各銘柄の数値列数（合計売前週比〜制度信用買前週比まで12列）
    _NUM_COLS = 12

    def parse_pdf_file(self, pdf_path: str) -> List[Dict]:
        """
        PDFファイルからすべての銘柄の信用残高データを抽出する。

        Returns:
            [
                {
                    'stock_code': '1234',      # 4桁証券コード
                    'stock_name': '銘柄名',
                    'short_balance': 1000,      # 売り残高（合計）
                    'long_balance':  2000,      # 買い残高（合計）
                },
                ...
            ]
        """
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            logger.error(f"PDFオープン失敗: {pdf_path} - {e}")
            return []

        total_pages = len(doc)
        logger.info(f"PDF解析開始: {total_pages} ページ")
        all_records = []
        for page_num in range(total_pages):
            page = doc[page_num]
            records = self._parse_page(page)
            all_records.extend(records)
            if records:
                logger.debug(f"  ページ {page_num + 1}: {len(records)} 件")

        doc.close()
        logger.info(f"PDF解析完了: {total_pages} ページ / {len(all_records)} 件")
        return all_records

    def _parse_page(self, page) -> List[Dict]:
        """
        1ページ分のテキストを解析する。

        get_text("text") でページ全テキストを取得し、行単位でパースする。
        各銘柄レコードは以下の行順序で出現する:
          [市場区分 1文字] [銘柄名] [5桁コード] [ISIN] [数値×12]
        """
        raw_text = page.get_text("text")
        if not raw_text:
            return []

        lines = [ln.strip() for ln in raw_text.split('\n')]
        records = []
        i = 0
        n = len(lines)

        while i < n:
            # 5桁コード行を探す
            if not re.match(r'^\d{5}$', lines[i]):
                i += 1
                continue

            stock_code = lines[i][:4]  # 先頭4桁が証券コード

            # 銘柄名: コードの直前の行を逆方向に探す
            stock_name = self._find_stock_name(lines, i)

            i += 1  # 5桁コードの次へ

            # ISINコード（JP...）をスキップ
            if i < n and re.match(r'^JP[A-Z0-9]+$', lines[i]):
                i += 1

            # 数値を最大12個収集
            nums, i = self._collect_nums(lines, i, n)

            # nums[0]=合計売残高, nums[2]=合計買残高
            if len(nums) >= 3 and nums[0] is not None and nums[2] is not None:
                records.append({
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'short_balance': nums[0],
                    'long_balance': nums[2],
                })

        return records

    def _find_stock_name(self, lines: List[str], code_idx: int) -> str:
        """5桁コード行の直前から銘柄名を探す（逆方向）"""
        j = code_idx - 1
        while j >= 0:
            line = lines[j]
            # 空行・1文字市場区分・ISINコード・数値行はスキップ
            if (not line
                    or re.match(r'^[A-Za-z]$', line)
                    or re.match(r'^JP[A-Z0-9]+$', line)
                    or re.match(r'^\d', line)):
                j -= 1
                continue
            # 制御文字除去して返す
            return re.sub(r'[\x00-\x1f\x7f]', '', line).strip()
        return ''

    def _collect_nums(self, lines: List[str], start: int, end: int) -> Tuple[List, int]:
        """
        start行目から数値を最大 _NUM_COLS 個収集する。

        対応フォーマット:
          正の整数: 70,200 → 70200
          変化量（負）: ▲3,200 or △3,200 → -3200（不使用だが収集）
          欠損: ―, -, 0
        非数値行に当たったら収集終了。
        """
        nums: List[Optional[int]] = []
        i = start
        while i < end and len(nums) < self._NUM_COLS:
            val = lines[i]

            # ▲NNN または △NNN（負の変化量）
            # ▲ (U+25B2, 黒三角) と △ (U+25B3, 白三角) の両方に対応
            if '▲' in val or '△' in val:
                clean = val.replace('▲', '').replace('△', '').replace(',', '').strip()
                if re.match(r'^\d+$', clean):
                    nums.append(-int(clean))
                    i += 1
                    continue
                # 記号だけで数字がない → 次の行が数値の場合がある
                i += 1
                continue

            clean = val.replace(',', '')
            if re.match(r'^\d+$', clean):
                nums.append(int(clean))
                i += 1
                continue

            # 欠損記号
            if val in ('―', '-', '－', ''):
                nums.append(None)
                i += 1
                continue

            # 数値でも欠損でもない → 次の銘柄の開始または列見出し
            break

        return nums, i

class JPXMarginService:
    """
    JPX信用倍率データの取得・保存を管理するサービス。
    """

    def __init__(self):
        self.parser = JPXMarginPDFParser()

    def fetch_and_save(self, record_date: date, force: bool = False) -> Dict:
        """
        指定日のJPX信用残高PDFを取得してDBに保存する。

        Args:
            record_date: 申込日（木曜日）
            force:       既存データがある場合も上書き

        Returns:
            {
                'success': bool,
                'created': int,
                'updated': int,
                'total': int,
                'pdf_url': str,
                'error': str or None,
            }
        """
        from django.utils import timezone
        from margin_tracking.models import MarginData, MarginFetchLog

        pdf_url = build_jpx_pdf_url(record_date)
        logger.info(f"信用残高データ取得開始: {record_date} ({pdf_url})")

        # 取得ログを作成（または更新）
        log, _ = MarginFetchLog.objects.get_or_create(
            record_date=record_date,
            defaults={'pdf_url': pdf_url, 'status': 'running'},
        )
        if log.status == 'success' and not force:
            logger.info(f"既に取得済み: {record_date} (force=Falseのためスキップ)")
            return {
                'success': True,
                'created': 0,
                'updated': 0,
                'total': log.total_records,
                'pdf_url': pdf_url,
                'error': None,
                'skipped': True,
            }

        log.status = 'running'
        log.pdf_url = pdf_url
        log.error_message = ''
        log.save(update_fields=['status', 'pdf_url', 'error_message'])

        # PDF取得
        pdf_path, not_found = self._download_pdf(pdf_url)
        if not pdf_path:
            if not_found:
                # 404 = JPXが当該週のデータを未公開（祝日・休場等）。正常扱い。
                log.status = 'failed'
                log.error_message = 'PDF未公開 (404)'
                log.completed_at = timezone.now()
                log.save(update_fields=['status', 'error_message', 'completed_at'])
                return {'success': False, 'created': 0, 'updated': 0, 'total': 0,
                        'pdf_url': pdf_url, 'error': None, 'not_found': True}
            error_msg = f"PDFダウンロード失敗: {pdf_url}"
            logger.error(error_msg)
            log.status = 'failed'
            log.error_message = error_msg
            log.completed_at = timezone.now()
            log.save(update_fields=['status', 'error_message', 'completed_at'])
            return {'success': False, 'created': 0, 'updated': 0, 'total': 0,
                    'pdf_url': pdf_url, 'error': error_msg, 'not_found': False}

        # PDF解析
        try:
            records = self.parser.parse_pdf_file(pdf_path)
        except Exception as e:
            error_msg = f"PDF解析エラー: {e}"
            logger.error(error_msg, exc_info=True)
            log.status = 'failed'
            log.error_message = error_msg
            log.completed_at = timezone.now()
            log.save(update_fields=['status', 'error_message', 'completed_at'])
            return {'success': False, 'created': 0, 'updated': 0, 'total': 0,
                    'pdf_url': pdf_url, 'error': error_msg}
        finally:
            # 一時ファイル削除
            try:
                os.unlink(pdf_path)
            except Exception:
                pass

        if not records:
            error_msg = "PDFからデータを抽出できませんでした"
            logger.warning(f"{error_msg}: {pdf_url}")
            log.status = 'failed'
            log.error_message = error_msg
            log.completed_at = timezone.now()
            log.save(update_fields=['status', 'error_message', 'completed_at'])
            return {'success': False, 'created': 0, 'updated': 0, 'total': 0,
                    'pdf_url': pdf_url, 'error': error_msg}

        # DB保存
        created_count, updated_count = self._save_records(records, record_date, force)

        # ログ更新
        total = created_count + updated_count
        log.status = 'success'
        log.records_created = created_count
        log.records_updated = updated_count
        log.total_records = total
        log.completed_at = timezone.now()
        log.save(update_fields=['status', 'records_created', 'records_updated',
                                'total_records', 'completed_at'])

        logger.info(
            f"信用残高データ保存完了: {record_date} "
            f"新規={created_count} 更新={updated_count} 合計={total}"
        )
        return {
            'success': True,
            'created': created_count,
            'updated': updated_count,
            'total': total,
            'pdf_url': pdf_url,
            'error': None,
        }

    def _download_pdf(self, url: str) -> Tuple[Optional[str], bool]:
        """
        PDFをダウンロードして一時ファイルパスを返す。

        Returns:
            (path, not_found)
            - path: ダウンロード済みの一時ファイルパス。失敗時はNone。
            - not_found: True = 404（未公開）。False = その他エラー。
        """
        try:
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                )
            }
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()

            # 一時ファイルに保存
            fd, path = tempfile.mkstemp(suffix='.pdf', prefix='jpx_margin_')
            with os.fdopen(fd, 'wb') as f:
                f.write(response.content)

            logger.info(f"PDFダウンロード完了: {len(response.content)} bytes -> {path}")
            return path, False

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.info(f"PDF未公開 (404): {url}")
                return None, True  # 未公開は正常扱い
            logger.error(f"PDFダウンロードHTTPエラー: {e}")
            return None, False
        except requests.exceptions.RequestException as e:
            logger.error(f"PDFダウンロードエラー: {e}")
            return None, False

    def _save_records(
        self, records: List[Dict], record_date: date, force: bool
    ) -> Tuple[int, int]:
        """抽出したレコードをDBに保存する。重複は更新する。"""
        from margin_tracking.models import MarginData

        created_count = 0
        updated_count = 0

        for rec in records:
            stock_code = rec['stock_code']
            defaults = {
                'stock_name': rec.get('stock_name', ''),
                'short_balance': rec['short_balance'],
                'long_balance': rec['long_balance'],
            }

            if force:
                obj, created = MarginData.objects.update_or_create(
                    record_date=record_date,
                    stock_code=stock_code,
                    defaults=defaults,
                )
            else:
                obj, created = MarginData.objects.get_or_create(
                    record_date=record_date,
                    stock_code=stock_code,
                    defaults=defaults,
                )
                if not created:
                    # 既存データは更新しない（forceなし）
                    continue

            if created:
                created_count += 1
            else:
                updated_count += 1

        return created_count, updated_count
