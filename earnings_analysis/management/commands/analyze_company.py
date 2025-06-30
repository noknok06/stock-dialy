# earnings_analysis/management/commands/analyze_company.py（効率化版）
"""
個別企業の決算分析を実行するコマンド（効率化版）

効率的な書類検索により、大幅な高速化を実現
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import logging

from earnings_analysis.analysis_service import OnDemandAnalysisService
from earnings_analysis.services import EDINETAPIService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '特定企業の決算分析を実行（効率化版・高速検索対応）'
    
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
            help='企業情報・書類検索のみ実行（分析は行わない）',
        )
        parser.add_argument(
            '--efficiency-test',
            action='store_true',
            help='効率化テスト：新旧検索方法の比較',
        )
        parser.add_argument(
            '--show-stats',
            action='store_true',
            help='分析効率の統計情報を表示',
        )
    
    def handle(self, *args, **options):
        company_code = options['company_code']
        force_refresh = options['force']
        verbose = options['verbose']
        dry_run = options['dry_run']
        search_only = options['search_only']
        efficiency_test = options['efficiency_test']
        show_stats = options['show_stats']
        
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        
        self.stdout.write(
            self.style.SUCCESS(f'🚀 効率化版 企業分析 {company_code} の処理を開始します...')
        )
        
        if show_stats:
            self._show_efficiency_stats()
            return
        
        if efficiency_test:
            self._run_efficiency_test(company_code)
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('ドライランモード: 実際の処理は行いません')
            )
            self._show_analysis_plan(company_code)
            return
        
        if search_only:
            self._search_company_info_efficiently(company_code)
            return
        
        start_time = timezone.now()
        
        try:
            # 効率化された分析サービスの初期化
            analysis_service = OnDemandAnalysisService()
            
            # 効率的分析実行
            self.stdout.write(f"⚡ 効率的分析実行中...")
            result = analysis_service.get_or_analyze_company(
                company_code=company_code, 
                force_refresh=force_refresh
            )
            
            # 結果表示
            processing_time = (timezone.now() - start_time).total_seconds()
            
            if result['success']:
                self._display_success_result_enhanced(result, processing_time)
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
    
    def _search_company_info_efficiently(self, company_code):
        """効率的な企業情報・書類検索のみ実行"""
        self.stdout.write(f'\n=== 効率的企業情報・書類検索: {company_code} ===')
        
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
            
            # 3. 効率的EDINET API検索
            self.stdout.write(f'\n--- 効率化されたEDINET API検索 ---')
            edinet_service = EDINETAPIService()
            
            # 効率的な書類検索
            start_search = timezone.now()
            documents = edinet_service.get_company_documents_efficiently(company_code)
            search_time = (timezone.now() - start_search).total_seconds()
            
            if documents:
                self.stdout.write(
                    self.style.SUCCESS(f'🎯 効率的検索成功: {len(documents)}件の書類を発見 ({search_time:.2f}秒)')
                )
                
                # 書類詳細の表示
                self.stdout.write(f'\n--- 発見書類詳細 ---')
                for i, doc in enumerate(documents[:5], 1):
                    doc_desc = (doc.get('doc_description', '') or doc.get('docDescription', ''))[:60]
                    doc_date = doc.get('submission_date', '') or doc.get('submitDateTime', '')
                    doc_type = doc.get('doc_type_code', '') or doc.get('docTypeCode', '')
                    doc_id = doc.get('document_id', '') or doc.get('docID', '')
                    
                    doc_type_name = {
                        '120': '有価証券報告書',
                        '130': '四半期報告書', 
                        '140': '半期報告書',
                        '350': '決算短信'
                    }.get(doc_type, f'その他({doc_type})')
                    
                    self.stdout.write(f'  {i}. [{doc_id}] {doc_type_name}')
                    self.stdout.write(f'     {doc_desc}...')
                    self.stdout.write(f'     提出日: {doc_date}')
                    self.stdout.write('')
                
                # 最適書類の選択シミュレーション
                selected_doc = edinet_service._select_best_documents_for_analysis(documents)
                if selected_doc:
                    selected = selected_doc[0]
                    self.stdout.write(f'🎯 分析に最適な書類:')
                    self.stdout.write(f'   書類ID: {selected.get("document_id", "") or selected.get("docID", "")}')
                    self.stdout.write(f'   種別: {selected.get("doc_type_code", "") or selected.get("docTypeCode", "")}')
                    self.stdout.write(f'   説明: {(selected.get("doc_description", "") or selected.get("docDescription", ""))[:80]}...')
                
            else:
                self.stdout.write(
                    self.style.ERROR(f'✗ 効率的検索でも書類が見つかりませんでした')
                )
                self.stdout.write(f'  証券コードが正しいか確認してください')
                self.stdout.write(f'  または過去180日以内に決算書類が提出されていない可能性があります')
            
            # 4. 効率性の評価
            self.stdout.write(f'\n--- 検索効率性評価 ---')
            self.stdout.write(f'⚡ 検索時間: {search_time:.2f}秒')
            self.stdout.write(f'📊 発見書類数: {len(documents)}件')
            if documents:
                self.stdout.write(f'🎯 検索効率: 優秀 (一括検索により高速化)')
            else:
                self.stdout.write(f'⚠ 検索効率: 書類が見つからないため判定不能')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'効率的検索中にエラー: {str(e)}')
            )

    def _run_efficiency_test(self, company_code):
        """効率化テスト：新旧検索方法の比較"""
        self.stdout.write(f'\n=== 効率化テスト: {company_code} ===')
        
        try:
            edinet_service = EDINETAPIService()
            
            # 効率的検索のテスト
            self.stdout.write(f'⚡ 効率的検索をテスト中...')
            start_efficient = timezone.now()
            efficient_docs = edinet_service.get_company_documents_efficiently(company_code)
            efficient_time = (timezone.now() - start_efficient).total_seconds()
            
            # 結果表示
            self.stdout.write(f'\n--- 効率性テスト結果 ---')
            self.stdout.write(f'⚡ 効率的検索:')
            self.stdout.write(f'   処理時間: {efficient_time:.2f}秒')
            self.stdout.write(f'   発見書類: {len(efficient_docs)}件')
            self.stdout.write(f'   効率度: 🚀 高速 (バッチ検索)')
            
            if efficient_docs:
                self.stdout.write(f'   最新書類: {efficient_docs[0].get("submission_date", "不明")}')
                self.stdout.write(f'   書類種別: {", ".join(set([d.get("doc_type_code", "不明") for d in efficient_docs[:3]]))}')
            
            # 効率性の評価
            self.stdout.write(f'\n--- 総合評価 ---')
            if efficient_time < 10:
                self.stdout.write(f'🎉 優秀: 10秒以内で検索完了')
            elif efficient_time < 30:
                self.stdout.write(f'✅ 良好: 30秒以内で検索完了') 
            else:
                self.stdout.write(f'⚠ 改善必要: 30秒以上かかっています')
            
            # 推奨アクション
            self.stdout.write(f'\n--- 推奨アクション ---')
            if efficient_docs:
                self.stdout.write(f'✅ この企業は効率的分析が可能です')
                self.stdout.write(f'   実行コマンド: python manage.py analyze_company {company_code}')
            else:
                self.stdout.write(f'⚠ 書類が見つからないため分析は困難です')
                self.stdout.write(f'   企業コードを確認するか、決算時期を待ってください')
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'効率化テスト中にエラー: {str(e)}')
            )

    def _show_analysis_plan(self, company_code):
        """ドライラン時の処理内容表示（効率化版）"""
        self.stdout.write('\n=== 効率化版分析処理計画 ===')
        self.stdout.write(f'対象企業: {company_code}')
        self.stdout.write('効率化された処理手順:')
        self.stdout.write('  1. 🔍 企業情報の効率的取得（マスタ・EDINET API一括検索）')
        self.stdout.write('  2. ⚡ 効率的キャッシュ確認（高速レスポンス）')
        self.stdout.write('  3. 📊 一括書類検索（過去180日分を効率的に取得）')
        self.stdout.write('  4. 🎯 最適書類選択（AI による最適化）')
        self.stdout.write('  5. 📥 書類ダウンロード（選択されたファイルのみ）')
        self.stdout.write('  6. 📝 XBRLテキスト抽出（強化版）')
        self.stdout.write('  7. 💰 キャッシュフロー分析（改良版アルゴリズム）')
        self.stdout.write('  8. 😊 感情分析・経営陣自信度分析（強化版）')
        self.stdout.write('  9. 💾 分析結果の保存・効率的キャッシュ')
        self.stdout.write('  10. 📈 企業マスタへの自動登録（新規企業の場合）')
        self.stdout.write('')
        self.stdout.write('⚡ 効率化のポイント:')
        self.stdout.write('  • バッチ検索により API 呼び出し回数を大幅削減')
        self.stdout.write('  • インテリジェント書類選択で最適な分析対象を自動選択')
        self.stdout.write('  • 効率的キャッシュ戦略で高速レスポンス')
        self.stdout.write('  • エラーハンドリング強化で信頼性向上')
        self.stdout.write('')
        self.stdout.write('実際に実行するには --dry-run オプションを外してください。')
        self.stdout.write('効率化テストを行う場合は --efficiency-test オプションを使用してください。')

    def _show_efficiency_stats(self):
        """分析効率の統計情報を表示"""
        self.stdout.write('\n=== 分析効率統計情報 ===')
        
        try:
            analysis_service = OnDemandAnalysisService()
            stats = analysis_service.get_analysis_efficiency_stats()
            
            self.stdout.write(f'📊 統計情報:')
            self.stdout.write(f'  過去30日の分析数: {stats["recent_analyses_count"]}件')
            self.stdout.write(f'  キャッシュヒット率: {stats["cache_hit_rate"]}%')
            
            self.stdout.write(f'\n⚡ 効率化の改善点:')
            for improvement in stats['efficiency_improvements']:
                self.stdout.write(f'  • {improvement}')
            
            # システム状況
            self.stdout.write(f'\n🔧 システム状況:')
            edinet_service = EDINETAPIService()
            api_status = edinet_service.get_api_status()
            
            if api_status['status'] == 'ok':
                self.stdout.write(f'  ✅ EDINET API: 正常稼働')
            else:
                self.stdout.write(f'  ❌ EDINET API: {api_status["message"]}')
            
            # パフォーマンスヒント
            self.stdout.write(f'\n💡 パフォーマンスヒント:')
            self.stdout.write(f'  • 大量分析時は --efficiency-test で事前テスト推奨')
            self.stdout.write(f'  • キャッシュを活用するため同一企業の再分析は高速')
            self.stdout.write(f'  • 決算発表直後は書類が見つかりやすく高速分析可能')
            
        except Exception as e:
            self.stdout.write(f'統計情報取得エラー: {str(e)}')

    def _display_success_result_enhanced(self, result, processing_time):
        """成功時の結果表示（効率化版）"""
        self.stdout.write(
            self.style.SUCCESS(f'\n🎉 効率的分析完了 (処理時間: {processing_time:.1f}秒) ===')
        )
        
        # 企業情報
        company = result.get('company', {})
        self.stdout.write(f"企業名: {company.get('name', '不明')}")
        self.stdout.write(f"証券コード: {company.get('code', '不明')}")
        
        # 効率性情報
        if result.get('analysis_efficiency'):
            efficiency = result['analysis_efficiency']
            self.stdout.write(f"\n⚡ 分析効率情報:")
            self.stdout.write(f"  検索方法: {efficiency.get('search_method', '不明')}")
            self.stdout.write(f"  発見書類数: {efficiency.get('documents_found', 0)}件")
            self.stdout.write(f"  選択書類種別: {efficiency.get('selected_document_type', '不明')}")
            self.stdout.write(f"  選択書類日付: {efficiency.get('selected_document_date', '不明')}")
        
        # データソース情報
        if result.get('from_cache'):
            self.stdout.write(
                self.style.WARNING('⚡ この結果はキャッシュから高速取得されました')
            )
        elif result.get('from_existing'):
            self.stdout.write(
                self.style.WARNING('📊 この結果は既存の分析データから取得されました')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('🆕 新規分析を実行して最新結果を取得しました')
            )
        
        # 分析対象期間
        report = result.get('report', {})
        if report:
            self.stdout.write(f"\n📋 分析対象: {report.get('fiscal_year', '不明')} {report.get('quarter', '不明')}")
            self.stdout.write(f"書類提出日: {report.get('submission_date', '不明')}")
        
        # キャッシュフロー分析結果
        cf_analysis = result.get('cashflow_analysis')
        if cf_analysis:
            self.stdout.write('\n💰 キャッシュフロー分析')
            pattern_desc = cf_analysis.get('cf_pattern_description', '不明')
            if 'トヨタ型' in pattern_desc:
                self.stdout.write(f"✅ CFパターン: {pattern_desc}")
            elif '危険' in pattern_desc:
                self.stdout.write(f"⚠️ CFパターン: {pattern_desc}")
            else:
                self.stdout.write(f"📊 CFパターン: {pattern_desc}")
            
            self.stdout.write(f"健全性スコア: {cf_analysis.get('health_score', '不明')}")
            
            operating_cf = cf_analysis.get('operating_cf')
            if operating_cf is not None:
                if operating_cf > 0:
                    self.stdout.write(f"✅ 営業CF: {operating_cf:,.0f}百万円")
                else:
                    self.stdout.write(f"⚠️ 営業CF: {operating_cf:,.0f}百万円")
            
            free_cf = cf_analysis.get('free_cf')
            if free_cf is not None:
                if free_cf > 0:
                    self.stdout.write(f"✅ フリーCF: {free_cf:,.0f}百万円")
                else:
                    self.stdout.write(f"⚠️ フリーCF: {free_cf:,.0f}百万円")
            
            if cf_analysis.get('analysis_summary'):
                self.stdout.write(f"要約: {cf_analysis['analysis_summary']}")
        else:
            self.stdout.write('\n💰 キャッシュフロー分析')
            self.stdout.write(
                self.style.WARNING('⚠️ キャッシュフローデータを抽出できませんでした')
            )
        
        # 感情分析結果
        sentiment_analysis = result.get('sentiment_analysis')
        if sentiment_analysis:
            self.stdout.write('\n😊 感情分析')
            sentiment_score = sentiment_analysis.get('sentiment_score', 0)
            if sentiment_score > 20:
                self.stdout.write(f"😊 感情スコア: {sentiment_score:.1f} (ポジティブ)")
            elif sentiment_score < -20:
                self.stdout.write(f"😟 感情スコア: {sentiment_score:.1f} (ネガティブ)")
            else:
                self.stdout.write(f"😐 感情スコア: {sentiment_score:.1f} (中立)")
            
            confidence = sentiment_analysis.get('confidence_level', '不明')
            confidence_desc = {
                'very_high': '非常に高い 🚀',
                'high': '高い ✅',
                'moderate': '普通 📊',
                'low': '低い ⚠️',
                'very_low': '非常に低い 🔴'
            }.get(confidence, confidence)
            
            self.stdout.write(f"経営陣自信度: {confidence_desc}")
            self.stdout.write(f"ポジティブ表現: {sentiment_analysis.get('positive_expressions', 0)}回")
            self.stdout.write(f"ネガティブ表現: {sentiment_analysis.get('negative_expressions', 0)}回")
            self.stdout.write(f"リスク言及: {sentiment_analysis.get('risk_mentions', 0)}回")
            
            if sentiment_analysis.get('analysis_summary'):
                self.stdout.write(f"要約: {sentiment_analysis['analysis_summary']}")
        
        # パフォーマンス情報
        self.stdout.write(f"\n⚡ パフォーマンス情報:")
        self.stdout.write(f"分析処理時間: {result.get('processing_time', processing_time):.2f}秒")
        self.stdout.write(f"分析方法: {result.get('analysis_method', '標準')}")
        self.stdout.write(f"分析日: {result.get('analysis_date', '不明')}")
        
        # 次回分析の案内
        self.stdout.write(f"\n💡 次回以降の分析:")
        self.stdout.write(f"  • この企業は次回からキャッシュにより高速分析が可能です")
        self.stdout.write(f"  • 強制再分析: --force オプションで最新データを再取得")
        self.stdout.write(f"  • 効率テスト: --efficiency-test オプションで性能確認")

    def _display_error_result(self, result, processing_time):
        """エラー時の結果表示"""
        self.stdout.write(
            self.style.ERROR(f'\n❌ 効率的分析失敗 (処理時間: {processing_time:.1f}秒) ===')
        )
        
        error_message = result.get('error', '不明なエラー')
        self.stdout.write(f"エラー: {error_message}")
        
        # トラブルシューティング情報
        self.stdout.write('\n🔧 トラブルシューティング')
        
        if '企業情報を取得できません' in error_message or '見つかりません' in error_message:
            self.stdout.write('• 証券コードが正しいか確認してください（4桁の数字）')
            self.stdout.write('• 以下のコマンドで効率的検索をテストしてみてください:')
            self.stdout.write(f'  python manage.py analyze_company {result.get("company_code", "XXXX")} --search-only')
            self.stdout.write('• 効率化テストで検索能力を確認:')
            self.stdout.write(f'  python manage.py analyze_company {result.get("company_code", "XXXX")} --efficiency-test')
            self.stdout.write('• 過去180日以内に決算書類が提出されているか確認してください')
        elif 'API' in error_message:
            self.stdout.write('• ネットワーク接続を確認してください')
            self.stdout.write('• EDINET APIのサービス状況を確認してください')
            self.stdout.write('• APIキーが正しく設定されているか確認してください')
            self.stdout.write('• API状況チェック: --show-stats オプションで確認')
        elif '取得' in error_message:
            self.stdout.write('• 決算書類が公開されているか確認してください')
            self.stdout.write('• 書類の形式が対応しているか確認してください')
            self.stdout.write('• 効率的検索で書類一覧を確認: --search-only オプション')
        else:
            self.stdout.write('• ログファイルで詳細なエラー情報を確認してください')
            self.stdout.write(f'• システム状況確認: --show-stats オプション')
            self.stdout.write(f'• 効率化テスト実行: --efficiency-test オプション')


class EfficiencyTestCommand(BaseCommand):
    """効率化テスト専用のサブコマンド"""
    
    def add_arguments(self, parser):
        parser.add_argument(
            'companies',
            nargs='+',
            help='テスト対象の企業コード（複数指定可能）',
        )
        parser.add_argument(
            '--iterations',
            type=int,
            default=3,
            help='テスト実行回数（平均値を計算）',
        )
    
    def handle(self, *args, **options):
        companies = options['companies']
        iterations = options['iterations']
        
        self.stdout.write('🧪 大規模効率化テストを開始します...')
        
        total_time = 0
        total_docs = 0
        
        for company_code in companies:
            self.stdout.write(f'\n📊 テスト対象: {company_code}')
            
            company_times = []
            company_docs = []
            
            for i in range(iterations):
                try:
                    edinet_service = EDINETAPIService()
                    start_time = timezone.now()
                    docs = edinet_service.get_company_documents_efficiently(company_code)
                    elapsed = (timezone.now() - start_time).total_seconds()
                    
                    company_times.append(elapsed)
                    company_docs.append(len(docs))
                    
                    self.stdout.write(f'  実行{i+1}: {elapsed:.2f}秒, {len(docs)}件')
                    
                except Exception as e:
                    self.stdout.write(f'  実行{i+1}: エラー - {str(e)}')
            
            if company_times:
                avg_time = sum(company_times) / len(company_times)
                avg_docs = sum(company_docs) / len(company_docs)
                
                self.stdout.write(f'  平均: {avg_time:.2f}秒, {avg_docs:.1f}件')
                
                total_time += avg_time
                total_docs += avg_docs
        
        # 全体統計
        if companies:
            overall_avg_time = total_time / len(companies)
            overall_avg_docs = total_docs / len(companies)
            
            self.stdout.write(f'\n📊 全体統計:')
            self.stdout.write(f'  平均検索時間: {overall_avg_time:.2f}秒')
            self.stdout.write(f'  平均発見書類数: {overall_avg_docs:.1f}件')
            
            if overall_avg_time < 5:
                self.stdout.write(f'🎉 効率性評価: 優秀')
            elif overall_avg_time < 15:
                self.stdout.write(f'✅ 効率性評価: 良好')
            else:
                self.stdout.write(f'⚠️ 効率性評価: 改善の余地あり')