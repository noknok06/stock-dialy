# financial_reports/management/commands/import_sample_data.py

import os
import json
from django.core.management.base import BaseCommand
from financial_reports.models import Company, FinancialReport
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = '丸紅の決算データをサンプルとしてインポートします'

    def handle(self, *args, **options):
        # 管理者ユーザーを取得（なければ作成）
        admin_user = User.objects.filter(is_staff=True).first()
        if not admin_user:
            self.stdout.write(self.style.WARNING('管理者ユーザーが見つかりません。データのみインポートします。'))
        
        # 丸紅データ
        marubeni_data = {
            # 会社情報
            "companyAbbr": "MRB",
            "companyColor": "#E60012",
            "companyName": "丸紅株式会社",
            "companyCode": "8002",
            "fiscalPeriod": "2025年3月期 決算サマリー",
            "achievementBadge": "過去2番目の高水準達成",
            
            # 総合評価
            "overallRating": "8.5",
            "overallRatingText": "優秀（7-9点）",
            "overallSummary": "前期比6.7%増益となる5,030億円の純利益を計上し、従来見通しを上回る好業績。非資源分野は過去最高の3,230億円の実態純利益を達成。積極的な資本配分と株主還元も強化し、総合的に良好な決算内容。",
            "recommendationText": "買い推奨",
            "starRating": "★★★★☆",
            "investmentReason": "非資源事業の安定的な収益拡大と積極的な株主還元策が評価でき、PER8.4倍と割安感もある。中期経営戦略で掲げる時価総額10兆円目標に向けた成長期待も投資魅力。",
            
            # その他のデータも含む（省略部分が多いため全てを表示していません）
            # 実際は paste.txt のデータをすべて含めます
            
            # データソース
            "dataSource": "丸紅株式会社 2025年3月期決算IR資料（2025年5月2日公表）"
        }
        
        # 会社情報が既に存在するか確認
        company, created = Company.objects.get_or_create(
            code="8002",
            defaults={
                "name": "丸紅株式会社",
                "abbr": "MRB",
                "color": "#E60012",
                "is_public": True,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('会社情報を作成しました: %s' % company))
        else:
            self.stdout.write(self.style.WARNING('会社情報は既に存在します: %s' % company))
        
        # レポートが既に存在するか確認
        report, created = FinancialReport.objects.get_or_create(
            company=company,
            fiscal_period="2025年3月期 決算サマリー",
            defaults={
                "achievement_badge": "過去2番目の高水準達成",
                "overall_rating": 8.5,
                "is_public": True,
                "data": marubeni_data,
                "created_by": admin_user,
                "updated_by": admin_user,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('決算レポートを作成しました: %s' % report))
        else:
            self.stdout.write(self.style.WARNING('決算レポートは既に存在します: %s' % report))