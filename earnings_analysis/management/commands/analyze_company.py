# earnings_analysis/management/commands/analyze_company.py（マスタなし企業対応版）
"""
個別企業の決算分析を実行するコマンド

マスタに登録されていない企業でも分析可能
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import logging

from earnings_analysis.analysis_service import OnDemandAnalysisService
from earnings_analysis.services import EDINETAPIService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '特定企業の決算分析を実行（マスタなし企業にも対応）'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'company_code',
            type=str,
            help='分析する企業の証券コード (例: 7203, 9983)',
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
        parser.add_argument(
            '--search-only',
            action='store_true',
            help='企業情報の検索のみ実行（分析は行わない）',
        )
    
    def handle(self, *args, **options):
        company_code = options['company_code']
        force_refresh = options['force']
        verbose = options['verbose']
        dry_run = options['dry_run']
        search_only = options['search_only']
        
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        
        self.stdout.write(
            self.style.SUCCESS(f'企業 {company_code} の処理を開始します...')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('ドライランモード: 実際の処理は行いません')
            )
            self._show_analysis_plan(company_code)
            return
        
        if search_only:
            self._search_company_info_only(company_code)
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
    
    def _search_company_info_only(self, company_code):
        """企業情報の検索のみ実行"""
        self.stdout.write(f'\n=== 企業情報検索: {company_code} ===')
        
        try:
            # 1. 既存のマスタチェック
            from earnings_analysis.models import CompanyEarnings
            existing_company = CompanyEarnings.objects.filter(company_code=company_code).first()
            
            if existing_company:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 分析済み企業として登録済み: {existing_company.company_name}')
                )
                self.stdout.write(f'  EDINET コード: {existing_company.edinet_code}')
                self.stdout.write(f'  決算月: {existing_company.fiscal_year_end_month}月')
                self.stdout.write(f'  最新分析日: {existing_company.latest_analysis_date or "未分析"}')
                return
            
            # 2. company_masterチェック
            try:
                from company_master.models import CompanyMaster
                master_company = CompanyMaster.objects.filter(code=company_code).first()
                
                if master_company:
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ 企業マスタに登録済み: {master_company.name}')
                    )
                    self.stdout.write(f'  業種: {master_company.industry_name_33 or master_company.industry_name_17 or "不明"}')
                    self.stdout.write(f'  市場: {master_company.market or "不明"}')
                else:
                    self.stdout.write(
                        self.style.WARNING(f'⚠ 企業マスタに未登録: {company_code}')
                    )
                    
            except ImportError:
                self.stdout.write(f'  企業マスタは利用できません')
            
            # 3. EDINET API検索
            self.stdout.write(f'\n--- EDINET API検索 ---')
            edinet_service = EDINETAPIService()
            company_info = edinet_service.get_company_info_by_code(company_code)
            
            if company_info:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ EDINET APIで企業情報を発見: {company_info["company_name"]}')
                )
                self.stdout.write(f'  EDINET コード: {company_info["edinet_code"]}')
                self.stdout.write(f'  推定決算月: {company_info["fiscal_year_end_month"]}月')
                self.stdout.write(f'  情報源: {company_info.get("source", "不明")}')
                
                if company_info.get('found_document'):
                    doc = company_info['found_document']
                    self.stdout.write(f'  発見書類: {doc.get("doc_description", "")[:50]}...')
                    self.stdout.write(f'  提出日: {doc.get("submission_date", "")}')
            else:
                self.stdout.write(
                    self.style.ERROR(f'✗ EDINET APIでも企業情報が見つかりませんでした')
                )
                self.stdout.write(f'  証券コードが正しいか確認してください')
                self.stdout.write(f'  または過去180日以内に決算書類が提出されていない可能性があります')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'検索中にエラー: {str(e)}')
            )
    
    def _show_analysis_plan(self, company_code):
        """ドライラン時の処理内容表示"""
        self.stdout.write('\n=== 分析処理計画 ===')
        self.stdout.write(f'対象企業: {company_code}')
        self.stdout.write('処理手順:')
        self.stdout.write('  1. 企業情報の取得・作成（マスタ・EDINET API両方チェック）')
        self.stdout.write('  2. キャッシュされた分析結果の確認')
        self.stdout.write('  3. 最新決算書類の検索（過去120日間）')
        self.stdout.write('  4. EDINET APIからの書類取得')
        self.stdout.write('  5. XBRL文書からのテキスト抽出')
        self.stdout.write('  6. キャッシュフロー分析')
        self.stdout.write('  7. 感情分析・経営陣自信度分析')
        self.stdout.write('  8. 分析結果の保存・キャッシュ')
        self.stdout.write('  9. 企業マスタへの自動登録（新規企業の場合）')
        self.stdout.write('\n実際に実行するには --dry-run オプションを外してください。')
        self.stdout.write('企業情報の検索のみ行う場合は --search-only オプションを使用してください。')
    
    def _display_success_result(self, result, processing_time):
        """成功時の結果表示"""
        self.stdout.write(
            self.style.SUCCESS(f'\n=== 分析完了 (処理時間: {processing_time:.1f}秒) ===')
        )
        
        # 企業情報
        company = result.get('company', {})
        self.stdout.write(f"企業名: {company.get('name', '不明')}")
        self.stdout.write(f"証券コード: {company.get('code', '不明')}")
        
        # 新規企業かどうかの判定
        if '新規作成' in str(result):
            self.stdout.write(
                self.style.WARNING('⚠ この企業は今回新規に登録されました')
            )
        
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
        else:
            self.stdout.write('\n--- キャッシュフロー分析 ---')
            self.stdout.write(
                self.style.WARNING('⚠ キャッシュフローデータを抽出できませんでした')
            )
        
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
        
        # 次回分析の案内
        self.stdout.write(f"\n💡 この企業は次回から高速分析が可能です")
    
    def _display_error_result(self, result, processing_time):
        """エラー時の結果表示"""
        self.stdout.write(
            self.style.ERROR(f'\n=== 分析失敗 (処理時間: {processing_time:.1f}秒) ===')
        )
        
        error_message = result.get('error', '不明なエラー')
        self.stdout.write(f"エラー: {error_message}")
        
        # トラブルシューティング情報
        self.stdout.write('\n--- トラブルシューティング ---')
        
        if '企業情報を取得できません' in error_message or '見つかりません' in error_message:
            self.stdout.write('• 証券コードが正しいか確認してください（4桁の数字）')
            self.stdout.write('• 以下のコマンドで企業情報を検索してみてください:')
            self.stdout.write(f'  python manage.py analyze_company {result.get("company_code", "XXXX")} --search-only')
            self.stdout.write('• 過去180日以内に決算書類が提出されているか確認してください')
        elif 'API' in error_message:
            self.stdout.write('• ネットワーク接続を確認してください')
            self.stdout.write('• EDINET APIのサービス状況を確認してください')
            self.stdout.write('• APIキーが正しく設定されているか確認してください')
        elif '取得' in error_message:
            self.stdout.write('• 決算書類が公開されているか確認してください')
            self.stdout.write('• 書類の形式が対応しているか確認してください')
        else:
            self.stdout.write('• ログファイルで詳細なエラー情報を確認してください')
            self.stdout.write(f'• ログファイル: earnings-analysis.log')


class CompanySearchCommand(BaseCommand):
    """企業検索用のサブコマンド（拡張版）"""
    
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
        parser.add_argument(
            '--include-unregistered',
            action='store_true',
            help='未登録企業も検索結果に含める',
        )
    
    def handle(self, *args, **options):
        query = options['query']
        limit = options['limit']
        include_unregistered = options['include_unregistered']
        
        self.stdout.write(f"企業検索: '{query}'")
        
        try:
            analysis_service = OnDemandAnalysisService()
            result = analysis_service.search_companies(query, limit)
            
            if result['success'] and result['results']:
                self.stdout.write(f"\n検索結果 ({len(result['results'])}件):")
                self.stdout.write("-" * 100)
                
                for i, company in enumerate(result['results'], 1):
                    status = "✓" if company['has_analysis'] else "✗"
                    analysis_date = company.get('latest_analysis_date', '未分析')
                    source = company.get('source', '')
                    
                    status_info = ""
                    if source == 'edinet_api':
                        status_info = " [EDINET検索]"
                    elif source == 'user_input':
                        status_info = " [要確認]"
                    
                    self.stdout.write(
                        f"{i:2d}. [{company['company_code']}] {company['company_name']} "
                        f"({company['industry']}) {status} {analysis_date}{status_info}"
                    )
                    
                    if not company['has_analysis'] and include_unregistered:
                        self.stdout.write(
                            f"    → 分析コマンド: python manage.py analyze_company {company['company_code']}"
                        )
                
                self.stdout.write("-" * 100)
                self.stdout.write("✓: 分析済み, ✗: 未分析")
                
            elif result['success']:
                self.stdout.write("検索結果が見つかりませんでした。")
                
                # 4桁の数字の場合は追加のヒントを表示
                if query.isdigit() and len(query) == 4:
                    self.stdout.write(f"\n💡 証券コード {query} として分析を試行してみてください:")
                    self.stdout.write(f"python manage.py analyze_company {query} --search-only")
                    
            else:
                self.stdout.write(f"検索エラー: {result.get('error', '不明')}")
                
        except Exception as e:
            self.stdout.write(f"検索処理エラー: {str(e)}")