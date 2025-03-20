# stockdiary/management/commands/create_stock_diaries.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from stockdiary.models import StockDiary, DiaryNote
from tags.models import Tag
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
import random
import datetime
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = "株式日記のテストデータを作成します"

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='テストデータを作成するユーザー名')
        parser.add_argument('--count', type=int, default=10, help='作成する日記の数 (デフォルト: 10)')
        parser.add_argument('--notes', type=int, default=3, help='各日記に追加するノートの数 (デフォルト: 3)')
        parser.add_argument('--with-analysis', action='store_true', help='分析テンプレートを適用するかどうか')

    def handle(self, *args, **options):
        username = options['username']
        diary_count = options['count']
        notes_per_diary = options['notes']
        with_analysis = options['with_analysis']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'ユーザー "{username}" が見つかりません。'))
            return

        # ユーザーのタグを取得
        user_tags = list(Tag.objects.filter(user=user))
        if not user_tags:
            self.stdout.write(self.style.WARNING(f'ユーザー "{username}" のタグが見つかりません。タグなしで日記を作成します。'))

        # ユーザーの分析テンプレートを取得
        templates = list(AnalysisTemplate.objects.filter(user=user).prefetch_related('items'))
        if with_analysis and not templates:
            self.stdout.write(self.style.WARNING(f'ユーザー "{username}" の分析テンプレートが見つかりません。テンプレートなしで日記を作成します。'))
        elif with_analysis:
            self.stdout.write(self.style.SUCCESS(f'ユーザー "{username}" の分析テンプレートが {len(templates)} 件見つかりました。'))

        # テストデータ用の株式リスト（セクター情報を追加）
        stocks = [
            {"symbol": "7203", "name": "トヨタ自動車", "sector": "自動車"},
            {"symbol": "6758", "name": "ソニーグループ", "sector": "テクノロジー"},
            {"symbol": "9432", "name": "日本電信電話", "sector": "通信"},
            {"symbol": "9984", "name": "ソフトバンクグループ", "sector": "テクノロジー"},
            {"symbol": "6861", "name": "キーエンス", "sector": "テクノロジー"},
            {"symbol": "6098", "name": "リクルートホールディングス", "sector": "サービス"},
            {"symbol": "8035", "name": "東京エレクトロン", "sector": "テクノロジー"},
            {"symbol": "4063", "name": "信越化学工業", "sector": "素材"},
            {"symbol": "9433", "name": "KDDI", "sector": "通信"},
            {"symbol": "8306", "name": "三菱UFJフィナンシャル・グループ", "sector": "金融"},
            {"symbol": "6367", "name": "ダイキン工業", "sector": "産業"},
            {"symbol": "4519", "name": "中外製薬", "sector": "ヘルスケア"},
            {"symbol": "7974", "name": "任天堂", "sector": "消費財"},
            {"symbol": "9983", "name": "ファーストリテイリング", "sector": "消費財"},
            {"symbol": "4568", "name": "第一三共", "sector": "ヘルスケア"},
            {"symbol": "4661", "name": "オリエンタルランド", "sector": "サービス"},
            {"symbol": "6501", "name": "日立製作所", "sector": "産業"},
            {"symbol": "8058", "name": "三菱商事", "sector": "商社"},
            {"symbol": "6594", "name": "日本電産", "sector": "産業"},
            {"symbol": "6460", "name": "セガサミーホールディングス", "sector": "エンターテイメント"},
            {"symbol": "7267", "name": "ホンダ", "sector": "自動車"},
            {"symbol": "4901", "name": "富士フイルムホールディングス", "sector": "素材"},
            {"symbol": "8591", "name": "オリックス", "sector": "金融"},
            {"symbol": "3382", "name": "セブン&アイ・ホールディングス", "sector": "消費財"},
            {"symbol": "6902", "name": "デンソー", "sector": "自動車部品"},
            {"symbol": "1925", "name": "大和ハウス工業", "sector": "不動産"},
            {"symbol": "9020", "name": "東日本旅客鉄道", "sector": "運輸"},
            {"symbol": "8031", "name": "三井物産", "sector": "商社"},
            {"symbol": "5108", "name": "ブリヂストン", "sector": "自動車部品"},
            {"symbol": "9022", "name": "東海旅客鉄道", "sector": "運輸"},
            # 米国株も必要に応じて追加可能
            {"symbol": "AAPL", "name": "アップル", "sector": "テクノロジー"},
            {"symbol": "MSFT", "name": "マイクロソフト", "sector": "テクノロジー"},
            {"symbol": "AMZN", "name": "アマゾン", "sector": "テクノロジー"},
            {"symbol": "GOOGL", "name": "アルファベット", "sector": "テクノロジー"},
            {"symbol": "NVDA", "name": "エヌビディア", "sector": "テクノロジー"},
            {"symbol": "TSLA", "name": "テスラ", "sector": "自動車"},
            {"symbol": "META", "name": "メタ・プラットフォームズ", "sector": "テクノロジー"},
            {"symbol": "NFLX", "name": "ネットフリックス", "sector": "エンターテイメント"},
            {"symbol": "ADBE", "name": "アドビ", "sector": "テクノロジー"},
            {"symbol": "JPM", "name": "JPモルガン・チェース", "sector": "金融"},
        ]

        # ランダムに日記を作成
        created_count = 0
        note_count = 0
        template_count = 0

        for _ in range(diary_count):
            stock = random.choice(stocks)
            
            # 購入日（過去3年以内）
            today = datetime.date.today()
            days_ago = random.randint(1, 1095)  # 最大3年（365*3日）
            purchase_date = today - datetime.timedelta(days=days_ago)
            
            # 購入価格
            purchase_price = Decimal(random.uniform(1000, 50000)).quantize(Decimal('0.01'))
            
            # 購入数量
            purchase_quantity = random.randint(1, 1000)
            
            # 購入理由
            reasons = [
                f"<p>{stock['name']}は、{random.choice(['将来性', '収益性', '安定性', '成長性'])}があると判断しました。</p><p>特に{random.choice(['新製品の開発', '市場シェアの拡大', '安定した業績', '高い配当利回り'])}が魅力的です。</p>",
                f"<p>業界内での{stock['name']}の{random.choice(['競争力', 'ブランド力', '技術力', '財務体質'])}が強いと考えています。</p><p>{random.choice(['将来の成長', '安定した配当', '株価の割安感', '短期的な値上がり'])}を期待して購入しました。</p>",
                f"<p>{random.choice(['決算発表', '新製品発表', '新規事業参入', 'M&A'])}を受けて、{stock['name']}の成長機会が拡大すると考えました。</p>",
                f"<p>{stock['name']}は{random.choice(['PER', 'PBR', 'ROE', '配当利回り'])}の観点から割安と判断しました。中長期で保有する方針です。</p>"
            ]
            reason = random.choice(reasons)
            
            # 売却データ（約20%の確率で売却済み）
            sell_date = None
            sell_price = None
            if random.random() < 0.2:
                days_after = random.randint(1, min(days_ago, 730))  # 購入から最大2年後（または今日まで）
                sell_date = purchase_date + datetime.timedelta(days=days_after)
                # 売却価格（購入価格の80%～150%）
                sell_price = purchase_price * Decimal(random.uniform(0.8, 1.5)).quantize(Decimal('0.01'))
            
            # メモ
            memos = [
                f"{stock['name']}の長期保有を検討。四半期ごとに業績をチェックする予定。",
                f"株主優待があるため、権利確定日まで保有予定。",
                f"配当金は再投資する方針。",
                f"チャートの動きを注視。サポートラインを下回ったら売却を検討。",
                ""  # 空のメモもあり得る
            ]
            memo = random.choice(memos)
            
            # 日記作成（セクター情報を追加）
            diary = StockDiary.objects.create(
                user=user,
                stock_symbol=stock["symbol"],
                stock_name=stock["name"],
                purchase_date=purchase_date,
                purchase_price=purchase_price,
                purchase_quantity=purchase_quantity,
                reason=reason,
                sell_date=sell_date,
                sell_price=sell_price,
                memo=memo,
                sector=stock["sector"]  # セクター情報を設定
            )
            
            # タグ付け（ランダムに1～4個のタグを選択）
            if user_tags:
                tag_count = min(random.randint(1, 4), len(user_tags))
                selected_tags = random.sample(user_tags, tag_count)
                for tag in selected_tags:
                    diary.tags.add(tag)
            
            created_count += 1
            
            # 分析テンプレートの適用（80%の確率で適用）
            if with_analysis and templates and random.random() < 0.8:
                # ランダムにテンプレートを選択
                template = random.choice(templates)
                
                # テンプレート内の各項目について値を生成
                for item in template.items.all():
                    # 項目タイプに応じて適切な値を生成
                    if item.item_type == 'boolean':
                        # ブール値の場合
                        boolean_value = random.choice([True, False])
                        DiaryAnalysisValue.objects.create(
                            diary=diary,
                            analysis_item=item,
                            boolean_value=boolean_value
                        )
                    
                    elif item.item_type == 'number':
                        # 数値の場合
                        if random.random() < 0.9:  # 90%の確率で値を設定
                            number_value = Decimal(random.uniform(1, 100)).quantize(Decimal('0.1'))
                            DiaryAnalysisValue.objects.create(
                                diary=diary,
                                analysis_item=item,
                                number_value=number_value
                            )
                    
                    elif item.item_type == 'select':
                        # 選択肢の場合
                        if random.random() < 0.9 and item.choices:  # 90%の確率で値を設定
                            choices = item.get_choices_list()
                            if choices:
                                text_value = random.choice(choices)
                                DiaryAnalysisValue.objects.create(
                                    diary=diary,
                                    analysis_item=item,
                                    text_value=text_value
                                )
                    
                    elif item.item_type == 'text':
                        # テキストの場合
                        if random.random() < 0.8:  # 80%の確率で値を設定
                            text_options = [
                                "良好", "注意が必要", "期待できる", "慎重に判断", 
                                "強気", "弱気", "横ばい", "上昇傾向", "下降傾向"
                            ]
                            text_value = random.choice(text_options)
                            DiaryAnalysisValue.objects.create(
                                diary=diary,
                                analysis_item=item,
                                text_value=text_value
                            )
                    
                    elif item.item_type == 'boolean_with_value':
                        # ブール値+値入力の複合型
                        boolean_value = random.choice([True, False])
                        
                        if boolean_value and random.random() < 0.8:  # TRUEかつ80%の確率で値を設定
                            # 数値か文字列かランダムに決定
                            if random.random() < 0.5:
                                # 数値
                                number_value = Decimal(random.uniform(1, 100)).quantize(Decimal('0.1'))
                                DiaryAnalysisValue.objects.create(
                                    diary=diary,
                                    analysis_item=item,
                                    boolean_value=boolean_value,
                                    number_value=number_value
                                )
                            else:
                                # 文字列
                                text_options = [
                                    "高い", "低い", "普通", "良い", "悪い", 
                                    "優れている", "不足している", "適切", "不適切"
                                ]
                                text_value = random.choice(text_options)
                                DiaryAnalysisValue.objects.create(
                                    diary=diary,
                                    analysis_item=item,
                                    boolean_value=boolean_value,
                                    text_value=text_value
                                )
                        else:
                            # ブール値のみ
                            DiaryAnalysisValue.objects.create(
                                diary=diary,
                                analysis_item=item,
                                boolean_value=boolean_value
                            )
                
                template_count += 1
            
            # ノート追加
            for j in range(random.randint(0, notes_per_diary)):
                # ノート作成日（購入日～今日または売却日まで）
                if sell_date:
                    days_after_purchase = random.randint(1, (sell_date - purchase_date).days)
                else:
                    days_after_purchase = random.randint(1, (today - purchase_date).days)
                note_date = purchase_date + datetime.timedelta(days=days_after_purchase)
                
                # 現在価格（購入価格の70%～200%）
                current_price = purchase_price * Decimal(random.uniform(0.7, 2.0)).quantize(Decimal('0.01'))
                
                # ノートタイプ
                note_type = random.choice(['analysis', 'news', 'earnings', 'insight', 'risk', 'other'])
                
                # 重要度
                importance = random.choice(['high', 'medium', 'low'])
                
                # ノート内容
                contents = {
                    'analysis': [
                        f"<p>テクニカル分析: {stock['name']}の株価はサポートラインを{random.choice(['上回った', '下回った'])}。{random.choice(['上昇トレンド継続中', '下降トレンドに注意', 'レンジ相場が続く'])}。</p>",
                        f"<p>ファンダメンタル分析: 四半期決算は{random.choice(['予想を上回った', '予想通り', '予想を下回った'])}。特に{random.choice(['売上高', '営業利益', '純利益', 'キャッシュフロー'])}に{random.choice(['改善', '悪化'])}がみられる。</p>",
                    ],
                    'news': [
                        f"<p>{stock['name']}が{random.choice(['新製品発表', '新規事業参入', 'リストラ計画', '自社株買い'])}を発表。株価は{random.choice(['上昇', '下落', '横ばい'])}。</p>",
                        f"<p>業界ニュース: {random.choice(['規制強化', '新技術登場', '市場拡大', '競合企業の動向'])}により、{stock['name']}への影響が{random.choice(['プラス', 'マイナス', '限定的'])}と予想される。</p>",
                    ],
                    'earnings': [
                        f"<p>{stock['name']}の{random.choice(['第1四半期', '第2四半期', '第3四半期', '通期'])}決算発表。売上高は{random.choice(['前年比増加', '前年比減少', '横ばい'])}、純利益は{random.choice(['前年比増加', '前年比減少', '横ばい'])}。</p>",
                        f"<p>来期の業績予想は{random.choice(['上方修正', '下方修正', '据え置き'])}。特に{random.choice(['国内事業', '海外事業', '新規事業', '主力事業'])}の{random.choice(['成長', '不振'])}が目立つ。</p>",
                    ],
                    'insight': [
                        f"<p>経営陣の{random.choice(['インタビュー', '株主総会での発言', 'IR資料'])}から、今後{random.choice(['積極的なM&A', '事業再編', 'コスト削減', '研究開発強化'])}の方針が明確になった。</p>",
                        f"<p>{stock['name']}の{random.choice(['業界内での位置づけ', '競争優位性', '成長戦略'])}について再評価。{random.choice(['より前向き', 'やや慎重', '変更なし'])}な見方に。</p>",
                    ],
                    'risk': [
                        f"<p>リスク要因: {random.choice(['為替変動', '原材料価格上昇', '競合激化', '規制強化', '技術革新の遅れ'])}が{stock['name']}の業績に影響を与える可能性がある。</p>",
                        f"<p>{random.choice(['景気後退', '金利上昇', 'インフレ', '地政学的リスク'])}により、{stock['name']}を含む{random.choice(['業界全体', 'セクター', '国内企業'])}への影響が懸念される。</p>",
                    ],
                    'other': [
                        f"<p>株主優待の内容が{random.choice(['変更', '拡充', '縮小'])}された。権利確定日は{random.choice(['3月末', '9月末', '12月末'])}。</p>",
                        f"<p>配当方針が{random.choice(['変更', '維持'])}された。配当性向は{random.randint(20, 50)}%程度に。</p>",
                        f"<p>個人的メモ: {random.choice(['もう少し様子を見る', '買い増しを検討', '利確を検討', '長期保有の方針は変更なし'])}。</p>",
                    ],
                }
                content = random.choice(contents[note_type])
                
                # ノート作成
                DiaryNote.objects.create(
                    diary=diary,
                    date=note_date,
                    content=content,
                    current_price=current_price,
                    note_type=note_type,
                    importance=importance
                )
                
                note_count += 1
            
            self.stdout.write(self.style.SUCCESS(f'{created_count}/{diary_count} 件の日記を作成: {stock["name"]} ({stock["symbol"]}) セクター: {stock["sector"]}'))
        
        template_status = f'うち {template_count} 件に分析テンプレートを適用' if with_analysis else ''
        self.stdout.write(self.style.SUCCESS(f'合計 {created_count} 件の日記と {note_count} 件のノート、{template_status}を作成しました。'))