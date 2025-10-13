# subscriptions/management/commands/setup_test_environment.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from subscriptions.models import SubscriptionPlan, UserSubscription
from ads.models import UserAdPreference, AdPlacement, AdUnit

User = get_user_model()

class Command(BaseCommand):
    help = 'サブスクリプションと広告表示のテスト環境をセットアップします'

    def add_arguments(self, parser):
        parser.add_argument('--create-plans', action='store_true', help='サブスクリプションプランを作成する')
        parser.add_argument('--create-users', action='store_true', help='テストユーザーを作成する')
        parser.add_argument('--create-ads', action='store_true', help='広告配置とユニットを作成する')
        parser.add_argument('--all', action='store_true', help='すべてのセットアップを実行する')

    def handle(self, *args, **options):
        if options['all'] or options['create_plans']:
            self.setup_subscription_plans()
        
        if options['all'] or options['create_users']:
            self.setup_test_users()
        
        if options['all'] or options['create_ads']:
            self.setup_ad_placements()
        
        self.stdout.write(self.style.SUCCESS('テスト環境のセットアップが完了しました'))
    
    def setup_subscription_plans(self):
        """サブスクリプションプランの作成"""
        self.stdout.write('サブスクリプションプランをセットアップ中...')
        
        # フリープラン
        free_plan, created = SubscriptionPlan.objects.get_or_create(
            slug='free',
            defaults={
                'name': 'フリープラン',
                'max_tags': 5,
                'max_templates': 3,
                'max_records': 30,
                'show_ads': True,
                'export_enabled': False,
                'advanced_analytics': False,
                'price_monthly': 0,
                'price_yearly': 0,
            }
        )
        self.stdout.write(f'フリープラン: {"作成" if created else "既存"}')
        
        # ベーシックプラン
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
        self.stdout.write(f'ベーシックプラン: {"作成" if created else "既存"}')
        
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
        self.stdout.write(f'プロプラン: {"作成" if created else "既存"}')
    
    def setup_test_users(self):
        """テストユーザーの作成"""
        self.stdout.write('テストユーザーをセットアップ中...')
        
        try:
            # 各プランのテストユーザーを作成
            plans = SubscriptionPlan.objects.all()
            if plans.count() == 0:
                self.stdout.write(self.style.ERROR('先にプランを作成してください'))
                return
            
            for plan in plans:
                username = f'test_{plan.slug}'
                email = f'{username}@example.com'
                password = 'testpassword123'
                
                # ユーザー作成
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': email,
                        'is_active': True
                    }
                )
                
                if created:
                    user.set_password(password)
                    user.save()
                    self.stdout.write(f'ユーザー "{username}" を作成しました')
                else:
                    self.stdout.write(f'ユーザー "{username}" は既に存在します')
                
                # サブスクリプション設定
                subscription, sub_created = UserSubscription.objects.get_or_create(
                    user=user,
                    defaults={
                        'plan': plan,
                        'is_active': True
                    }
                )
                
                if not sub_created:
                    subscription.plan = plan
                    subscription.is_active = True
                    subscription.save()
                
                # 広告設定
                ad_pref, ad_created = UserAdPreference.objects.get_or_create(
                    user=user,
                    defaults={
                        'show_ads': plan.show_ads,
                        'is_premium': not plan.show_ads,
                        'allow_personalized_ads': plan.show_ads
                    }
                )
                
                if not ad_created:
                    ad_pref.show_ads = plan.show_ads
                    ad_pref.is_premium = not plan.show_ads
                    ad_pref.allow_personalized_ads = plan.show_ads
                    ad_pref.save()
                
                self.stdout.write(f'{plan.name}用のテストユーザーをセットアップしました (username: {username}, password: {password})')
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'テストユーザー作成中にエラーが発生しました: {str(e)}'))
    
    def setup_ad_placements(self):
        """広告配置の設定"""
        self.stdout.write('広告配置をセットアップ中...')
        
        try:
            # 広告配置の作成
            placements = [
                ('header', 'ヘッダー広告', 'ページ上部に表示される広告'),
                ('sidebar', 'サイドバー広告', 'サイドバーに表示される広告'),
                ('content_top', 'コンテンツ上部広告', 'コンテンツの上部に表示される広告'),
                ('content_bottom', 'コンテンツ下部広告', 'コンテンツの下部に表示される広告'),
                ('footer', 'フッター広告', 'フッター部分に表示される広告'),
            ]
            
            for position, name, description in placements:
                placement, created = AdPlacement.objects.get_or_create(
                    position=position,
                    defaults={
                        'name': name,
                        'description': description,
                        'is_active': True
                    }
                )
                self.stdout.write(f'{name}: {"作成" if created else "既存"}')
                
                # 広告ユニットの作成（テスト用なのでダミーの値）
                if created:
                    AdUnit.objects.create(
                        placement=placement,
                        name=f'{name}ユニット',
                        ad_client='ca-pub-0000000000000000',  # テスト用ダミー値
                        ad_slot='0000000000',  # テスト用ダミー値
                        ad_format='responsive',
                        is_active=True
                    )
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'広告配置設定中にエラーが発生しました: {str(e)}'))