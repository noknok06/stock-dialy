# management/commands/import_jpx_split_batch.py
import requests
import pdfplumber
import re
import tempfile
import os
import gc
import warnings
import time
import subprocess
import sys
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.conf import settings
from margin_trading.models import MarketIssue, MarginTradingData, DataImportLog

# 警告抑制
warnings.filterwarnings('ignore')
import logging
logging.getLogger('pdfplumber').setLevel(logging.ERROR)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

class Command(BaseCommand):
    help = '分割バッチ処理でJPXデータを取得（メモリ安全版）'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, help='取得対象日付 (YYYYMMDD形式)')
        parser.add_argument('--force', action='store_true', help='強制実行')
        parser.add_argument('--pages-per-batch', type=int, default=10, help='バッチあたりのページ数（デフォルト: 10）')
        parser.add_argument('--batch-size', type=int, default=20, help='データ保存バッチサイズ（デフォルト: 20）')
        parser.add_argument('--cleanup-interval', type=int, default=30, help='バッチ間の待機秒数（デフォルト: 30）')
        parser.add_argument('--coordinator', action='store_true', help='コーディネーター（分割実行管理）モード')
        parser.add_argument('--worker', action='store_true', help='ワーカー（個別処理）モード')
        parser.add_argument('--start-page', type=int, help='開始ページ（ワーカーモード用）')
        parser.add_argument('--end-page', type=int, help='終了ページ（ワーカーモード用）')
        parser.add_argument('--pdf-path', type=str, help='PDFファイルパス（ワーカーモード用）')

    def handle(self, *args, **options):
        target_date = options.get('date')
        force = options.get('force', False)
        
        if target_date:
            try:
                target_date = datetime.strptime(target_date, '%Y%m%d').date()
            except ValueError:
                raise CommandError('日付は YYYYMMDD 形式で指定してください')
        else:
            target_date = date.today()
        
        # ワーカーモードの場合
        if options.get('worker'):
            return self._worker_mode(options, target_date)
        
        # コーディネーターモード（デフォルト）
        return self._coordinator_mode(options, target_date, force)

    def _coordinator_mode(self, options, target_date, force):
        """コーディネーター：分割実行を管理"""
        pages_per_batch = options.get('pages_per_batch', 10)
        cleanup_interval = options.get('cleanup_interval', 30)
        batch_size = options.get('batch_size', 20)
        
        self.stdout.write("=" * 60)
        self.stdout.write(f"🚀 分割バッチ処理開始: {target_date}")
        self.stdout.write(f"📊 設定: {pages_per_batch}ページ/バッチ, {cleanup_interval}秒間隔")
        self.stdout.write("=" * 60)
        
        # 既存データチェック
        existing_count = MarginTradingData.objects.filter(date=target_date).count()
        if not force and existing_count > 0:
            self.stdout.write(
                self.style.WARNING(f'既存データ {existing_count}件あり。--force で上書き可能'))
            return
        
        # PDF取得
        pdf_url = self._generate_pdf_url(target_date)
        pdf_path = self._download_pdf(pdf_url)
        
        try:
            # 総ページ数取得
            total_pages = self._get_total_pages(pdf_path)
            self.stdout.write(f"📄 総ページ数: {total_pages}")
            
            # 既存データ削除（force時）
            if force and existing_count > 0:
                MarginTradingData.objects.filter(date=target_date).delete()
                self.stdout.write(f"🗑️ 既存データ {existing_count}件削除")
            
            # バッチ実行計画
            batches = []
            for start_page in range(0, total_pages, pages_per_batch):
                end_page = min(start_page + pages_per_batch, total_pages)
                batches.append((start_page, end_page))
            
            self.stdout.write(f"📦 実行予定: {len(batches)}バッチ")
            for i, (start, end) in enumerate(batches):
                self.stdout.write(f"  バッチ{i+1}: ページ{start+1}-{end}")
            
            # バッチ実行
            total_records = 0
            success_batches = 0
            
            for batch_num, (start_page, end_page) in enumerate(batches, 1):
                self.stdout.write(f"\n🔄 バッチ{batch_num}/{len(batches)} 実行中...")
                self.stdout.write(f"📄 対象: ページ{start_page+1}-{end_page}")
                
                try:
                    # ワーカープロセス実行
                    records = self._execute_worker_batch(
                        pdf_path, target_date, start_page, end_page, batch_size
                    )
                    
                    total_records += records
                    success_batches += 1
                    
                    self.stdout.write(f"✅ バッチ{batch_num}完了: {records}件取得")
                    self.stdout.write(f"📈 累計: {total_records}件")
                    
                    # バッチ間待機（システム回復）
                    if batch_num < len(batches):
                        self.stdout.write(f"⏳ {cleanup_interval}秒待機中...")
                        time.sleep(cleanup_interval)
                        
                        # システムリソース確認
                        if PSUTIL_AVAILABLE:
                            self._log_system_status()
                
                except Exception as e:
                    self.stdout.write(f"❌ バッチ{batch_num}でエラー: {str(e)}")
                    continue
            
            # 結果報告
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(f"🎉 分割バッチ処理完了!")
            self.stdout.write(f"✅ 成功バッチ: {success_batches}/{len(batches)}")
            self.stdout.write(f"📊 総取得件数: {total_records}件")
            
            # ログ記録
            DataImportLog.objects.create(
                date=target_date,
                status='SUCCESS',
                message=f'分割バッチで{total_records}件取得（{success_batches}/{len(batches)}バッチ成功）',
                records_count=total_records,
                pdf_url=pdf_url
            )
            
        finally:
            # PDF削除
            os.unlink(pdf_path)

    def _worker_mode(self, options, target_date):
        """ワーカー：指定ページ範囲のみ処理"""
        pdf_path = options.get('pdf_path')
        start_page = options.get('start_page')
        end_page = options.get('end_page')
        batch_size = options.get('batch_size', 20)
        
        if not all([pdf_path, start_page is not None, end_page is not None]):
            raise CommandError('ワーカーモードには --pdf-path, --start-page, --end-page が必要')
        
        self.stdout.write(f"🔧 ワーカー開始: ページ{start_page+1}-{end_page}")
        
        # メモリ使用量ログ
        self._log_memory("ワーカー開始")
        
        records_count = 0
        batch_data = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num in range(start_page, min(end_page, len(pdf.pages))):
                    self.stdout.write(f"📄 ページ{page_num+1}処理中...")
                    
                    page = pdf.pages[page_num]
                    
                    try:
                        tables = page.extract_tables()
                        if tables:
                            for table in tables:
                                for row in table:
                                    if self._is_data_row(row):
                                        try:
                                            data_dict = self._parse_data_row(row)
                                            batch_data.append(data_dict)
                                            
                                            # バッチ保存
                                            if len(batch_data) >= batch_size:
                                                self._save_batch(batch_data, target_date)
                                                records_count += len(batch_data)
                                                batch_data = []
                                                gc.collect()
                                                
                                        except Exception as e:
                                            continue
                    except Exception as e:
                        self.stdout.write(f"⚠️ ページ{page_num+1}でエラー: {str(e)}")
                        continue
                    
                    # ページごとにメモリクリーンアップ
                    del page
                    gc.collect()
            
            # 残りデータ保存
            if batch_data:
                self._save_batch(batch_data, target_date)
                records_count += len(batch_data)
            
            self._log_memory("ワーカー完了")
            self.stdout.write(f"✅ ワーカー完了: {records_count}件")
            
            # 結果を標準出力に出力（親プロセスが読み取り）
            print(f"WORKER_RESULT:{records_count}")
            
        except Exception as e:
            self.stdout.write(f"❌ ワーカーエラー: {str(e)}")
            print("WORKER_RESULT:0")
            raise

    def _execute_worker_batch(self, pdf_path, target_date, start_page, end_page, batch_size):
        """ワーカープロセスを実行"""
        cmd = [
            sys.executable, 'manage.py', 'import_jpx_margin_data',
            '--worker',
            '--pdf-path', pdf_path,
            '--start-page', str(start_page),
            '--end-page', str(end_page),
            '--batch-size', str(batch_size),
            '--date', target_date.strftime('%Y%m%d')
        ]
        
        self.stdout.write(f"🚀 ワーカー実行: {' '.join(cmd[-8:])}")
        
        # プロセス実行
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # 出力をリアルタイム表示
        records_count = 0
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                line = output.strip()
                if line.startswith('WORKER_RESULT:'):
                    records_count = int(line.split(':')[1])
                else:
                    self.stdout.write(f"  {line}")
        
        return_code = process.poll()
        if return_code != 0:
            raise Exception(f"ワーカープロセスが失敗しました（終了コード: {return_code}）")
        
        return records_count

    def _download_pdf(self, pdf_url):
        """PDF ダウンロード"""
        self.stdout.write('📥 PDFダウンロード開始...')
        
        response = requests.get(pdf_url, timeout=60, stream=True)
        response.raise_for_status()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            total_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
                total_size += len(chunk)
            
            self.stdout.write(f'✅ ダウンロード完了: {total_size/1024/1024:.1f}MB')
            return tmp_file.name

    def _get_total_pages(self, pdf_path):
        """総ページ数取得"""
        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)

    def _generate_pdf_url(self, target_date):
        """PDF URLを生成"""
        date_str = target_date.strftime('%Y%m%d')
        base_url = 'https://www.jpx.co.jp/markets/statistics-equities/margin/tvdivq0000001rnl-att/'
        filename = f'syumatsu{date_str}00.pdf'
        return f'{base_url}{filename}'

    def _is_data_row(self, row):
        """データ行かどうかを判定"""
        if not row or len(row) < 4:
            return False
        
        first_cell = str(row[0]) if row[0] else ''
        return (first_cell.startswith('B ') and 
                '普通株式' in first_cell and 
                len(row) >= 10)

    def _parse_data_row(self, row):
        """データ行の解析"""
        first_cell = str(row[0])
        
        match = re.match(r'B\s+(.+?)\s+普通株式\s+(\d+)', first_cell)
        if not match:
            raise ValueError(f'銘柄情報の解析に失敗: {first_cell}')
        
        issue_name = match.group(1).strip()
        issue_code = match.group(2)
        jp_code = str(row[3]) if row[3] else ''
        
        numeric_values = []
        for i in range(4, len(row)):
            value = self._parse_numeric_value(row[i])
            numeric_values.append(value)
        
        while len(numeric_values) < 12:
            numeric_values.append(0)
        
        return {
            'issue_code': issue_code,
            'jp_code': jp_code,
            'issue_name': issue_name,
            'margin_data': {
                'outstanding_sales': numeric_values[0],
                'outstanding_sales_change': numeric_values[1],
                'outstanding_purchases': numeric_values[2],
                'outstanding_purchases_change': numeric_values[3],
                'negotiable_credit': numeric_values[4],
                'negotiable_credit_change': numeric_values[5],
                'standardized_credit': numeric_values[6],
                'standardized_credit_change': numeric_values[7],
                'additional_data_1': numeric_values[8] if len(numeric_values) > 8 else None,
                'additional_data_2': numeric_values[9] if len(numeric_values) > 9 else None,
                'additional_data_3': numeric_values[10] if len(numeric_values) > 10 else None,
                'additional_data_4': numeric_values[11] if len(numeric_values) > 11 else None,
            }
        }

    def _parse_numeric_value(self, value):
        """数値の解析"""
        if not value or value == '-':
            return 0
        
        value_str = str(value).strip()
        is_negative = value_str.startswith('▲')
        if is_negative:
            value_str = value_str[1:]
        
        try:
            value_str = value_str.replace(',', '')
            numeric_value = int(float(value_str))
            return -numeric_value if is_negative else numeric_value
        except (ValueError, TypeError):
            return 0

    def _save_batch(self, batch_data, target_date):
        """バッチデータの保存"""
        if not batch_data:
            return
        
        with transaction.atomic():
            for data_dict in batch_data:
                try:
                    issue, created = MarketIssue.objects.get_or_create(
                        code=data_dict['issue_code'],
                        defaults={
                            'jp_code': data_dict['jp_code'],
                            'name': data_dict['issue_name'],
                            'category': 'B'
                        }
                    )
                    
                    MarginTradingData.objects.update_or_create(
                        issue=issue,
                        date=target_date,
                        defaults=data_dict['margin_data']
                    )
                    
                except Exception as e:
                    continue

    def _log_memory(self, label):
        """メモリ使用量をログ出力"""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.stdout.write(f'📊 {label}: {memory_mb:.1f}MB')
        except:
            pass

    def _log_system_status(self):
        """システム状況ログ"""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            memory = psutil.virtual_memory()
            self.stdout.write(f'💾 システムメモリ: {memory.available/1024/1024:.0f}MB利用可能 ({memory.percent:.1f}%使用中)')
        except:
            pass