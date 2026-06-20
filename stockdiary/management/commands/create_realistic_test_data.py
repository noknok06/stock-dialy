# stockdiary/management/commands/create_realistic_test_data.py
"""カブログの利用イメージが伝わるデモデータを作成する。

取引量の多さではなく、本アプリのコア価値（思考の記録・想起・銘柄のつながり）が
一目で伝わるよう、物語性のある少数精鋭の日記を投入する。

含まれる要素:
  - テーマ別クラスター（半導体 / 地政学）を `@タグ` + `(銘柄コード)` 言及 +
    linked_diaries で結び、関連グラフが意味のある形で描画される
  - 投資理由(reason)は Markdown で「なぜ買ったか」の思考を記述
  - 継続記録(DiaryNote)は news / analysis / earnings / risk / retrospective など
    複数の note_type で「考えの変化」を時系列に残す
  - 売却完結した銘柄には振り返り(retrospective)を付与し、想起・教訓を表現
  - 取引のない監視銘柄（メモ的な日記）も含める
  - タグ方向(DiaryTagDirection)で「このテーマは自分にプラス/マイナス」を表現
  - 検証ループ(Thesis/Verdict)で投資家カルテ・知識ライブラリ・ホーム想起
    「答え合わせを待つ仮説」を埋める。検証予定日は相対日で持ち、毎日の
    デモ再投入でも想起が陳腐化しない（status='open' かつ予定日到来で出る）

使い方:
    python manage.py create_realistic_test_data --username testuser --clear
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from stockdiary.models import (
    StockDiary, Transaction, DiaryNote, StockSplit, DiaryTagDirection,
    Thesis, Verdict,
)
from stockdiary.services.aggregate_service import AggregateService
from tags.models import Tag

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────
# デモ日記データ。日付は「今日からの相対日数（負＝過去）」で指定する。
#   reason       : Markdown。本文中の @テーマ / (銘柄コード) が関連グラフの素になる
#   tag_dirs     : {タグ名: 'up'|'down'|'neutral'} … テーマの順相関/逆相関
#   transactions : (type, 相対日, price, qty, is_margin, memo)
#   notes        : (相対日, content, price, note_type, _未使用, topic)  # 旧importance枠は無視
#   splits       : (相対日, ratio, memo, applied)
#   links        : linked_diaries に張る相手の銘柄コード
#   thesis       : 検証ループ（仮説・検証）。投資家カルテ／知識ライブラリ／
#                  ホーム想起「答え合わせを待つ仮説」を埋める。
#     {claim, basis(タグ名), worst, horizon, due(相対日), status, verdict}
#       due    : 検証予定日の相対日数（負＝過去）。**毎日のデモ再投入に追随する
#                よう必ず相対日で持つ**（固定日にすると想起が陳腐化する）
#       status : 'verified'（検証済み）| 'open'（未検証）。open かつ due≤今日 で
#                ホームの「答え合わせを待つ仮説」に出る
#       verdict: (仮説の当否, 損益, 判断の質1-5, 見落とし, 学び, 再現したいか)
#                ／open は None
# ─────────────────────────────────────────────────────────────────────────
DIARIES = [
    # ── テーマ1: 半導体製造装置クラスター ────────────────────────────
    {
        'code': '8035', 'name': '東京エレクトロン', 'sector': '電気機器',
        'reason': (
            '## 投資仮説\n\n'
            'AI向けデータセンタ投資を起点とした **半導体の長期成長サイクル** に乗る中核として取得。\n\n'
            '- 前工程の成膜・エッチング装置で世界トップシェア\n'
            '- 顧客（TSMC・サムスン）の設備投資が再加速局面\n'
            '- 配当性向50%目安で株主還元も明確\n\n'
            '同じ装置クラスタの アドバンテスト(6857) とは需要の連動性が高いので併せて監視する。\n'
            '在庫調整での急落は **押し目** と捉える。\n\n'
            '@半導体 @AI需要 @設備投資'
        ),
        'tags': ['半導体', 'AI需要', '設備投資', '長期投資'],
        'tag_dirs': {'AI需要': 'up', '設備投資': 'up'},
        'transactions': [
            ('buy', -300, 22000, 30, False, 'AIサイクル初動と判断し打診買い'),
            ('buy', -210, 19500, 20, False, '在庫調整の急落で買い増し（押し目）'),
            ('buy', -90, 24500, 20, False, '前工程投資の再加速を確認し追加'),
        ],
        'notes': [
            (-260, '主要顧客の設備投資計画が上方修正。仮説の前提は強化された。', 23000, 'news', 'high', '顧客動向'),
            (-150, '四半期決算は受注残が過去最高。粗利率も改善傾向。', 21000, 'earnings', 'high', '決算'),
            (-40, 'AI以外のレガシー半導体は調整中。需要の二極化に留意。', 25500, 'risk', 'medium', 'リスク'),
        ],
        'thesis': {
            'claim': 'AI設備投資を起点に、半導体の長期成長サイクルへ乗れる',
            'basis': ['半導体', 'AI需要'],
            'worst': 'AI投資が一巡し、設備投資が急減速したとき',
            'horizon': 'long', 'due': -90, 'status': 'verified',
            'verdict': ('hit', 'profit', 5, '', '実需に近い装置株は長期で握り続ける', True),
        },
        'links': ['6857', '6920'],
    },
    {
        'code': '6857', 'name': 'アドバンテスト', 'sector': '電気機器',
        'reason': (
            '## 投資仮説\n\n'
            'AI半導体の **テスト工程** のボトルネックを握る。SoC・HBM テスタで圧倒的シェア。\n\n'
            '- 生成AI向け高性能チップの検査需要が構造的に増加\n'
            '- 東京エレクトロン(8035) と並ぶ装置クラスタの主役\n\n'
            'ボラティリティが高いので一括ではなく分割で積む方針。\n\n'
            '@半導体 @AI需要'
        ),
        'tags': ['半導体', 'AI需要'],
        'tag_dirs': {'AI需要': 'up'},
        'transactions': [
            ('buy', -240, 5800, 100, False, 'AIテスト需要に賭けて取得'),
            ('buy', -120, 5200, 100, False, '調整局面で買い増し'),
        ],
        'notes': [
            (-180, 'HBM向けテスタの引き合いが想定以上との報道。', 6200, 'news', 'medium', '需要'),
            (-30, '通期見通しを上方修正。テスト工程の逼迫が追い風。', 7400, 'earnings', 'high', '決算'),
        ],
        'thesis': {
            'claim': 'AIチップのテスト工程の逼迫が構造的に続く',
            'basis': ['半導体', 'AI需要'],
            'worst': 'AI向け高性能チップの需要が頭打ちになったとき',
            'horizon': '1y', 'due': 30, 'status': 'open', 'verdict': None,
        },
        'links': ['8035'],
    },
    {
        'code': '6920', 'name': 'レーザーテック', 'sector': '電気機器',
        # 売却完結 → 振り返り(retrospective)で教訓を残すケース
        'reason': (
            '## 投資仮説\n\n'
            'EUV マスク欠陥検査装置で独占的地位。半導体微細化の必需品として エントリー。\n\n'
            '- 競合不在のニッチ独占\n'
            '- ただし **PER は相当な割高水準** で、期待先行の懸念あり\n\n'
            '装置クラスタ（8035 / 6857）の一角として監視。\n\n'
            '@半導体'
        ),
        'tags': ['半導体', '成長株'],
        'tag_dirs': {},
        'transactions': [
            ('buy', -280, 32000, 20, False, '独占ビジネスに期待して取得'),
            ('buy', -200, 28000, 10, False, '下落で買い増し（ナンピン）'),
            ('sell', -110, 38000, 30, False, '割高感と地合い悪化で全株売却'),
        ],
        'notes': [
            (-150, '空売りレポートが出て急落。事業の本質は毀損していないと判断。', 26000, 'analysis', 'high', '急落対応'),
            (
                -110,
                ('## 振り返り（この投資の総括）\n\n'
                 '- 結果: 約 +22万円で全株売却。利益は出たが**運の要素が大きい**\n'
                 '- 反省: ナンピンの根拠が「下がったから」で、仮説の再検証を伴っていなかった\n'
                 '- 教訓: 割高バリュエーションの銘柄は **撤退ラインを最初に決める**。\n'
                 '  次に半導体で入るなら 8035 / 6857 のような実需に近い装置株を厚くする'),
                38000, 'retrospective', 'high', '振り返り',
            ),
        ],
        'thesis': {
            'claim': 'EUVマスク検査の独占的地位が高成長を支える',
            'basis': ['半導体'],
            'worst': '高い期待がバリュエーションに織り込まれ過ぎたとき',
            'horizon': '6m', 'due': -100, 'status': 'verified',
            # 利益は出たが仮説は外れ＝偶然の勝ち（要注意）。振り返りの教訓と一致
            'verdict': ('miss', 'profit', 2, 'バリュエーションの高さを軽視していた',
                        '割高銘柄は撤退ラインを最初に決める', False),
        },
        'links': ['8035'],
    },

    # ── テーマ2: 地政学・エネルギー / 防衛 ───────────────────────────
    {
        'code': '1605', 'name': 'INPEX', 'sector': '鉱業',
        'reason': (
            '## 投資仮説\n\n'
            '中東情勢の緊迫化で **資源価格の高止まり** が続くとみて、国内最大の資源開発企業を取得。\n\n'
            '- 原油・LNG 価格に連動する業績\n'
            '- 自社株買い・増配など還元姿勢が積極的\n'
            '- 地政学リスクが顕在化するほど業績にプラスという **ヘッジ的な位置づけ**\n\n'
            '同じ地政学テーマで 三菱重工(7011) も併せて持ち、防衛とエネルギーの両面で備える。\n\n'
            '@地政学リスク @資源高 @高配当'
        ),
        'tags': ['地政学リスク', '資源高', '高配当'],
        'tag_dirs': {'地政学リスク': 'up', '資源高': 'up'},
        'transactions': [
            ('buy', -220, 1850, 300, False, '中東リスクのヘッジとして取得'),
            ('buy', -100, 2050, 200, False, '増配発表を受けて買い増し'),
        ],
        'notes': [
            (-160, '原油が一時急騰。仮説どおりの値動き。', 2100, 'news', 'medium', '原油'),
            (-50, '自社株買いを発表。需給面でも追い風。', 2200, 'insight', 'medium', '還元'),
        ],
        'thesis': {
            'claim': '地政学リスクの高まりで資源価格の高止まりが続く',
            'basis': ['地政学リスク', '高配当'],
            'worst': '増産合意などで需給が緩むとき',
            'horizon': '6m', 'due': -80, 'status': 'verified',
            'verdict': ('hit', 'profit', 4, '', '地政学はヘッジとして一定枠を持つ', True),
        },
        'links': ['7011'],
    },
    {
        'code': '7011', 'name': '三菱重工業', 'sector': '機械',
        'reason': (
            '## 投資仮説\n\n'
            '防衛予算の増額と GX（脱炭素）の二本柱で **中期の構造的な追い風**。\n\n'
            '- 防衛・原子力・ガスタービンの受注拡大\n'
            '- 地政学リスクの高まりが受注に直結\n\n'
            'エネルギー側の INPEX(1605) と組み合わせ、地政学テーマを多面的に押さえる。\n\n'
            '@地政学リスク @防衛 @GX'
        ),
        'tags': ['地政学リスク', '防衛', 'GX'],
        'tag_dirs': {'地政学リスク': 'up', '防衛': 'up'},
        'transactions': [
            ('buy', -200, 1100, 300, False, '防衛予算増額の流れに乗る'),
            ('buy', -60, 1450, 200, False, '受注好調を確認し追加'),
        ],
        'notes': [
            (-120, '中期経営計画で防衛・エネルギーの受注目標を上方修正。', 1300, 'earnings', 'high', '中計'),
            (-20, '株価は急騰後の過熱感あり。短期は調整も想定。', 1600, 'risk', 'medium', '過熱感'),
        ],
        'thesis': {
            'claim': '防衛費の増額が中期の受注残を押し上げる',
            'basis': ['地政学リスク', '防衛'],
            'worst': '予算の執行が想定より遅れるとき',
            # 検証予定日が到来済みの未検証＝ホームの「答え合わせを待つ仮説」に出る
            'horizon': '6m', 'due': -10, 'status': 'open', 'verdict': None,
        },
        'links': ['1605'],
    },

    # ── テーマ3: 金利・高配当（タグ方向で「金利上昇=自分にプラス」を表現）──
    {
        'code': '8306', 'name': '三菱UFJフィナンシャル・グループ', 'sector': '銀行業',
        'reason': (
            '## 投資仮説\n\n'
            '日銀の **金融正常化（利上げ）** 局面で利ざや改善が効く中核銀行。\n\n'
            '- 金利上昇は銀行業の収益に直接プラス\n'
            '- 配当利回り・累進配当方針が魅力\n'
            '- PBR1倍割れ是正の動きも追い風\n\n'
            '@金利上昇 @高配当 @長期投資'
        ),
        'tags': ['金利上昇', '高配当', '長期投資'],
        'tag_dirs': {'金利上昇': 'up'},
        'transactions': [
            ('buy', -330, 1180, 500, False, '正常化を見越して取得'),
            ('buy', -150, 1450, 300, False, 'マイナス金利解除で買い増し'),
        ],
        'notes': [
            (-200, '日銀がマイナス金利を解除。仮説の本丸が動き出した。', 1500, 'news', 'high', '金融政策'),
            (-40, '通期最終益が過去最高を更新。利ざや改善が寄与。', 1850, 'earnings', 'high', '決算'),
        ],
        'thesis': {
            'claim': '金融正常化（利上げ）の進展で利ざやが構造的に改善する',
            'basis': ['金利上昇', '高配当'],
            'worst': '利上げが想定より緩慢で、利ざや改善が鈍るとき',
            'horizon': '1y', 'due': -120, 'status': 'verified',
            'verdict': ('hit', 'profit', 4, '', '金融正常化は時間をかけて効く。腰を据える', True),
        },
        'links': [],
    },

    # ── 監視のみ（取引なし＝メモ的な日記。仮説だけ先に置いておくケース）──
    {
        'code': '6758', 'name': 'ソニーグループ', 'sector': '電気機器',
        'reason': (
            '## 監視メモ（未エントリー）\n\n'
            'ゲーム・音楽・映画・イメージセンサーの **複合エンタメ＆半導体** ポートフォリオ。\n\n'
            '- センサー事業は半導体テーマ（8035 / 6857）とも一部つながる\n'
            '- 金融事業の分離（IPO）が株価のカタリストになり得る\n\n'
            'PER と為替前提を見て、押したところでエントリーを検討する。\n\n'
            '@エンタメ @半導体 @監視中'
        ),
        'tags': ['エンタメ', '半導体', '監視中'],
        'tag_dirs': {},
        'transactions': [],
        'notes': [
            (-30, '金融子会社のパーシャルスピンオフ方針が報道。カタリストとして注目。', 13000, 'news', 'medium', '再編'),
        ],
        'thesis': {
            'claim': '金融子会社の分離（IPO）が再評価のカタリストになる',
            'basis': ['エンタメ'],
            'worst': '分離の方針が撤回・後ろ倒しになったとき',
            # 監視中に仮説だけ先に置くケース（検証予定日はまだ先）
            'horizon': '1y', 'due': 60, 'status': 'open', 'verdict': None,
        },
        'links': ['8035'],
    },
]


class Command(BaseCommand):
    help = 'カブログの利用イメージが伝わるデモデータを作成します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username', type=str, default='testuser',
            help='データを作成するユーザー名（デフォルト: testuser）',
        )
        parser.add_argument(
            '--clear', action='store_true',
            help='対象ユーザーの既存日記を削除してから作成',
        )

    def handle(self, *args, **options):
        username = options['username']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ ユーザー "{username}" が見つかりません'))
            self.stdout.write('先に作成してください: python manage.py createsuperuser')
            return

        if options['clear']:
            deleted = StockDiary.objects.filter(user=user).delete()[0]
            self.stdout.write(self.style.WARNING(f'🗑  既存日記を削除しました（{deleted} オブジェクト）'))

        today = timezone.now().date()
        tag_cache = {}
        diary_by_code = {}
        tx_count = note_count = split_count = dir_count = 0
        thesis_count = verdict_count = 0

        def get_tag(name):
            if name not in tag_cache:
                tag_cache[name], _ = Tag.objects.get_or_create(user=user, name=name)
            return tag_cache[name]

        # ── パス1: 日記・取引・分割・継続記録・タグ・タグ方向を作成 ──
        for spec in DIARIES:
            diary = StockDiary.objects.create(
                user=user,
                stock_symbol=spec['code'],
                stock_name=spec['name'],
                sector=spec['sector'],
                reason=spec['reason'],
            )
            diary_by_code[spec['code']] = diary

            for tag_name in spec['tags']:
                diary.tags.add(get_tag(tag_name))

            for tag_name, direction in spec.get('tag_dirs', {}).items():
                DiaryTagDirection.objects.create(
                    diary=diary, tag=get_tag(tag_name), direction=direction,
                )
                dir_count += 1

            for t_type, days, price, qty, is_margin, memo in spec['transactions']:
                Transaction.objects.create(
                    diary=diary,
                    transaction_type=t_type,
                    transaction_date=today + timedelta(days=days),
                    price=Decimal(str(price)),
                    quantity=Decimal(str(qty)),
                    is_margin=is_margin,
                    memo=memo,
                )
                tx_count += 1

            for days, ratio, memo, applied in spec.get('splits', []):
                split = StockSplit.objects.create(
                    diary=diary,
                    split_date=today + timedelta(days=days),
                    split_ratio=Decimal(str(ratio)),
                    memo=memo,
                    is_applied=applied,
                )
                split_count += 1
                if applied:
                    split.apply_split()

            for days, content, price, ntype, _imp, topic in spec['notes']:
                DiaryNote.objects.create(
                    diary=diary,
                    date=today + timedelta(days=days),
                    content=content,
                    current_price=Decimal(str(price)),
                    note_type=ntype,
                    topic=topic,
                )
                note_count += 1

            # 取引変更後は必ず集計を再計算（CLAUDE.md 必須ルール）
            AggregateService.recalculate(diary)

            # 検証ループ（仮説・検証）。検証予定日は today からの相対日で持つため
            # 毎日のデモ再投入でも「答え合わせを待つ仮説」が陳腐化しない。
            th_spec = spec.get('thesis')
            if th_spec:
                status = th_spec.get('status', Thesis.STATUS_OPEN)
                thesis = Thesis.objects.create(
                    diary=diary,
                    claim=th_spec['claim'],
                    horizon=th_spec.get('horizon', '6m'),
                    worst_case=th_spec.get('worst', ''),
                    review_due_date=today + timedelta(days=th_spec['due']),
                    status=status,
                )
                thesis.basis_tags.set([get_tag(n) for n in th_spec.get('basis', [])])
                thesis_count += 1

                vd = th_spec.get('verdict')
                if vd:
                    hyp, pnl, dq, missed, learn, rep = vd
                    Verdict.objects.create(
                        thesis=thesis,
                        hypothesis_result=hyp, pnl_result=pnl,
                        decision_quality=dq, missed_factor=missed,
                        learning=learn, is_repeatable=rep,
                    )
                    verdict_count += 1

            self.stdout.write(f'  ✓ {spec["name"]} ({spec["code"]})')

        # ── パス2: linked_diaries（手動リンク）を張る ──
        link_count = 0
        for spec in DIARIES:
            src = diary_by_code[spec['code']]
            for target_code in spec.get('links', []):
                target = diary_by_code.get(target_code)
                if target and target != src:
                    src.linked_diaries.add(target)
                    link_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ デモデータ作成完了（ユーザー: {username}）'
        ))
        self.stdout.write(
            f'  日記 {len(DIARIES)} / 取引 {tx_count} / 継続記録 {note_count} / '
            f'分割 {split_count} / タグ方向 {dir_count} / 手動リンク {link_count}'
        )
        self.stdout.write(f'  仮説 {thesis_count} / 検証 {verdict_count}')
        self._show_statistics(user)

    def _show_statistics(self, user):
        from django.db.models import Sum
        self.stdout.write('\n📈 統計:')
        holding = StockDiary.objects.filter(user=user, current_quantity__gt=0).count()
        sold = StockDiary.objects.filter(
            user=user, current_quantity=0, transaction_count__gt=0
        ).count()
        memo_only = StockDiary.objects.filter(user=user, transaction_count=0).count()
        retro = DiaryNote.objects.filter(
            diary__user=user, note_type='retrospective'
        ).count()
        profit = StockDiary.objects.filter(user=user).aggregate(
            s=Sum('realized_profit')
        )['s'] or 0
        self.stdout.write(f'  保有中: {holding} / 売却済み: {sold} / 監視のみ: {memo_only}')
        self.stdout.write(f'  振り返り記録: {retro} 件 / 実現損益合計: {profit:,.0f} 円')

        # 検証ループ（カルテ／ライブラリ／ホーム想起の状態）
        today = timezone.now().date()
        verified = Thesis.objects.filter(
            diary__user=user, status=Thesis.STATUS_VERIFIED
        ).count()
        due = Thesis.objects.filter(
            diary__user=user, status=Thesis.STATUS_OPEN,
            review_due_date__lte=today,
        ).count()
        self.stdout.write(
            f'  仮説（検証済み）: {verified} 件 / 答え合わせを待つ仮説: {due} 件'
        )
