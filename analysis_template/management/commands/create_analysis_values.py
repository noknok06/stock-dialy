# analysis_template/management/commands/create_analysis_values.py
# python manage.py create_analysis_values --username admin --template_id 5 --all_diaries
# python manage.py create_analysis_values --username admin --template_id 5 --diary_id 31
# python manage.py create_analysis_values --username admin --template_id 5

# analysis_template/management/commands/create_analysis_values.py
# analysis_template/management/commands/create_analysis_values.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from stockdiary.models import StockDiary
import random
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = "既存の株式日記に分析値を追加します"

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='テストデータを作成するユーザー名')
        parser.add_argument('--template_id', type=int, help='使用する分析テンプレートID')
        parser.add_argument('--all_diaries', action='store_true', help='すべての日記に分析値を追加する')
        parser.add_argument('--diary_id', type=int, help='特定の日記IDに分析値を追加する')

    def handle(self, *args, **options):
        username = options['username']
        template_id = options['template_id']
        all_diaries = options['all_diaries']
        diary_id = options['diary_id']

        if not username:
            self.stdout.write(self.style.ERROR('ユーザー名が指定されていません。--username オプションを指定してください。'))
            return

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'ユーザー "{username}" が見つかりません。'))
            return

        if not template_id:
            self.stdout.write(self.style.ERROR('テンプレートIDが指定されていません。--template_id オプションを指定してください。'))
            return

        try:
            template = AnalysisTemplate.objects.get(id=template_id, user=user)
        except AnalysisTemplate.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'テンプレートID {template_id} が見つかりません。'))
            return

        # 分析項目の取得
        items = template.items.all()
        if not items:
            self.stdout.write(self.style.ERROR(f'テンプレート "{template.name}" には分析項目がありません。'))
            return

        # 対象となる日記を取得
        if diary_id:
            diaries = StockDiary.objects.filter(id=diary_id, user=user)
            if not diaries:
                self.stdout.write(self.style.ERROR(f'日記ID {diary_id} が見つかりません。'))
                return
        elif all_diaries:
            diaries = StockDiary.objects.filter(user=user)
        else:
            # ランダムに5件の日記を選択
            diaries = StockDiary.objects.filter(user=user).order_by('?')[:5]

        if not diaries:
            self.stdout.write(self.style.ERROR(f'対象となる日記が見つかりません。'))
            return

        self.stdout.write(f'テンプレート "{template.name}" を使用して {diaries.count()} 件の日記に分析値を追加します...')

        # 各日記に分析値を追加
        for diary in diaries:
            # 既存の分析値を削除（同じテンプレートのものだけ）
            DiaryAnalysisValue.objects.filter(
                diary=diary,
                analysis_item__template=template
            ).delete()

            # 各分析項目に値を追加
            for item in items:
                if item.item_type == 'number':
                    # 数値型の場合はランダムな数値を設定
                    if 'PER' in item.name:
                        value = Decimal(random.uniform(5, 40)).quantize(Decimal('0.01'))
                    elif 'PBR' in item.name:
                        value = Decimal(random.uniform(0.5, 3)).quantize(Decimal('0.01'))
                    elif 'ROE' in item.name or '利回り' in item.name:
                        value = Decimal(random.uniform(1, 15)).quantize(Decimal('0.01'))
                    elif '成長率' in item.name:
                        value = Decimal(random.uniform(-5, 30)).quantize(Decimal('0.01'))
                    elif '配当性向' in item.name:
                        value = Decimal(random.uniform(20, 70)).quantize(Decimal('0.01'))
                    elif '連続増配年数' in item.name:
                        value = Decimal(random.randint(0, 20))
                    elif '負債比率' in item.name:
                        value = Decimal(random.uniform(20, 80)).quantize(Decimal('0.01'))
                    elif 'FCF' in item.name:
                        value = Decimal(random.uniform(10, 500)).quantize(Decimal('0.01'))
                    else:
                        value = Decimal(random.uniform(1, 100)).quantize(Decimal('0.01'))
                    
                    DiaryAnalysisValue.objects.create(
                        diary=diary,
                        analysis_item=item,
                        number_value=value
                    )
                
                elif item.item_type == 'boolean':
                    # 真偽値型の場合はランダムにTrue/Falseを設定
                    value = random.choice([True, False])
                    DiaryAnalysisValue.objects.create(
                        diary=diary,
                        analysis_item=item,
                        boolean_value=value
                    )
                
                elif item.item_type == 'boolean_with_value':
                    # 複合型の場合
                    boolean_value = random.choice([True, False])
                    
                    # 条件に応じたモックデータを作成
                    if 'PER' in item.name:
                        if 'PER < 15' in item.name:
                            number_value = Decimal(random.uniform(10, 20)).quantize(Decimal('0.01'))
                            boolean_value = number_value < 15
                        elif 'PER > 40' in item.name:
                            number_value = Decimal(random.uniform(35, 45)).quantize(Decimal('0.01'))
                            boolean_value = number_value > 40
                        else:
                            number_value = Decimal(random.uniform(5, 40)).quantize(Decimal('0.01'))
                    elif 'PBR' in item.name:
                        if 'PBR < 1.0' in item.name:
                            number_value = Decimal(random.uniform(0.7, 1.3)).quantize(Decimal('0.01'))
                            boolean_value = number_value < 1.0
                        else:
                            number_value = Decimal(random.uniform(0.5, 3)).quantize(Decimal('0.01'))
                    elif 'ROE' in item.name:
                        if 'ROE > 10%' in item.name:
                            number_value = Decimal(random.uniform(8, 12)).quantize(Decimal('0.01'))
                            boolean_value = number_value > 10
                        else:
                            number_value = Decimal(random.uniform(1, 15)).quantize(Decimal('0.01'))
                    elif '配当利回り' in item.name:
                        if '配当利回り 3%超' in item.name:
                            number_value = Decimal(random.uniform(2.5, 3.5)).quantize(Decimal('0.01'))
                            boolean_value = number_value > 3
                        else:
                            number_value = Decimal(random.uniform(1, 5)).quantize(Decimal('0.01'))
                    else:
                        number_value = None
                        text_value = "競争優位性の詳細情報" if boolean_value else ""
                    
                    DiaryAnalysisValue.objects.create(
                        diary=diary,
                        analysis_item=item,
                        boolean_value=boolean_value,
                        number_value=number_value if 'number_value' in locals() else None,
                        text_value=text_value if 'text_value' in locals() else ""
                    )
                
                elif item.item_type == 'select':
                    # 選択肢型の場合はランダムに選択肢を選ぶ
                    choices = item.get_choices_list()
                    if choices:
                        value = random.choice(choices)
                        DiaryAnalysisValue.objects.create(
                            diary=diary,
                            analysis_item=item,
                            text_value=value
                        )
                
                else:  # text
                    # テキスト型の場合はダミーテキストを入力
                    text_options = [
                        "強固なブランド力と特許技術",
                        "効率的な生産システムによるコスト優位性",
                        "優れた研究開発能力",
                        "強力な販売網とカスタマーサポート",
                        "市場ニーズを先取りする商品開発力",
                        "独自の販売チャネルを持っている",
                        "規模の経済によるコスト優位性",
                        "特定産業での高いシェアと専門性",
                        "長年の経験と高い技術力"
                    ]
                    value = random.choice(text_options)
                    DiaryAnalysisValue.objects.create(
                        diary=diary,
                        analysis_item=item,
                        text_value=value
                    )
            
            # StockDiaryモデルにはtitle属性がないので、stock_nameを表示
            self.stdout.write(self.style.SUCCESS(f'日記 "{diary.stock_name} ({diary.stock_symbol})" に分析値を追加しました。'))
        
        self.stdout.write(self.style.SUCCESS(f'合計 {diaries.count()} 件の日記に分析値を追加しました。'))