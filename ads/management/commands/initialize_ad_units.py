# ads/management/commands/initialize_ad_units.py
from django.core.management.base import BaseCommand
from ads.models import AdPlacement, AdUnit

class Command(BaseCommand):
    help = '広告配置と広告ユニットの初期データを設定'

    def handle(self, *args, **kwargs):
        # 広告配置の作成
        header_placement, created = AdPlacement.objects.get_or_create(
            position='header',
            defaults={
                'name': 'ヘッダー広告',
                'description': 'ページ上部に表示される広告',
                'is_active': True
            }
        )
        self.stdout.write(f"ヘッダー配置: {'作成' if created else '既存'}")

        sidebar_placement, created = AdPlacement.objects.get_or_create(
            position='sidebar',
            defaults={
                'name': 'サイドバー広告',
                'description': 'サイドバーに表示される広告',
                'is_active': True
            }
        )
        self.stdout.write(f"サイドバー配置: {'作成' if created else '既存'}")

        content_top_placement, created = AdPlacement.objects.get_or_create(
            position='content_top',
            defaults={
                'name': 'コンテンツ上部広告',
                'description': 'コンテンツの上部に表示される広告',
                'is_active': True
            }
        )
        self.stdout.write(f"コンテンツ上部配置: {'作成' if created else '既存'}")

        content_bottom_placement, created = AdPlacement.objects.get_or_create(
            position='content_bottom',
            defaults={
                'name': 'コンテンツ下部広告',
                'description': 'コンテンツの下部に表示される広告',
                'is_active': True
            }
        )
        self.stdout.write(f"コンテンツ下部配置: {'作成' if created else '既存'}")

        footer_placement, created = AdPlacement.objects.get_or_create(
            position='footer',
            defaults={
                'name': 'フッター広告',
                'description': 'フッター部分に表示される広告',
                'is_active': True
            }
        )
        self.stdout.write(f"フッター配置: {'作成' if created else '既存'}")

        # 広告ユニットの作成
        header_ad, created = AdUnit.objects.get_or_create(
            placement=header_placement,
            defaults={
                'name': 'ヘッダーバナー広告',
                'ad_client': 'ca-pub-3954701883136363',  # 実際のAdSenseクライアントIDに置き換え
                'ad_slot': '1234567890',  # 実際のAdSenseスロットIDに置き換え
                'ad_format': 'responsive',  # 'horizontal'から変更
                'is_active': True
            }
        )
        self.stdout.write(f"ヘッダー広告ユニット: {'作成' if created else '既存'}")

        sidebar_ad, created = AdUnit.objects.get_or_create(
            placement=sidebar_placement,
            defaults={
                'name': 'サイドバーレクタングル広告',
                'ad_client': 'ca-pub-3954701883136363',
                'ad_slot': '0987654321',
                'ad_format': 'responsive',  # 'horizontal'から変更
                'is_active': True
            }
        )
        self.stdout.write(f"サイドバー広告ユニット: {'作成' if created else '既存'}")

        content_top_ad, created = AdUnit.objects.get_or_create(
            placement=content_top_placement,
            defaults={
                'name': 'コンテンツ上部広告',
                'ad_client': 'ca-pub-3954701883136363',
                'ad_slot': '1357924680',
                'ad_format': 'responsive',
                'is_active': True
            }
        )
        self.stdout.write(f"コンテンツ上部広告ユニット: {'作成' if created else '既存'}")

        content_bottom_ad, created = AdUnit.objects.get_or_create(
            placement=content_bottom_placement,
            defaults={
                'name': 'コンテンツ下部広告',
                'ad_client': 'ca-pub-3954701883136363',
                'ad_slot': '2468013579',
                'ad_format': 'responsive',
                'is_active': True
            }
        )
        self.stdout.write(f"コンテンツ下部広告ユニット: {'作成' if created else '既存'}")

        footer_ad, created = AdUnit.objects.get_or_create(
            placement=footer_placement,
            defaults={
                'name': 'フッター広告',
                'ad_client': 'ca-pub-3954701883136363',
                'ad_slot': '0864213579',
                'ad_format': 'responsive',  # 'horizontal'から変更
                'is_active': True
            }
        )
        self.stdout.write(f"フッター広告ユニット: {'作成' if created else '既存'}")

        self.stdout.write(self.style.SUCCESS('広告配置と広告ユニットの設定が完了しました'))


        # 日記タブ内広告
        diary_tab_ad, created = AdUnit.objects.get_or_create(
            template_type='diary_tab',
            defaults={
                'name': '日記タブ内広告',
                'ad_client': 'ca-pub-3954701883136363',
                'ad_slot': '8710672022',
                'ad_format': 'fluid',
                'ad_layout': 'in-article',
                'custom_style': 'display:block; text-align:center;',
                'is_fluid': True,
                'is_active': True,
                'placement': content_bottom_placement,  # 既存の配置を使用
            }
        )
        self.stdout.write(f"日記タブ内広告ユニット: {'作成' if created else '既存'}")
        self.stdout.write(self.style.SUCCESS('日記タブ内広告ユニットの設定が完了しました'))

        # 日記一覧広告
        diary_list_ad, created = AdUnit.objects.get_or_create(
            template_type='diary_list',
            defaults={
                'name': '日記一覧広告',
                'ad_client': 'ca-pub-3954701883136363',
                'ad_slot': '9620670260',
                'ad_format': 'fluid',
                'ad_layout_key': '-h2+d+5c-9-3e',
                'is_fluid': True,
                'is_active': True,
                'placement': content_bottom_placement,  # 既存の配置を使用
            }
        )
        self.stdout.write(f"日記一覧広告ユニット: {'作成' if created else '既存'}")        
        self.stdout.write(self.style.SUCCESS('日記一覧広告の設定が完了しました'))