# python manage.py create_tags --username admin
# tags/management/commands/create_tags.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tags.models import Tag

User = get_user_model()

class Command(BaseCommand):
    help = "タグのテストデータを作成します"

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='テストデータを作成するユーザー名')

    def handle(self, *args, **options):
        username = options['username']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'ユーザー "{username}" が見つかりません。'))
            return

        # 投資関連のタグリスト
        tag_names = [
            # 投資スタイル
            "バリュー投資", "グロース投資", "高配当投資", "インデックス投資", "スイングトレード",
            "デイトレード", "中長期投資", "短期投資", "アクティブ投資", "パッシブ投資",
            
            # 業種・セクター
            "IT", "テクノロジー", "金融", "医療・ヘルスケア", "エネルギー", "不動産", "消費財",
            "通信", "素材", "産業", "サービス", "小売", "食品", "自動車", "航空", "鉄道", "電力",
            "ガス", "水道", "インフラ", "メディア", "エンターテイメント", "観光", "教育",
            
            # 投資判断
            "買い増し候補", "売却検討", "要観察", "長期保有", "短期売買", "高成長", "安定配当",
            "割安株", "割高株", "出来高急増", "決算良好", "業績悪化", "経営陣交代", "新規事業",
            "M&A", "構造改革", "自社株買い", "増配", "減配", "赤字転落", "黒字転換",
            
            # 市場・地域
            "米国株", "日本株", "中国株", "欧州株", "アジア株", "新興国", "先進国",
            "東証一部", "東証二部", "マザーズ", "JASDAQ", "ナスダック", "NYSE", "FTSE", "DAX",
            
            # その他投資関連
            "ETF", "投資信託", "REIT", "IPO", "大型株", "中型株", "小型株", "優待株", "連続増配",
            "高ROE", "低PER", "低PBR", "高ベータ", "低ベータ", "高ボラティリティ", "低リスク",
            "ESG投資", "インフレ耐性", "金利敏感", "新技術", "特許", "ブランド力", "AI", "IoT",
            "5G", "クラウド", "サブスクリプション", "プラットフォーム", "SaaS", "フィンテック",
            "eコマース", "再生可能エネルギー", "電気自動車", "半導体", "バイオテック", "デジタル変革"
        ]

        created_count = 0
        skipped_count = 0

        for tag_name in tag_names:
            # 既存のタグがあれば作成しない
            if Tag.objects.filter(user=user, name=tag_name).exists():
                skipped_count += 1
                continue
                
            Tag.objects.create(user=user, name=tag_name)
            created_count += 1
            
        self.stdout.write(self.style.SUCCESS(f'{created_count} 件のタグを作成しました。'))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'{skipped_count} 件のタグは既に存在していたためスキップしました。'))