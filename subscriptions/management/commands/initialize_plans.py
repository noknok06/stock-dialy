# python manage.py initialize_plans
# subscriptions/management/commands/initialize_plans.py
from django.core.management.base import BaseCommand
from subscriptions.models import SubscriptionPlan

class Command(BaseCommand):
    help = 'Initialize subscription plans'

    def handle(self, *args, **kwargs):
        # フリープラン
        free_plan, created = SubscriptionPlan.objects.get_or_create(
            slug='free',
            defaults={
                'name': 'フリープラン',
                'max_tags': 5,
                'max_templates': 3,
                'max_snapshots': 3,
                'max_records': 30,
                'show_ads': True,
                'export_enabled': False,
                'advanced_analytics': False,
                'price_monthly': 0,
                'price_yearly': 0,
            }
        )
        
        # 広告削除プラン
        ad_free_plan, created = SubscriptionPlan.objects.get_or_create(
            slug='ad_free',
            defaults={
                'name': '広告削除プラン',
                'max_tags': 10,
                'max_templates': 10,
                'max_snapshots': 10,
                'max_records': 100,
                'show_ads': False,
                'export_enabled': False,
                'advanced_analytics': False,
                'price_monthly': 400,
                'price_yearly': 3900,
            }
        )
        
        # プロプラン
        pro_plan, created = SubscriptionPlan.objects.get_or_create(
            slug='pro',
            defaults={
                'name': 'プロプラン',
                'max_tags': 9999,
                'max_templates': 9999,
                'max_snapshots': 9999,
                'max_records': 9999,
                'show_ads': False,
                'export_enabled': True,
                'advanced_analytics': True,
                'price_monthly': 900,
                'price_yearly': 9000,
            }
        )
        
        self.stdout.write(self.style.SUCCESS('Subscription plans have been initialized successfully'))