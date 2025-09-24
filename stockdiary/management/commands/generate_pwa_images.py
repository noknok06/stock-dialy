# stockdiary/management/commands/generate_pwa_images.py
from django.core.management.base import BaseCommand
from utils.image_generator import generate_pwa_icons

class Command(BaseCommand):
    help = 'PWA用画像を生成します'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='既存の画像を強制的に上書きします',
        )
    
    def handle(self, *args, **options):
        try:
            generate_pwa_icons()
            self.stdout.write(
                self.style.SUCCESS('✅ PWA画像の生成が完了しました')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ 画像生成でエラーが発生しました: {str(e)}')
            )
            raise e