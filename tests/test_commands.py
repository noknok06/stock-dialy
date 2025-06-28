from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
import random
from django.utils import timezone
from stockdiary.models import StockDiary, Tag

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample stock diaries'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True)
        parser.add_argument('--count', type=int, default=10)
        parser.add_argument('--notes', type=int, default=5)

    def handle(self, *args, **options):
        username = options['username']
        count = options['count']
        notes = options['notes']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'ユーザー "{username}" が見つかりません。')
            )
            return

        # サンプル株式データ
        sample_stocks = [
            {'name': 'トヨタ自動車', 'symbol': '7203'},
            {'name': 'ソフトバンクグループ', 'symbol': '9984'},
            {'name': '任天堂', 'symbol': '7974'},
            {'name': 'KDDI', 'symbol': '9433'},
            {'name': 'NTTドコモ', 'symbol': '9437'},
        ]

        created_count = 0
        
        for i in range(count):
            stock = random.choice(sample_stocks)
            
            # 価格を2桁小数点に制限
            current_price = round(random.uniform(1000, 5000), 2)  # 2桁小数点
            entry_price = round(current_price * random.uniform(0.8, 1.2), 2)  # 2桁小数点
            
            diary = StockDiary.objects.create(
                user=user,
                stock_name=stock['name'],
                stock_symbol=stock['symbol'],
                current_price=Decimal(str(current_price)),  # Decimalに変換
                entry_price=Decimal(str(entry_price)),      # Decimalに変換
                quantity=random.randint(100, 1000),
                date=timezone.now(),  # timezone-aware datetime
                content=f'{stock["name"]}についての投資メモ。現在価格は{current_price}円。',
                notes_count=random.randint(1, notes)
            )
            
            # ランダムにタグを追加
            if Tag.objects.exists():
                tags = Tag.objects.order_by('?')[:random.randint(1, 3)]
                diary.tags.set(tags)
            
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'{created_count}件の日記を作成しました。')
        )