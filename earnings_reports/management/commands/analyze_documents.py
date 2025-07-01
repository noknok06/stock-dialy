"""
earnings_reports/management/commands/analyze_documents.py
書類分析実行コマンド
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import logging

from earnings_reports.models import Company, Document, Analysis
from earnings_reports.services.analysis_service import EarningsAnalysisService

logger = logging.getLogger('earnings_analysis')
User = get_user_model()


class Command(BaseCommand):
    """書類分析実行コマンド"""
    
    help = '指定条件の書類を分析します'
    
    def add_arguments(self, parser):
        """コマンド引数の定義"""
        
        parser.add_argument(
            '--company',
            type=str,
            help='対象企業の証券コード'
        )
        
        parser.add_argument(
            '--user',
            type=str,
            help='実行ユーザーのユーザー名'
        )
        
        parser.add_argument(
            '--doc-type',
            type=str,
            choices=['120', '130', '140', '350'],
            help='書類種別'
        )
        
        parser.add_argument(
            '--days-back',
            type=int,
            default=30,
            help='何日前までの書類を対象とするか'
        )
        
        parser.add_argument(
            '--max-documents',
            type=int,
            default=10,
            help='最大分析書類数'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='既に分析済みの書類も再分析する'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際には分析せず、対象書類のみ表示'
        )
        
        parser.add_argument(
            '--analysis-depth',
            type=str,
            choices=['basic', 'detailed', 'comprehensive'],
            default='detailed',
            help='分析レベル'
        )
    
    def handle(self, *args, **options):
        """コマンド実行"""
        
        self.stdout.write(
            self.style.SUCCESS('書類分析コマンドを開始します...')
        )
        
        try:
            # ユーザーの取得
            user = self._get_user(options['user'])
            
            # 対象書類の取得
            documents = self._get_target_documents(options)
            
            if not documents:
                self.stdout.write(
                    self.style.WARNING('対象書類が見つかりません')
                )
                return
            
            self.stdout.write(f'対象書類: {len(documents)}件')
            
            # Dry runの場合は書類一覧のみ表示
            if options['dry_run']:
                self._display_documents(documents)
                return
            
            # 分析実行
            results = self._execute_analyses(documents, user, options)
            
            # 結果表示
            self._display_results(results)
            
        except Exception as e:
            logger.error(f"分析コマンドエラー: {str(e)}")
            raise CommandError(f'分析実行でエラーが発生しました: {str(e)}')
    
    def _get_user(self, username):
        """ユーザーの取得"""
        if not username:
            # デフォルトユーザーを作成または取得
            user, created = User.objects.get_or_create(
                username='system_analyzer',
                defaults={
                    'email': 'system@example.com',
                    'is_staff': True
                }
            )
            if created:
                self.stdout.write('システム分析ユーザーを作成しました')
            return user
        
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'ユーザー "{username}" が見つかりません')
    
    def _get_target_documents(self, options):
        """対象書類の取得"""
        
        # 基本クエリ
        query = Document.objects.all()
        
        # 企業フィルター
        if options['company']:
            try:
                company = Company.objects.get(stock_code=options['company'])
                query = query.filter(company=company)
            except Company.DoesNotExist:
                raise CommandError(f'企業 "{options["company"]}" が見つかりません')
        
        # 書類種別フィルター
        if options['doc_type']:
            query = query.filter(doc_type=options['doc_type'])
        else:
            # デフォルトは決算関連書類のみ
            query = query.filter(doc_type__in=['120', '130', '140', '350'])
        
        # 日付フィルター
        days_back = options['days_back']
        cutoff_date = timezone.now().date() - timedelta(days=days_back)
        query = query.filter(submit_date__gte=cutoff_date)
        
        # 分析済み書類の除外
        if not options['force']:
            analyzed_doc_ids = Analysis.objects.filter(
                status='completed'
            ).values_list('document_id', flat=True)
            query = query.exclude(id__in=analyzed_doc_ids)
        
        # 並び順と件数制限
        documents = query.order_by('-submit_date')[:options['max_documents']]
        
        return list(documents)
    
    def _display_documents(self, documents):
        """書類一覧の表示"""
        
        self.stdout.write('\n対象書類一覧:')
        self.stdout.write('-' * 80)
        
        for doc in documents:
            self.stdout.write(
                f'{doc.company.stock_code:>6} | '
                f'{doc.company.name:<20} | '
                f'{doc.get_doc_type_display():<10} | '
                f'{doc.submit_date} | '
                f'{doc.doc_description[:40]}...'
            )
    
    def _execute_analyses(self, documents, user, options):
        """分析の実行"""
        
        results = {
            'total': len(documents),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        # 分析設定
        analysis_settings = {
            'analysis_depth': options['analysis_depth'],
            'include_sentiment': True,
            'include_cashflow': True,
            'compare_previous': False,
            'custom_keywords': []
        }
        
        service = EarningsAnalysisService()
        
        for i, document in enumerate(documents, 1):
            self.stdout.write(
                f'[{i}/{len(documents)}] 分析中: '
                f'{document.company.name} - {document.get_doc_type_display()}'
            )
            
            try:
                # 分析レコードを作成
                analysis = Analysis.objects.create(
                    document=document,
                    user=user,
                    status='pending',
                    settings_json=analysis_settings
                )
                
                # 分析実行
                success = service.execute_analysis(analysis)
                
                if success:
                    results['success'] += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ 完了 (スコア: {analysis.overall_score or "N/A"})'
                        )
                    )
                else:
                    results['failed'] += 1
                    results['errors'].append(f'{document.company.name}: {analysis.error_message}')
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ 失敗: {analysis.error_message}')
                    )
                
            except Exception as e:
                results['failed'] += 1
                error_msg = f'{document.company.name}: {str(e)}'
                results['errors'].append(error_msg)
                self.stdout.write(
                    self.style.ERROR(f'  ✗ エラー: {str(e)}')
                )
        
        return results
    
    def _display_results(self, results):
        """結果の表示"""
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('分析結果'))
        self.stdout.write('=' * 50)
        
        self.stdout.write(f"総書類数: {results['total']}")
        self.stdout.write(f"成功: {results['success']}")
        self.stdout.write(f"失敗: {results['failed']}")
        
        if results['errors']:
            self.stdout.write('\nエラー詳細:')
            for error in results['errors']:
                self.stdout.write(f"  - {error}")
        
        success_rate = (results['success'] / results['total']) * 100 if results['total'] > 0 else 0
        self.stdout.write(f'\n成功率: {success_rate:.1f}%')


# =====================================


"""
earnings_reports/management/commands/cleanup_analysis_data.py
分析データクリーンアップコマンド
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from earnings_reports.models import Analysis, Document

logger = logging.getLogger('earnings_analysis')


class Command(BaseCommand):
    """分析データクリーンアップコマンド"""
    
    help = '古い分析データを清掃します'
    
    def add_arguments(self, parser):
        """コマンド引数の定義"""
        
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='何日前より古いデータを削除するか'
        )
        
        parser.add_argument(
            '--failed-only',
            action='store_true',
            help='失敗した分析のみ削除'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際には削除せず、対象データのみ表示'
        )
        
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='書類キャッシュもクリア'
        )
    
    def handle(self, *args, **options):
        """コマンド実行"""
        
        self.stdout.write(
            self.style.SUCCESS('データクリーンアップを開始します...')
        )
        
        try:
            # 削除対象の特定
            cutoff_date = timezone.now() - timedelta(days=options['days'])
            
            query = Analysis.objects.filter(analysis_date__lt=cutoff_date)
            
            if options['failed_only']:
                query = query.filter(status='failed')
            
            target_analyses = query.select_related('document__company')
            
            if not target_analyses.exists():
                self.stdout.write(
                    self.style.WARNING('削除対象のデータが見つかりません')
                )
                return
            
            # 統計表示
            self._display_cleanup_stats(target_analyses, options)
            
            if options['dry_run']:
                self.stdout.write('Dry run モードのため、実際の削除は行いません')
                return
            
            # 削除実行の確認
            if not self._confirm_deletion(len(target_analyses)):
                self.stdout.write('削除をキャンセルしました')
                return
            
            # 削除実行
            deleted_count = self._execute_cleanup(target_analyses, options)
            
            self.stdout.write(
                self.style.SUCCESS(f'クリーンアップ完了: {deleted_count}件削除')
            )
            
        except Exception as e:
            logger.error(f"クリーンアップエラー: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'クリーンアップでエラーが発生しました: {str(e)}')
            )
    
    def _display_cleanup_stats(self, target_analyses, options):
        """削除統計の表示"""
        
        total_count = target_analyses.count()
        
        # ステータス別集計
        status_counts = {}
        for analysis in target_analyses:
            status = analysis.get_status_display()
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # 企業別集計
        company_counts = {}
        for analysis in target_analyses:
            company_name = analysis.document.company.name
            company_counts[company_name] = company_counts.get(company_name, 0) + 1
        
        self.stdout.write(f'\n削除対象: {total_count}件')
        self.stdout.write(f'対象期間: {options["days"]}日前より古いデータ')
        
        self.stdout.write('\nステータス別:')
        for status, count in status_counts.items():
            self.stdout.write(f'  {status}: {count}件')
        
        self.stdout.write('\n企業別 (上位10社):')
        sorted_companies = sorted(company_counts.items(), key=lambda x: x[1], reverse=True)
        for company, count in sorted_companies[:10]:
            self.stdout.write(f'  {company}: {count}件')
    
    def _confirm_deletion(self, count):
        """削除確認"""
        
        response = input(f'\n{count}件のデータを削除します。よろしいですか？ (y/N): ')
        return response.lower() in ['y', 'yes']
    
    def _execute_cleanup(self, target_analyses, options):
        """クリーンアップ実行"""
        
        deleted_count = 0
        
        for analysis in target_analyses:
            try:
                # 関連データも含めて削除
                if hasattr(analysis, 'sentiment'):
                    analysis.sentiment.delete()
                if hasattr(analysis, 'cashflow'):
                    analysis.cashflow.delete()
                
                analysis.delete()
                deleted_count += 1
                
                if deleted_count % 100 == 0:
                    self.stdout.write(f'  {deleted_count}件削除完了...')
                
            except Exception as e:
                logger.warning(f'分析ID {analysis.id} の削除エラー: {str(e)}')
                continue
        
        # キャッシュクリアの実行
        if options['clear_cache']:
            self._clear_document_cache()
        
        return deleted_count
    
    def _clear_document_cache(self):
        """書類キャッシュのクリア"""
        
        try:
            from django.core.cache import cache
            
            # 書類関連のキャッシュキーをクリア
            cache_keys = []
            
            for document in Document.objects.all():
                cache_key = f"document_content_{document.doc_id}"
                cache_keys.append(cache_key)
            
            if cache_keys:
                cache.delete_many(cache_keys)
                self.stdout.write(f'キャッシュクリア完了: {len(cache_keys)}件')
            
        except Exception as e:
            logger.warning(f'キャッシュクリアエラー: {str(e)}')


# =====================================


"""
earnings_reports/management/commands/export_analysis_data.py
分析データエクスポートコマンド
"""

import csv
import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from datetime import datetime

from earnings_reports.models import Analysis, Company
from earnings_reports.utils.company_utils import export_company_analysis_data

User = get_user_model()


class Command(BaseCommand):
    """分析データエクスポートコマンド"""
    
    help = '分析データをエクスポートします'
    
    def add_arguments(self, parser):
        """コマンド引数の定義"""
        
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'csv'],
            default='json',
            help='エクスポート形式'
        )
        
        parser.add_argument(
            '--output',
            type=str,
            help='出力ファイルパス'
        )
        
        parser.add_argument(
            '--company',
            type=str,
            help='特定企業のみエクスポート（証券コード）'
        )
        
        parser.add_argument(
            '--user',
            type=str,
            help='特定ユーザーのデータのみエクスポート'
        )
        
        parser.add_argument(
            '--completed-only',
            action='store_true',
            help='完了した分析のみエクスポート'
        )
    
    def handle(self, *args, **options):
        """コマンド実行"""
        
        self.stdout.write(
            self.style.SUCCESS('データエクスポートを開始します...')
        )
        
        try:
            # 出力ファイル名の決定
            output_file = self._get_output_filename(options)
            
            # データの取得とエクスポート
            if options['company']:
                # 特定企業のデータ
                success = self._export_company_data(options, output_file)
            else:
                # 全データまたはユーザー別データ
                success = self._export_all_data(options, output_file)
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'エクスポート完了: {output_file}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('エクスポートに失敗しました')
                )
                
        except Exception as e:
            raise CommandError(f'エクスポートエラー: {str(e)}')
    
    def _get_output_filename(self, options):
        """出力ファイル名の生成"""
        
        if options['output']:
            return options['output']
        
        # 自動生成
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        extension = options['format']
        
        if options['company']:
            filename = f"analysis_data_{options['company']}_{timestamp}.{extension}"
        elif options['user']:
            filename = f"analysis_data_{options['user']}_{timestamp}.{extension}"
        else:
            filename = f"analysis_data_all_{timestamp}.{extension}"
        
        return filename
    
    def _export_company_data(self, options, output_file):
        """特定企業のデータエクスポート"""
        
        try:
            company = Company.objects.get(stock_code=options['company'])
        except Company.DoesNotExist:
            raise CommandError(f'企業 "{options["company"]}" が見つかりません')
        
        # ユーザーの特定
        if options['user']:
            try:
                user = User.objects.get(username=options['user'])
            except User.DoesNotExist:
                raise CommandError(f'ユーザー "{options["user"]}" が見つかりません')
        else:
            # システムユーザーとして実行
            user = User.objects.filter(is_staff=True).first()
            if not user:
                raise CommandError('管理者ユーザーが見つかりません')
        
        # データエクスポート
        export_data = export_company_analysis_data(
            company, 
            user, 
            options['format']
        )
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(export_data)
        
        return True
    
    def _export_all_data(self, options, output_file):
        """全データのエクスポート"""
        
        # 分析データの取得
        query = Analysis.objects.select_related(
            'document__company', 'user'
        ).prefetch_related('sentiment', 'cashflow')
        
        if options['user']:
            try:
                user = User.objects.get(username=options['user'])
                query = query.filter(user=user)
            except User.DoesNotExist:
                raise CommandError(f'ユーザー "{options["user"]}" が見つかりません')
        
        if options['completed_only']:
            query = query.filter(status='completed')
        
        analyses = query.order_by('-analysis_date')
        
        if not analyses.exists():
            self.stdout.write(
                self.style.WARNING('エクスポート対象のデータが見つかりません')
            )
            return False
        
        # 形式に応じてエクスポート
        if options['format'] == 'json':
            self._export_json(analyses, output_file)
        else:
            self._export_csv(analyses, output_file)
        
        return True
    
    def _export_json(self, analyses, output_file):
        """JSON形式でエクスポート"""
        
        data = []
        
        for analysis in analyses:
            item = {
                'id': analysis.id,
                'analysis_date': analysis.analysis_date.isoformat(),
                'status': analysis.status,
                'overall_score': analysis.overall_score,
                'confidence_level': analysis.confidence_level,
                'processing_time': analysis.processing_time,
                'company': {
                    'stock_code': analysis.document.company.stock_code,
                    'name': analysis.document.company.name,
                    'market': analysis.document.company.market,
                    'sector': analysis.document.company.sector
                },
                'document': {
                    'doc_id': analysis.document.doc_id,
                    'doc_type': analysis.document.doc_type,
                    'doc_description': analysis.document.doc_description,
                    'submit_date': analysis.document.submit_date.isoformat()
                },
                'user': analysis.user.username
            }
            
            # 感情分析データ
            if hasattr(analysis, 'sentiment'):
                sentiment = analysis.sentiment
                item['sentiment_analysis'] = {
                    'positive_score': sentiment.positive_score,
                    'negative_score': sentiment.negative_score,
                    'neutral_score': sentiment.neutral_score,
                    'confidence_keywords_count': sentiment.confidence_keywords_count,
                    'risk_keywords_count': sentiment.risk_keywords_count,
                    'risk_severity': sentiment.risk_severity
                }
            
            # キャッシュフロー分析データ
            if hasattr(analysis, 'cashflow'):
                cashflow = analysis.cashflow
                item['cashflow_analysis'] = {
                    'operating_cf': cashflow.operating_cf,
                    'investing_cf': cashflow.investing_cf,
                    'financing_cf': cashflow.financing_cf,
                    'free_cf': cashflow.free_cf,
                    'pattern': cashflow.pattern,
                    'pattern_score': cashflow.pattern_score
                }
            
            data.append(item)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _export_csv(self, analyses, output_file):
        """CSV形式でエクスポート"""
        
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            # ヘッダー
            writer.writerow([
                'ID', '分析日時', 'ステータス', '証券コード', '企業名', '市場', '業種',
                '書類種別', '書類名', '提出日', 'ユーザー', '総合スコア', '信頼性',
                '処理時間', 'ポジティブ度', 'ネガティブ度', 'リスク言及数',
                '営業CF', '投資CF', '財務CF', 'CFパターン'
            ])
            
            # データ行
            for analysis in analyses:
                sentiment = getattr(analysis, 'sentiment', None)
                cashflow = getattr(analysis, 'cashflow', None)
                
                writer.writerow([
                    analysis.id,
                    analysis.analysis_date.strftime('%Y-%m-%d %H:%M:%S'),
                    analysis.get_status_display(),
                    analysis.document.company.stock_code,
                    analysis.document.company.name,
                    analysis.document.company.market or '',
                    analysis.document.company.sector or '',
                    analysis.document.get_doc_type_display(),
                    analysis.document.doc_description,
                    analysis.document.submit_date.strftime('%Y-%m-%d'),
                    analysis.user.username,
                    analysis.overall_score or '',
                    analysis.confidence_level or '',
                    analysis.processing_time or '',
                    sentiment.positive_score if sentiment else '',
                    sentiment.negative_score if sentiment else '',
                    sentiment.risk_keywords_count if sentiment else '',
                    cashflow.operating_cf if cashflow else '',
                    cashflow.investing_cf if cashflow else '',
                    cashflow.financing_cf if cashflow else '',
                    cashflow.get_pattern_display() if cashflow else ''
                ])