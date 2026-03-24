"""
JPX信用倍率PDF解析デバッグコマンド

使い方:
  python manage.py debug_margin_pdf --date 2026-03-19
  python manage.py debug_margin_pdf --date 2026-03-19 --dump-rows 3
"""

import os
import tempfile
import requests
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'JPX信用残高PDFの解析状況を詳細に表示する（デバッグ用）'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, required=True,
                            help='対象日付（YYYY-MM-DD形式）')
        parser.add_argument('--dump-rows', type=int, default=3,
                            help='各テーブルの先頭N行を表示（デフォルト:3）')

    def handle(self, *args, **options):
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz

        try:
            target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
        except ValueError:
            raise CommandError(f"日付形式エラー: {options['date']}")

        from margin_tracking.services.jpx_margin_service import build_jpx_pdf_url
        pdf_url = build_jpx_pdf_url(target_date)
        self.stdout.write(f"URL: {pdf_url}\n")

        # ダウンロード
        self.stdout.write("PDFダウンロード中...")
        try:
            resp = requests.get(pdf_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
            }, timeout=60)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise CommandError(f"ダウンロード失敗: {e}")

        fd, path = tempfile.mkstemp(suffix='.pdf', prefix='jpx_debug_')
        with os.fdopen(fd, 'wb') as f:
            f.write(resp.content)
        self.stdout.write(f"ダウンロード完了: {len(resp.content):,} bytes\n")

        try:
            doc = fitz.open(path)
            total_pages = len(doc)
            self.stdout.write(f"=== ページ数: {total_pages} ===\n")

            dump_n = options['dump_rows']
            total_table_rows = 0
            total_text_rows = 0

            for page_num in range(total_pages):
                page = doc[page_num]
                self.stdout.write(f"\n--- ページ {page_num + 1}/{total_pages} ---")

                # テーブル抽出
                finder = page.find_tables()
                tables = getattr(finder, 'tables', None) or []
                self.stdout.write(f"  find_tables(): {len(tables)} テーブル")

                page_table_rows = 0
                for ti, table in enumerate(tables):
                    rows = table.extract()
                    self.stdout.write(f"  テーブル[{ti}]: {len(rows)} 行 × {len(rows[0]) if rows else 0} 列")
                    page_table_rows += len(rows)
                    for ri, row in enumerate(rows[:dump_n]):
                        self.stdout.write(f"    行[{ri}]: {row}")
                    if len(rows) > dump_n:
                        self.stdout.write(f"    ... 残り {len(rows) - dump_n} 行")
                total_table_rows += page_table_rows

                # テキスト行数（比較用）
                words = page.get_text("words")
                import re
                # 5桁コードで始まる行を数える
                five_digit_lines = set()
                for w in words:
                    if re.match(r'^\d{5}$', w[4]):
                        five_digit_lines.add(round(w[1]))  # Y座標でユニーク化
                self.stdout.write(f"  テキスト中の5桁コード行: {len(five_digit_lines)} 行")
                total_text_rows += len(five_digit_lines)

            doc.close()
            self.stdout.write(f"\n=== サマリー ===")
            self.stdout.write(f"  テーブル抽出 合計行数: {total_table_rows}")
            self.stdout.write(f"  テキスト中の5桁コード行数: {total_text_rows}（期待される銘柄数の目安）")

        finally:
            try:
                os.unlink(path)
            except Exception:
                pass
