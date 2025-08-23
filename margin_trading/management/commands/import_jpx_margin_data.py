# management/commands/import_jpx_margin_data_improved.py
import requests
import pdfplumber
import re
import tempfile
import os
import gc
import warnings
import time
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.conf import settings
from margin_trading.models import MarketIssue, MarginTradingData, DataImportLog

# PDF警告を抑制
warnings.filterwarnings('ignore', category=UserWarning, module='pdfplumber')
warnings.filterwarnings('ignore', category=RuntimeWarning, module='pdfplumber')

# PDFのカラー処理警告を抑制
import logging
logging.getLogger('pdfplumber').setLevel(logging.ERROR)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

class Command(BaseCommand):
    help = 'JPXから信用取引データを取得してデータベースに保存（メモリ効率化版）'

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
            default=128,  # デフォルトを128MBに削減
            help='メモリ使用量制限（MB、デフォルト: 128）',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=25,  # デフォルトを25に削減
            help='バッチサイズ（デフォルト: 25）',
        )
        parser.add_argument(
            '--page-interval',
            type=int,
            default=5,
            help='何ページごとにメモリクリーンアップするか（デフォルト: 5）',
        )
        parser.add_argument(
            '--aggressive-gc',
            action='store_true',
            help='積極的なガベージコレクションを有効にする',
        )

    def handle(self, *args, **options):
        target_date = options.get('date')
        force = options.get('force', False)
        batch_size = options.get('batch_size', 25)
        memory_limit = options.get('memory_limit', 128) * 1024 * 1024  # MB to bytes
        page_interval = options.get('page_interval', 5)
        aggressive_gc = options.get('aggressive_gc', False)
        
        self.batch_size = batch_size
        self.memory_limit = memory_limit
        self.page_interval = page_interval
        self.aggressive_gc = aggressive_gc
        
        if target_date:
            try:
                target_date = datetime.strptime(target_date, '%Y%m%d').date()
            except ValueError:
                raise CommandError('日付は YYYYMMDD 形式で指定してください')
        else:
            target_date = date.today()
        
        self.stdout.write(f"🚀 処理開始: {target_date}")
        self.stdout.write(f"📊 設定 - メモリ制限: {memory_limit/1024/1024:.0f}MB, バッチサイズ: {batch_size}")
        
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
                self.style.SUCCESS(f'✅ データ取得完了: {target_date} ({records_count}件)')
            )
            self._log_memory_usage("完了時")
            
        except requests.RequestException as e:
            error_msg = f'PDF取得エラー: {str(e)}'
            self._log_error(target_date, error_msg, pdf_url)
            self.stdout.write(self.style.ERROR(f"❌ {error_msg}"))
            
        except MemoryError as e:
            error_msg = f'メモリ不足エラー: {str(e)}'
            self._log_error(target_date, error_msg, pdf_url)
            self.stdout.write(self.style.ERROR(f"❌ {error_msg}"))
            self.stdout.write(self.style.ERROR('💡 対策: --memory-limit を増やすか --batch-size を小さくしてください'))
            
        except Exception as e:
            error_msg = f'データ処理エラー: {str(e)}'
            self._log_error(target_date, error_msg, pdf_url)
            raise CommandError(error_msg)

    def _generate_pdf_url(self, target_date):
        """PDF URLを生成"""
        date_str = target_date.strftime('%Y%m%d')
        base_url = 'https://www.jpx.co.jp/markets/statistics-equities/margin/tvdivq0000001rnl-att/'
        filename = f'syumatsu{date_str}00.pdf'
        return f'{base_url}{filename}'

    def _import_data(self, pdf_url, target_date, force):
        """PDFデータの取得・処理（超効率版）"""
        # PDF取得（ストリーミング）
        self.stdout.write('📥 PDFダウンロード開始...')
        response = requests.get(pdf_url, timeout=60, stream=True)
        response.raise_for_status()
        
        # 一時ファイルに保存（チャンク単位）
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
                downloaded += len(chunk)
                if downloaded % (1024*1024) == 0:  # 1MBごとに進捗表示
                    self.stdout.write(f'📥 ダウンロード中: {downloaded/1024/1024:.1f}MB')
            tmp_file_path = tmp_file.name
        
        self.stdout.write(f'📥 ダウンロード完了: {downloaded/1024/1024:.1f}MB')
        self._log_memory_usage("PDF保存後")
        
        try:
            records_count = self._parse_pdf_ultra_efficient(tmp_file_path, target_date, force)
            return records_count
        finally:
            # 一時ファイル削除
            os.unlink(tmp_file_path)

    def _parse_pdf_ultra_efficient(self, pdf_path, target_date, force):
        """PDF解析とデータ保存（超効率版）"""
        records_count = 0
        batch_data = []
        
        # 既存データの削除（force時）
        if force:
            with transaction.atomic():
                deleted_count = MarginTradingData.objects.filter(date=target_date).delete()[0]
                self.stdout.write(f'🗑️  既存データ {deleted_count} 件を削除しました')
        
        self.stdout.write('📄 PDF解析開始...')
        
        # PDFを開く
        pdf_file = None
        try:
            pdf_file = pdfplumber.open(pdf_path)
            total_pages = len(pdf_file.pages)
            self.stdout.write(f'📄 総ページ数: {total_pages}')
            
            for page_num in range(total_pages):
                self.stdout.write(f'📄 ページ {page_num + 1}/{total_pages} 処理中...')
                
                # メモリ使用量チェック（ページ処理前）
                if self._check_memory_limit():
                    self.stdout.write('🧠 メモリ制限近づく - バッチ保存実行')
                    if batch_data:
                        self._save_batch(batch_data, target_date)
                        records_count += len(batch_data)
                        batch_data = []
                    self._aggressive_cleanup()
                
                # ページを個別に読み込み（メモリ効率化）
                page = None
                try:
                    page = pdf_file.pages[page_num]
                    
                    # テーブル抽出
                    tables = page.extract_tables()
                    
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
                                        
                                        if self.aggressive_gc:
                                            self._aggressive_cleanup()
                                        
                                except Exception as e:
                                    self.stdout.write(f'⚠️  行処理エラー: {str(e)}')
                                    continue
                    
                    # ページ処理完了後のクリーンアップ
                    if (page_num + 1) % self.page_interval == 0:
                        self.stdout.write(f'🧹 {page_num + 1}ページ処理完了 - クリーンアップ実行')
                        self._aggressive_cleanup()
                        self._log_memory_usage(f"ページ {page_num + 1} 処理後")
                    
                except Exception as e:
                    self.stdout.write(f'⚠️  ページ {page_num + 1} 処理エラー: {str(e)}')
                    continue
                finally:
                    # ページオブジェクトを明示的に削除
                    if page:
                        del page
                
                # 小休止（メモリ安定化）
                time.sleep(0.1)
        
        finally:
            if pdf_file:
                pdf_file.close()
        
        # 残りのデータを保存
        if batch_data:
            self._save_batch(batch_data, target_date)
            records_count += len(batch_data)
        
        # 最終クリーンアップ
        self._aggressive_cleanup()
        self._log_memory_usage("解析完了後")
        
        return records_count

    def _save_batch(self, batch_data, target_date):
        """バッチデータの保存（DB接続修正版）"""
        if not batch_data:
            return
        
        self.stdout.write(f'💾 {len(batch_data)} 件のデータを保存中...')
        
        # 接続状態をチェックして必要に応じて再接続
        try:
            connection.ensure_connection()
        except Exception:
            # 接続が切れている場合は何もしない（Djangoが自動で再接続）
            pass
        
        # バッチサイズが大きい場合はさらに分割
        chunk_size = min(len(batch_data), 10)
        
        try:
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
                        self.stdout.write(f'⚠️  データ保存エラー: {data_dict["issue_code"]} - {str(e)}')
                        continue
                        
        except Exception as e:
            self.stdout.write(f'🚨 バッチ保存で重大エラー: {str(e)}')
            # エラー時は個別に保存を試行
            self._save_batch_individually(batch_data, target_date)

    def _parse_data_row(self, row, target_date):
        """データ行の解析（辞書形式で返す）"""
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
        if not PSUTIL_AVAILABLE:
            return False
        
        try:
            process = psutil.Process()
            memory_usage = process.memory_info().rss
            return memory_usage > self.memory_limit * 0.8  # 80%で警告
        except:
            return False

    def _log_memory_usage(self, label):
        """メモリ使用量をログ出力"""
        if not PSUTIL_AVAILABLE:
            self.stdout.write(f'{label}: メモリ監視不可 (psutil未インストール)')
            return
        
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            limit_mb = self.memory_limit / 1024 / 1024
            usage_percent = (memory_mb / limit_mb) * 100
            
            status = "🟢" if usage_percent < 60 else "🟡" if usage_percent < 80 else "🔴"
            self.stdout.write(f'{status} {label}: {memory_mb:.1f}MB ({usage_percent:.1f}%)')
        except Exception as e:
            self.stdout.write(f'{label}: メモリ監視エラー {e}')

    def _aggressive_cleanup(self):
        """積極的なクリーンアップ（DB接続問題修正版）"""
        # ガベージコレクション実行
        gc.collect()
        
        # データベース接続のクリア（接続が存在する場合のみ）
        try:
            if connection.connection is not None:
                connection.close()
        except Exception:
            # 接続関連でエラーが発生しても無視
            pass
        
        # 少し待機（システムがメモリを解放する時間を与える）
        time.sleep(0.5)

    def _save_batch_individually(self, batch_data, target_date):
        """個別保存（フォールバック）"""
        self.stdout.write('🔄 個別保存モードで再試行...')
        success_count = 0
        
        for data_dict in batch_data:
            try:
                # 新しいトランザクションで個別に保存
                with transaction.atomic():
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
                    success_count += 1
                    
            except Exception as e:
                self.stdout.write(f'❌ 個別保存も失敗: {data_dict["issue_code"]} - {str(e)}')
                continue
        
        self.stdout.write(f'✅ 個別保存で {success_count}/{len(batch_data)} 件成功')

    def _log_error(self, target_date, error_msg, pdf_url):
        """エラーログの記録"""
        try:
            DataImportLog.objects.create(
                date=target_date,
                status='FAILED',
                message=error_msg,
                pdf_url=pdf_url
            )
        except:
            pass  # ログ記録でエラーが起きても処理は続行