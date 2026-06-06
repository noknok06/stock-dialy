"""tag_master.md の章構成に基づき既存タグへ軸を自動割り当てるデータマイグレーション。

新規タグ（マスタ外）はデフォルトの 'theme' が維持される。
"""
from django.db import migrations


# タグ名 → 軸 のマッピング（tag_master.md 準拠）
TAG_AXIS_MAP = {
    # マクロ経済 → macro
    'インフレ':         'macro',
    '金利上昇':         'macro',
    '金利低下':         'macro',
    '円安メリット':     'macro',
    '円高メリット':     'macro',
    '景気敏感':         'macro',
    'ディフェンシブ':   'macro',
    '資源価格上昇':     'macro',
    # 不動産・金融 → macro
    '金利感応':         'macro',
    '都心オフィス':     'macro',
    '不動産市況':       'macro',

    # AI・デジタル → theme
    'AI':               'theme',
    'フィジカルAI':     'theme',
    'ドローン':         'theme',
    'DX':               'theme',
    'サイバーセキュリティ': 'theme',
    'AIセキュリティ':   'theme',
    'データセンター':   'theme',
    '半導体':           'theme',
    'オルタナティブデータ': 'theme',
    '通信インフラ':     'theme',
    # 化石燃料・資源エネルギー → theme
    'エネルギー':       'theme',
    'LNG':              'theme',
    # 脱炭素・クリーンエネルギー → theme
    '脱炭素':           'theme',
    '再生可能エネルギー': 'theme',
    '水素':             'theme',
    '蓄電池':           'theme',
    'CCS':              'theme',
    'SAF':              'theme',
    # 社会・政策テーマ → theme
    '防衛':             'theme',
    '国土強靭化':       'theme',
    'インフラ老朽化':   'theme',
    '建設補修':         'theme',
    '少子高齢化':       'theme',
    'インバウンド':     'theme',
    'アジア消費':       'theme',
    # ヘルスケア・医療 → theme
    'ヘルスケア':       'theme',
    'ヘルスケア施設開発': 'theme',
    '医療DX':           'theme',
    '創薬':             'theme',
    '医療機器':         'theme',
    # 物流・サプライチェーン → theme
    '物流':             'theme',
    'EC物流':           'theme',
    'サプライチェーン': 'theme',
    # 人材・サービス → theme
    'HRテック':         'theme',
    '採用プラットフォーム': 'theme',
    'ハイクラス人材':   'theme',
    '人材ビジネス':     'theme',
    '人材集約型':       'theme',

    # 配当・株主還元 → capital_policy
    '高配当':           'capital_policy',
    '累進配当':         'capital_policy',
    '連続増配':         'capital_policy',
    '連続増益':         'capital_policy',
    '高ROE':            'capital_policy',
    '株主還元強化':     'capital_policy',

    # 成長戦略 → business_model
    'M&A成長':          'business_model',
    '海外展開':         'business_model',
    'IPビジネス':       'business_model',
    'プラットフォーム': 'business_model',
    'ストック収益':     'business_model',
    '高シェア':         'business_model',
    'ニッチトップ':     'business_model',
    # 商社・バリューチェーン → business_model
    '総合商社':         'business_model',
    '資源権益':         'business_model',
    'バリューチェーン': 'business_model',

    # リスク → risk
    '地政学リスク':     'risk',
    '規制リスク':       'risk',
    '需給変化':         'risk',

    # 経営・企業イベント → event
    '構造改革':         'event',
    '利益率改善':       'event',
    '設備投資拡大':     'event',
    '決算注目':         'event',
    '業績上方修正':     'event',
    '増配':             'event',
    '減配':             'event',
    'MBO・買収':        'event',
    '決算ミス':         'event',
}


def assign_tag_axes(apps, schema_editor):
    Tag = apps.get_model('tags', 'Tag')
    updates = []
    for tag in Tag.objects.all():
        new_axis = TAG_AXIS_MAP.get(tag.name)
        if new_axis and tag.axis != new_axis:
            tag.axis = new_axis
            updates.append(tag)
    if updates:
        Tag.objects.bulk_update(updates, ['axis'])


def reverse_assign_tag_axes(apps, schema_editor):
    Tag = apps.get_model('tags', 'Tag')
    Tag.objects.update(axis='theme')


class Migration(migrations.Migration):

    dependencies = [
        ('tags', '0003_tag_axis_parent_df'),
    ]

    operations = [
        migrations.RunPython(assign_tag_axes, reverse_code=reverse_assign_tag_axes),
    ]
