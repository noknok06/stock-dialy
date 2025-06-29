# earnings_analysis/analysis_service.py（マスタなし企業対応版）

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from decimal import Decimal

from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from .models import (
    CompanyEarnings, EarningsReport, CashFlowAnalysis, 
    SentimentAnalysis, AnalysisHistory
)
from .services import EDINETAPIService, XBRLTextExtractor, CashFlowExtractor
from .analyzers import SentimentAnalyzer, CashFlowAnalyzer

logger = logging.getLogger(__name__)


class OnDemandAnalysisService:
    """オンデマンド決算分析サービス（マスタなし企業対応版）"""
    
    def __init__(self):
        self.edinet_service = EDINETAPIService()
        self.xbrl_extractor = XBRLTextExtractor()
        self.cashflow_extractor = CashFlowExtractor()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.cashflow_analyzer = CashFlowAnalyzer()
        
        # 設定値を取得
        self.analysis_settings = getattr(settings, 'EARNINGS_ANALYSIS_SETTINGS', {})
        self.cache_settings = getattr(settings, 'ANALYSIS_CACHE_SETTINGS', {})
        self.enable_cache = self.cache_settings.get('ENABLE_CACHE', True)
    
    def get_or_analyze_company(self, company_code: str, force_refresh: bool = False) -> Dict:
        """
        企業の分析結果を取得または新規分析を実行（マスタなし企業対応版）
        
        Args:
            company_code: 証券コード（例: "7203"）
            force_refresh: 強制的に再分析するかどうか
            
        Returns:
            分析結果辞書
        """
        logger.info(f"Starting analysis request for company: {company_code}")
        start_time = time.time()
        
        try:
            # 1. 企業情報の取得・作成（改良版）
            company = self._get_or_create_company_enhanced(company_code)
            if not company:
                return {
                    'success': False,
                    'error': f'企業コード {company_code} の企業情報を取得できませんでした'
                }
            
            # 2. キャッシュチェック（強制更新でない場合）
            if not force_refresh and self.enable_cache:
                cached_result = self._get_cached_analysis(company_code)
                if cached_result:
                    logger.info(f"Returning cached analysis for {company_code}")
                    return cached_result
            
            # 3. 既存の分析結果チェック
            latest_analysis = self._get_latest_analysis(company)
            if latest_analysis and not force_refresh:
                # 最新分析が1週間以内なら既存結果を返す
                if latest_analysis['analysis_date'] > timezone.now().date() - timedelta(days=7):
                    result = self._format_analysis_result(company, latest_analysis)
                    self._cache_analysis_result(company_code, result)
                    return result
            
            # 4. 新規分析の実行
            logger.info(f"Performing new analysis for {company_code}")
            analysis_result = self._perform_analysis(company)
            
            # 5. 結果のキャッシュ
            if self.enable_cache and analysis_result['success']:
                self._cache_analysis_result(company_code, analysis_result)
            
            processing_time = time.time() - start_time
            analysis_result['processing_time'] = round(processing_time, 2)
            
            logger.info(f"Completed analysis for {company_code} in {processing_time:.2f} seconds")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in get_or_analyze_company for {company_code}: {str(e)}")
            return {
                'success': False,
                'error': f'分析処理中にエラーが発生しました: {str(e)}',
                'processing_time': time.time() - start_time
            }

    def _get_or_create_company_enhanced(self, company_code: str) -> Optional[CompanyEarnings]:
        """企業情報を取得または作成（マスタなし企業対応版）"""
        try:
            # 1. 既存の企業情報を検索
            company = CompanyEarnings.objects.filter(company_code=company_code).first()
            if company:
                logger.info(f"Found existing company: {company.company_name}")
                return company
            
            # 2. company_masterから情報を取得を試行
            company_info = None
            try:
                from company_master.models import CompanyMaster
                
                master_company = CompanyMaster.objects.filter(code=company_code).first()
                if master_company:
                    logger.info(f"Found company in master: {master_company.name}")
                    company_info = {
                        'company_code': company_code,
                        'company_name': master_company.name,
                        'edinet_code': f'E{company_code.zfill(5)}',
                        'fiscal_year_end_month': 3,  # デフォルト
                        'source': 'company_master'
                    }
                    
            except ImportError:
                logger.info("company_master not available, will search via EDINET API")
            
            # 3. マスタにない場合は、EDINET APIから企業情報を取得
            if not company_info:
                logger.info(f"Company {company_code} not found in master, searching via EDINET API...")
                company_info = self.edinet_service.get_company_info_by_code(company_code)
                
                if not company_info:
                    logger.warning(f"Company {company_code} not found via EDINET API either")
                    return None
            
            # 4. 企業情報でCompanyEarningsレコードを作成
            with transaction.atomic():
                company = CompanyEarnings.objects.create(
                    edinet_code=company_info.get('edinet_code', f'E{company_code.zfill(5)}'),
                    company_code=company_code,
                    company_name=company_info['company_name'],
                    fiscal_year_end_month=company_info.get('fiscal_year_end_month', 3),
                    is_active=True
                )
                
                logger.info(f"Created new company entry: {company.company_name} (source: {company_info.get('source', 'unknown')})")
                
                # 企業情報の出典をログに記録
                if company_info.get('found_document'):
                    doc_info = company_info['found_document']
                    logger.info(f"Company info source document: {doc_info.get('document_id')} - {doc_info.get('doc_description', '')[:50]}...")
                
                return company
                
        except Exception as e:
            logger.error(f"Error in _get_or_create_company_enhanced for {company_code}: {str(e)}")
            return None
    
    def _find_latest_documents(self, company: CompanyEarnings) -> list:
        """最新の決算書類を検索（改良版）"""
        try:
            logger.info(f"Searching documents for {company.company_name} ({company.company_code})")
            
            # 過去120日分の書類を検索（期間を延長）
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=120)
            
            all_documents = []
            current_date = start_date
            
            # 効率的な検索のため、週単位でスキップ
            search_count = 0
            while current_date <= end_date and search_count < 20:  # 最大20回検索
                date_str = current_date.strftime('%Y-%m-%d')
                
                try:
                    # 特定企業の書類を検索
                    documents = self.edinet_service.get_document_list(date_str, company.company_code)
                    
                    if documents:
                        logger.info(f"Found {len(documents)} documents on {date_str}")
                        all_documents.extend(documents)
                        
                        # 十分な書類が見つかったら検索終了
                        if len(all_documents) >= 5:
                            break
                
                except Exception as e:
                    logger.warning(f"Error searching documents for {date_str}: {str(e)}")
                
                # 次の検索日（3日後）
                current_date += timedelta(days=3)
                search_count += 1
                
                # APIレート制限対策
                time.sleep(self.edinet_service.session.headers.get('rate_limit_delay', 0.5))
            
            # 見つからない場合は、より広範囲で検索
            if not all_documents:
                logger.warning(f"No documents found in recent dates, searching wider range...")
                documents = self.edinet_service.search_company_documents(company.company_code, days_back=180)
                all_documents.extend(documents)
            
            # 日付順でソート（新しい順）
            all_documents.sort(key=lambda x: x.get('submission_date', ''), reverse=True)
            
            logger.info(f"Total documents found for {company.company_name}: {len(all_documents)}")
            
            # 詳細ログ出力
            for i, doc in enumerate(all_documents[:3]):
                logger.info(f"  {i+1}. {doc.get('doc_description', '')[:60]}... ({doc.get('submission_date', '')})")
            
            return all_documents[:10]  # 最新10件まで
            
        except Exception as e:
            logger.error(f"Error finding latest documents for {company.company_code}: {str(e)}")
            return []

    def search_companies(self, query: str, limit: int = 20) -> Dict:
        """
        企業検索（マスタなし企業対応版）
        
        Args:
            query: 検索クエリ（企業名または証券コード）
            limit: 検索結果の上限
            
        Returns:
            検索結果辞書
        """
        try:
            from django.db.models import Q
            # キャッシュキーを生成
            cache_key = f"company_search_{query}_{limit}"
            
            if self.enable_cache:
                cached_result = cache.get(cache_key)
                if cached_result:
                    return cached_result
            
            results = []
            
            # 1. 既存の分析済み企業から検索
            existing_companies = CompanyEarnings.objects.filter(
                Q(company_name__icontains=query) | 
                Q(company_code__icontains=query)
            ).filter(is_active=True)[:limit//2]
            
            for company in existing_companies:
                # 最新分析日を取得
                latest_report = EarningsReport.objects.filter(
                    company=company,
                    is_processed=True
                ).order_by('-submission_date').first()
                
                results.append({
                    'company_code': company.company_code,
                    'company_name': company.company_name,
                    'industry': '分析済み企業',
                    'market': '東証',
                    'has_analysis': latest_report is not None,
                    'latest_analysis_date': latest_report.submission_date.isoformat() if latest_report else None
                })
            
            # 2. company_masterからも検索（存在する場合）
            try:
                from company_master.models import CompanyMaster
                
                found_codes = [r['company_code'] for r in results]
                
                master_companies = CompanyMaster.objects.filter(
                    Q(name__icontains=query) | 
                    Q(code__icontains=query)
                ).exclude(code__in=found_codes)[:limit - len(results)]
                
                for company in master_companies:
                    earnings_company = CompanyEarnings.objects.filter(
                        company_code=company.code
                    ).first()
                    
                    results.append({
                        'company_code': company.code,
                        'company_name': company.name,
                        'industry': company.industry_name_33 or company.industry_name_17 or "不明",
                        'market': company.market or "東証",
                        'has_analysis': earnings_company is not None,
                        'latest_analysis_date': earnings_company.latest_analysis_date.isoformat() if earnings_company and earnings_company.latest_analysis_date else None
                    })
                    
            except ImportError:
                # company_masterアプリがない場合はスキップ
                logger.info("company_master not available for search")
            
            # 3. 直接的な証券コード入力の場合は、マスタになくても候補として表示
            if query.isdigit() and len(query) == 4:
                found_codes = [r['company_code'] for r in results]
                if query not in found_codes:
                    # EDINET APIで企業情報を取得を試行
                    try:
                        company_info = self.edinet_service.get_company_info_by_code(query, days_back=30)
                        if company_info:
                            results.append({
                                'company_code': query,
                                'company_name': company_info['company_name'],
                                'industry': company_info.get('industry', '不明'),
                                'market': '東証',
                                'has_analysis': False,
                                'latest_analysis_date': None,
                                'source': 'edinet_api'
                            })
                        else:
                            # 見つからない場合でも候補として表示
                            results.append({
                                'company_code': query,
                                'company_name': f'企業コード{query}（未確認）',
                                'industry': '不明',
                                'market': '不明',
                                'has_analysis': False,
                                'latest_analysis_date': None,
                                'source': 'user_input'
                            })
                    except Exception as e:
                        logger.warning(f"Error getting company info for {query}: {str(e)}")
                        # エラーでも候補として表示
                        results.append({
                            'company_code': query,
                            'company_name': f'企業コード{query}（要確認）',
                            'industry': '不明',
                            'market': '不明',
                            'has_analysis': False,
                            'latest_analysis_date': None,
                            'source': 'user_input'
                        })
            
            result = {
                'success': True,
                'results': results[:limit],
                'total_count': len(results)
            }
            
            # 検索結果をキャッシュ（短時間）
            if self.enable_cache:
                cache.set(cache_key, result, self.cache_settings.get('SEARCH_RESULTS_TIMEOUT', 300))
            
            return result
            
        except Exception as e:
            logger.error(f"Error in search_companies: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }

    # 既存のメソッドはそのまま維持
    def _get_cached_analysis(self, company_code: str) -> Optional[Dict]:
        """キャッシュされた分析結果を取得"""
        if not self.enable_cache:
            return None
        
        cache_key = f"{self.cache_settings.get('CACHE_KEY_PREFIX', 'earnings_analysis')}_{company_code}"
        return cache.get(cache_key)
    
    def _cache_analysis_result(self, company_code: str, result: Dict) -> None:
        """分析結果をキャッシュ"""
        if not self.enable_cache:
            return
        
        cache_key = f"{self.cache_settings.get('CACHE_KEY_PREFIX', 'earnings_analysis')}_{company_code}"
        timeout = self.cache_settings.get('COMPANY_ANALYSIS_TIMEOUT', 86400)  # 24時間
        
        cache.set(cache_key, result, timeout)
        logger.debug(f"Cached analysis result for {company_code}")
    
    def _get_latest_analysis(self, company: CompanyEarnings) -> Optional[Dict]:
        """最新の分析結果を取得"""
        try:
            latest_report = EarningsReport.objects.filter(
                company=company,
                is_processed=True
            ).order_by('-submission_date').first()

            if not latest_report:
                return None
            
            return {
                'report': latest_report,
                'analysis_date': latest_report.created_at.date() if latest_report.created_at else timezone.now().date()
            }
            
        except Exception as e:
            logger.error(f"Error getting latest analysis for {company.company_code}: {str(e)}")
            return None

    def _perform_analysis(self, company: CompanyEarnings) -> Dict:
        """新規分析を実行"""
        try:
            # 1. 最新の決算書類を検索
            documents = self._find_latest_documents(company)
            if not documents:
                return {
                    'success': False,
                    'error': f'{company.company_name}の分析対象の決算書類が見つかりませんでした。過去120日以内に決算書類が提出されていない可能性があります。'
                }
            
            # 2. 最新の書類を分析
            latest_document = documents[0]
            
            # 書類の内容を取得
            document_content = self.edinet_service.get_document_content(latest_document['document_id'])
            if not document_content:
                return {
                    'success': False,
                    'error': f'決算書類（{latest_document["document_id"]}）の取得に失敗しました'
                }
            
            # 3. テキスト抽出
            text_sections = self.xbrl_extractor.extract_text_from_zip(document_content)
            if not text_sections:
                return {
                    'success': False,
                    'error': '決算書類からテキストの抽出に失敗しました'
                }
            
            # 4. 報告書レコードの作成
            report = self._create_earnings_report(company, latest_document)
            
            # 5. キャッシュフロー分析
            cf_analysis = self._analyze_cashflow(report, text_sections)
            
            # 6. 感情分析
            sentiment_analysis = self._analyze_sentiment(report, text_sections)
            
            # 7. 分析履歴の記録
            self._record_analysis_history(company, cf_analysis, sentiment_analysis)
            
            # 8. 企業情報の更新
            company.latest_analysis_date = timezone.now().date()
            company.latest_fiscal_year = report.fiscal_year
            company.latest_quarter = report.quarter
            company.save()
            
            # 9. 処理完了フラグ
            report.is_processed = True
            report.save()
            
            # 10. 結果のフォーマット
            return self._format_analysis_result(company, {
                'report': report,
                'analysis_date': timezone.now().date()
            })
            
        except Exception as e:
            logger.error(f"Error in _perform_analysis for {company.company_code}: {str(e)}")
            return {
                'success': False,
                'error': f'分析処理中にエラーが発生しました: {str(e)}'
            }

    # その他の既存メソッドはそのまま（省略）
    def _create_earnings_report(self, company: CompanyEarnings, document_info: Dict) -> EarningsReport:
        """決算報告書レコードを作成"""
        # 書類種別の判定
        doc_type = document_info.get('doc_type_code', '')
        if doc_type == '120':
            report_type = 'annual'
        elif doc_type in ['130', '140']:
            report_type = 'quarterly'
        else:
            report_type = 'summary'
        
        # 四半期の判定
        doc_desc = document_info.get('doc_description', '') or ''
        if '第1四半期' in doc_desc:
            quarter = 'Q1'
        elif '第2四半期' in doc_desc:
            quarter = 'Q2'
        elif '第3四半期' in doc_desc:
            quarter = 'Q3'
        else:
            quarter = 'Q4'
        
        # 会計年度の抽出
        submission_date = document_info.get('submission_date', '')
        
        if submission_date:
            try:
                if isinstance(submission_date, str):
                    date_part = submission_date.split(' ')[0] if ' ' in submission_date else submission_date
                    date_part = date_part.split('T')[0] if 'T' in date_part else date_part
                    fiscal_year = str(datetime.strptime(date_part, '%Y-%m-%d').year)
                    submission_date_obj = datetime.strptime(date_part, '%Y-%m-%d').date()
                else:
                    fiscal_year = str(submission_date.year)
                    submission_date_obj = submission_date
            except ValueError as e:
                logger.warning(f"Failed to parse submission_date '{submission_date}': {str(e)}")
                fiscal_year = str(datetime.now().year)
                submission_date_obj = datetime.now().date()
        else:
            fiscal_year = str(datetime.now().year)
            submission_date_obj = datetime.now().date()
        
        return EarningsReport.objects.create(
            company=company,
            report_type=report_type,
            fiscal_year=fiscal_year,
            quarter=quarter,
            document_id=document_info['document_id'],
            submission_date=submission_date_obj,
            is_processed=False
        )


    def _analyze_cashflow(self, report: EarningsReport, text_sections: Dict) -> Optional[CashFlowAnalysis]:
        """キャッシュフロー分析を実行"""
        try:
            # テキストからCFデータを抽出
            cf_data = self.cashflow_extractor.extract_cashflow_data(
                ' '.join(text_sections.values())
            )
            
            if not any(cf_data.values()):
                logger.warning(f"No cashflow data found for report {report.id}")
                return None
            
            # CF分析を実行
            cf_analysis = self.cashflow_analyzer.analyze_cashflow_pattern(
                cf_data.get('operating_cf', 0),
                cf_data.get('investing_cf', 0),
                cf_data.get('financing_cf', 0)
            )
            
            # 前期比較
            previous_cf = self._get_previous_cashflow(report.company)
            if previous_cf:
                changes = self.cashflow_analyzer.compare_with_previous(cf_data, previous_cf)
                cf_analysis.update(changes)
            
            # データベースに保存
            return CashFlowAnalysis.objects.create(
                report=report,
                operating_cf=Decimal(str(cf_data.get('operating_cf', 0))),
                investing_cf=Decimal(str(cf_data.get('investing_cf', 0))),
                financing_cf=Decimal(str(cf_data.get('financing_cf', 0))),
                free_cf=Decimal(str(cf_data.get('free_cf', 0))),
                cf_pattern=cf_analysis['cf_pattern'],
                health_score=cf_analysis['health_score'],
                operating_cf_change_rate=Decimal(str(cf_analysis.get('operating_cf_change_rate', 0))),
                free_cf_change_rate=Decimal(str(cf_analysis.get('free_cf_change_rate', 0))),
                analysis_summary=cf_analysis['analysis_summary'],
                risk_factors=cf_analysis['risk_factors']
            )
            
        except Exception as e:
            logger.error(f"Error in cashflow analysis for report {report.id}: {str(e)}")
            return None
    
    def _analyze_sentiment(self, report: EarningsReport, text_sections: Dict) -> Optional[SentimentAnalysis]:
        """感情分析を実行"""
        try:
            # 感情分析を実行
            sentiment_result = self.sentiment_analyzer.analyze_sentiment(text_sections)
            
            # 前期比較
            previous_sentiment = self._get_previous_sentiment(report.company)
            if previous_sentiment:
                sentiment_change = sentiment_result['sentiment_score'] - float(previous_sentiment.sentiment_score)
                sentiment_result['sentiment_change'] = sentiment_change
            
            # データベースに保存
            sentiment_analysis = SentimentAnalysis.objects.create(
                report=report,
                positive_expressions=sentiment_result['positive_expressions'],
                negative_expressions=sentiment_result['negative_expressions'],
                confidence_keywords=sentiment_result['confidence_keywords'],
                uncertainty_keywords=sentiment_result['uncertainty_keywords'],
                risk_mentions=sentiment_result['risk_mentions'],
                sentiment_score=Decimal(str(sentiment_result['sentiment_score'])),
                confidence_level=sentiment_result['confidence_level'],
                sentiment_change=Decimal(str(sentiment_result.get('sentiment_change', 0))),
                analysis_summary=sentiment_result['analysis_summary']
            )
            
            # 抽出キーワードの保存
            sentiment_analysis.set_extracted_keywords_dict(sentiment_result['extracted_keywords'])
            sentiment_analysis.save()
            
            return sentiment_analysis
            
        except Exception as e:
            logger.error(f"Error in sentiment analysis for report {report.id}: {str(e)}")
            return None
    
    def _get_previous_cashflow(self, company: CompanyEarnings) -> Optional[Dict]:
        """前期のキャッシュフローデータを取得"""
        try:
            previous_report = EarningsReport.objects.filter(
                company=company,
                is_processed=True
            ).order_by('-submission_date')[1:2].first()  # 2番目に新しいレポート
            
            if previous_report and hasattr(previous_report, 'cashflow_analysis'):
                cf = previous_report.cashflow_analysis
                return {
                    'operating_cf': float(cf.operating_cf or 0),
                    'investing_cf': float(cf.investing_cf or 0),
                    'financing_cf': float(cf.financing_cf or 0),
                    'free_cf': float(cf.free_cf or 0)
                }
            return None
            
        except Exception:
            return None
    
    def _get_previous_sentiment(self, company: CompanyEarnings) -> Optional[SentimentAnalysis]:
        """前期の感情分析データを取得"""
        try:
            previous_report = EarningsReport.objects.filter(
                company=company,
                is_processed=True
            ).order_by('-submission_date')[1:2].first()
            
            if previous_report and hasattr(previous_report, 'sentiment_analysis'):
                return previous_report.sentiment_analysis
            return None
            
        except Exception:
            return None
    
    def _record_analysis_history(self, company: CompanyEarnings, cf_analysis: CashFlowAnalysis, 
                                sentiment_analysis: SentimentAnalysis) -> None:
        """分析履歴を記録"""
        try:
            import json
            
            cf_summary = {}
            if cf_analysis:
                cf_summary = {
                    'cf_pattern': cf_analysis.cf_pattern,
                    'health_score': cf_analysis.health_score,
                    'operating_cf': float(cf_analysis.operating_cf or 0),
                    'free_cf': float(cf_analysis.free_cf or 0)
                }
            
            sentiment_summary = {}
            if sentiment_analysis:
                sentiment_summary = {
                    'sentiment_score': float(sentiment_analysis.sentiment_score),
                    'confidence_level': sentiment_analysis.confidence_level,
                    'risk_mentions': sentiment_analysis.risk_mentions
                }
            
            AnalysisHistory.objects.create(
                company=company,
                fiscal_year=str(datetime.now().year),
                quarter='Q4',  # 簡略化
                cashflow_summary=json.dumps(cf_summary, ensure_ascii=False),
                sentiment_summary=json.dumps(sentiment_summary, ensure_ascii=False),
                processing_time_seconds=0  # 簡略化
            )
            
        except Exception as e:
            logger.warning(f"Failed to record analysis history for {company.company_code}: {str(e)}")
    
    def _format_analysis_result(self, company: CompanyEarnings, latest_analysis: Dict) -> Dict:
        try:
            report = latest_analysis['report']
            
            # 日付処理の修正
            analysis_date = latest_analysis.get('analysis_date')
            if isinstance(analysis_date, str):
                try:
                    # 既に文字列の場合はそのまま使用
                    analysis_date_iso = analysis_date
                except ValueError:
                    analysis_date_iso = timezone.now().date().isoformat()
            elif hasattr(analysis_date, 'isoformat'):
                # datetime オブジェクトの場合
                analysis_date_iso = analysis_date.isoformat()
            else:
                # その他の場合は現在日付を使用
                analysis_date_iso = timezone.now().date().isoformat()
            
            result = {
                'success': True,
                'company': {
                    'code': company.company_code,
                    'name': company.company_name,
                    'edinet_code': company.edinet_code,
                    'fiscal_year_end_month': company.fiscal_year_end_month
                },
                'report': {
                    'fiscal_year': report.fiscal_year,
                    'quarter': report.quarter,
                    'submission_date': report.submission_date.isoformat() if hasattr(report.submission_date, 'isoformat') else str(report.submission_date),
                    'report_type': report.get_report_type_display()
                },
                'analysis_date': analysis_date_iso,  # ← ここを修正
                'cashflow_analysis': None,
                'sentiment_analysis': None
            }

            
            # キャッシュフロー分析データ
            if hasattr(report, 'cashflow_analysis'):
                cf = report.cashflow_analysis
                result['cashflow_analysis'] = {
                    'operating_cf': float(cf.operating_cf) if cf.operating_cf else None,
                    'investing_cf': float(cf.investing_cf) if cf.investing_cf else None,
                    'financing_cf': float(cf.financing_cf) if cf.financing_cf else None,
                    'free_cf': float(cf.free_cf) if cf.free_cf else None,
                    'cf_pattern': cf.cf_pattern,
                    'cf_pattern_description': cf.get_cf_pattern_description(),
                    'health_score': cf.health_score,
                    'operating_cf_change_rate': float(cf.operating_cf_change_rate) if cf.operating_cf_change_rate else None,
                    'free_cf_change_rate': float(cf.free_cf_change_rate) if cf.free_cf_change_rate else None,
                    'analysis_summary': cf.analysis_summary,
                    'risk_factors': cf.risk_factors
                }
            
            # 感情分析データ
            if hasattr(report, 'sentiment_analysis'):
                sentiment = report.sentiment_analysis
                result['sentiment_analysis'] = {
                    'sentiment_score': float(sentiment.sentiment_score),
                    'confidence_level': sentiment.confidence_level,
                    'positive_expressions': sentiment.positive_expressions,
                    'negative_expressions': sentiment.negative_expressions,
                    'confidence_keywords': sentiment.confidence_keywords,
                    'uncertainty_keywords': sentiment.uncertainty_keywords,
                    'risk_mentions': sentiment.risk_mentions,
                    'sentiment_change': float(sentiment.sentiment_change) if sentiment.sentiment_change else None,
                    'analysis_summary': sentiment.analysis_summary
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error formatting analysis result for {company.company_code}: {str(e)}")
            return {
                'success': False,
                'error': f'分析結果のフォーマットに失敗しました: {str(e)}'
            }
            