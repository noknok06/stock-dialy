"""tag_master（投資タグマスタ）を MasterTag に一括登録する管理コマンド。

使い方:
    python manage.py seed_master_tags          # 登録/更新（冪等）
    python manage.py seed_master_tags --prune   # マスタ外の既存MasterTagを無効化(is_active=False)

目的:
    @タグの「軸(axis)」は関連度・想起の精度を直接左右する。
    MasterTag に未登録のタグは custom 軸となり、関連付け計算から除外される。
    本コマンドで投資タグマスタを正しい軸で登録し、語彙全体を機能に効かせる。

注意:
    軸は tag_master の分類に対応。event 軸は一過性イベント＝関連付けに使われない（絞り込み専用）。
    「利益率改善・構造改革・設備投資拡大」は銘柄横断で繋げる価値があるため business_model に格上げ。
"""
from django.core.cache import cache
from django.core.management.base import BaseCommand

from tags.models import MasterTag, Tag

# 軸 → タグ名（投資タグマスタ tag_master.md と対応。並び順は sort_order に反映）
TAG_MASTER: list[tuple[str, list[str]]] = [
    ('macro', [
        'インフレ', '金利上昇', '金利低下', '円安メリット', '円高メリット',
        '景気敏感', 'ディフェンシブ', '資源価格上昇', '金利感応',
    ]),
    ('theme', [
        'AI', 'フィジカルAI', 'ドローン', 'DX', 'サイバーセキュリティ', 'AIセキュリティ',
        'データセンター', '半導体', 'オルタナティブデータ', '通信インフラ',
        'エネルギー', 'LNG',
        '脱炭素', '再生可能エネルギー', '水素', '蓄電池', 'CCS', 'SAF',
        '防衛', '国土強靭化', 'インフラ老朽化', '建設補修', '少子高齢化', 'インバウンド', 'アジア消費',
        'ヘルスケア', 'ヘルスケア施設開発', '医療DX', '創薬', '医療機器',
        '物流', 'EC物流', 'サプライチェーン',
        '都心オフィス', '不動産市況',
    ]),
    ('business_model', [
        'IPビジネス', 'プラットフォーム', 'ストック収益', '高シェア', 'ニッチトップ',
        '総合商社', '資源権益', 'バリューチェーン',
        'HRテック', '採用プラットフォーム', 'ハイクラス人材', '人材ビジネス', '人材集約型',
        'M&A成長', '海外展開',
        # 経営テーマ（イベント群から格上げ：銘柄横断で繋げる）
        '利益率改善', '構造改革', '設備投資拡大',
    ]),
    ('capital_policy', [
        '高配当', '累進配当', '連続増配', '連続増益', '高ROE', '株主還元強化',
    ]),
    ('risk', [
        '地政学リスク', '規制リスク', '需給変化',
    ]),
    ('event', [
        # 一過性イベント（関連付けには使わない・絞り込み専用）
        '決算注目', '業績上方修正', '増配', '減配', 'MBO・買収', '決算ミス',
    ]),
]

# 子タグ名 → 親タグ名（tag_master.md の細分タグ＝インデント表現に対応。階層は2段階まで）
TAG_MASTER_PARENTS: dict[str, str] = {
    'LNG': 'エネルギー',
    'フィジカルAI': 'AI',
    '再生可能エネルギー': '脱炭素',
    '水素': '脱炭素',
    '蓄電池': '脱炭素',
    'CCS': '脱炭素',
    'SAF': '脱炭素',
    '創薬': 'ヘルスケア',
    '医療機器': 'ヘルスケア',
    'ヘルスケア施設開発': 'ヘルスケア',
    'EC物流': '物流',
}


class Command(BaseCommand):
    help = '投資タグマスタ(tag_master)を MasterTag に正しい軸で一括登録する（冪等）。'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prune', action='store_true',
            help='マスタに無いMasterTagを is_active=False にする（削除はしない）。',
        )
        parser.add_argument(
            '--no-user-tags', action='store_true',
            help='既存のユーザー個別タグ(Tag)の軸を同期しない。',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='変更を保存せず、対象だけ表示する。',
        )

    def handle(self, *args, **options):
        prune = options['prune']
        dry_run = options['dry_run']
        sync_user_tags = not options['no_user_tags']

        created = updated = unchanged = 0
        master_names: set[str] = set()
        name_axis: dict[str, str] = {}
        sort_order = 0

        for axis, names in TAG_MASTER:
            for name in names:
                master_names.add(name)
                name_axis[name] = axis
                sort_order += 1
                existing = MasterTag.objects.filter(name=name).first()
                if existing is None:
                    created += 1
                    if not dry_run:
                        MasterTag.objects.create(
                            name=name, axis=axis, is_active=True, sort_order=sort_order,
                        )
                    self.stdout.write(f'  + {name}（{axis}）')
                elif (existing.axis != axis or not existing.is_active
                      or existing.sort_order != sort_order):
                    updated += 1
                    if not dry_run:
                        existing.axis = axis
                        existing.is_active = True
                        existing.sort_order = sort_order
                        existing.save()
                    self.stdout.write(f'  ~ {name}: {existing.axis} → {axis}')
                else:
                    unchanged += 1

        # 親子関係の同期（TAG_MASTER_PARENTS）。
        # 親は必ず先に登録済み（TAG_MASTER内の並び）である前提。存在しない/軸不一致はスキップ。
        parents_linked = 0
        for child_name, parent_name in TAG_MASTER_PARENTS.items():
            child = MasterTag.objects.filter(name=child_name).first()
            parent = MasterTag.objects.filter(name=parent_name).first()
            if not child or not parent:
                self.stdout.write(self.style.WARNING(
                    f'  ! 親子関係スキップ: {child_name} → {parent_name}（未登録）'
                ))
                continue
            if child.axis != parent.axis:
                self.stdout.write(self.style.WARNING(
                    f'  ! 親子関係スキップ: {child_name} → {parent_name}（軸不一致）'
                ))
                continue
            if child.parent_id != parent.id:
                parents_linked += 1
                self.stdout.write(f'  ⤷ {child_name} の親を {parent_name} に設定')
                if not dry_run:
                    child.parent = parent
                    child.save()

        pruned = 0
        if prune:
            stale = MasterTag.objects.filter(is_active=True).exclude(name__in=master_names)
            pruned = stale.count()
            for t in stale:
                self.stdout.write(f'  - 無効化: {t.name}（{t.axis}）')
            if not dry_run:
                stale.update(is_active=False)

        # 既存のユーザー個別タグ(Tag)の軸も同期する。
        # 理由: 関連度計算は Tag.axis を MasterTag より優先するため、過去に custom で
        #       保存された同名タグはマスタを直しても custom のまま＝関連付けに効かない。
        user_synced = 0
        if sync_user_tags:
            for axis, names in TAG_MASTER:
                qs = Tag.objects.filter(name__in=names).exclude(axis=axis)
                cnt = qs.count()
                if cnt:
                    user_synced += cnt
                    for t in qs[:50]:
                        self.stdout.write(f'  ↻ Tag {t.name}: {t.axis} → {axis}')
                    if not dry_run:
                        qs.update(axis=axis)

        if not dry_run:
            cache.delete(MasterTag.CACHE_KEY)

        prefix = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}MasterTag シード完了: 新規 {created} / 更新 {updated} / 変更なし {unchanged}'
            + f' / 親子関係設定 {parents_linked}'
            + (f' / 無効化 {pruned}' if prune else '')
            + (f' / ユーザータグ同期 {user_synced}' if sync_user_tags else '')
        ))
