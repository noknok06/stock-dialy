# stockdiary/management/commands/send_notifications.py
from django.core.management.base import BaseCommand
from stockdiary.services.notification_service import NotificationService
import traceback


class Command(BaseCommand):
    help = '通知を処理して送信'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['all', 'reminder', 'price_alert', 'periodic'],
            default='all',
            help='処理する通知タイプ'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='詳細なログを出力'
        )
    
    def handle(self, *args, **options):
        notification_type = options['type']
        verbose = options.get('verbose', False)
        
        self.stdout.write(
            self.style.SUCCESS(f'通知処理を開始: {notification_type}')
        )
        
        try:
            service = NotificationService()
            
            if notification_type == 'all':
                result = service.process_all_notifications()
            elif notification_type == 'reminder':
                result = service.process_reminder_notifications()
            elif notification_type == 'price_alert':
                result = service.process_price_alert_notifications()
            elif notification_type == 'periodic':
                result = service.process_periodic_notifications()
            
            # 結果を表示
            if verbose:
                self.stdout.write(self.style.WARNING(f'詳細結果: {result}'))
            
            sent = result.get("total_sent", result.get("sent", 0))
            errors = result.get("total_errors", result.get("errors", 0))
            
            if errors > 0:
                self.stdout.write(
                    self.style.ERROR(f'⚠️ エラーが発生しました: {errors}件')
                )
            
            self.stdout.write(
                self.style.SUCCESS(f'完了: 送信={sent}, エラー={errors}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ 致命的なエラー: {str(e)}')
            )
            if verbose:
                self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise