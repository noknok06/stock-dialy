from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from analysis_template.models import AnalysisTemplate, AnalysisItem

User = get_user_model()

@receiver(post_save, sender=User)
def create_sample_template(sender, instance, created, **kwargs):
    """
    ユーザー作成時にサンプルテンプレートを作成する
    """
    if created:  # 新規ユーザー作成時のみ実行
        # サンプルテンプレートの作成
        template = AnalysisTemplate.objects.create(
            user=instance,
            name="【サンプル】高配当銘柄選定",
            description="高配当株を選ぶための基本チェックポイント"
        )
        
        # 1. 配当利回り（チェック＋値）
        AnalysisItem.objects.create(
            template=template,
            order=1,
            name="配当利回り 3%以上",
            description="3%以上の利回りがあるか",
            item_type="boolean_with_value",
            value_label="利回り(%)"
        )
        
        # 2. 配当性向（数値）
        AnalysisItem.objects.create(
            template=template,
            order=2,
            name="配当性向",
            description="30-70%が適正範囲",
            item_type="number",
            value_label="性向(%)"
        )
        
        # 3. 財務安全性（単純チェック）
        AnalysisItem.objects.create(
            template=template,
            order=3,
            name="財務安全性",
            description="自己資本比率30%以上",
            item_type="boolean"
        )
        
        # 4. 増配実績（選択式）
        AnalysisItem.objects.create(
            template=template,
            order=4,
            name="増配実績",
            description="過去の配当推移",
            item_type="select",
            choices="連続増配,安定配当,明確な方針,不安定/減配"
        )
        
        # 5. 信用倍率（チェック＋値）
        AnalysisItem.objects.create(
            template=template,
            order=5,
            name="信用倍率 2以下",
            description="買われすぎでないか確認",
            item_type="boolean_with_value",
            value_label="倍率"
        )