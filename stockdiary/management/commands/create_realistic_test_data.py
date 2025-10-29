# stockdiary/management/commands/create_realistic_test_data.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from stockdiary.models import StockDiary, Transaction, DiaryNote, StockSplit
from tags.models import Tag
from decimal import Decimal
from datetime import datetime, timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'リアルなテストデータを作成します'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='testuser',
            help='データを作成するユーザー名（デフォルト: testuser）',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='既存データを削除してから作成',
        )
    
    def handle(self, *args, **options):
        username = options['username']
        clear_data = options['clear']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ ユーザー "{username}" が見つかりません'))
            self.stdout.write('先にユーザーを作成してください: python manage.py createsuperuser')
            return
        
        if clear_data:
            self.stdout.write('🗑️  既存データを削除中...')
            StockDiary.objects.filter(user=user).delete()
            Tag.objects.filter(user=user).delete()
            self.stdout.write(self.style.SUCCESS('✅ 既存データを削除しました'))
        
        self.stdout.write(f'📊 ユーザー "{username}" のテストデータを作成中...\n')
        
        # タグの作成
        tags = self.create_tags(user)
        self.stdout.write(self.style.SUCCESS(f'✅ タグを {len(tags)}個 作成しました'))
        
        # 銘柄データの作成
        diaries_created, transactions_created, notes_created, splits_created = self.create_stock_diaries(user, tags)
        
        self.stdout.write(self.style.SUCCESS(f'✅ 日記を {diaries_created}件 作成しました'))
        self.stdout.write(self.style.SUCCESS(f'✅ 取引を {transactions_created}件 作成しました'))
        self.stdout.write(self.style.SUCCESS(f'✅ 継続記録を {notes_created}件 作成しました'))
        self.stdout.write(self.style.SUCCESS(f'✅ 株式分割を {splits_created}件 作成しました'))
        
        # 統計情報を表示
        self._show_statistics(user)
        
        self.stdout.write(self.style.SUCCESS('\n🎉 テストデータの作成が完了しました！'))
    
    def create_tags(self, user):
        """リアルなタグを作成"""
        tag_names = [
            '長期保有', '高配当', '成長株', 'バリュー株',
            'テクノロジー', '自動車', '金融', '半導体',
            '要注視', '買い増し候補', '損切り検討', '優待目当て',
            'IPO', 'ESG投資', '割安株'
        ]
        
        tags = []
        for name in tag_names:
            tag, created = Tag.objects.get_or_create(user=user, name=name)
            tags.append(tag)
        
        return tags
    
    def create_stock_diaries(self, user, tags):
        """リアルな株式日記データを作成"""
        
        created_count = 0
        transactions_count = 0
        notes_count = 0
        splits_count = 0
        
        # 実在の日本株データ（銘柄コード、名称、業種、投資理由、メモ）
        stock_data = [
            {
                'code': '7203',
                'name': 'トヨタ自動車',
                'sector': '輸送用機器',
                'reason': '''電気自動車（EV）への転換期において、トヨタは全方位戦略を採用しており、ハイブリッド、プラグインハイブリッド、燃料電池車、EVをバランス良く展開している。特にハイブリッド技術では世界トップレベルの実績を持ち、この技術をEVにも活かせる強みがある。

2025年に向けて、全固体電池の実用化を目指しており、これが実現すれば航続距離と充電時間で大きなアドバンテージを得られる可能性がある。また、豊田章男会長の後継体制も順調で、経営の安定性も評価できる。

配当利回りも3%前後と安定しており、長期保有に適した銘柄と判断。株価は景気敏感株のため変動が大きいが、世界販売台数No.1の実績と財務基盤の強さから、押し目買いの機会と捉えている。''',
                'memo': 'EV市場の動向と全固体電池の開発進捗に注目。特に中国市場でのシェア低下が懸念材料だが、CASE対応への投資は着実に進んでいる。',
                'tags': ['長期保有', 'テクノロジー', '自動車'],
                'transactions': [
                    {'date': -365, 'type': 'buy', 'price': 2420, 'quantity': 100, 'memo': '新NISA枠で初回購入'},
                    {'date': -300, 'type': 'buy', 'price': 2380, 'quantity': 100, 'memo': '米国金利上昇による下落で買い増し'},
                    {'date': -250, 'type': 'buy', 'price': 2550, 'quantity': 50, 'memo': '自動車販売台数好調により追加'},
                    {'date': -180, 'type': 'buy', 'price': 2650, 'quantity': 100, 'memo': '円安進行で業績上方修正期待'},
                    {'date': -150, 'type': 'sell', 'price': 2880, 'quantity': 50, 'memo': '短期的な過熱感により一部利確'},
                    {'date': -120, 'type': 'buy', 'price': 2450, 'quantity': 100, 'memo': '押し目買いのチャンス'},
                    {'date': -90, 'type': 'buy', 'price': 2590, 'quantity': 50, 'memo': '全固体電池開発進展のニュースで追加'},
                    {'date': -60, 'type': 'buy', 'price': 2720, 'quantity': 50, 'memo': '配当権利落ち後の取得'},
                    {'date': -30, 'type': 'buy', 'price': 2820, 'quantity': 50, 'memo': '決算好調による買い増し'},
                ],
                'stock_splits': [
                    {'date': -400, 'ratio': 5.0, 'memo': '1:5の株式分割実施', 'applied': True}
                ],
                'notes': [
                    {
                        'days_ago': 30,
                        'content': '2024年第3四半期決算を確認。営業利益率が改善傾向にあり、為替の追い風もあって好調。ただし半導体不足の影響はまだ残っている。電動化への投資を加速する方針を表明。',
                        'type': 'earnings',
                        'importance': 'high',
                        'price': 2850
                    },
                    {
                        'days_ago': 15,
                        'content': '全固体電池の試作品が公開され、2027-2028年の実用化を目指すとのニュース。充電時間10分以下、航続距離1200kmを実現する可能性があり、ゲームチェンジャーになり得る技術。',
                        'type': 'news',
                        'importance': 'high',
                        'price': 2920
                    },
                    {
                        'days_ago': 5,
                        'content': '中国のEVメーカーBYDが価格攻勢を強めており、アジア市場でのシェア争いが激化。トヨタもハイブリッド車の価格競争力を高める必要がある。',
                        'type': 'risk',
                        'importance': 'medium',
                        'price': 2780
                    }
                ]
            },
            {
                'code': '6758',
                'name': 'ソニーグループ',
                'sector': '電気機器',
                'reason': '''エンターテインメント、ゲーム、音楽、映画、金融、センサーなど多角的な事業ポートフォリオを持ち、リスク分散が効いている。特にPlayStation 5の好調な販売と、ゲーム事業の収益性の高さが魅力。

イメージセンサー事業では世界シェアトップを維持しており、スマートフォン向けだけでなく、自動運転車向けセンサーの需要拡大も見込める。音楽・映画などのコンテンツIPも豊富で、ストリーミング時代に強い。

株価は一時期と比べて落ち着いているが、PERは20倍程度と妥当な水準。配当性向も30%程度で、増配余地もある。中長期での成長が期待できる。''',
                'memo': 'PS5の販売台数と半導体調達状況、イメージセンサーの新規受注状況に注目。',
                'tags': ['成長株', 'テクノロジー', '長期保有'],
                'transactions': [
                    {'date': -320, 'type': 'buy', 'price': 12200, 'quantity': 20, 'memo': 'PS5好調で長期保有目的で購入'},
                    {'date': -280, 'type': 'buy', 'price': 11800, 'quantity': 20, 'memo': '半導体不足の懸念で下落したが買い増し'},
                    {'date': -200, 'type': 'buy', 'price': 12800, 'quantity': 20, 'memo': 'イメージセンサー事業好調'},
                    {'date': -150, 'type': 'buy', 'price': 13200, 'quantity': 20, 'memo': 'エンタメ事業の成長期待'},
                    {'date': -120, 'type': 'buy', 'price': 12600, 'quantity': 30, 'memo': '調整局面での買い増し'},
                    {'date': -90, 'type': 'buy', 'price': 11900, 'quantity': 30, 'memo': '押し目買い'},
                    {'date': -45, 'type': 'buy', 'price': 13500, 'quantity': 20, 'memo': '決算好調で追加投資'},
                ],
                'notes': [
                    {
                        'days_ago': 45,
                        'content': 'PS5の累計販売台数が5000万台を突破。ソフトウェアの売上も好調で、デジタル販売比率が70%を超えている。利益率の高いデジタル販売が主流になりつつある。',
                        'type': 'news',
                        'importance': 'high',
                        'price': 13500
                    },
                    {
                        'days_ago': 20,
                        'content': 'イメージセンサー事業の第4四半期は、スマホ需要の回復により前年比15%増収。車載向けセンサーの引き合いも強く、将来の成長ドライバーとして期待。',
                        'type': 'analysis',
                        'importance': 'medium',
                        'price': 13800
                    }
                ]
            },
            {
                'code': '6861',
                'name': 'キーエンス',
                'sector': '電気機器',
                'reason': '''FAセンサーのトップメーカーで、高い技術力と営業力を持つ。営業利益率が50%を超える圧倒的な収益性が魅力。顧客の生産性向上に直結する製品を提供しており、価格競争に巻き込まれにくいビジネスモデル。

研究開発投資も積極的で、新製品開発サイクルが早い。従業員の平均年収が2000万円超と高く、優秀な人材を確保できている点も強み。

PERは40-50倍と割高だが、成長性と収益性を考えれば妥当。世界的な自動化需要の高まりを背景に、中長期での成長が見込める。配当利回りは低いが、増配率が高い。''',
                'memo': '製造業の設備投資動向と中国景気に注意。株価のボラティリティは高いが、長期では右肩上がり。',
                'tags': ['成長株', 'テクノロジー', '半導体'],
                'transactions': [
                    {'date': -350, 'type': 'buy', 'price': 54000, 'quantity': 5, 'memo': '高収益企業として長期保有開始'},
                    {'date': -280, 'type': 'buy', 'price': 51000, 'quantity': 5, 'memo': '製造業の設備投資期待で追加'},
                    {'date': -250, 'type': 'buy', 'price': 58000, 'quantity': 5, 'memo': '受注好調で買い増し'},
                    {'date': -200, 'type': 'sell', 'price': 64000, 'quantity': 3, 'memo': '高値圏での利益確定'},
                    {'date': -180, 'type': 'buy', 'price': 52000, 'quantity': 5, 'memo': '調整局面で買い戻し'},
                    {'date': -140, 'type': 'buy', 'price': 60000, 'quantity': 3, 'memo': 'FAセンサー需要増で追加'},
                    {'date': -100, 'type': 'sell', 'price': 68000, 'quantity': 3, 'memo': '目標株価到達で一部売却'},
                    {'date': -50, 'type': 'buy', 'price': 62000, 'quantity': 3, 'memo': '押し目買い'},
                ],
                'notes': [
                    {
                        'days_ago': 60,
                        'content': '2024年度の業績予想を上方修正。特にアジア地域での受注が好調で、工場自動化の需要が旺盛。半導体製造装置向けセンサーの売上が前年比30%増。',
                        'type': 'earnings',
                        'importance': 'high',
                        'price': 65000
                    },
                    {
                        'days_ago': 25,
                        'content': 'PERが50倍を超えており、短期的には割高感がある。一旦利益確定も検討したが、長期的な成長ストーリーは変わらないので保有継続の方針。',
                        'type': 'insight',
                        'importance': 'medium',
                        'price': 67000
                    }
                ]
            },
            {
                'code': '8306',
                'name': '三菱UFJフィナンシャル・グループ',
                'sector': '銀行業',
                'reason': '''日本最大のメガバンクで、安定した収益基盤を持つ。配当利回りが4%前後と高く、インカムゲイン重視の投資に適している。株価純資産倍率(PBR)も0.7倍程度と割安。

日銀の金融政策正常化により、金利上昇局面では利ザヤ拡大が期待できる。2024年以降、マイナス金利政策の解除により、銀行株全体にとって追い風となる可能性が高い。

海外展開も積極的で、アジアを中心にリテール・法人向けビジネスを拡大中。デジタル化投資も進めており、コスト削減効果が今後顕在化する見込み。''',
                'memo': '金利動向と日銀政策に注目。不良債権比率は低く、財務健全性は高い。',
                'tags': ['高配当', '金融', 'バリュー株', '長期保有'],
                'transactions': [
                    {'date': -330, 'type': 'buy', 'price': 880, 'quantity': 500, 'memo': '高配当銘柄として初回購入'},
                    {'date': -280, 'type': 'buy', 'price': 920, 'quantity': 300, 'memo': '金利上昇期待で追加'},
                    {'date': -220, 'type': 'buy', 'price': 950, 'quantity': 500, 'memo': 'マイナス金利解除観測で買い増し'},
                    {'date': -180, 'type': 'buy', 'price': 900, 'quantity': 400, 'memo': '調整局面での買い増し'},
                    {'date': -160, 'type': 'buy', 'price': 880, 'quantity': 500, 'memo': '押し目買いチャンス'},
                    {'date': -120, 'type': 'buy', 'price': 980, 'quantity': 300, 'memo': '日銀政策転換期待で追加'},
                    {'date': -80, 'type': 'buy', 'price': 1020, 'quantity': 300, 'memo': 'マイナス金利解除で買い増し'},
                    {'date': -40, 'type': 'buy', 'price': 1150, 'quantity': 200, 'memo': '利ザヤ改善期待で追加投資'},
                ],
                'notes': [
                    {
                        'days_ago': 40,
                        'content': '日銀がマイナス金利政策の解除を示唆。これにより銀行の利ザヤ改善が期待され、株価は上昇基調。今後の金融政策に注目。',
                        'type': 'news',
                        'importance': 'high',
                        'price': 1150
                    },
                    {
                        'days_ago': 10,
                        'content': '2025年3月期第2四半期決算。純利益は前年同期比20%増と好調。海外事業の収益貢献が大きく、特にアジアでの法人向け融資が伸びている。',
                        'type': 'earnings',
                        'importance': 'high',
                        'price': 1220
                    }
                ]
            },
            {
                'code': '7974',
                'name': '任天堂',
                'sector': '電気機器',
                'reason': '''Nintendo Switchの累計販売台数が1.3億台を超え、歴代ゲーム機でもトップクラスの成功を収めている。ソフトウェアの販売も好調で、「ゼルダの伝説」「スプラトゥーン」「あつまれ どうぶつの森」などのキラーコンテンツを多数保有。

次世代機の開発も進んでおり、2025年以降の発売が予想される。Switch後継機への期待と、既存Switchユーザーの買い替え需要が見込める。

IPの活用にも積極的で、映画「ザ・スーパーマリオブラザーズ・ムービー」は世界的な大ヒット。USJのスーパーニンテンドーワールドも好評で、ゲーム以外の収益源も育ちつつある。''',
                'memo': '次世代機の発表時期と仕様に注目。為替の影響を受けやすいため、円高局面では注意が必要。',
                'tags': ['成長株', 'テクノロジー', '長期保有'],
                'transactions': [
                    {'date': -310, 'type': 'buy', 'price': 5800, 'quantity': 30, 'memo': 'Switch好調で長期保有開始'},
                    {'date': -260, 'type': 'buy', 'price': 6100, 'quantity': 40, 'memo': 'ゼルダ発売前に買い増し'},
                    {'date': -190, 'type': 'buy', 'price': 6200, 'quantity': 50, 'memo': 'ゼルダ好調で追加投資'},
                    {'date': -150, 'type': 'buy', 'price': 5700, 'quantity': 40, 'memo': '調整局面での買い増し'},
                    {'date': -130, 'type': 'buy', 'price': 5800, 'quantity': 50, 'memo': '次世代機期待で追加'},
                    {'date': -100, 'type': 'sell', 'price': 6800, 'quantity': 50, 'memo': '高値圏での利益確定'},
                    {'date': -70, 'type': 'buy', 'price': 6500, 'quantity': 30, 'memo': '押し目買い'},
                    {'date': -30, 'type': 'buy', 'price': 7000, 'quantity': 20, 'memo': '次世代機発表期待で追加'},
                ],
                'stock_splits': [
                    {'date': -420, 'ratio': 10.0, 'memo': '1:10の株式分割実施', 'applied': True}
                ],
                'notes': [
                    {
                        'days_ago': 50,
                        'content': '「ゼルダの伝説 ティアーズ オブ ザ キングダム」の販売本数が2000万本を突破。Switch向けタイトルとしては歴代最高ペースの売上。',
                        'type': 'news',
                        'importance': 'medium',
                        'price': 6800
                    },
                    {
                        'days_ago': 20,
                        'content': '次世代機に関する噂が各メディアで報じられている。2025年春の発表、秋の発売が有力視されている。スペックは現行機の3-4倍程度の性能になると予想。',
                        'type': 'insight',
                        'importance': 'high',
                        'price': 7100
                    }
                ]
            },
            {
                'code': '9984',
                'name': 'ソフトバンクグループ',
                'sector': '情報・通信業',
                'reason': '''世界的なテクノロジー投資会社で、AI、半導体、フィンテックなど成長分野に幅広く投資。特にArm Holdings（半導体設計）の保有比率が高く、AI向けチップ需要の恩恵を受けられる。

孫正義会長の投資眼は賛否両論あるが、これまでアリババ、Yahoo!など数々の成功事例を生み出してきた。ビジョン・ファンドのポートフォリオには有望なスタートアップが多数含まれており、将来的なIPOやM&Aによるキャピタルゲインが期待できる。

財務レバレッジが高く、金利上昇局面ではマイナス要因だが、保有資産の価値向上により相殺可能。株価は純資産価値(NAV)に対して割安で推移しており、バリュエーション面での妙味がある。''',
                'memo': 'Armの株価と業績、ビジョン・ファンドの投資先のIPO動向に注目。LTVレシオは要監視。',
                'tags': ['成長株', 'テクノロジー', 'バリュー株'],
                'transactions': [
                    {'date': -280, 'type': 'buy', 'price': 5200, 'quantity': 50, 'memo': 'Arm上場期待で購入'},
                    {'date': -240, 'type': 'buy', 'price': 4800, 'quantity': 60, 'memo': '株価調整局面で買い増し'},
                    {'date': -200, 'type': 'buy', 'price': 5500, 'quantity': 40, 'memo': 'Arm好調で追加投資'},
                    {'date': -170, 'type': 'buy', 'price': 5800, 'quantity': 50, 'memo': 'AI投資拡大発表で買い増し'},
                    {'date': -140, 'type': 'sell', 'price': 6500, 'quantity': 40, 'memo': '高値圏での利益確定'},
                    {'date': -110, 'type': 'buy', 'price': 5200, 'quantity': 80, 'memo': '押し目買いの好機'},
                    {'date': -70, 'type': 'buy', 'price': 6200, 'quantity': 50, 'memo': 'ビジョンファンド好調で追加'},
                    {'date': -40, 'type': 'sell', 'price': 6900, 'quantity': 50, 'memo': '短期的な過熱感で利確'},
                ],
                'notes': [
                    {
                        'days_ago': 35,
                        'content': 'Armの2024年度Q2決算が予想を上回る好調な内容。AI向けチップの需要増加により、ライセンス収入が大幅増。株価も上昇しており、SBGの保有資産価値も向上。',
                        'type': 'earnings',
                        'importance': 'high',
                        'price': 6500
                    },
                    {
                        'days_ago': 12,
                        'content': '孫社長が「AI革命に全力投資」と発言。今後1年で1兆円規模のAI関連投資を行う方針。積極姿勢は評価できるが、リスクも高まる。',
                        'type': 'news',
                        'importance': 'medium',
                        'price': 7200
                    }
                ]
            },
            {
                'code': '9433',
                'name': 'KDDI',
                'sector': '情報・通信業',
                'reason': '''通信インフラ事業の安定収益に加え、金融、エネルギー、DXなど非通信事業の拡大により、成長性と安定性を両立。配当利回りは3.5%程度で、16期連続増配を継続中。

5G基地局の整備が進み、今後は5Gを活用した法人向けソリューション事業の拡大が期待できる。auスマートフォンのシェアも安定しており、ARPU（ユーザー単価）は微増傾向。

楽天モバイルとのローミング契約終了により、ネットワークコストが削減される見込み。株主優待もカタログギフトで魅力的。''',
                'memo': '通信料金値下げ圧力と楽天モバイルの動向に注意。金融事業の成長性に期待。',
                'tags': ['高配当', '長期保有', '優待目当て'],
                'transactions': [
                    {'date': -340, 'type': 'buy', 'price': 3720, 'quantity': 100, 'memo': '高配当・優待目当てで購入'},
                    {'date': -300, 'type': 'buy', 'price': 3650, 'quantity': 100, 'memo': '配当権利落ち後の取得'},
                    {'date': -270, 'type': 'buy', 'price': 3800, 'quantity': 100, 'memo': '16期連続増配で追加'},
                    {'date': -240, 'type': 'buy', 'price': 3680, 'quantity': 100, 'memo': '調整局面での買い増し'},
                    {'date': -210, 'type': 'buy', 'price': 3650, 'quantity': 100, 'memo': '押し目買い'},
                    {'date': -180, 'type': 'buy', 'price': 3920, 'quantity': 100, 'memo': '金融事業好調で追加'},
                    {'date': -140, 'type': 'buy', 'price': 4100, 'quantity': 100, 'memo': '増配発表で買い増し'},
                    {'date': -90, 'type': 'buy', 'price': 4250, 'quantity': 100, 'memo': '配当利回り3.5%維持で追加'},
                    {'date': -50, 'type': 'buy', 'price': 4200, 'quantity': 100, 'memo': '優待拡充発表で買い増し'},
                ],
                'notes': [
                    {
                        'days_ago': 55,
                        'content': '2025年3月期の配当予想を1株135円に引き上げ。17期連続増配となる見込み。株主還元姿勢が明確で、長期保有に適している。',
                        'type': 'earnings',
                        'importance': 'high',
                        'price': 4300
                    },
                    {
                        'days_ago': 28,
                        'content': 'auじぶん銀行の口座数が500万を突破。金融事業の収益貢献度が年々高まっている。auペイの利用者数も増加傾向。',
                        'type': 'analysis',
                        'importance': 'medium',
                        'price': 4250
                    }
                ]
            },
            {
                'code': '8035',
                'name': '東京エレクトロン',
                'sector': '電気機器',
                'reason': '''半導体製造装置の世界大手で、特にエッチング装置、CVD装置で高いシェアを持つ。AI、データセンター、自動運転などの需要拡大により、半導体製造装置市場は中長期的に成長が見込める。

顧客には台湾TSMC、サムスン、インテルなど世界トップクラスの半導体メーカーが名を連ね、技術力の高さが評価されている。中国向け輸出規制の影響はあるものの、先端半導体向け装置の需要は堅調。

営業利益率は30%前後と高く、ROEも20%超。株価のボラティリティは大きいが、半導体サイクルの底値圏で買い増しできれば、大きなリターンが期待できる。''',
                'memo': '半導体市況と設備投資動向、米中関係に注目。在庫調整局面では株価が大きく下がるため、買い増しのチャンス。',
                'tags': ['成長株', '半導体', 'テクノロジー'],
                'transactions': [
                    {'date': -320, 'type': 'buy', 'price': 16500, 'quantity': 10, 'memo': '半導体サイクル底打ち期待で購入'},
                    {'date': -280, 'type': 'buy', 'price': 17200, 'quantity': 10, 'memo': 'AI向け需要増で追加'},
                    {'date': -240, 'type': 'buy', 'price': 18500, 'quantity': 10, 'memo': 'TSMC熊本工場で受注増期待'},
                    {'date': -200, 'type': 'buy', 'price': 17000, 'quantity': 10, 'memo': '調整局面での買い増し'},
                    {'date': -180, 'type': 'buy', 'price': 16200, 'quantity': 15, 'memo': '押し目買いチャンス'},
                    {'date': -140, 'type': 'buy', 'price': 18800, 'quantity': 10, 'memo': '決算好調で追加投資'},
                    {'date': -120, 'type': 'buy', 'price': 19800, 'quantity': 10, 'memo': '半導体市況回復で買い増し'},
                    {'date': -80, 'type': 'sell', 'price': 25000, 'quantity': 10, 'memo': '高値圏での利益確定'},
                    {'date': -60, 'type': 'sell', 'price': 26500, 'quantity': 10, 'memo': '目標株価到達で売却'},
                    {'date': -30, 'type': 'buy', 'price': 24000, 'quantity': 10, 'memo': '調整後の押し目買い'},
                ],
                'notes': [
                    {
                        'days_ago': 70,
                        'content': 'TSMCが熊本に新工場を建設中。東京エレクトロンも装置供給で大きな受注を獲得したとの報道。日本国内での半導体生産拡大は同社にとってプラス材料。',
                        'type': 'news',
                        'importance': 'high',
                        'price': 24000
                    },
                    {
                        'days_ago': 35,
                        'content': '2024年度第3四半期決算。受注額は前年同期比15%減だが、AI向け半導体製造装置の需要は底堅い。2025年度は回復基調に転じる見込み。',
                        'type': 'earnings',
                        'importance': 'high',
                        'price': 25500
                    },
                    {
                        'days_ago': 8,
                        'content': 'NVIDIAの次世代AI向けチップ「B200」の量産開始により、製造装置の需要が急増する可能性。株価は短期的に上昇しすぎている印象もあるが、ファンダメンタルズは良好。',
                        'type': 'insight',
                        'importance': 'medium',
                        'price': 28000
                    }
                ]
            },
            {
                'code': '4063',
                'name': '信越化学工業',
                'sector': '化学',
                'reason': '''塩化ビニル樹脂と半導体シリコンウエハーで世界トップシェアを持つ化学メーカー。特にシリコンウエハー事業は、半導体需要の拡大により中長期的な成長が見込める。

営業利益率は25%前後と化学業界では極めて高く、ROEも15%超。財務体質も盤石で、ネットキャッシュポジション。配当性向は60%前後で、配当利回りも3%台と安定している。

シクリカル（景気循環）な側面はあるものの、半導体の長期需要は確実に伸びており、ウエハー不足が続いている。シェア拡大余地は限定的だが、価格転嫁力が強い。''',
                'memo': '半導体市況と設備投資動向に注意。為替（円安）もプラス要因。塩ビ事業の市況も確認が必要。',
                'tags': ['高配当', '長期保有', 'バリュー株', '半導体'],
                'transactions': [
                    {'date': -290, 'type': 'buy', 'price': 14800, 'quantity': 20, 'memo': '高配当・安定企業として購入'},
                    {'date': -250, 'type': 'buy', 'price': 15200, 'quantity': 20, 'memo': 'シリコンウエハー不足で追加'},
                    {'date': -200, 'type': 'buy', 'price': 15800, 'quantity': 20, 'memo': '半導体需要増で買い増し'},
                    {'date': -170, 'type': 'buy', 'price': 14500, 'quantity': 25, 'memo': '調整局面での買い増し'},
                    {'date': -150, 'type': 'buy', 'price': 14200, 'quantity': 25, 'memo': '押し目買い'},
                    {'date': -110, 'type': 'buy', 'price': 16500, 'quantity': 20, 'memo': '決算好調で追加投資'},
                    {'date': -80, 'type': 'buy', 'price': 17500, 'quantity': 15, 'memo': 'ウエハー工場増強発表で買い増し'},
                    {'date': -40, 'type': 'buy', 'price': 18200, 'quantity': 15, 'memo': '配当増額で追加'},
                ],
                'notes': [
                    {
                        'days_ago': 48,
                        'content': '2024年度の業績予想を据え置き。シリコンウエハーの需要は堅調だが、塩ビ事業は中国景気の影響を受けて伸び悩み。',
                        'type': 'earnings',
                        'importance': 'medium',
                        'price': 18200
                    },
                    {
                        'days_ago': 18,
                        'content': '台湾のウエハー工場の増強を発表。2026年稼働予定で、生産能力を20%増強する計画。半導体需要の長期拡大に対応。',
                        'type': 'news',
                        'importance': 'high',
                        'price': 18800
                    }
                ]
            },
            {
                'code': '2914',
                'name': 'JT（日本たばこ産業）',
                'sector': '食料品',
                'reason': '''たばこ事業の利益率は高く、キャッシュフローが潤沢。配当利回りは6%前後と極めて高く、15年連続増配を継続中。株主還元姿勢が明確で、配当性向は75%程度。

加熱式たばこ「Ploom」シリーズの販売が好調で、日本国内でのシェアを拡大している。海外事業も収益の柱で、特にロシア・中東・アフリカ地域で強いプレゼンスを持つ。

ESG投資の観点からは敬遠されがちだが、たばこ需要は安定しており、規制リスクも織り込み済み。株価は割安で推移しており、高配当狙いの長期投資に適している。''',
                'memo': '健康志向の高まりと規制強化リスクはあるが、成人喫煙者向けの商品提供は継続される見込み。',
                'tags': ['高配当', '長期保有', 'バリュー株'],
                'transactions': [
                    {'date': -360, 'type': 'buy', 'price': 2750, 'quantity': 200, 'memo': '超高配当銘柄として購入'},
                    {'date': -330, 'type': 'buy', 'price': 2680, 'quantity': 200, 'memo': '配当利回り6%超で買い増し'},
                    {'date': -300, 'type': 'buy', 'price': 2850, 'quantity': 200, 'memo': '15期連続増配で追加'},
                    {'date': -270, 'type': 'buy', 'price': 2720, 'quantity': 200, 'memo': '調整局面での買い増し'},
                    {'date': -240, 'type': 'buy', 'price': 2600, 'quantity': 300, 'memo': '大きく下落したため追加投資'},
                    {'date': -220, 'type': 'buy', 'price': 2650, 'quantity': 200, 'memo': '押し目買い'},
                    {'date': -180, 'type': 'buy', 'price': 2920, 'quantity': 200, 'memo': 'Ploom好調で買い増し'},
                    {'date': -140, 'type': 'buy', 'price': 3100, 'quantity': 200, 'memo': '配当増額発表で追加'},
                    {'date': -100, 'type': 'buy', 'price': 3050, 'quantity': 200, 'memo': '配当利回り6.5%維持で買い増し'},
                    {'date': -60, 'type': 'buy', 'price': 3200, 'quantity': 100, 'memo': '長期保有目的で追加'},
                ],
                'notes': [
                    {
                        'days_ago': 65,
                        'content': '2024年度の配当予想を188円に引き上げ。配当利回りは6.5%に達し、日本株でもトップクラスの高配当銘柄。',
                        'type': 'earnings',
                        'importance': 'high',
                        'price': 3200
                    },
                    {
                        'days_ago': 30,
                        'content': '「Ploom X ADVANCED」の新製品を発売。加熱式たばこ市場でのシェア拡大を狙う。紙巻きたばこからの移行が進めば、利益率向上にも寄与。',
                        'type': 'news',
                        'importance': 'medium',
                        'price': 3250
                    },
                    {
                        'days_ago': 10,
                        'content': 'WHOのたばこ規制枠組条約（FCTC）の議論が進んでいるが、大きな規制強化は当面なさそう。株価は安定推移を続けている。',
                        'type': 'risk',
                        'importance': 'low',
                        'price': 3180
                    }
                ]
            },
            {
                'code': '4519',
                'name': '中外製薬',
                'sector': '医薬品',
                'reason': '''ロシュグループの傘下で、がん治療薬や自己免疫疾患治療薬に強みを持つ製薬会社。「アバスチン」「ハーセプチン」などのバイオ医薬品で高い収益性を維持している。

新薬開発パイプラインも充実しており、特にがん免疫療法の分野で有望な候補薬を複数保有。ロシュとの共同開発により、グローバル展開も可能。

医薬品業界は規制が厳しく参入障壁が高いため、安定した収益が期待できる。配当利回りは2%台と高くないが、成長性を考慮すれば魅力的。''',
                'memo': '新薬の承認状況と薬価改定の影響に注目。',
                'tags': ['成長株', '長期保有'],
                'transactions': [
                    {'date': -200, 'type': 'buy', 'price': 4800, 'quantity': 50, 'memo': '新薬パイプライン評価で購入'},
                    {'date': -150, 'type': 'buy', 'price': 4500, 'quantity': 50, 'memo': '調整局面での買い増し'},
                    {'date': -100, 'type': 'buy', 'price': 5200, 'quantity': 30, 'memo': '決算好調で追加'},
                    {'date': -50, 'type': 'buy', 'price': 5500, 'quantity': 30, 'memo': 'がん治療薬好調で買い増し'},
                ],
                'notes': [
                    {
                        'days_ago': 40,
                        'content': '新規がん免疫治療薬が米国FDAの承認を取得。欧州でも承認される見込みで、グローバル市場での売上拡大が期待される。',
                        'type': 'news',
                        'importance': 'high',
                        'price': 5800
                    },
                    {
                        'days_ago': 15,
                        'content': '2024年度第3四半期決算。主力製品の売上が堅調で、営業利益率は35%を維持。研究開発費も積極的に投資しており、将来への布石は十分。',
                        'type': 'earnings',
                        'importance': 'medium',
                        'price': 5900
                    }
                ]
            },
            {
                'code': '6098',
                'name': 'リクルートホールディングス',
                'sector': 'サービス業',
                'reason': '''人材派遣、求人情報、販促メディアなど多角的な事業を展開。特に海外の求人サイト「Indeed」が収益の柱で、世界60ヶ国以上で展開している。

日本の人手不足を背景に、人材マッチング事業の需要は高まる一方。デジタル化により、従来のアナログな求人市場がオンラインへシフトしており、その恩恵を大きく受けている。

M&Aも積極的で、グローバル展開を加速。営業利益率は15%前後で、ROEも20%超と高水準。成長性と収益性のバランスが良い。''',
                'memo': '米国の雇用市場と景気動向に注意。',
                'tags': ['成長株', 'テクノロジー'],
                'transactions': [
                    {'date': -180, 'type': 'buy', 'price': 4200, 'quantity': 50, 'memo': 'デジタル転換期待で購入'},
                    {'date': -120, 'type': 'buy', 'price': 3900, 'quantity': 60, 'memo': '押し目買い'},
                    {'date': -80, 'type': 'buy', 'price': 4500, 'quantity': 40, 'memo': 'Indeed好調で追加'},
                    {'date': -40, 'type': 'buy', 'price': 4800, 'quantity': 30, 'memo': '決算好調で買い増し'},
                ],
                'notes': [
                    {
                        'days_ago': 25,
                        'content': 'Indeedの月間訪問者数が過去最高を更新。米国雇用市場の回復により、求人広告収入が増加傾向。',
                        'type': 'analysis',
                        'importance': 'high',
                        'price': 5000
                    }
                ]
            },
            {
                'code': '6502',
                'name': '東芝',
                'sector': '電気機器',
                'reason': '''経営再建が進み、非上場化を経て事業の選択と集中が進展。エネルギー事業、インフラ事業、デバイス事業に注力しており、特に半導体メモリや電力インフラに強みを持つ。

過去の不正会計問題から立ち直り、財務体質も改善。今後は成長戦略に軸足を移せる段階にきている。''',
                'memo': 'この銘柄は既に全株売却済み。経営不安定期に撤退。',
                'tags': ['売却済み'],
                'transactions': [
                    {'date': -400, 'type': 'buy', 'price': 3500, 'quantity': 100, 'memo': '再建期待で購入'},
                    {'date': -350, 'type': 'buy', 'price': 3200, 'quantity': 100, 'memo': '下落局面で買い増し'},
                    {'date': -300, 'type': 'sell', 'price': 3800, 'quantity': 100, 'memo': '不透明感強く一部売却'},
                    {'date': -250, 'type': 'sell', 'price': 3600, 'quantity': 100, 'memo': '全株売却でポジション解消'},
                ],
                'notes': []
            },
            {
                'code': '9020',
                'name': '東日本旅客鉄道（JR東日本）',
                'sector': '陸運業',
                'reason': '''首都圏の鉄道インフラを支配し、安定した乗客数を確保。コロナ禍からの回復が進み、通勤・通学需要が戻りつつある。

駅ナカ商業施設やSuica関連事業など、鉄道以外の収益源も充実。不動産開発にも積極的で、駅周辺の再開発により資産価値を向上させている。''',
                'memo': 'インバウンド需要の回復と新幹線利用者数の推移に注目。',
                'tags': ['長期保有', 'バリュー株'],
                'transactions': [
                    {'date': -250, 'type': 'buy', 'price': 6800, 'quantity': 30, 'memo': 'コロナ回復期待で購入'},
                    {'date': -200, 'type': 'buy', 'price': 6500, 'quantity': 30, 'memo': '押し目買い'},
                    {'date': -150, 'type': 'buy', 'price': 7200, 'quantity': 30, 'memo': 'インバウンド回復で追加'},
                    {'date': -100, 'type': 'buy', 'price': 7500, 'quantity': 20, 'memo': '決算好調で買い増し'},
                ],
                'notes': [
                    {
                        'days_ago': 30,
                        'content': 'インバウンド観光客が大幅に増加。新幹線や特急列車の利用率が上昇しており、収益改善が顕著。駅ナカ店舗の売上も好調。',
                        'type': 'analysis',
                        'importance': 'high',
                        'price': 7800
                    }
                ]
            },
            {
                'code': '8001',
                'name': '伊藤忠商事',
                'sector': '卸売業',
                'reason': '''総合商社の中でも非資源分野に強みを持ち、繊維、食料、生活資材などの事業が安定収益源。中国ビジネスにも積極的で、CITIC（中国中信集団）への出資により中国市場へのアクセスを確保。

株主還元姿勢も明確で、配当性向30%以上を維持。配当利回りは3%前後と安定しており、長期保有に適している。''',
                'memo': '資源価格と中国景気に注意。',
                'tags': ['高配当', '長期保有'],
                'transactions': [
                    {'date': -220, 'type': 'buy', 'price': 4800, 'quantity': 50, 'memo': '非資源商社として購入'},
                    {'date': -180, 'type': 'buy', 'price': 4500, 'quantity': 50, 'memo': '調整局面での買い増し'},
                    {'date': -140, 'type': 'buy', 'price': 5200, 'quantity': 40, 'memo': '決算好調で追加'},
                    {'date': -90, 'type': 'buy', 'price': 5500, 'quantity': 40, 'memo': '増配発表で買い増し'},
                ],
                'notes': [
                    {
                        'days_ago': 35,
                        'content': '2024年度上期決算。純利益は過去最高を更新。非資源事業が堅調で、特に食料・生活資材分野が好調。配当も増額見込み。',
                        'type': 'earnings',
                        'importance': 'high',
                        'price': 5800
                    }
                ]
            }
        ]
        
        created_count = 0
        
        for stock in stock_data:
            try:
                # StockDiaryを作成
                diary = StockDiary.objects.create(
                    user=user,
                    stock_symbol=stock['code'],
                    stock_name=stock['name'],
                    sector=stock['sector'],
                    reason=stock['reason'],
                    memo=stock['memo']
                )
                
                # タグを追加
                for tag_name in stock['tags']:
                    tag = Tag.objects.get(user=user, name=tag_name)
                    diary.tags.add(tag)
                
                # 取引を追加（時系列順にソート）
                sorted_transactions = sorted(stock['transactions'], key=lambda x: x['date'])
                
                for trans_data in sorted_transactions:
                    trans_date = timezone.now().date() + timedelta(days=trans_data['date'])
                    
                    # メモ内容を充実
                    memo_text = trans_data.get('memo', '')
                    if not memo_text:
                        if trans_data['type'] == 'buy':
                            reasons = [
                                '押し目買い',
                                '業績好調により追加投資',
                                '下落局面での買い増し',
                                '配当権利落ち後の取得',
                                'ポートフォリオのリバランス',
                                '決算好調による買い増し'
                            ]
                            memo_text = random.choice(reasons)
                        else:
                            reasons = [
                                '利益確定',
                                '目標株価到達による売却',
                                'リスク回避のための部分売却',
                                'ポートフォリオ調整',
                                '他銘柄への資金移動',
                                '短期的な過熱感により利確'
                            ]
                            memo_text = random.choice(reasons)
                    
                    Transaction.objects.create(
                        diary=diary,
                        transaction_type=trans_data['type'],
                        transaction_date=trans_date,
                        price=Decimal(str(trans_data['price'])),
                        quantity=Decimal(str(trans_data['quantity'])),
                        memo=memo_text
                    )
                    transactions_count += 1
                
                # 株式分割データを追加（該当する銘柄のみ）
                if 'stock_splits' in stock:
                    for split_data in stock['stock_splits']:
                        split_date = timezone.now().date() + timedelta(days=split_data['date'])
                        
                        split = StockSplit.objects.create(
                            diary=diary,
                            split_date=split_date,
                            split_ratio=Decimal(str(split_data['ratio'])),
                            memo=split_data.get('memo', f"{split_data['ratio']}倍の株式分割"),
                            is_applied=split_data.get('applied', False)
                        )
                        splits_count += 1
                        
                        # 適用済みの場合は適用処理を実行
                        if split_data.get('applied', False):
                            split.apply_split()
                
                # 継続記録を追加
                if 'notes' in stock:
                    for note_data in stock['notes']:
                        note_date = timezone.now().date() - timedelta(days=note_data['days_ago'])
                        
                        DiaryNote.objects.create(
                            diary=diary,
                            date=note_date,
                            content=note_data['content'],
                            note_type=note_data['type'],
                            importance=note_data['importance'],
                            current_price=Decimal(str(note_data['price']))
                        )
                        notes_count += 1
                
                # 集計を更新
                diary.update_aggregates()
                
                created_count += 1
                self.stdout.write(f'  ✓ {stock["name"]} ({stock["code"]}) を作成')
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ {stock["name"]} の作成に失敗: {str(e)}'))
        
        return created_count, transactions_count, notes_count, splits_count
    
    def _show_statistics(self, user):
        """作成したデータの統計情報を表示"""
        self.stdout.write(f'\n📈 統計情報:')
        
        # 保有中の銘柄
        active_holdings = StockDiary.objects.filter(user=user, current_quantity__gt=0).count()
        self.stdout.write(f'  保有中: {active_holdings}銘柄')
        
        # 売却済みの銘柄
        sold_out = StockDiary.objects.filter(user=user, current_quantity=0, transaction_count__gt=0).count()
        self.stdout.write(f'  売却済み: {sold_out}銘柄')
        
        # メモのみ
        memo_only = StockDiary.objects.filter(user=user, transaction_count=0).count()
        self.stdout.write(f'  メモのみ: {memo_only}銘柄')
        
        # 実現損益の合計
        from django.db.models import Sum
        total_profit = StockDiary.objects.filter(user=user).aggregate(Sum('realized_profit'))['realized_profit__sum'] or 0
        self.stdout.write(f'  実現損益合計: {total_profit:,.0f}円')
        
        # 総取引回数
        total_transactions = Transaction.objects.filter(diary__user=user).count()
        self.stdout.write(f'  総取引回数: {total_transactions}件')
        
        # 業種の分散
        from django.db.models import Count
        sector_count = StockDiary.objects.filter(user=user).values('sector').distinct().count()
        self.stdout.write(f'  投資業種数: {sector_count}業種')