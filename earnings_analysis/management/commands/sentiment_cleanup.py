# earnings_analysis/management/commands/sentiment_cleanup.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from earnings_analysis.services.sentiment_analyzer import SentimentAnalysisService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '感情分析セッションのクリーンアップ'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際には削除せず、対象件数のみ表示'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='指定日数より古いセッションを削除（デフォルト: 1日）'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days = options['days']
        
        self.stdout.write(f'感情分析セッション クリーンアップ開始')
        self.stdout.write(f'対象: {days}日以上前のセッション')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN モード - 実際には削除しません'))
        
        try:
            from earnings_analysis.models import SentimentAnalysisSession
            
            # 対象セッション検索
            cutoff_date = timezone.now() - timedelta(days=days)
            target_sessions = SentimentAnalysisSession.objects.filter(
                expires_at__lt=cutoff_date
            )
            
            count = target_sessions.count()
            
            if count == 0:
                self.stdout.write(self.style.SUCCESS('削除対象のセッションはありません'))
                return
            
            self.stdout.write(f'削除対象: {count}件のセッション')
            
            if not dry_run:
                # 実際に削除
                deleted_count = target_sessions.delete()[0]
                self.stdout.write(
                    self.style.SUCCESS(f'クリーンアップ完了: {deleted_count}件削除')
                )
                
                # 統計出力
                remaining_count = SentimentAnalysisSession.objects.count()
                self.stdout.write(f'残存セッション数: {remaining_count}件')
            else:
                self.stdout.write('DRY RUN完了')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'クリーンアップエラー: {e}')
            )
            logger.error(f"感情分析クリーンアップエラー: {e}")