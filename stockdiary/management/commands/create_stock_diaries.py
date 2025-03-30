# stockdiary/management/commands/create_stock_diaries.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from stockdiary.models import StockDiary, DiaryNote
from tags.models import Tag
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from company_master.models import CompanyMaster  # For looking up sector info
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

        # テストデータ用の株式リスト（セクター情報はCompanyMasterから取得するため省略）
        stocks = [
            {"symbol": "7203", "name": "トヨタ自動車"},
            {"symbol": "6758", "name": "ソニーグループ"},
            {"symbol": "9432", "name": "日本電信電話"},
            {"symbol": "9984", "name": "ソフトバンクグループ"},
            {"symbol": "6861", "name": "キーエンス"},
            {"symbol": "6098", "name": "リクルートホールディングス"},
            {"symbol": "8035", "name": "東京エレクトロン"},
            {"symbol": "4063", "name": "信越化学工業"},
            {"symbol": "9433", "name": "KDDI"},
            {"symbol": "8306", "name": "三菱UFJフィナンシャル・グループ"},
            {"symbol": "6367", "name": "ダイキン工業"},
            {"symbol": "4519", "name": "中外製薬"},
            {"symbol": "7974", "name": "任天堂"},
            {"symbol": "9983", "name": "ファーストリテイリング"},
            {"symbol": "4568", "name": "第一三共"},
            {"symbol": "4661", "name": "オリエンタルランド"},
            {"symbol": "6501", "name": "日立製作所"},
            {"symbol": "8058", "name": "三菱商事"},
            {"symbol": "6594", "name": "日本電産"},
            {"symbol": "6460", "name": "セガサミーホールディングス"},
            {"symbol": "7267", "name": "ホンダ"},
            {"symbol": "4901", "name": "富士フイルムホールディングス"},
            {"symbol": "8591", "name": "オリックス"},
            {"symbol": "3382", "name": "セブン&アイ・ホールディングス"},
            {"symbol": "6902", "name": "デンソー"},
            {"symbol": "1925", "name": "大和ハウス工業"},
            {"symbol": "9020", "name": "東日本旅客鉄道"},
            {"symbol": "8031", "name": "三井物産"},
            {"symbol": "5108", "name": "ブリヂストン"},
            {"symbol": "9022", "name": "東海旅客鉄道"},
        ]
        
        # CompanyMasterからセクター情報を取得するメソッド
        def get_sector_for_stock(symbol):
            fallback_sectors = {
                "7203": "自動車", "6758": "テクノロジー", "9432": "通信",
                "9984": "テクノロジー", "6861": "テクノロジー", "6098": "サービス",
                "8035": "テクノロジー", "4063": "素材", "9433": "通信",
                "8306": "金融", "6367": "産業", "4519": "ヘルスケア",
                "7974": "消費財", "9983": "消費財", "4568": "ヘルスケア",
                "4661": "サービス", "6501": "産業", "8058": "商社",
                "6594": "産業", "6460": "エンターテイメント", "7267": "自動車",
                "4901": "素材", "8591": "金融", "3382": "消費財",
                "6902": "自動車部品", "1925": "不動産", "9020": "運輸",
                "8031": "商社", "5108": "自動車部品", "9022": "運輸"
            }
            
            try:
                # CompanyMasterから企業情報を取得
                company = CompanyMaster.objects.filter(code=symbol).first()
                if company and company.industry_name_33:
                    return company.industry_name_33
                
                # 見つからない場合はフォールバック
                return fallback_sectors.get(symbol, "その他")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"CompanyMaster検索中にエラー: {e}"))
                return fallback_sectors.get(symbol, "その他")
        
        # テンプレートに基づいた分析値を生成するメソッド
        def generate_template_analysis_values(template, diary):
            # テンプレート名に基づいて適切な値を生成
            template_name = template.name
            
            for item in template.items.all():
                if template_name == "基本財務分析テンプレート":
                    self.create_basic_financial_value(item, diary)
                elif template_name == "グロース株評価テンプレート":
                    self.create_growth_stock_value(item, diary)
                elif template_name == "高配当株スクリーニング":
                    self.create_high_dividend_value(item, diary)
                elif template_name == "業界比較分析":
                    self.create_industry_comparison_value(item, diary)
                elif template_name == "バリュー投資チェックリスト":
                    self.create_value_investment_value(item, diary)
                else:
                    # 不明なテンプレートの場合はランダム値
                    self.create_random_value(item, diary)

        # ランダムに日記を作成
        created_count = 0
        note_count = 0
        template_count = 0

        for _ in range(diary_count):
            stock = random.choice(stocks)
            
            # CompanyMasterからセクター情報を取得
            sector = get_sector_for_stock(stock["symbol"])
            
            # 購入/メモ日（過去3年以内）
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
            
            # 日記作成（CompanyMasterから取得したセクターを設定）
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
                sector=sector  # CompanyMasterから取得したセクター
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
                
                # テンプレートに基づいた分析値を生成
                generate_template_analysis_values(template, diary)
                
                template_count += 1
            
            # ノート追加
            for j in range(random.randint(0, notes_per_diary)):
                # ノート作成日（購入/メモ日～今日または売却日まで）
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
            
            self.stdout.write(self.style.SUCCESS(f'{created_count}/{diary_count} 件の日記を作成: {stock["name"]} ({stock["symbol"]}) セクター: {sector}'))
        
        template_status = f'うち {template_count} 件に分析テンプレートを適用' if with_analysis else ''
        self.stdout.write(self.style.SUCCESS(f'合計 {created_count} 件の日記と {note_count} 件のノート、{template_status}を作成しました。'))

    # 以下、テンプレート別の分析値生成メソッド
    def create_basic_financial_value(self, item, diary):
        """基本財務分析テンプレートの値を生成"""
        if item.name == 'PER':
            # PERは通常10〜30倍程度
            value = Decimal(random.uniform(8, 35)).quantize(Decimal('0.1'))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == 'PBR':
            # PBRは通常0.5〜3倍程度
            value = Decimal(random.uniform(0.5, 3.5)).quantize(Decimal('0.1'))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == 'ROE':
            # ROEは通常5〜20%程度
            value = Decimal(random.uniform(3, 25)).quantize(Decimal('0.1'))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == '配当利回り':
            # 配当利回りは通常0〜5%程度
            value = Decimal(random.uniform(0, 6)).quantize(Decimal('0.1'))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == '成長性評価':
            # 成長性評価の選択肢
            choices = item.get_choices_list()
            if choices:
                text_value = random.choice(choices)
                DiaryAnalysisValue.objects.create(
                    diary=diary,
                    analysis_item=item,
                    text_value=text_value
                )
        elif item.name == '投資判断':
            # 投資判断の選択肢
            choices = item.get_choices_list()
            if choices:
                text_value = random.choice(choices)
                DiaryAnalysisValue.objects.create(
                    diary=diary,
                    analysis_item=item,
                    text_value=text_value
                )

    def create_growth_stock_value(self, item, diary):
        """グロース株評価テンプレートの値を生成"""
        if item.name == '売上高成長率':
            # 成長株なので高めの成長率
            value = Decimal(random.uniform(5, 40)).quantize(Decimal('0.1'))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == '利益成長率':
            # 利益成長率も高め
            value = Decimal(random.uniform(8, 50)).quantize(Decimal('0.1'))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == 'PSR':
            # PSRは通常1〜10倍程度
            value = Decimal(random.uniform(1, 15)).quantize(Decimal('0.1'))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == 'PER > 40':
            # 成長株は高PERの可能性がある
            is_high_per = random.random() < 0.4  # 40%の確率で高PER
            per_value = Decimal(random.uniform(25, 60)).quantize(Decimal('0.1'))
            
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                boolean_value=is_high_per,
                number_value=per_value
            )
        elif item.name == '市場シェア':
            choices = item.get_choices_list()
            if choices:
                text_value = random.choice(choices)
                DiaryAnalysisValue.objects.create(
                    diary=diary,
                    analysis_item=item,
                    text_value=text_value
                )
        elif item.name == '競争優位性':
            advantages = [
                "独自技術による参入障壁", 
                "ブランド力と顧客忠誠度", 
                "ネットワーク効果が強い", 
                "特許によるプロテクション", 
                "スケールメリットによるコスト優位性",
                "サブスクリプションモデルによる安定収益"
            ]
            text_value = random.choice(advantages)
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                text_value=text_value
            )
        elif item.name == '今後3年間の予想':
            choices = item.get_choices_list()
            if choices:
                text_value = random.choice(choices)
                DiaryAnalysisValue.objects.create(
                    diary=diary,
                    analysis_item=item,
                    text_value=text_value
                )

    def create_high_dividend_value(self, item, diary):
        """高配当株スクリーニングの値を生成"""
        if item.name == '配当利回り':
            # 高配当株なので高めの利回り
            value = Decimal(random.uniform(2, 8)).quantize(Decimal('0.1'))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == '配当性向':
            # 配当性向は通常20〜50%程度
            value = Decimal(random.uniform(15, 70)).quantize(Decimal('0.1'))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == '連続増配年数':
            # 0〜10年程度
            value = Decimal(random.randint(0, 12))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == '配当利回り 3%超':
            # 高配当株なので高確率で3%超え
            is_over_3pct = random.random() < 0.7  # 70%の確率で3%超え
            yield_value = Decimal(random.uniform(2, 7)).quantize(Decimal('0.1'))
            
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                boolean_value=is_over_3pct,
                number_value=yield_value
            )
        elif item.name == '安定配当':
            # 安定配当かどうか
            is_stable = random.random() < 0.8  # 80%の確率で安定配当
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                boolean_value=is_stable
            )
        elif item.name == '財務健全性':
            choices = item.get_choices_list()
            if choices:
                text_value = random.choice(choices)
                DiaryAnalysisValue.objects.create(
                    diary=diary,
                    analysis_item=item,
                    text_value=text_value
                )
        elif item.name == '配当の継続性予想':
            choices = item.get_choices_list()
            if choices:
                text_value = random.choice(choices)
                DiaryAnalysisValue.objects.create(
                    diary=diary,
                    analysis_item=item,
                    text_value=text_value
                )

    def create_industry_comparison_value(self, item, diary):
        """業界比較分析の値を生成"""
        if item.name == '業界内PER順位':
            # 1〜10位程度
            value = Decimal(random.randint(1, 15))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == '業界内ROE順位':
            # 1〜10位程度
            value = Decimal(random.randint(1, 15))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == '売上高シェア':
            # 売上高シェアは1〜30%程度
            value = Decimal(random.uniform(1, 35)).quantize(Decimal('0.1'))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == '利益率比較':
            choices = item.get_choices_list()
            if choices:
                text_value = random.choice(choices)
                DiaryAnalysisValue.objects.create(
                    diary=diary,
                    analysis_item=item,
                    text_value=text_value
                )
        elif item.name == '成長率比較':
            choices = item.get_choices_list()
            if choices:
                text_value = random.choice(choices)
                DiaryAnalysisValue.objects.create(
                    diary=diary,
                    analysis_item=item,
                    text_value=text_value
                )
        elif item.name == '競争優位性あり':
            has_advantage = random.random() < 0.6  # 60%の確率で競争優位性あり
            
            advantage_text = ""
            if has_advantage:
                advantages = [
                    "ブランド力", "特許技術", "コスト競争力", "流通網", 
                    "研究開発力", "顧客基盤", "デジタル変革", "ESG対応"
                ]
                advantage_text = random.choice(advantages)
            
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                boolean_value=has_advantage,
                text_value=advantage_text
            )

    def create_value_investment_value(self, item, diary):
        """バリュー投資チェックリストの値を生成"""
        if item.name == 'PER < 15':
            # バリュー投資なので、低PERの確率が高い
            is_low_per = random.random() < 0.7  # 70%の確率で低PER
            per_value = Decimal(random.uniform(7, 20)).quantize(Decimal('0.1'))
            
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                boolean_value=is_low_per,
                number_value=per_value
            )
        elif item.name == 'PBR < 1.0':
            # バリュー投資なので、低PBRの確率が高い
            is_low_pbr = random.random() < 0.6  # 60%の確率で低PBR
            pbr_value = Decimal(random.uniform(0.5, 1.5)).quantize(Decimal('0.1'))
            
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                boolean_value=is_low_pbr,
                number_value=pbr_value
            )
        elif item.name == 'ROE > 10%':
            # ROE 10%以上かどうか
            is_high_roe = random.random() < 0.65  # 65%の確率で高ROE
            roe_value = Decimal(random.uniform(5, 20)).quantize(Decimal('0.1'))
            
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                boolean_value=is_high_roe,
                number_value=roe_value
            )
        elif item.name == '負債比率':
            # 負債比率は20〜80%程度
            value = Decimal(random.uniform(15, 90)).quantize(Decimal('0.1'))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == 'FCF':
            # フリーキャッシュフロー（億円）
            value = Decimal(random.uniform(10, 1000)).quantize(Decimal('0.1'))
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                number_value=value
            )
        elif item.name == '業績の安定性':
            choices = item.get_choices_list()
            if choices:
                text_value = random.choice(choices)
                DiaryAnalysisValue.objects.create(
                    diary=diary,
                    analysis_item=item,
                    text_value=text_value
                )
        elif item.name == '株主還元姿勢':
            choices = item.get_choices_list()
            if choices:
                text_value = random.choice(choices)
                DiaryAnalysisValue.objects.create(
                    diary=diary,
                    analysis_item=item,
                    text_value=text_value
                )
        elif item.name == '市場での過小評価理由':
            reasons = [
                "短期志向の市場が長期価値を評価していない",
                "一時的な業績悪化による過剰反応",
                "セクター全体の不人気",
                "複雑なビジネスモデルの理解不足",
                "ESG問題への懸念",
                "経営陣への不信感",
                "新規事業の成長性が過小評価されている",
                "構造改革の効果が市場に認識されていない"
            ]
            text_value = random.choice(reasons)
            DiaryAnalysisValue.objects.create(
                diary=diary,
                analysis_item=item,
                text_value=text_value
            )

    def create_random_value(self, item, diary):
        """ランダムな分析値を生成（既存のロジックを使用）"""
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