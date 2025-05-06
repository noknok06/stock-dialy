# financial_reports/management/commands/import_report_json.py

import os
import json
from django.core.management.base import BaseCommand, CommandError
from financial_reports.models import Company, FinancialReport
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'JSONファイルから企業決算レポートをインポートします'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='インポートするJSONファイルのパス')
        parser.add_argument('--user', type=str, help='レポート作成者のユーザー名 (デフォルト: 最初の管理者)', required=False)
        parser.add_argument('--public', action='store_true', help='インポート後にレポートを公開する')

    def handle(self, *args, **options):
        json_file = options['json_file']
        is_public = options['public']
        
        # ファイルの存在確認
        if not os.path.exists(json_file):
            raise CommandError(f'ファイルが見つかりません: {json_file}')
        
        # 作成者を取得
        if options['user']:
            try:
                user = User.objects.get(username=options['user'])
            except User.DoesNotExist:
                raise CommandError(f'指定されたユーザーが見つかりません: {options["user"]}')
        else:
            # デフォルトでは最初の管理者ユーザーを使用
            user = User.objects.filter(is_staff=True).first()
            if not user:
                self.stdout.write(self.style.WARNING('管理者ユーザーが見つかりません。データのみインポートします。'))
        
        # JSONファイルの読み込み
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # 末尾のセミコロンを削除（JavaScriptオブジェクトからの変換対応）
                if content.strip().endswith(';'):
                    content = content.strip()[:-1]
                data = json.loads(content)
        except json.JSONDecodeError as e:
            raise CommandError(f'JSONの解析に失敗しました: {str(e)}')
        except Exception as e:
            raise CommandError(f'ファイルの読み込みに失敗しました: {str(e)}')
        
        # 必須フィールドの確認
        required_fields = ['companyName', 'companyCode', 'fiscalPeriod']
        for field in required_fields:
            if field not in data:
                raise CommandError(f'必須フィールドがありません: {field}')
        
        # 会社情報の取得または作成
        company, created = Company.objects.get_or_create(
            code=data['companyCode'],
            defaults={
                'name': data['companyName'],
                'abbr': data.get('companyAbbr', data['companyName'][:3]),
                'color': data.get('companyColor', '#3B82F6'),
                'is_public': is_public,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'会社情報を作成しました: {company.name} ({company.code})'))
        else:
            self.stdout.write(self.style.WARNING(f'既存の会社情報を使用します: {company.name} ({company.code})'))
        
        # overall_rating を Decimal に変換
        overall_rating = data.get('overallRating', '0')
        try:
            overall_rating = Decimal(overall_rating)
        except:
            overall_rating = Decimal('0')
        
        # レポートの取得または作成
        report, created = FinancialReport.objects.get_or_create(
            company=company,
            fiscal_period=data['fiscalPeriod'],
            defaults={
                'achievement_badge': data.get('achievementBadge', ''),
                'overall_rating': overall_rating,
                'is_public': is_public,
                'data': data,
                'created_by': user,
                'updated_by': user,
            }
        )
        
        if not created:
            # 既存レポートの更新
            report.achievement_badge = data.get('achievementBadge', '')
            report.overall_rating = overall_rating
            report.data = data
            report.updated_by = user
            report.save()
            self.stdout.write(self.style.WARNING(f'既存のレポートを更新しました: {report.fiscal_period}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'新規レポートを作成しました: {report.fiscal_period}'))
        
        self.stdout.write(self.style.SUCCESS(f'インポート完了: {company.name} - {report.fiscal_period}'))