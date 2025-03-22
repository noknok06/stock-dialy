# # メンテナンスモードを有効化
# python manage.py maintenance_mode on

# # メンテナンスモードを無効化
# python manage.py maintenance_mode off

# # 現在の状態を確認
# python manage.py maintenance_mode status

import os
import re
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

class Command(BaseCommand):
    help = 'メンテナンスモードの有効/無効を切り替えます'

    def add_arguments(self, parser):
        parser.add_argument(
            'mode',
            choices=['on', 'off', 'status'],
            help='メンテナンスモードを有効化(on)、無効化(off)するか、現在の状態を確認(status)します'
        )

    def handle(self, *args, **options):
        # 設定ファイルのパスを取得
        settings_path = self._get_settings_path()
        if not settings_path:
            raise CommandError('settings.py ファイルが見つかりません。')
        
        mode = options['mode']
        
        if mode == 'status':
            is_maintenance_mode = getattr(settings, 'MAINTENANCE_MODE', False)
            status = '有効' if is_maintenance_mode else '無効'
            self.stdout.write(f'現在のメンテナンスモード: {status}')
            return
        
        # 設定ファイルの内容を読み込む
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # MAINTENANCE_MODE の設定行を探して置換
        pattern = r'MAINTENANCE_MODE\s*=\s*(True|False)'
        new_value = 'True' if mode == 'on' else 'False'
        
        if re.search(pattern, content):
            # 既存の設定を置換
            modified_content = re.sub(pattern, f'MAINTENANCE_MODE = {new_value}', content)
            
            # 変更を保存
            with open(settings_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            
            action = '有効化' if mode == 'on' else '無効化'
            self.stdout.write(self.style.SUCCESS(f'メンテナンスモードを{action}しました。'))
        else:
            # 設定が見つからない場合
            self.stdout.write(self.style.WARNING(f'MAINTENANCE_MODE の設定が見つかりません。settings.py に手動で追加してください。'))
    
    def _get_settings_path(self):
        """
        設定ファイルのパスを取得する
        """
        # Django設定モジュールのパスを取得
        settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', '')
        if not settings_module:
            # プロジェクト名から推測
            project_name = os.path.basename(os.getcwd())
            settings_module = f'{project_name}.settings'
        
        # モジュールパスからファイルパスを作成
        module_parts = settings_module.split('.')
        settings_dir = os.path.join(os.getcwd(), *module_parts[:-1])
        settings_file = f'{module_parts[-1]}.py'
        
        settings_path = os.path.join(settings_dir, settings_file)
        
        if os.path.exists(settings_path):
            return settings_path
        
        # 標準的な場所にある場合の代替パス
        alt_settings_path = os.path.join(os.getcwd(), 'settings.py')
        if os.path.exists(alt_settings_path):
            return alt_settings_path
        
        # プロジェクト名と同じディレクトリにある場合
        project_settings_path = os.path.join(os.getcwd(), module_parts[0], 'settings.py')
        if os.path.exists(project_settings_path):
            return project_settings_path
            
        return None