# earnings_analysis/management/commands/analyze_company_v2.py（効率化版）
"""
個別企業の決算分析を実行するコマンド（v2効率化版）

インデックス事前構築による大幅な高速化を実現
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import logging
import time

from earnings_analysis.analysis_service import OnDemandAnalysisService
from earnings_analysis.services import EDINETAPIService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '特定企業の決算分析を実行（v2効率化版・インデックス事前構築対応）'
    
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
            help='v2効率化テスト：インデックス構築と検索のパフォーマンステスト',
        )
        parser.add_argument(
            '--show-stats',
            action='store_true',
            help='v2分析効率の統計情報を表示',
        )
        parser.add_argument(
            '--build-index',
            action='store_true',
            help='書類インデックスの事前構築のみ実行',
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=180,
            help='検索対象期間（日数、デフォルト：180日）',
        )
    
    def handle(self, *args, **options):
        company_code = options['company_code']
        force_refresh = options['force']
        verbose = options['verbose']
        dry_run = options['dry_run']
        search_only = options['search_only']
        efficiency_test = options['efficiency_test']
        show_stats = options['show_stats']
        build_index = options['build_index']
        days_back = options['days_back']
        
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        
        self.stdout.write(
            self.style.SUCCESS(f'🚀 v2効率化版 企業分析 {company_code} の処理を開始します...')
        )
        
        if show_stats:
            self._show_efficiency_stats_v2()
            return
        
        if build_index:
            self._build_document_index(days_back)
            return
        
        if efficiency_test:
            self._run_efficiency_test_v2(company_code, days_back)
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('ドライランモード: 実際の処理は行いません')
            )
            self._show_analysis_plan_v2(company_code)
            return
        
        if search_only:
            self._search_company_info_efficiently_v2(company_code, days_back)
            return
        
        start_time = timezone.now()
        
        try:
            # v2効率化された分析サービスの初期化
            analysis_service = OnDemandAnalysisService()
            
            # v2効率的分析実行
            self.stdout.write(f"⚡ v2効率的分析実行中...")
            result = analysis_service.get_or_analyze_company(
                company_code=company_code, 
                force_refresh=force_refresh
            )
            
            # 結果表示
            processing_time = (timezone.now() - start_time).total_seconds()
            
            if result['success']:
                self._display_success_result_v2(result, processing_time)
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
    
    def _build_document_index(self, days_back: int):
        """書類インデックスの事前構築"""
        self.stdout.write(f'\n=== v2書類インデックス事前構築: 過去{days_back}日分 ===')
        
        try:
            edinet_service = EDINETAPIService()
            
            start_time = time.time()
            self.stdout.write(f'📊 インデックス構築を開始します...')
            
            # インデックス構築
            document_index = edinet_service.build_document_index_efficiently(days_back)
            
            build_time = time.time() - start_time
            
            # 結果表示
            total_dates = len(document_index)
            total_documents = sum(len(docs) for docs in document_index.values())
            
            self.stdout.write(f'\n--- 構築結果 ---')
            self.stdout.write(f'⏱ 構築時間: {build_time:.2f}秒')
            self.stdout.write(f'📅 対象日数: {total_dates}日')
            self.stdout.write(f'📄 総書類数: {total_documents}件')
            self.stdout.write(f'📊 平均書類数/日: {total_documents / max(total_dates, 1):.1f}件')
            
            # パフォーマンス統計
            perf_stats = edinet_service.get_search_performance_stats()
            self.stdout.write(f'\n--- パフォーマンス統計 ---')
            self.stdout.write(f'💾 キャッシュ済み日数: {perf_stats.get("cached_dates_count", 0)}日')
            
            # 最新日のサンプル表示
            if document_index:
                latest_date = max(document_index.keys())
                latest_docs = document_index[latest_date]
                self.stdout.write(f'\n--- 最新日サンプル ({latest_date}) ---')
                self.stdout.write(f'📄 書類数: {len(latest_docs)}件')
                
                for i, doc in enumerate(latest_docs[:3], 1):
                    company_name = doc.get('company_name', '不明')[:20]
                    doc_type = doc.get('doc_type_code', '不明')
                    self.stdout.write(f'  {i}. {company_name}... [{doc_type}]')
            
            self.stdout.write(f'\n✅ インデックス構築完了！')
            
        except Exception as e:
            self.stdout.write(f'❌ インデックス構築エラー: {str(e)}')
    
    def _search_company_info_efficiently_v2(self, company_code: str, days_back: int):
        """v2効率的な企業情報・書類検索のみ実行"""
        self.stdout.write(f'\n=== v2効率的企業情報・書類検索: {company_code} ===')
        
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
            
            # 3. v2効率的EDINET API検索
            self.stdout.write(f'\n--- v2効率化されたEDINET API検索 ---')
            edinet_service = EDINETAPIService()
            
            # v2効率的な書類検索（インデックス利用版）
            start_search = time.time()
            documents = edinet_service.get_company_documents_efficiently_v2(company_code, days_back)
            search_time = time.time() - start_search
            
            if documents:
                self.stdout.write(
                    self.style.SUCCESS(f'🎯 v2効率的検索成功: {len(documents)}件の書類を発見 ({search_time:.2f}秒)')
                )
                
                # 書類詳細の表示
                self.stdout.write(f'\n--- 発見書類詳細（v2版） ---')
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
                selected_docs = edinet_service._select_best_documents_for_analysis(documents)
                if selected_docs:
                    selected = selected_docs[0]
                    self.stdout.write(f'🎯 v2分析に最適な書類:')
                    self.stdout.write(f'   書類ID: {selected.get("document_id", "") or selected.get("docID", "")}')
                    self.stdout.write(f'   種別: {selected.get("doc_type_code", "") or selected.get("docTypeCode", "")}')
                    self.stdout.write(f'   説明: {(selected.get("doc_description", "") or selected.get("docDescription", ""))[:80]}...')
                
            else:
                self.stdout.write(
                    self.style.ERROR(f'✗ v2効率的検索でも書類が見つかりませんでした')
                )
                self.stdout.write(f'  証券コードが正しいか確認してください')
                self.stdout.write(f'  または過去{days_back}日以内に決算書類が提出されていない可能性があります')
            
            # 4. v2効率性の評価
            self.stdout.write(f'\n--- v2検索効率性評価 ---')
            self.stdout.write(f'⚡ 検索時間: {search_time:.2f}秒')
            self.stdout.write(f'📊 発見書類数: {len(documents)}件')
            self.stdout.write(f'🔧 検索方式: インデックス事前構築 + 企業フィルタリング')
            if documents:
                self.stdout.write(f'🎯 検索効率: 優秀 (v2インデックス検索により大幅高速化)')
            else:
                self.stdout.write(f'⚠ 検索効率: 書類が見つからないため判定不能')
            
            # 5. パフォーマンス統計表示
            perf_stats = edinet_service.get_search_performance_stats()
            self.stdout.write(f'\n--- v2パフォーマンス統計 ---')
            self.stdout.write(f'💾 キャッシュ済み日数: {perf_stats.get("cached_dates_count", 0)}日')
            
            recent_cache = perf_stats.get('recent_cache_status', [])
            if recent_cache:
                cached_days = sum(1 for day in recent_cache if day['cached'])
                self.stdout.write(f'📈 直近キャッシュ率: {cached_days}/{len(recent_cache)}日 ({cached_days/len(recent_cache)*100:.1f}%)')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'v2効率的検索中にエラー: {str(e)}')
            )
    
    def _run_efficiency_test_v2(self, company_code: str, days_back: int):
        """v2効率化テスト：インデックス構築と検索のパフォーマンステスト"""
        self.stdout.write(f'\n=== v2効率化テスト: {company_code} (過去{days_back}日) ===')
        
        try:
            edinet_service = EDINETAPIService()
            
            # v2効率的検索のテスト
            self.stdout.write(f'⚡ v2効率的検索をテスト中...')
            start_efficient = time.time()
            efficient_docs = edinet_service.get_company_documents_efficiently_v2(company_code, days_back)
            efficient_time = time.time() - start_efficient
            
            # デバッグ情報を取得
            debug_info = edinet_service.debug_company_search(company_code)
            
            # 結果表示
            self.stdout.write(f'\n--- v2効率性テスト結果 ---')
            self.stdout.write(f'⚡ v2効率的検索:')
            self.stdout.write(f'   処理時間: {efficient_time:.2f}秒')
            self.stdout.write(f'   発見書類: {len(efficient_docs)}件')
            self.stdout.write(f'   検索方式: 🚀 インデックス事前構築 + 高速フィルタリング')
            
            if efficient_docs:
                self.stdout.write(f'   最新書類: {efficient_docs[0].get("submission_date", "不明")}')
                self.stdout.write(f'   書類種別: {", ".join(set([d.get("doc_type_code", "不明") for d in efficient_docs[:3]]))}')
            
            # デバッグ情報の表示
            if debug_info.get('success'):
                self.stdout.write(f'\n--- v2デバッグ情報 ---')
                for step in debug_info.get('steps', []):
                    step_name = step.get('step', 'unknown')
                    duration = step.get('duration_seconds', 0)
                    self.stdout.write(f'   {step_name}: {duration:.2f}秒')
                
                total_time = debug_info.get('total_time', 0)
                self.stdout.write(f'   総処理時間: {total_time:.2f}秒')
            
            # 効率性の評価
            self.stdout.write(f'\n--- 総合評価 ---')
            if efficient_time < 5:
                self.stdout.write(f'🎉 優秀: 5秒以内でv2検索完了')
            elif efficient_time < 15:
                self.stdout.write(f'✅ 良好: 15秒以内でv2検索完了') 
            else:
                self.stdout.write(f'⚠ 改善必要: 15秒以上かかっています（v2でも）')
            
            # 推奨アクション
            self.stdout.write(f'\n--- 推奨アクション ---')
            if efficient_docs:
                self.stdout.write(f'✅ この企業はv2効率的分析が可能です')
                self.stdout.write(f'   実行コマンド: python manage.py analyze_company_v2 {company_code}')
            else:
                self.stdout.write(f'⚠ 書類が見つからないためv2でも分析は困難です')
                self.stdout.write(f'   企業コードを確認するか、検索期間を延長してください')
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'v2効率化テスト中にエラー: {str(e)}')
            )
    
    def _show_analysis_plan_v2(self, company_code: str):
        """ドライラン時のv2処理内容表示"""
        self.stdout.write('\n=== v2効率化版分析処理計画 ===')
        self.stdout.write(f'対象企業: {company_code}')
        self.stdout.write('v2効率化された処理手順:')
        self.stdout.write('  1. 🔍 企業情報の効率的取得（マスタ・v2インデックス検索）')
        self.stdout.write('  2. ⚡ 高速キャッシュ確認（インデックス利用）')
        self.stdout.write('  3. 📊 v2インデックス構築（キャッシュ最大活用）')
        self.stdout.write('  4. 🎯 企業書類の高速フィルタリング（インデックスから抽出）')
        self.stdout.write('  5. 📥 最適書類選択・ダウンロード（選択されたファイルのみ）')
        self.stdout.write('  6. 📝 XBRLテキスト抽出（強化版）')
        self.stdout.write('  7. 💰 キャッシュフロー分析（改良版アルゴリズム）')
        self.stdout.write('  8. 😊 感情分析・経営陣自信度分析（強化版）')
        self.stdout.write('  9. 💾 分析結果の保存・効率的キャッシュ')
        self.stdout.write('  10. 📈 企業マスタへの自動登録（新規企業の場合）')
        self.stdout.write('')
        self.stdout.write('⚡ v2効率化のポイント:')
        self.stdout.write('  • インデックス事前構築により検索時間を大幅短縮')
        self.stdout.write('  • キャッシュ戦略でAPI呼び出し回数を最小化')
        self.stdout.write('  • 企業フィルタリングの高速化')
        self.stdout.write('  • 重複排除とデータ正規化の自動化')
        self.stdout.write('  • エラーハンドリング強化で信頼性向上')
        self.stdout.write('')
        self.stdout.write('実際に実行するには --dry-run オプションを外してください。')
        self.stdout.write('v2効率化テストを行う場合は --efficiency-test オプションを使用してください。')
    
    def _show_efficiency_stats_v2(self):
        """v2分析効率の統計情報を表示"""
        self.stdout.write('\n=== v2分析効率統計情報 ===')
        
        try:
            analysis_service = OnDemandAnalysisService()
            stats = analysis_service.get_analysis_efficiency_stats()
            
            self.stdout.write(f'📊 統計情報:')
            self.stdout.write(f'  過去30日の分析数: {stats["recent_analyses_count"]}件')
            self.stdout.write(f'  キャッシュヒット率: {stats["cache_hit_rate"]}%')
            
            self.stdout.write(f'\n⚡ v2効率化の改善点:')
            for improvement in stats['efficiency_improvements']:
                self.stdout.write(f'  • {improvement}')
            
            # v2固有の改善点を追加
            self.stdout.write(f'  • v2インデックス事前構築による検索高速化')
            self.stdout.write(f'  • 企業フィルタリングの最適化')
            self.stdout.write(f'  • 書類選択アルゴリズムの改善')
            
            # システム状況
            self.stdout.write(f'\n🔧 v2システム状況:')
            edinet_service = EDINETAPIService()
            api_status = edinet_service.get_api_status()
            
            if api_status['status'] == 'ok':
                self.stdout.write(f'  ✅ EDINET API: 正常稼働 (v2)')
                self.stdout.write(f'  🔧 検索方式: {api_status.get("search_method", "standard")}')
            else:
                self.stdout.write(f'  ❌ EDINET API: {api_status["message"]}')
            
            # v2パフォーマンス統計
            perf_stats = edinet_service.get_search_performance_stats()
            self.stdout.write(f'\n📈 v2パフォーマンス統計:')
            self.stdout.write(f'  💾 キャッシュ済み日数: {perf_stats.get("cached_dates_count", 0)}日')
            
            # パフォーマンスヒント
            self.stdout.write(f'\n💡 v2パフォーマンスヒント:')
            self.stdout.write(f'  • インデックス事前構築: --build-index で高速化')
            self.stdout.write(f'  • 大量分析時は --efficiency-test で事前テスト推奨')
            self.stdout.write(f'  • キャッシュ活用により同日の再検索は超高速')
            self.stdout.write(f'  • 決算発表直後は新規書類が見つかりやすく高速分析可能')
            
        except Exception as e:
            self.stdout.write(f'v2統計情報取得エラー: {str(e)}')
    
    def _display_success_result_v2(self, result, processing_time):
        """成功時の結果表示（v2版）"""
        self.stdout.write(
            self.style.SUCCESS(f'\n🎉 v2効率的分析完了 (処理時間: {processing_time:.1f}秒) ===')
        )
        
        # 企業情報
        company = result.get('company', {})
        self.stdout.write(f"企業名: {company.get('name', '不明')}")
        self.stdout.write(f"証券コード: {company.get('code', '不明')}")
        
        # v2効率性情報
        if result.get('analysis_efficiency'):
            efficiency = result['analysis_efficiency']
            self.stdout.write(f"\n⚡ v2分析効率情報:")
            self.stdout.write(f"  検索方法: {efficiency.get('search_method', '不明')}")
            self.stdout.write(f"  発見書類数: {efficiency.get('documents_found', 0)}件")
            self.stdout.write(f"  選択書類種別: {efficiency.get('selected_document_type', '不明')}")
            self.stdout.write(f"  選択書類日付: {efficiency.get('selected_document_date', '不明')}")
        
        # データソース情報
        if result.get('from_cache'):
            self.stdout.write(
                self.style.WARNING('⚡ この結果はv2キャッシュから高速取得されました')
            )
        elif result.get('from_existing'):
            self.stdout.write(
                self.style.WARNING('📊 この結果は既存の分析データから取得されました')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('🆕 v2新規分析を実行して最新結果を取得しました')
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
        
        # v2パフォーマンス情報
        self.stdout.write(f"\n⚡ v2パフォーマンス情報:")
        self.stdout.write(f"分析処理時間: {result.get('processing_time', processing_time):.2f}秒")
        self.stdout.write(f"分析方法: {result.get('analysis_method', 'v2_efficient')}")
        self.stdout.write(f"分析日: {result.get('analysis_date', '不明')}")
        
        # 次回分析の案内
        self.stdout.write(f"\n💡 次回以降のv2分析:")
        self.stdout.write(f"  • この企業は次回からv2キャッシュにより超高速分析が可能です")
        self.stdout.write(f"  • 強制再分析: --force オプションで最新データを再取得")
        self.stdout.write(f"  • v2効率テスト: --efficiency-test オプションで性能確認")
        self.stdout.write(f"  • インデックス更新: --build-index オプションで事前構築")
    
    def _display_error_result(self, result, processing_time):
        """エラー時の結果表示"""
        self.stdout.write(
            self.style.ERROR(f'\n❌ v2効率的分析失敗 (処理時間: {processing_time:.1f}秒) ===')
        )
        
        error_message = result.get('error', '不明なエラー')
        self.stdout.write(f"エラー: {error_message}")
        
        # v2トラブルシューティング情報
        self.stdout.write('\n🔧 v2トラブルシューティング')
        
        if '企業情報を取得できません' in error_message or '見つかりません' in error_message:
            self.stdout.write('• 証券コードが正しいか確認してください（4桁の数字）')
            self.stdout.write('• 以下のコマンドでv2効率的検索をテストしてみてください:')
            self.stdout.write(f'  python manage.py analyze_company_v2 {result.get("company_code", "XXXX")} --search-only')
            self.stdout.write('• v2効率化テストで検索能力を確認:')
            self.stdout.write(f'  python manage.py analyze_company_v2 {result.get("company_code", "XXXX")} --efficiency-test')
            self.stdout.write('• 検索期間を延長して再試行:')
            self.stdout.write(f'  python manage.py analyze_company_v2 {result.get("company_code", "XXXX")} --days-back 365')
            self.stdout.write('• インデックス事前構築で高速化:')
            self.stdout.write(f'  python manage.py analyze_company_v2 {result.get("company_code", "XXXX")} --build-index')
        elif 'API' in error_message:
            self.stdout.write('• ネットワーク接続を確認してください')
            self.stdout.write('• EDINET APIのサービス状況を確認してください')
            self.stdout.write('• APIキーが正しく設定されているか確認してください')
            self.stdout.write('• v2API状況チェック: --show-stats オプションで確認')
        elif '取得' in error_message:
            self.stdout.write('• 決算書類が公開されているか確認してください')
            self.stdout.write('• 書類の形式が対応しているか確認してください')
            self.stdout.write('• v2効率的検索で書類一覧を確認: --search-only オプション')
        else:
            self.stdout.write('• ログファイルで詳細なエラー情報を確認してください')
            self.stdout.write(f'• v2システム状況確認: --show-stats オプション')
            self.stdout.write(f'• v2効率化テスト実行: --efficiency-test オプション')
            self.stdout.write(f'• インデックス再構築: --build-index オプション')