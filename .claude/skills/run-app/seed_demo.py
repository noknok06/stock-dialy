# 日記詳細ページ確認用シードデータ（manage.py shell で実行）
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model

from stockdiary.models import StockDiary, Transaction, DiaryNote
from stockdiary.services.aggregate_service import AggregateService
from tags.models import Tag

User = get_user_model()

user, _ = User.objects.get_or_create(
    username='uxcheck',
    defaults={'email': 'uxcheck@example.com'},
)
user.set_password('uxcheck-pass')
user.is_active = True
user.save()

StockDiary.objects.filter(user=user).delete()

diary = StockDiary.objects.create(
    user=user,
    stock_symbol='7203',
    stock_name='トヨタ自動車',
    sector='輸送用機器',
    reason=(
        '## 投資理由\n\n'
        'EV移行期でも全方位戦略（HV・PHEV・EV・水素）でリスク分散できている点を評価。\n\n'
        '- PER は業界平均より割安\n'
        '- 円安局面での輸出採算改善\n'
        '- 北米販売が堅調で在庫水準も健全\n\n'
        '中期では認定中古車とKINTOのストック収益化に注目。決算ごとに営業利益率の推移を確認する。'
    ),
)

txs = [
    ('buy', date.today() - timedelta(days=180), '2450.00', '100', False, '初回打診買い'),
    ('buy', date.today() - timedelta(days=120), '2300.00', '100', False, '下落で買い増し'),
    ('sell', date.today() - timedelta(days=60), '2750.00', '50', False, '一部利確'),
    ('buy', date.today() - timedelta(days=20), '2600.00', '100', True, '決算またぎ信用買い'),
]
for t_type, t_date, price, qty, is_margin, memo in txs:
    Transaction.objects.create(
        diary=diary, transaction_type=t_type, transaction_date=t_date,
        price=Decimal(price), quantity=Decimal(qty), is_margin=is_margin, memo=memo,
    )
AggregateService.recalculate(diary)

notes = [
    (90, '四半期決算は営業利益が市場予想を上回った。北米の値引き抑制が効いている。', '2550.00', 'earnings', 'high', '決算'),
    (45, '新型EVプラットフォーム発表。投資判断の前提は変わらず。', '2700.00', 'news', 'medium', '新製品'),
    (10, '為替が円高方向へ。輸出採算の前提を見直す必要があるか要確認。', '2580.00', 'analysis', 'high', '為替'),
    (3, '月次販売データは前年同月比プラスを維持。', '2620.00', 'other', 'low', '月次'),
]
for days, content, price, ntype, imp, topic in notes:
    DiaryNote.objects.create(
        diary=diary, date=date.today() - timedelta(days=days),
        content=content, current_price=Decimal(price),
        note_type=ntype, importance=imp, topic=topic,
    )

for name in ['長期投資', '高配当']:
    tag, _ = Tag.objects.get_or_create(user=user, name=name)
    diary.tags.add(tag)

# 関連日記用にもう1銘柄
other = StockDiary.objects.create(
    user=user, stock_symbol='7267', stock_name='ホンダ',
    sector='輸送用機器', reason='二輪事業の収益性を評価',
)
Transaction.objects.create(
    diary=other, transaction_type='buy', transaction_date=date.today() - timedelta(days=30),
    price=Decimal('1500.00'), quantity=Decimal('100'),
)
AggregateService.recalculate(other)
diary.linked_diaries.add(other)

print(f"SEED_OK diary_id={diary.id} other_id={other.id}")
