# margin_trading/management/commands/monitor_import.py
import subprocess
import time
import sys
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

class Command(BaseCommand):
    help = 'JPXデータ取得プロセスを監視しながら実行'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='対象日付 (YYYYMMDD形式)',
        )
        parser.add_argument(
            '--memory-limit',
            type=int,
            default=256,
            help='メモリ監視制限(MB、デフォルト: 256)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='強制実行フラグ',
        )
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='システムリソースチェックのみ実行',
        )
        parser.add_argument(
            '--use-improved',
            action='store_true',
            help='改良版import_jpx_margin_dataを使用（--memory-limit等のオプション付き）',
        )

    def handle(self, *args, **options):
        date_str = options.get('date')
        memory_limit = options.get('memory_limit', 256)
        force = options.get('force', False)
        check_only = options.get('check_only', False)
        use_improved = options.get('use_improved', False)

        # Django環境確認
        self.stdout.write("🔍 Django環境チェック...")
        try:
            from margin_trading.models import MarginTradingData, MarketIssue, DataImportLog
            self.stdout.write(self.style.SUCCESS("✅ Django環境: 正常"))
        except Exception as e:
            raise CommandError(f"❌ Django環境エラー: {e}")

        # システムリソースチェック
        self._check_system_resources()

        if check_only:
            self.stdout.write(self.style.SUCCESS("ℹ️  リソースチェックのみ実行しました"))
            return

        # メイン監視実行
        success = self._monitor_import_process(
            date_str=date_str,
            memory_limit=memory_limit,
            force=force,
            use_improved=use_improved
        )

        if success:
            self.stdout.write(self.style.SUCCESS("✅ データ取得が正常に完了しました"))
        else:
            raise CommandError("❌ データ取得が失敗しました")

    def _monitor_import_process(self, date_str=None, memory_limit=256, force=False, use_improved=False):
        """インポートプロセスを監視しながら実行"""
        
        # コマンド構築
        cmd = [sys.executable, 'manage.py', 'import_jpx_margin_data']
        
        # 基本オプション
        if date_str:
            cmd.extend(['--date', date_str])
        if force:
            cmd.append('--force')
        
        # 改良版を使用する場合の追加オプション
        if use_improved:
            # まず改良版がサポートしているか確認
            help_result = subprocess.run(
                [sys.executable, 'manage.py', 'import_jpx_margin_data', '--help'],
                capture_output=True, text=True
            )
            
            if '--memory-limit' in help_result.stdout:
                cmd.extend(['--memory-limit', str(memory_limit)])
                self.stdout.write(f"🧠 メモリ制限設定: {memory_limit}MB")
            
            if '--batch-size' in help_result.stdout:
                batch_size = 25 if memory_limit < 128 else 50 if memory_limit < 256 else 100
                cmd.extend(['--batch-size', str(batch_size)])
                self.stdout.write(f"📦 バッチサイズ設定: {batch_size}")

        self.stdout.write(f"🚀 実行コマンド: {' '.join(cmd)}")
        self.stdout.write(f"📊 メモリ監視制限: {memory_limit}MB")
        self.stdout.write(f"⏰ 開始時刻: {datetime.now()}")
        self.stdout.write("-" * 60)

        if not PSUTIL_AVAILABLE:
            self.stdout.write(
                self.style.WARNING("⚠️  psutil未インストール: pip install psutil")
            )
            self.stdout.write(
                self.style.WARNING("⚠️  メモリ監視機能が制限されます")
            )

        # プロセス開始
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        start_time = time.time()
        max_memory = 0
        memory_warnings = 0

        try:
            # プロセス監視ループ
            while True:
                # プロセス終了チェック
                if process.poll() is not None:
                    break

                # メモリ使用量取得
                current_memory = 0
                if PSUTIL_AVAILABLE:
                    try:
                        proc_info = psutil.Process(process.pid)
                        current_memory = proc_info.memory_info().rss / 1024 / 1024
                        max_memory = max(max_memory, current_memory)
                    except psutil.NoSuchProcess:
                        break
                    except Exception as e:
                        self.stdout.write(f"📊 メモリ監視エラー: {e}")

                # 出力読み取り
                output = process.stdout.readline()
                if output:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    memory_str = f"{current_memory:.1f}MB" if PSUTIL_AVAILABLE else "N/A"
                    self.stdout.write(f"[{timestamp}] 💾 {memory_str} | {output.strip()}")
                elif PSUTIL_AVAILABLE and current_memory > 0:
                    # 出力がない場合でもメモリ状況を表示（10秒ごと）
                    if int(time.time()) % 10 == 0:
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        self.stdout.write(f"[{timestamp}] 💾 {current_memory:.1f}MB | (処理中...)")

                # メモリ制限チェック
                if PSUTIL_AVAILABLE and current_memory > memory_limit * 1.2:
                    memory_warnings += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"🚨 警告 #{memory_warnings}: メモリ使用量が制限を超過 "
                            f"({current_memory:.1f}MB > {memory_limit}MB)"
                        )
                    )

                    if memory_warnings >= 5:
                        self.stdout.write(
                            self.style.ERROR("🚨 メモリ使用量が危険レベル。プロセス強制終了します。")
                        )
                        process.terminate()
                        time.sleep(5)
                        if process.poll() is None:
                            process.kill()
                        break

                time.sleep(2)  # 2秒間隔で監視

            # 残りの出力を読み取り
            remaining_output = process.stdout.read()
            if remaining_output:
                self.stdout.write(remaining_output)

            # 結果表示
            end_time = time.time()
            duration = end_time - start_time
            return_code = process.returncode

            self.stdout.write("-" * 60)
            self.stdout.write(f"⏱️  実行時間: {duration:.1f}秒")
            if PSUTIL_AVAILABLE:
                self.stdout.write(f"📊 最大メモリ使用量: {max_memory:.1f}MB")
                self.stdout.write(f"⚠️  メモリ警告回数: {memory_warnings}")
            self.stdout.write(f"🔢 終了コード: {return_code}")
            self.stdout.write(f"✅ 完了時刻: {datetime.now()}")

            # 結果評価
            if return_code == 0:
                if PSUTIL_AVAILABLE and max_memory > memory_limit:
                    self.stdout.write(
                        self.style.WARNING(
                            "⚠️  メモリ制限超過がありました。設定見直しを推奨します。"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS("🎉 メモリ使用量も制限内でした")
                    )
            
            return return_code == 0

        except KeyboardInterrupt:
            self.stdout.write(self.style.ERROR("\n🛑 ユーザーによって中断されました"))
            process.terminate()
            process.wait()
            return False

    def _check_system_resources(self):
        """システムリソースをチェック"""
        self.stdout.write("=" * 40)
        self.stdout.write("🖥️  システムリソース状況")
        self.stdout.write("=" * 40)

        if not PSUTIL_AVAILABLE:
            self.stdout.write(
                self.style.WARNING("⚠️  詳細リソース情報が取得できません（psutil未インストール）")
            )
            return

        try:
            # メモリ使用量
            memory = psutil.virtual_memory()
            self.stdout.write(
                f"💾 メモリ: {memory.used/1024/1024:.0f}MB / {memory.total/1024/1024:.0f}MB "
                f"({memory.percent:.1f}% 使用)"
            )

            # スワップ使用量
            swap = psutil.swap_memory()
            if swap.total > 0:
                self.stdout.write(
                    f"🔄 スワップ: {swap.used/1024/1024:.0f}MB / {swap.total/1024/1024:.0f}MB "
                    f"({swap.percent:.1f}% 使用)"
                )

            # ディスク使用量
            disk = psutil.disk_usage('/')
            self.stdout.write(
                f"💿 ディスク: {disk.used/1024/1024/1024:.1f}GB / {disk.total/1024/1024/1024:.1f}GB "
                f"({disk.percent:.1f}% 使用)"
            )

            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            self.stdout.write(f"🖥️  CPU: {cpu_percent:.1f}% 使用")

            # 実行中のPythonプロセス
            python_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if 'python' in proc.info['name'].lower():
                        memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                        python_processes.append((proc.info['pid'], memory_mb))
                except:
                    pass

            if python_processes:
                self.stdout.write(f"🐍 実行中のPythonプロセス: {len(python_processes)} 個")
                for pid, mem in sorted(python_processes, key=lambda x: x[1], reverse=True)[:3]:
                    self.stdout.write(f"   PID {pid}: {mem:.1f}MB")

        except Exception as e:
            self.stdout.write(f"⚠️  リソース情報取得エラー: {e}")

        self.stdout.write("")