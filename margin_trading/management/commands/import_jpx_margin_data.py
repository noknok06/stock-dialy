# management/commands/import_jpx_margin_data.py
import requests
import pdfplumber
import re
import tempfile
import os
import gc
import warnings
import psutil
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.conf import settings
from margin_trading.models import MarketIssue, MarginTradingData, DataImportLog

# PDF警告を抑制
warnings.filterwarnings('ignore', category=UserWarning, module='pdfplumber')

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    
class Command(BaseCommand):
    help = 'JPXから信用取引データを取得してデータベースに保存'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='取得対象日付 (YYYYMMDD形式, 省略時は当日)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='既存データがあっても強制的に取得・更新',
        )
        parser.add_argument(
            '--memory-limit',
            type=int,
            default=256,
            help='メモリ使用量制限（MB、デフォルト: 256）',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='バッチサイズ（デフォルト: 100）',
        )

    def handle(self, *args, **options):
        target_date = options.get('date')
        force = options.get('force', False)
        batch_size = options.get('batch_size', 100)
        memory_limit = options.get('memory_limit', 512) * 1024 * 1024  # MB to bytes
        
        self.batch_size = batch_size
        self.memory_limit = memory_limit
        
        if target_date:
            try:
                target_date = datetime.strptime(target_date, '%Y%m%d').date()
            except ValueError:
                raise CommandError('日付は YYYYMMDD 形式で指定してください')
        else:
            target_date = date.today()
        
        # 初期メモリ使用量を記録
        self._log_memory_usage("開始時")
        
        # 既存データのチェック
        if not force and MarginTradingData.objects.filter(date=target_date).exists():
            self.stdout.write(
                self.style.WARNING(f'{target_date} のデータは既に存在します。--force オプションで強制更新可能です。')
            )
            return
        
        # PDF URL生成
        pdf_url = self._generate_pdf_url(target_date)
        
        try:
            # データ取得・処理
            records_count = self._import_data(pdf_url, target_date, force)
            
            # ログ記録（成功）
            DataImportLog.objects.create(
                date=target_date,
                status='SUCCESS',
                message=f'正常に {records_count} 件のデータを取得しました',
                records_count=records_count,
                pdf_url=pdf_url
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'データ取得完了: {target_date} ({records_count}件)')
            )
            self._log_memory_usage("完了時")
            
        except requests.RequestException as e:
            # ネットワークエラー
            error_msg = f'PDF取得エラー: {str(e)}'
            DataImportLog.objects.create(
                date=target_date,
                status='FAILED',
                message=error_msg,
                pdf_url=pdf_url
            )
            self.stdout.write(self.style.ERROR(error_msg))
            
        except MemoryError as e:
            # メモリエラー
            error_msg = f'メモリ不足エラー: {str(e)}'
            DataImportLog.objects.create(
                date=target_date,
                status='FAILED',
                message=error_msg,
                pdf_url=pdf_url
            )
            self.stdout.write(self.style.ERROR(error_msg))
            self.stdout.write(self.style.ERROR('メモリ制限を増やすか、バッチサイズを小さくしてください'))
            
        except Exception as e:
            # その他のエラー
            error_msg = f'データ処理エラー: {str(e)}'
            DataImportLog.objects.create(
                date=target_date,
                status='FAILED',
                message=error_msg,
                pdf_url=pdf_url
            )
            raise CommandError(error_msg)

    def _generate_pdf_url(self, target_date):
        """PDF URLを生成"""
        date_str = target_date.strftime('%Y%m%d')
        base_url = 'https://www.jpx.co.jp/markets/statistics-equities/margin/tvdivq0000001rnl-att/'
        filename = f'syumatsu{date_str}00.pdf'
        return f'{base_url}{filename}'

    def _import_data(self, pdf_url, target_date, force):
        """PDFデータの取得・処理（メモリ効率版）"""
        # PDF取得（ストリーミング）
        self.stdout.write('PDFダウンロード開始...')
        response = requests.get(pdf_url, timeout=60, stream=True)
        response.raise_for_status()
        
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            # チャンク単位でダウンロード
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
            tmp_file_path = tmp_file.name
        
        self._log_memory_usage("PDF保存後")
        
        try:
            records_count = self._parse_pdf_and_save_batched(tmp_file_path, target_date, force)
            return records_count
        finally:
            # 一時ファイル削除
            os.unlink(tmp_file_path)

    def _parse_pdf_and_save_batched(self, pdf_path, target_date, force):
        """PDF解析とデータ保存（バッチ処理版）"""
        records_count = 0
        batch_data = []
        
        # 既存データの削除（force時）
        if force:
            with transaction.atomic():
                deleted_count = MarginTradingData.objects.filter(date=target_date).delete()[0]
                self.stdout.write(f'既存データ {deleted_count} 件を削除しました')
        
        self.stdout.write('PDF解析開始...')
        
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            self.stdout.write(f'総ページ数: {total_pages}')
            
            for page_num, page in enumerate(pdf.pages, 1):
                self.stdout.write(f'ページ {page_num}/{total_pages} 処理中...')
                
                # メモリ使用量チェック
                if self._check_memory_limit():
                    # メモリが不足している場合、現在のバッチを保存
                    if batch_data:
                        self._save_batch(batch_data, target_date)
                        records_count += len(batch_data)
                        batch_data = []
                        self._force_garbage_collection()
                
                # テーブル抽出
                try:
                    tables = page.extract_tables()
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'ページ {page_num} のテーブル抽出エラー: {str(e)}')
                    )
                    continue
                
                for table in tables:
                    for row in table:
                        if self._is_data_row(row):
                            try:
                                data_dict = self._parse_data_row(row, target_date)
                                batch_data.append(data_dict)
                                
                                # バッチサイズに達したら保存
                                if len(batch_data) >= self.batch_size:
                                    self._save_batch(batch_data, target_date)
                                    records_count += len(batch_data)
                                    batch_data = []
                                    self._force_garbage_collection()
                                    
                            except Exception as e:
                                self.stdout.write(
                                    self.style.WARNING(f'行処理エラー: {row} - {str(e)}')
                                )
                                continue
        
        # 残りのデータを保存
        if batch_data:
            self._save_batch(batch_data, target_date)
            records_count += len(batch_data)
        
        self._log_memory_usage("解析完了後")
        return records_count

    def _save_batch(self, batch_data, target_date):
        """バッチデータの保存"""
        if not batch_data:
            return
        
        self.stdout.write(f'{len(batch_data)} 件のデータを保存中...')
        
        with transaction.atomic():
            for data_dict in batch_data:
                try:
                    # 銘柄の取得または作成
                    issue, created = MarketIssue.objects.get_or_create(
                        code=data_dict['issue_code'],
                        defaults={
                            'jp_code': data_dict['jp_code'],
                            'name': data_dict['issue_name'],
                            'category': 'B'
                        }
                    )
                    
                    # 信用取引データの作成・更新
                    MarginTradingData.objects.update_or_create(
                        issue=issue,
                        date=target_date,
                        defaults=data_dict['margin_data']
                    )
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'データ保存エラー: {data_dict["issue_code"]} - {str(e)}')
                    )
                    continue

    def _parse_data_row(self, row, target_date):
        """データ行の解析（辞書形式で返す）"""
        # データ行の解析
        first_cell = str(row[0])
        
        # 銘柄情報の抽出
        match = re.match(r'B\s+(.+?)\s+普通株式\s+(\d+)', first_cell)
        if not match:
            raise ValueError(f'銘柄情報の解析に失敗: {first_cell}')
        
        issue_name = match.group(1).strip()
        issue_code = match.group(2)
        jp_code = str(row[3]) if row[3] else ''
        
        # 数値データの解析
        numeric_values = []
        for i in range(4, len(row)):
            value = self._parse_numeric_value(row[i])
            numeric_values.append(value)
        
        # 足りない値を0で埋める
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

    def _is_data_row(self, row):
        """データ行かどうかを判定"""
        if not row or len(row) < 4:
            return False
        
        # 銘柄データの特徴（B + 銘柄名 + 普通株式 + コード）をチェック
        first_cell = str(row[0]) if row[0] else ''
        return (first_cell.startswith('B ') and 
                '普通株式' in first_cell and 
                len(row) >= 10)

    def _parse_numeric_value(self, value):
        """数値の解析（カンマ区切り、▲マイナス記号対応）"""
        if not value or value == '-':
            return 0
        
        value_str = str(value).strip()
        
        # ▲マイナス記号の処理
        is_negative = value_str.startswith('▲')
        if is_negative:
            value_str = value_str[1:]
        
        # カンマを除去して数値変換
        try:
            value_str = value_str.replace(',', '')
            numeric_value = int(float(value_str))
            return -numeric_value if is_negative else numeric_value
        except (ValueError, TypeError):
            return 0

    def _check_memory_limit(self):
        """メモリ使用量が制限を超えているかチェック"""
        try:
            process = psutil.Process()
            memory_usage = process.memory_info().rss
            return memory_usage > self.memory_limit
        except:
            return False

    def _log_memory_usage(self, label):
        """メモリ使用量をログ出力"""
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.stdout.write(f'{label}: メモリ使用量 {memory_mb:.1f}MB')
        except:
            pass

    def _force_garbage_collection(self):
        """強制的にガベージコレクションを実行"""
        gc.collect()
        # データベース接続もクリア
        connection.close()