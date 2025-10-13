# python manage.py initialize_plans
# subscriptions/management/commands/initialize_plans.py
from django.core.management.base import BaseCommand
from subscriptions.models import SubscriptionPlan

class Command(BaseCommand):
    help = 'Initialize subscription plans'

    def handle(self, *args, **kwargs):
        # 既存のプランを確認
        existing_slugs = set(SubscriptionPlan.objects.values_list('slug', flat=True))
        
        # フリープラン
        free_plan, created = SubscriptionPlan.objects.get_or_create(
            slug='free',
            defaults={
                'name': 'フリープラン',
                'max_tags': 5,
                'max_templates': 3,
                'max_records': -1,  # 無制限
                'show_ads': True,
                'export_enabled': False,
                'advanced_analytics': False,
                'price_monthly': 0,
                'price_yearly': 0,
            }
        )
        self.stdout.write(f"フリープラン: {'作成' if created else '既存'}")
        
        # ベーシックプラン (以前のad_freeプランの代替)
        basic_plan, created = SubscriptionPlan.objects.get_or_create(
            slug='basic',
            defaults={
                'name': 'ベーシックプラン',
                'max_tags': 10,
                'max_templates': 10,
                'max_records': 100,
                'show_ads': False,
                'export_enabled': False,
                'advanced_analytics': False,
                'price_monthly': 400,
                'price_yearly': 3800,
            }
        )
        self.stdout.write(f"ベーシックプラン: {'作成' if created else '既存'}")
        
        # プロプラン
        pro_plan, created = SubscriptionPlan.objects.get_or_create(
            slug='pro',
            defaults={
                'name': 'プロプラン',
                'max_tags': -1,  # 無制限
                'max_templates': -1,  # 無制限
                'max_records': -1,  # 無制限
                'show_ads': False,
                'export_enabled': True,
                'advanced_analytics': True,
                'price_monthly': 800,
                'price_yearly': 7600,
            }
        )
        self.stdout.write(f"プロプラン: {'作成' if created else '既存'}")
        
        # 古いプランの非アクティブ化 (ad_freeプランなど)
        old_slugs = {'ad_free'}
        for old_slug in old_slugs:
            if old_slug in existing_slugs:
                try:
                    old_plan = SubscriptionPlan.objects.get(slug=old_slug)
                    # 必要に応じて古いプランの処理を追加
                    self.stdout.write(f"古いプラン '{old_slug}' を検出しました")
                except SubscriptionPlan.DoesNotExist:
                    pass
        
        self.stdout.write(self.style.SUCCESS('サブスクリプションプランの初期化が完了しました'))