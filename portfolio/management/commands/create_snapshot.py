# portfolio/management/commands/create_snapshot.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from portfolio.models import PortfolioSnapshot, HoldingRecord, SectorAllocation
from stockdiary.models import StockDiary
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = '自動的にポートフォリオスナップショットを作成します'
    
    def add_arguments(self, parser):
        parser.add_argument('--user', type=int, help='特定のユーザーIDのスナップショットのみ作成')
        parser.add_argument('--all', action='store_true', help='すべてのユーザーのスナップショットを作成')
    
    def handle(self, *args, **options):
        if not options['all'] and not options['user']:
            self.stdout.write(self.style.ERROR('--user または --all オプションを指定してください'))
            return
        
        users = []
        if options['all']:
            users = User.objects.all()
        elif options['user']:
            try:
                users = [User.objects.get(id=options['user'])]
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"ID {options['user']} のユーザーは存在しません"))
                return
        
        now = timezone.now()
        snapshot_name = f"自動スナップショット {now.strftime('%Y年%m月')}"
        
        for user in users:
            # 既に同名のスナップショットがあるか確認
            if PortfolioSnapshot.objects.filter(user=user, name=snapshot_name).exists():
                self.stdout.write(self.style.WARNING(f"ユーザー {user.username} は既に {snapshot_name} を持っています"))
                continue
            
            # アクティブな株式を取得
            active_diaries = StockDiary.objects.filter(
                user=user, 
                sell_date__isnull=True,
                purchase_price__isnull=False,
                purchase_quantity__isnull=False
            )
            
            if not active_diaries.exists():
                self.stdout.write(self.style.WARNING(f"ユーザー {user.username} にはアクティブな株式がありません"))
                continue
            
            # 合計評価額を計算
            total_value = Decimal('0')
            for diary in active_diaries:
                total_value += diary.purchase_price * diary.purchase_quantity
            
            # スナップショットを作成
            snapshot = PortfolioSnapshot.objects.create(
                user=user,
                name=snapshot_name,
                description=f"{now.strftime('%Y年%m月%d日')}に自動作成されました",
                total_value=total_value
            )
            
            # 銘柄の記録を作成
            for diary in active_diaries:
                stock_value = diary.purchase_price * diary.purchase_quantity
                percentage = (stock_value / total_value * 100) if total_value else Decimal('0')
                
                HoldingRecord.objects.create(
                    snapshot=snapshot,
                    stock_symbol=diary.stock_symbol,
                    stock_name=diary.stock_name,
                    quantity=diary.purchase_quantity,
                    price=diary.purchase_price,
                    total_value=stock_value,
                    sector=sector,
                    percentage=percentage
                )
            
            # セクター配分を計算
            self.calculate_sector_allocations(snapshot)
            
            self.stdout.write(self.style.SUCCESS(f"ユーザー {user.username} のスナップショット {snapshot_name} を作成しました"))
    
    def calculate_sector_allocations(self, snapshot):
        """セクター別の配分を計算して保存"""
        holdings = HoldingRecord.objects.filter(snapshot=snapshot)
        sectors = {}
        
        # セクターごとに集計
        for holding in holdings:
            if holding.sector in sectors:
                sectors[holding.sector] += holding.percentage
            else:
                sectors[holding.sector] = holding.percentage
        
        # セクター配分を保存
        for sector_name, percentage in sectors.items():
            SectorAllocation.objects.create(
                snapshot=snapshot,
                sector_name=sector_name,
                percentage=percentage
            )