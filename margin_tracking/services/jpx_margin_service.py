"""
JPX 信用取引残高 PDF 取得・解析サービス

データソース:
  https://www.jpx.co.jp/markets/statistics-equities/margin/
  URL形式: syumatsu{YYYYMMDD}00.pdf
  例: syumatsu2026031900.pdf (2026年3月19日申込分)

PDFの構造:
  - 銘柄コード: 5桁（末尾1桁は不要。先頭4桁が証券コード）
  - 合計欄: 売り残高・買い残高・信用倍率
  - 信用倍率 = 買い残高 / 売り残高

取得するデータ:
  - 銘柄コード（4桁）
  - 銘柄名
  - 合計の売り残高
  - 合計の買い残高
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
    PyMuPDFを使ってPDFからテーブルデータを抽出する。
    """

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
            records = self._parse_page(page, page_num)
            all_records.extend(records)

        doc.close()
        logger.info(f"PDF解析完了: {total_pages} ページ / {len(all_records)} 件")
        return all_records

    def _parse_page(self, page, page_num: int) -> List[Dict]:
        """
        1ページ分のデータを解析する。

        テーブル解析とテキスト解析を両方実行し、より多くの件数を返す方を採用する。
        find_tables() は JPX PDF の複雑なレイアウトで一部しか取れない場合があるため、
        テキストベース解析を常に実行して比較する。
        """
        table_records: List[Dict] = []
        text_records: List[Dict] = []

        # テーブル解析（PyMuPDF >= 1.23）
        try:
            finder = page.find_tables()
            table_list = getattr(finder, 'tables', None) or []
            for table in table_list:
                table_records.extend(self._extract_from_table(table))
            logger.debug(
                f"ページ {page_num}: テーブル={len(table_list)}個 → {len(table_records)} 件"
            )
        except (AttributeError, TypeError):
            pass

        # テキスト行ベース解析（常に実行）
        text_records = self._parse_page_text(page, page_num)
        logger.debug(f"ページ {page_num}: テキスト → {len(text_records)} 件")

        # より多くの件数を返す方を採用
        if len(table_records) >= len(text_records):
            logger.info(f"  ページ {page_num + 1}: テーブル解析採用 {len(table_records)} 件")
            return table_records
        else:
            logger.info(f"  ページ {page_num + 1}: テキスト解析採用 {len(text_records)} 件（テーブル={len(table_records)}）")
            return text_records

    def _extract_from_table(self, table) -> List[Dict]:
        """PyMuPDFのTableオブジェクトからデータを抽出する"""
        records = []
        try:
            df = table.to_pandas()
            records = self._extract_from_dataframe(df)
        except Exception:
            # pandasが使えない場合はセルデータを直接処理
            try:
                rows = table.extract()
                records = self._extract_from_rows(rows)
            except Exception as e:
                logger.debug(f"テーブル抽出エラー: {e}")
        return records

    def _extract_from_dataframe(self, df) -> List[Dict]:
        """DataFrameから信用残高データを抽出する"""
        records = []
        # 列数チェック: 銘柄コード+銘柄名+各市場(5列)×複数市場+合計(3列)
        # 合計は最後の3列: 売り残高, 買い残高, 信用倍率
        if len(df.columns) < 5:
            return records

        for _, row in df.iterrows():
            record = self._extract_from_row_values(list(row.values))
            if record:
                records.append(record)
        return records

    def _extract_from_rows(self, rows: List) -> List[Dict]:
        """生のセルデータ行リストからデータを抽出する"""
        records = []
        for row in rows:
            if row is None:
                continue
            record = self._extract_from_row_values(row)
            if record:
                records.append(record)
        return records

    def _extract_from_row_values(self, values: List) -> Optional[Dict]:
        """
        1行分のセル値リストからデータを抽出する。

        JPXのPDF列構造（典型例）:
          [0] 銘柄コード(5桁)
          [1] 銘柄名
          [2-6]  東証: 売前週比, 売残高, 買前週比, 買残高, 倍率
          [7-11] 名証: 同上
          [12-16] 福証: 同上
          [17-21] 札証: 同上
          [22] 合計: 売残高
          [23] 合計: 買残高
          [24] 合計: 信用倍率
        """
        if not values or len(values) < 5:
            return None

        # 銘柄コード（先頭セル）
        raw_code = str(values[0]).strip() if values[0] else ''
        code_match = re.match(r'^(\d{4})\d$', raw_code)
        if not code_match:
            # 5桁でない場合、4桁の証券コードの可能性も確認
            code4_match = re.match(r'^(\d{4})$', raw_code)
            if not code4_match:
                return None
            stock_code = raw_code
        else:
            stock_code = code_match.group(1)

        # 銘柄名（2番目のセル）
        stock_name = str(values[1]).strip() if len(values) > 1 and values[1] else ''
        # 制御文字・余分な空白を除去
        stock_name = re.sub(r'[\x00-\x1f\x7f]', '', stock_name).strip()

        # 合計欄: 末尾から整数の売り残・買い残を探す
        # 注意: 末尾の「信用倍率」列は小数（例: 2.54）または「―」
        #       小数はスキップ、空欄/Noneはスキップ、非数値セルで終了
        int_vals = []
        for v in reversed(values):
            s = str(v).strip().replace(',', '')
            # 空・欠損・記号はスキップ
            if s in ('', 'None', 'nan', '―', '-', '△'):
                continue
            # 整数（コンマ区切りを除いた後）
            if re.match(r'^\d+$', s):
                int_vals.append(int(s))
                if len(int_vals) >= 2:
                    break  # 買残・売残の2つが揃ったら終了
                continue
            # 小数（信用倍率など）はスキップして続行
            if re.match(r'^\d+\.\d+$', s):
                continue
            # それ以外の文字列は合計欄を過ぎたと判断して終了
            break

        if len(int_vals) < 2:
            return None

        # int_vals[0] = 買残高（末尾から最初に見つかった整数）
        # int_vals[1] = 売残高（2番目に見つかった整数）
        long_balance = int_vals[0]
        short_balance = int_vals[1]

        if short_balance < 0 or long_balance < 0:
            return None

        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'short_balance': short_balance,
            'long_balance': long_balance,
        }

    def _parse_page_text(self, page, page_num: int) -> List[Dict]:
        """
        テキスト抽出ベースのフォールバックパーサー。
        ページの各行を解析して信用残高データを抽出する。
        """
        records = []
        # "words" モードで単語と座標を取得
        words = page.get_text("words")  # [(x0, y0, x1, y1, word, block, line, word_idx), ...]

        if not words:
            return records

        # Y座標でグループ化（同じ行の単語をまとめる）
        lines = self._group_words_by_line(words)

        for line_words in lines:
            record = self._parse_text_line(line_words)
            if record:
                records.append(record)

        return records

    def _group_words_by_line(self, words: List) -> List[List]:
        """Y座標が近い単語を同じ行としてグループ化する"""
        if not words:
            return []

        # Y0座標でソート
        sorted_words = sorted(words, key=lambda w: (round(w[1] / 3), w[0]))

        lines = []
        current_line = [sorted_words[0]]
        current_y = sorted_words[0][1]

        for word in sorted_words[1:]:
            if abs(word[1] - current_y) < 3:  # 3pt以内は同一行
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]
                current_y = word[1]
        lines.append(current_line)

        return lines

    def _parse_text_line(self, line_words: List) -> Optional[Dict]:
        """
        1行分の単語リストから銘柄コードと残高データを抽出する。
        先頭に5桁コードがある行のみ処理する。
        """
        if not line_words:
            return None

        # X座標でソート
        sorted_words = sorted(line_words, key=lambda w: w[0])
        texts = [w[4] for w in sorted_words]

        if not texts:
            return None

        # 先頭が5桁の数字であること
        raw_code = texts[0]
        code_match = re.match(r'^(\d{4})\d$', raw_code)
        if not code_match:
            return None
        stock_code = code_match.group(1)

        # 銘柄名（数字以外の連続テキスト）
        stock_name = ''
        name_parts = []
        for t in texts[1:]:
            if re.match(r'^[\d,]+$', t) or t in ('―', '-', '△'):
                break
            name_parts.append(t)
        stock_name = ''.join(name_parts)

        # 数値を後ろから収集（合計欄 = 最後の整数群）
        numbers = []
        for t in texts:
            clean = t.replace(',', '').replace('△', '-')
            if re.match(r'^-?\d+$', clean):
                numbers.append(int(clean))

        if len(numbers) < 2:
            return None

        # 最後の2整数値が合計欄の買残・売残
        long_balance = numbers[-1]
        short_balance = numbers[-2]

        if short_balance < 0 or long_balance < 0:
            return None

        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'short_balance': short_balance,
            'long_balance': long_balance,
        }


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
