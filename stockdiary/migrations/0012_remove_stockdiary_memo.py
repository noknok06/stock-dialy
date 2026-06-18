"""StockDiary.memo を migration state とDBの両方から正式に外す。

memo は reason へ統合済み（improvement_plan 論点9）でモデルからは既に削除されているが、
その削除を記録した migration が repo にコミットされていなかった。このため毎デプロイで
`makemigrations` が RemoveField('stockdiary','memo') を自動生成し、本番では
（過去のローカル限定 migration で列が既に DROP 済みのため）`column "memo" does not exist`
で migrate が失敗していた。

この migration を正式にコミットすることで:
- state から memo を外す → 以後 makemigrations が再生成しない
- DB 側は「列が存在するときだけ DROP」する冪等な操作にする
  （本番=既に削除済みでも no-op、新規DB=0001 で作られた列を DROP）

テストは --nomigrations のため本 migration は実行されない（モデル基準で memo 無し）。
"""
from django.db import migrations


TABLE = 'stockdiary_stockdiary'
COLUMN = 'memo'


def _column_exists(schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cursor:
        return COLUMN in [
            col.name for col in conn.introspection.get_table_description(cursor, TABLE)
        ]


def drop_memo_if_exists(apps, schema_editor):
    if _column_exists(schema_editor):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f'ALTER TABLE {TABLE} DROP COLUMN {COLUMN}')


def add_memo_if_missing(apps, schema_editor):
    if not _column_exists(schema_editor):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f'ALTER TABLE {TABLE} ADD COLUMN {COLUMN} text')


class Migration(migrations.Migration):

    dependencies = [
        ('stockdiary', '0012_merge_0011_merge_memo_into_reason_0011_thesis_verdict'),
    ]

    operations = [
        migrations.RunPython(drop_memo_if_exists, add_memo_if_missing),
    ]
