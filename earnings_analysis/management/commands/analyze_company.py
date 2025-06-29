# earnings_analysis/management/commands/analyze_company.py
"""
個別企業の決算分析を実行するコマンド

オンデマンド分析に特化したシンプルな管理コマンド
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import logging

from earnings_analysis.analysis_service import OnDemandAnalysisService
from earnings_analysis.services import EDINETAPIService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '特定企業の決算分析を実行'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'company_code',
            type=str,
            help='分析する企業の証券コード (例: 7203)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='キャッシュを無視して強制的に再分析',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='詳細ログを出力',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際の分析は行わず、処理内容のみ表示',
        )
    
    def handle(self, *args, **options):
        company_code = options['company_code']
        force_refresh = options['force']
        verbose = options['verbose']
        dry_run = options['dry_run']
        
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        
        self.stdout.write(
            self.style.SUCCESS(f'企業 {company_code} の決算分析を開始します...')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('ドライランモード: 実際の分析は行いません')
            )
            self._show_analysis_plan(company_code)
            return
        
        start_time = timezone.now()
        
        try:
            # 分析サービスの初期化
            analysis_service = OnDemandAnalysisService()
            
            # 分析実行
            self.stdout.write(f"分析実行中...")
            result = analysis_service.get_or_analyze_company(
                company_code=company_code, 
                force_refresh=force_refresh
            )
            
            # 結果表示
            processing_time = (timezone.now() - start_time).total_seconds()
            
            if result['success']:
                self._display_success_result(result, processing_time)
            else:
                self._display_error_result(result, processing_time)
                raise CommandError(f"分析に失敗しました: {result.get('error', '不明なエラー')}")
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.ERROR('処理が中断されました')
            )
            raise CommandError('ユーザーによって処理が中断されました')
        
        except Exception as e:
            processing_time = (timezone.now() - start_time).total_seconds()
            self.stdout.write(
                self.style.ERROR(f'予期しないエラーが発生しました (処理時間: {processing_time:.1f}秒): {str(e)}')
            )
            raise CommandError(f'分析処理に失敗しました: {str(e)}')
    
    def _show_analysis_plan(self, company_code):
        """ドライラン時の処理内容表示"""
        self.stdout.write('\n=== 分析処理計画 ===')
        self.stdout.write(f'対象企業: {company_code}')
        self.stdout.write('処理手順:')
        self.stdout.write('  1. 企業情報の取得・作成')
        self.stdout.write('  2. キャッシュされた分析結果の確認')
        self.stdout.write('  3. 最新決算書類の検索')
        self.stdout.write('  4. EDINET APIからの書類取得')
        self.stdout.write('  5. XBRL文書からのテキスト抽出')
        self.stdout.write('  6. キャッシュフロー分析')
        self.stdout.write('  7. 感情分析・経営陣自信度分析')
        self.stdout.write('  8. 分析結果の保存・キャッシュ')
        self.stdout.write('\n実際に実行するには --dry-run オプションを外してください。')
    
    def _display_success_result(self, result, processing_time):
        """成功時の結果表示"""
        self.stdout.write(
            self.style.SUCCESS(f'\n=== 分析完了 (処理時間: {processing_time:.1f}秒) ===')
        )
        
        # 企業情報
        company = result.get('company', {})
        self.stdout.write(f"企業名: {company.get('name', '不明')}")
        self.stdout.write(f"証券コード: {company.get('code', '不明')}")
        
        # 分析対象期間
        report = result.get('report', {})
        if report:
            self.stdout.write(f"分析対象: {report.get('fiscal_year', '不明')} {report.get('quarter', '不明')}")
            self.stdout.write(f"書類提出日: {report.get('submission_date', '不明')}")
        
        # キャッシュフロー分析結果
        cf_analysis = result.get('cashflow_analysis')
        if cf_analysis:
            self.stdout.write('\n--- キャッシュフロー分析 ---')
            self.stdout.write(f"CFパターン: {cf_analysis.get('cf_pattern_description', '不明')}")
            self.stdout.write(f"健全性スコア: {cf_analysis.get('health_score', '不明')}")
            
            operating_cf = cf_analysis.get('operating_cf')
            if operating_cf is not None:
                self.stdout.write(f"営業CF: {operating_cf:,.0f}百万円")
            
            free_cf = cf_analysis.get('free_cf')
            if free_cf is not None:
                self.stdout.write(f"フリーCF: {free_cf:,.0f}百万円")
            
            if cf_analysis.get('analysis_summary'):
                self.stdout.write(f"要約: {cf_analysis['analysis_summary']}")
        
        # 感情分析結果
        sentiment_analysis = result.get('sentiment_analysis')
        if sentiment_analysis:
            self.stdout.write('\n--- 感情分析 ---')
            self.stdout.write(f"感情スコア: {sentiment_analysis.get('sentiment_score', 0):.1f}")
            self.stdout.write(f"経営陣自信度: {sentiment_analysis.get('confidence_level', '不明')}")
            self.stdout.write(f"ポジティブ表現: {sentiment_analysis.get('positive_expressions', 0)}回")
            self.stdout.write(f"ネガティブ表現: {sentiment_analysis.get('negative_expressions', 0)}回")
            self.stdout.write(f"リスク言及: {sentiment_analysis.get('risk_mentions', 0)}回")
            
            if sentiment_analysis.get('analysis_summary'):
                self.stdout.write(f"要約: {sentiment_analysis['analysis_summary']}")
        
        # 追加情報
        self.stdout.write(f"\n分析日: {result.get('analysis_date', '不明')}")
        
        if result.get('processing_time'):
            self.stdout.write(f"分析処理時間: {result['processing_time']:.2f}秒")
    
    def _display_error_result(self, result, processing_time):
        """エラー時の結果表示"""
        self.stdout.write(
            self.style.ERROR(f'\n=== 分析失敗 (処理時間: {processing_time:.1f}秒) ===')
        )
        
        error_message = result.get('error', '不明なエラー')
        self.stdout.write(f"エラー: {error_message}")
        
        # トラブルシューティング情報
        self.stdout.write('\n--- トラブルシューティング ---')
        
        if '見つかりません' in error_message:
            self.stdout.write('• 企業コードが正しいか確認してください')
            self.stdout.write('• 企業マスタに該当企業が登録されているか確認してください')
        elif 'API' in error_message:
            self.stdout.write('• ネットワーク接続を確認してください')
            self.stdout.write('• EDINET APIのサービス状況を確認してください')
        elif '取得' in error_message:
            self.stdout.write('• 決算書類が公開されているか確認してください')
            self.stdout.write('• 書類の形式が対応しているか確認してください')
        else:
            self.stdout.write('• ログファイルで詳細なエラー情報を確認してください')
            self.stdout.write(f'• ログファイル: earnings-analysis.log')


class CompanySearchCommand(BaseCommand):
    """企業検索用のサブコマンド"""
    
    def add_arguments(self, parser):
        parser.add_argument(
            'query',
            type=str,
            help='検索クエリ（企業名または証券コード）',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='検索結果の上限（デフォルト: 10）',
        )
    
    def handle(self, *args, **options):
        query = options['query']
        limit = options['limit']
        
        self.stdout.write(f"企業検索: '{query}'")
        
        try:
            analysis_service = OnDemandAnalysisService()
            result = analysis_service.search_companies(query, limit)
            
            if result['success'] and result['results']:
                self.stdout.write(f"\n検索結果 ({len(result['results'])}件):")
                self.stdout.write("-" * 80)
                
                for i, company in enumerate(result['results'], 1):
                    status = "✓" if company['has_analysis'] else "✗"
                    analysis_date = company.get('latest_analysis_date', '未分析')
                    
                    self.stdout.write(
                        f"{i:2d}. [{company['company_code']}] {company['company_name']} "
                        f"({company['industry']}) {status} {analysis_date}"
                    )
                
                self.stdout.write("-" * 80)
                self.stdout.write("✓: 分析済み, ✗: 未分析")
                
            elif result['success']:
                self.stdout.write("検索結果が見つかりませんでした。")
            else:
                self.stdout.write(f"検索エラー: {result.get('error', '不明')}")
                
        except Exception as e:
            self.stdout.write(f"検索処理エラー: {str(e)}")