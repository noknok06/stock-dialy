import os
import django
import random
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

# Djangoの設定を読み込む
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stockdiary.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from stockdiary.models import StockDiary

User = get_user_model()

def create_test_data():
    """開発用のテストデータを作成するスクリプト"""
    print("テストデータ作成を開始します...")
    
    # テストユーザーの作成
    try:
        user = User.objects.get(username='testuser')
        print("既存のテストユーザーを使用します")
    except User.DoesNotExist:
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        print("新しいテストユーザーを作成しました")
    
    # 複数のテンプレートを作成
    templates = [
        {
            'name': '基本分析テンプレート',
            'description': '株式の基本的な分析項目',
            'items': [
                {'name': 'PER', 'description': '株価収益率', 'item_type': 'number', 'order': 1},
                {'name': 'PBR', 'description': '株価純資産倍率', 'item_type': 'number', 'order': 2},
                {'name': 'ROE', 'description': '自己資本利益率', 'item_type': 'number', 'order': 3},
                {'name': '配当利回り', 'description': '年間配当金÷株価', 'item_type': 'number', 'order': 4},
                {'name': '成長性', 'description': '将来の成長可能性', 'item_type': 'select', 
                 'choices': '高い,中程度,低い', 'order': 5},
            ]
        },
        {
            'name': 'バフェット方式チェックリスト',
            'description': 'ウォーレン・バフェットの投資基準に基づくチェックリスト',
            'items': [
                {'name': '理解できるビジネスか', 'description': 'ビジネスモデルが理解しやすいか', 
                 'item_type': 'boolean', 'order': 1},
                {'name': '長期的な競争優位性', 'description': '経済的堀（競争優位性）があるか', 
                 'item_type': 'select', 'choices': '強い,中程度,弱い', 'order': 2},
                {'name': '有能な経営陣', 'description': '経営陣は株主利益を重視しているか', 
                 'item_type': 'boolean', 'order': 3},
                {'name': '株価は割安か', 'description': '本質的価値と比較して株価が割安か', 
                 'item_type': 'boolean_with_value', 'value_label': '割安度（％）', 'order': 4},
                {'name': '負債比率は健全か', 'description': '過剰な負債を抱えていないか', 
                 'item_type': 'boolean_with_value', 'value_label': '負債比率', 'order': 5},
            ]
        },
        {
            'name': 'デイトレード分析',
            'description': '短期トレード用の分析項目',
            'items': [
                {'name': 'RSI', 'description': '相対力指数', 'item_type': 'number', 'order': 1},
                {'name': 'ボリンジャーバンド', 'description': '標準偏差に基づくバンド', 
                 'item_type': 'select', 'choices': '上限突破,上バンド内,中心線付近,下バンド内,下限突破', 'order': 2},
                {'name': '移動平均線', 'description': '移動平均線の状態', 
                 'item_type': 'select', 'choices': 'ゴールデンクロス,上昇トレンド,デッドクロス,下降トレンド', 'order': 3},
                {'name': '出来高増加', 'description': '出来高が増加しているか', 'item_type': 'boolean', 'order': 4},
                {'name': '値動きの勢い', 'description': 'モメンタムの強さ', 
                 'item_type': 'select', 'choices': '強い,中程度,弱い', 'order': 5},
            ]
        }
    ]
    
    created_templates = []
    for template_data in templates:
        try:
            template = AnalysisTemplate.objects.get(user=user, name=template_data['name'])
            print(f"テンプレート '{template_data['name']}' は既に存在します")
        except AnalysisTemplate.DoesNotExist:
            template = AnalysisTemplate.objects.create(
                user=user,
                name=template_data['name'],
                description=template_data['description']
            )
            print(f"テンプレート '{template_data['name']}' を作成しました")
            
            # 分析項目を追加
            for item_data in template_data['items']:
                AnalysisItem.objects.create(
                    template=template,
                    name=item_data['name'],
                    description=item_data['description'],
                    item_type=item_data['item_type'],
                    choices=item_data.get('choices', ''),
                    value_label=item_data.get('value_label', ''),
                    order=item_data['order']
                )
            print(f"  {len(template_data['items'])}個の分析項目を追加しました")
            
        created_templates.append(template)
    
    # サンプル株式のデータ
    stocks = [
        {'name': 'トヨタ自動車', 'symbol': '7203', 'sector': '自動車'},
        {'name': 'ソニーグループ', 'symbol': '6758', 'sector': '電機'},
        {'name': '任天堂', 'symbol': '7974', 'sector': 'ゲーム'},
        {'name': '三菱UFJフィナンシャルG', 'symbol': '8306', 'sector': '銀行'},
        {'name': 'ソフトバンクグループ', 'symbol': '9984', 'sector': '情報・通信'},
        {'name': 'ファーストリテイリング', 'symbol': '9983', 'sector': '小売'},
        {'name': '東京エレクトロン', 'symbol': '8035', 'sector': '半導体'},
        {'name': '武田薬品工業', 'symbol': '4502', 'sector': '医薬品'},
        {'name': '日本電信電話', 'symbol': '9432', 'sector': '情報・通信'},
        {'name': 'KDDI', 'symbol': '9433', 'sector': '情報・通信'},
    ]
    
    # 各テンプレートに対してサンプル日記を作成
    for template in created_templates:
        print(f"\nテンプレート '{template.name}' の日記を作成します")
        
        items = list(template.items.all())
        
        for stock in stocks:
            # 既存の日記をチェック
            existing_diary = StockDiary.objects.filter(
                user=user,
                stock_name=stock['name'],
                stock_symbol=stock['symbol']
            ).first()
            
            if existing_diary:
                diary = existing_diary
                print(f"  既存の日記 '{stock['name']}' を更新します")
            else:
                # 日記の作成日をランダムに過去30日以内に設定
                random_days = random.randint(0, 30)
                diary_date = timezone.now() - timedelta(days=random_days)
                
                # 日記本文を生成
                content = f"{stock['name']}（{stock['symbol']}）の分析メモ。\n"
                content += f"業種: {stock['sector']}\n\n"
                content += "今後の見通しについて検討した結果、"
                outlook = random.choice(['ポジティブ', 'やや前向き', '様子見', 'やや慎重', 'ネガティブ'])
                content += f"{outlook}な見方をしている。\n\n"
                content += "詳細な分析結果は添付の分析シートを参照。"
                
                diary = StockDiary.objects.create(
                    user=user,
                    stock_name=stock['name'],
                    stock_symbol=stock['symbol'],
                    date=diary_date,
                    content=content
                )
                print(f"  新規日記 '{stock['name']}' を作成しました")
            
            # 各分析項目に値を設定
            for item in items:
                # 既存の値をチェック
                existing_value = DiaryAnalysisValue.objects.filter(
                    diary=diary,
                    analysis_item=item
                ).first()
                
                if existing_value:
                    value = existing_value
                    print(f"    項目 '{item.name}' の値を更新します")
                else:
                    value = DiaryAnalysisValue(
                        diary=diary,
                        analysis_item=item
                    )
                    print(f"    項目 '{item.name}' の値を新規作成します")
                
                # 項目タイプに応じてランダムな値を設定
                if item.item_type == 'number':
                    if '配当利回り' in item.name:
                        value.Decimal(str(random.uniform(0, 5))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)  # 0-5%
                    elif 'PER' in item.name:
                        value.number_value = Decimal(str(random.uniform(8, 40))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)   # 8-40倍
                    elif 'PBR' in item.name:
                        value.number_value = Decimal(str(random.uniform(0.5, 3))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)   # 0.5-3倍
                    elif 'ROE' in item.name:
                        value.number_value = Decimal(str(random.uniform(1, 20))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)   # 1-20%
                    elif 'RSI' in item.name:
                        value.number_value = Decimal(str(random.uniform(20, 80))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)   # 20-80
                    else:
                        value.number_value = Decimal(str(random.uniform(1, 100))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) 
                
                elif item.item_type == 'text':
                    value.text_value = random.choice([
                        '今後の成長に期待',
                        '安定した業績',
                        '競争環境に注意',
                        '収益性の改善が必要',
                        '新規事業の展開に注目'
                    ])
                
                elif item.item_type == 'select':
                    choices = item.get_choices_list()
                    if choices:
                        value.text_value = random.choice(choices)
                
                elif item.item_type == 'boolean':
                    value.boolean_value = random.choice([True, False])
                
                elif item.item_type == 'boolean_with_value':
                    value.boolean_value = random.choice([True, False])
                    if '株価は割安か' in item.name:
                        value.number_value = round(random.uniform(-20, 40), 1)  # -20%〜40%
                    elif '負債比率' in item.name:
                        value.number_value = round(random.uniform(10, 80), 1)  # 10-80%
                    else:
                        value.number_value = round(random.uniform(0, 100), 2)
                
                value.save()
    
    print("\nテストデータの作成が完了しました！")

if __name__ == "__main__":
    create_test_data()