# management/commands/diagnose_jpx_pdf.py
import requests
import pdfplumber
import tempfile
import os
import warnings
import logging
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError

# ログとワーニングの設定
warnings.filterwarnings('ignore')
logging.getLogger('pdfplumber').setLevel(logging.CRITICAL)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

class Command(BaseCommand):
    help = 'JPX PDFファイルの診断と前処理チェック'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='診断対象日付 (YYYYMMDD形式, 省略時は当日)',
        )
        parser.add_argument(
            '--download-only',
            action='store_true',
            help='ダウンロードのみ実行（解析はしない）',
        )
        parser.add_argument(
            '--analyze-structure',
            action='store_true',
            help='PDF構造の詳細解析',
        )
        parser.add_argument(
            '--count-data-rows',
            action='store_true',
            help='データ行数をカウント',
        )
        parser.add_argument(
            '--test-memory',
            action='store_true',
            help='メモリ使用量テスト',
        )

    def handle(self, *args, **options):
        target_date = options.get('date')
        download_only = options.get('download_only', False)
        analyze_structure = options.get('analyze_structure', False)
        count_data_rows = options.get('count_data_rows', False)
        test_memory = options.get('test_memory', False)
        
        if target_date:
            try:
                target_date = datetime.strptime(target_date, '%Y%m%d').date()
            except ValueError:
                raise CommandError('日付は YYYYMMDD 形式で指定してください')
        else:
            target_date = date.today()
        
        self.stdout.write("=" * 60)
        self.stdout.write(f"🔍 JPX PDF診断開始: {target_date}")
        self.stdout.write("=" * 60)
        
        # PDF URL生成
        pdf_url = self._generate_pdf_url(target_date)
        self.stdout.write(f"📄 PDF URL: {pdf_url}")
        
        # システムリソース確認
        if PSUTIL_AVAILABLE:
            self._check_system_resources()
        else:
            self.stdout.write("⚠️  psutil未インストール: pip install psutil")
        
        try:
            # PDFダウンロード
            pdf_path = self._download_pdf(pdf_url)
            
            if download_only:
                self.stdout.write(f"✅ ダウンロード完了: {pdf_path}")
                return
            
            # PDF基本情報
            self._analyze_pdf_basic_info(pdf_path)
            
            # 構造解析
            if analyze_structure:
                self._analyze_pdf_structure(pdf_path)
            
            # データ行数カウント
            if count_data_rows:
                self._count_data_rows(pdf_path)
            
            # メモリテスト
            if test_memory:
                self._test_memory_usage(pdf_path)
            
            # 推奨設定を出力
            self._recommend_settings(pdf_path)
            
        except Exception as e:
            raise CommandError(f"診断エラー: {str(e)}")
        finally:
            # クリーンアップ
            if 'pdf_path' in locals():
                try:
                    os.unlink(pdf_path)
                except:
                    pass

    def _generate_pdf_url(self, target_date):
        """PDF URLを生成"""
        date_str = target_date.strftime('%Y%m%d')
        base_url = 'https://www.jpx.co.jp/markets/statistics-equities/margin/tvdivq0000001rnl-att/'
        filename = f'syumatsu{date_str}00.pdf'
        return f'{base_url}{filename}'

    def _download_pdf(self, pdf_url):
        """PDF ダウンロード"""
        self.stdout.write('📥 PDFダウンロード開始...')
        
        try:
            response = requests.get(pdf_url, timeout=60, stream=True)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise CommandError(f"PDF取得エラー: {str(e)}")
        
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            total_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
                total_size += len(chunk)
                if total_size % (1024*1024) == 0:  # 1MBごと
                    self.stdout.write(f'📥 {total_size/1024/1024:.1f}MB ダウンロード中...')
            
            self.stdout.write(f'✅ ダウンロード完了: {total_size/1024/1024:.1f}MB')
            return tmp_file.name

    def _analyze_pdf_basic_info(self, pdf_path):
        """PDF基本情報の解析"""
        self.stdout.write("\n📊 PDF基本情報")
        self.stdout.write("-" * 30)
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                self.stdout.write(f"📄 総ページ数: {len(pdf.pages)}")
                
                if pdf.metadata:
                    self.stdout.write("📋 メタデータ:")
                    for key, value in pdf.metadata.items():
                        self.stdout.write(f"  {key}: {value}")
                
                # 最初のページの情報
                if pdf.pages:
                    first_page = pdf.pages[0]
                    self.stdout.write(f"📐 ページサイズ: {first_page.width} x {first_page.height}")
                    
                    # テーブル数チェック
                    try:
                        tables = first_page.extract_tables()
                        self.stdout.write(f"📋 最初のページのテーブル数: {len(tables) if tables else 0}")
                    except Exception as e:
                        self.stdout.write(f"⚠️  テーブル抽出テストで警告: {str(e)}")
                
        except Exception as e:
            self.stdout.write(f"❌ 基本情報取得エラー: {str(e)}")

    def _analyze_pdf_structure(self, pdf_path):
        """PDF構造の詳細解析"""
        self.stdout.write("\n🏗️  PDF構造解析")
        self.stdout.write("-" * 30)
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # サンプルページを解析（最初の3ページ）
                sample_pages = min(3, len(pdf.pages))
                
                for i in range(sample_pages):
                    page = pdf.pages[i]
                    self.stdout.write(f"\n📄 ページ {i+1}:")
                    
                    # テキスト量
                    text = page.extract_text()
                    if text:
                        self.stdout.write(f"  📝 テキスト文字数: {len(text)}")
                        self.stdout.write(f"  📝 行数: {len(text.split('\n'))}")
                    
                    # オブジェクト数
                    objects = page.objects
                    if objects:
                        self.stdout.write(f"  🎯 オブジェクト数: {len(objects)}")
                        
                        # オブジェクトタイプ別カウント
                        object_types = {}
                        for obj in objects:
                            obj_type = obj.get('object_type', 'unknown')
                            object_types[obj_type] = object_types.get(obj_type, 0) + 1
                        
                        for obj_type, count in object_types.items():
                            self.stdout.write(f"    - {obj_type}: {count}")
                
        except Exception as e:
            self.stdout.write(f"❌ 構造解析エラー: {str(e)}")

    def _count_data_rows(self, pdf_path):
        """データ行数をカウント"""
        self.stdout.write("\n🔢 データ行数カウント")
        self.stdout.write("-" * 30)
        
        data_row_count = 0
        total_row_count = 0
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        tables = page.extract_tables()
                        if tables:
                            for table in tables:
                                for row in table:
                                    total_row_count += 1
                                    if self._is_data_row(row):
                                        data_row_count += 1
                    except Exception as e:
                        self.stdout.write(f"⚠️  ページ {page_num+1} でエラー: {str(e)}")
                        continue
                
                self.stdout.write(f"📊 総行数: {total_row_count}")
                self.stdout.write(f"📈 データ行数: {data_row_count}")
                self.stdout.write(f"📉 データ率: {data_row_count/total_row_count*100:.1f}%" if total_row_count > 0 else "N/A")
                
        except Exception as e:
            self.stdout.write(f"❌ データ行カウントエラー: {str(e)}")

    def _test_memory_usage(self, pdf_path):
        """メモリ使用量テスト"""
        self.stdout.write("\n🧠 メモリ使用量テスト")
        self.stdout.write("-" * 30)
        
        if not PSUTIL_AVAILABLE:
            self.stdout.write("⚠️  psutil未インストール")
            return
        
        try:
            import psutil
            process = psutil.Process()
            
            # テスト開始時のメモリ
            initial_memory = process.memory_info().rss / 1024 / 1024
            self.stdout.write(f"🏁 開始時メモリ: {initial_memory:.1f}MB")
            
            # PDF全体読み込みテスト
            with pdfplumber.open(pdf_path) as pdf:
                current_memory = process.memory_info().rss / 1024 / 1024
                self.stdout.write(f"📖 PDF読み込み後: {current_memory:.1f}MB (+{current_memory-initial_memory:.1f}MB)")
                
                # 5ページごとにメモリをチェック
                for i in range(0, len(pdf.pages), 5):
                    end_page = min(i+5, len(pdf.pages))
                    
                    # ページ処理
                    for page_num in range(i, end_page):
                        try:
                            page = pdf.pages[page_num]
                            tables = page.extract_tables()
                        except:
                            pass
                    
                    current_memory = process.memory_info().rss / 1024 / 1024
                    self.stdout.write(f"📄 ページ {end_page} 処理後: {current_memory:.1f}MB")
                    
                    # メモリが200MBを超えたら警告
                    if current_memory > 200:
                        self.stdout.write("⚠️  メモリ使用量が200MBを超えました")
                        break
                
            final_memory = process.memory_info().rss / 1024 / 1024
            self.stdout.write(f"🏁 最終メモリ: {final_memory:.1f}MB")
            self.stdout.write(f"📈 総メモリ増加: {final_memory-initial_memory:.1f}MB")
            
        except Exception as e:
            self.stdout.write(f"❌ メモリテストエラー: {str(e)}")

    def _recommend_settings(self, pdf_path):
        """推奨設定の出力"""
        self.stdout.write("\n💡 推奨実行設定")
        self.stdout.write("-" * 30)
        
        file_size_mb = os.path.getsize(pdf_path) / 1024 / 1024
        
        # ファイルサイズベースの推奨設定
        if file_size_mb < 1:
            memory_limit = 64
            batch_size = 50
        elif file_size_mb < 5:
            memory_limit = 128
            batch_size = 25
        elif file_size_mb < 10:
            memory_limit = 256
            batch_size = 15
        else:
            memory_limit = 512
            batch_size = 10
        
        self.stdout.write(f"📁 PDFファイルサイズ: {file_size_mb:.1f}MB")
        self.stdout.write(f"🧠 推奨メモリ制限: {memory_limit}MB")
        self.stdout.write(f"📦 推奨バッチサイズ: {batch_size}")
        
        # 推奨コマンド
        self.stdout.write(f"\n🚀 推奨実行コマンド:")
        self.stdout.write(f"python manage.py import_jpx_margin_data_improved \\")
        self.stdout.write(f"  --memory-limit {memory_limit} \\")
        self.stdout.write(f"  --batch-size {batch_size} \\")
        self.stdout.write(f"  --page-interval 5 \\")
        self.stdout.write(f"  --aggressive-gc")

    def _is_data_row(self, row):
        """データ行かどうかを判定"""
        if not row or len(row) < 4:
            return False
        
        first_cell = str(row[0]) if row[0] else ''
        return (first_cell.startswith('B ') and 
                '普通株式' in first_cell and 
                len(row) >= 10)

    def _check_system_resources(self):
        """システムリソース確認"""
        self.stdout.write("\n💻 システムリソース")
        self.stdout.write("-" * 30)
        
        try:
            import psutil
            
            # メモリ
            memory = psutil.virtual_memory()
            self.stdout.write(f"💾 メモリ: {memory.available/1024/1024:.0f}MB 利用可能")
            
            # ディスク
            disk = psutil.disk_usage('/')
            self.stdout.write(f"💿 ディスク: {disk.free/1024/1024/1024:.1f}GB 利用可能")
            
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            self.stdout.write(f"🖥️  CPU使用率: {cpu_percent:.1f}%")
            
        except Exception as e:
            self.stdout.write(f"❌ リソース確認エラー: {str(e)}")