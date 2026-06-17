# stockdiary/management/commands/seed_library_demo.py
"""知識ライブラリ／投資家カルテ／ホーム想起のデモデータを投入する。

検証ループ（仮説 Thesis・検証 Verdict・学び）を中心に、
- 学び軸: 多彩な learning（検索しやすいテーマ語を含む）
- テーマ軸: 根拠タグ（複数銘柄で共有）
- 仮説軸: 未検証(答え合わせ待ち)／的中／外れ
- 投資家カルテ: 2×2分布・繰り返す見落とし・得意/苦手・投資哲学
が一通り埋まるよう、物語性のある少数精鋭で投入する。

冪等: 銘柄コードで get_or_create、仮説/検証は update_or_create。
--clear で対象ユーザーの Thesis/Verdict を一旦削除してから作り直す。

使い方:
    python manage.py seed_library_demo --username testuser --clear
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from stockdiary.models import StockDiary, Thesis, Verdict
from tags.models import Tag

User = get_user_model()


# verdict: (hypothesis_result, pnl_result, decision_quality, missed_factor, learning, is_repeatable)
# open:    検証予定日の相対日数（負＝過去＝答え合わせ待ち、正＝未来）
DATA = [
    {
        'code': '7203', 'name': 'トヨタ自動車', 'sector': '輸送用機器',
        'reason': '円安の追い風と全方位戦略を評価して取得。',
        'tags': ['円安', '輸出'],
        'claim': '円安が続き、輸出採算の改善が利益を押し上げる',
        'worst': '為替が円高に反転し、想定の前提が崩れたとき',
        'verdict': ('miss', 'profit', 2, '為替より米金利の影響を過小評価していた',
                    '為替単独を根拠に投資しない', False),
    },
    {
        'code': '5803', 'name': 'フジクラ', 'sector': '非鉄金属',
        'reason': '生成AIデータセンタ向け光関連の中核として注目。',
        'tags': ['生成AI', '半導体'],
        'claim': '生成AI需要は10年続き、光関連の構造的な伸びに乗れる',
        'worst': 'AI投資が一巡し、設備投資が急減速したとき',
        'verdict': ('hit', 'profit', 5, '', 'テーマが効くなら、握り続ける', True),
    },
    {
        'code': '9101', 'name': '日本郵船', 'sector': '海運業',
        'reason': '運賃高止まりと高配当に着目。',
        'tags': ['海運', '高配当'],
        'claim': '運賃市況の高止まりが続き、増配余地がある',
        'worst': '運賃市況がサイクルの天井から急落したとき',
        'verdict': ('hit', 'loss', 3, '利確の出口設計が甘く、ピークアウトで戻した',
                    '海運はサイクル株。出口を先に決める', True),
    },
    {
        'code': '9984', 'name': 'ソフトバンクグループ', 'sector': '情報・通信業',
        'reason': 'AI投資の再評価を期待。',
        'tags': ['生成AI'],
        'claim': 'AI関連投資先の再評価でNAVが拡大する',
        'worst': '金利上昇でグロース全体が圧縮されたとき',
        'verdict': ('miss', 'loss', 2, '期待先行で、検証可能な根拠が薄かった',
                    'イベント期待だけで入らない', False),
    },
    {
        'code': '8058', 'name': '三菱商事', 'sector': '卸売業',
        'reason': '資源高と累進配当の継続に着目。',
        'tags': ['高配当', '地政学リスク'],
        'claim': '資源高と株主還元方針の強化で、配当成長が続く',
        'worst': '資源価格が長期下落トレンドに入ったとき',
        'verdict': ('hit', 'profit', 4, '', '配当成長は長期で効く。腰を据える', True),
    },
    {
        'code': '6920', 'name': 'レーザーテック', 'sector': '電気機器',
        'reason': 'EUV検査装置の独占的地位を評価。',
        'tags': ['半導体'],
        'claim': '検査装置の独占的地位が高成長を支える',
        'worst': '高い期待がバリュエーションに織り込まれ過ぎたとき',
        'verdict': ('miss', 'loss', 2, 'バリュエーションの高さを軽視していた',
                    '高PER銘柄は決算跨ぎで脆い', False),
    },
    {
        'code': '7974', 'name': '任天堂', 'sector': 'その他製品',
        'reason': '次世代機の発売期待で取得。',
        'tags': ['決算プレイ', '内需回復'],
        'claim': '新ハードの立ち上がりで業績が一段跳ねる',
        'worst': '発売スケジュールの後ろ倒しや初動の不振',
        'verdict': ('miss', 'loss', 1, '入るのが早い',
                    '決算プレイは握れない。分散する', False),
    },
    {
        'code': '6594', 'name': 'ニデック', 'sector': '電気機器',
        'reason': 'EV駆動システムの本命として注目。',
        'tags': ['内需回復'],
        'claim': 'EV化の加速で車載モーターの需要が伸びる',
        'worst': 'EV普及ペースが鈍化したとき',
        'verdict': ('miss', 'loss', 2, '入るのが早い',
                    '普及ストーリーは時間軸を保守的に見る', True),
    },
    {
        'code': '1605', 'name': 'INPEX', 'sector': '鉱業',
        'reason': '原油高局面のヘッジとして取得。',
        'tags': ['地政学リスク', '高配当'],
        'claim': '地政学リスクの高まりで原油高が続く',
        'worst': '増産合意で需給が緩むとき',
        'verdict': ('hit', 'profit', 4, '', '地政学はヘッジとして一定枠を持つ', True),
    },
    # ── 未検証（答え合わせ待ち／予定） ──────────────────────────
    {
        'code': '7011', 'name': '三菱重工業', 'sector': '機械',
        'reason': '防衛費増額の流れを継続記録。',
        'tags': ['地政学リスク'],
        'claim': '防衛費の増額が中期の受注残を押し上げる',
        'worst': '予算執行が想定より遅れるとき',
        'open': -20,   # 検証予定日が到来済み＝答え合わせ待ち
    },
    {
        'code': '4063', 'name': '信越化学工業', 'sector': '化学',
        'reason': '半導体材料の構造的優位に注目。',
        'tags': ['半導体', '内需回復'],
        'claim': 'シリコンウエハの構造的な需給逼迫が続く',
        'worst': '汎用品の市況悪化が長引くとき',
        'open': 75,    # まだ先
    },
]

TAG_AXIS = {
    '円安': 'macro', '輸出': 'business_model', '生成AI': 'theme', '半導体': 'theme',
    '海運': 'theme', '高配当': 'capital_policy', '地政学リスク': 'risk',
    '決算プレイ': 'event', '内需回復': 'macro',
}


class Command(BaseCommand):
    help = '知識ライブラリ／投資家カルテ／想起のデモデータ（仮説・検証・学び）を投入する'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='testuser',
                            help='対象ユーザー名（デモ/テスト用アカウント推奨）')
        parser.add_argument('--clear', action='store_true',
                            help='対象ユーザーの既存 Thesis/Verdict を削除してから作り直す')

    def handle(self, *args, **options):
        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ ユーザー "{username}" が見つかりません'))
            return

        if options['clear']:
            n = Thesis.objects.filter(diary__user=user).count()
            Thesis.objects.filter(diary__user=user).delete()  # Verdict は CASCADE
            self.stdout.write(f'🧹 既存の仮説/検証を削除: {n} 件')

        today = timezone.localdate()
        tag_cache = {}

        def get_tag(name):
            if name not in tag_cache:
                tag_cache[name], _ = Tag.objects.get_or_create(
                    user=user, name=name,
                    defaults={'axis': TAG_AXIS.get(name, 'custom')},
                )
            return tag_cache[name]

        n_thesis = n_verdict = n_open = 0
        for spec in DATA:
            # 同一銘柄コードの日記が複数あっても落ちないよう get_or_create は使わない
            diary = (StockDiary.objects
                     .filter(user=user, stock_symbol=spec['code'])
                     .order_by('id').first())
            if diary is None:
                diary = StockDiary.objects.create(
                    user=user, stock_symbol=spec['code'],
                    stock_name=spec['name'], sector=spec['sector'],
                    reason=spec['reason'],
                )
            else:
                # 既存日記でも名称/業種/理由が空なら補完
                updated = False
                if not diary.stock_name:
                    diary.stock_name = spec['name']; updated = True
                if not diary.sector:
                    diary.sector = spec['sector']; updated = True
                if not diary.reason:
                    diary.reason = spec['reason']; updated = True
                if updated:
                    diary.save()
            for tname in spec['tags']:
                diary.tags.add(get_tag(tname))

            is_open = 'open' in spec
            thesis, _ = Thesis.objects.update_or_create(
                diary=diary,
                defaults={
                    'claim': spec['claim'],
                    'worst_case': spec.get('worst', ''),
                    'horizon': '6m',
                    'status': Thesis.STATUS_OPEN if is_open else Thesis.STATUS_VERIFIED,
                    'review_due_date': today + timedelta(days=spec['open']) if is_open
                                       else today - timedelta(days=120),
                },
            )
            thesis.basis_tags.set([get_tag(t) for t in spec['tags']])
            n_thesis += 1

            if is_open:
                Verdict.objects.filter(thesis=thesis).delete()
                n_open += 1
            else:
                hyp, pnl, dq, missed, learn, rep = spec['verdict']
                Verdict.objects.update_or_create(
                    thesis=thesis,
                    defaults={
                        'hypothesis_result': hyp, 'pnl_result': pnl,
                        'decision_quality': dq, 'missed_factor': missed,
                        'learning': learn, 'is_repeatable': rep,
                    },
                )
                n_verdict += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ デモデータ投入完了（ユーザー: {username}）\n'
            f'   仮説 {n_thesis} 件 / 検証 {n_verdict} 件 / 未検証 {n_open} 件\n'
            f'   → /library/（学び・テーマ・仮説）, /karte/, ホーム想起 を確認'
        ))
