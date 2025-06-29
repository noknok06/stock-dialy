# earnings_analysis/analysis_service.py
"""
オンデマンド決算分析サービス

特定企業の個別分析に特化したサービスクラス
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from decimal import Decimal

from django.core.cache import cache
from django.conf import settings
from django.utils import timezone

from .models import (
    CompanyEarnings, EarningsReport, CashFlowAnalysis, 
    SentimentAnalysis, AnalysisHistory
)
from .services import EDINETAPIService, XBRLTextExtractor, CashFlowExtractor
from .analyzers import SentimentAnalyzer, CashFlowAnalyzer

logger = logging.getLogger(__name__)


class OnDemandAnalysisService:
    """オンデマンド決算分析サービス"""
    
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
        企業の分析結果を取得または新規分析を実行
        
        Args:
            company_code: 証券コード（例: "7203"）
            force_refresh: 強制的に再分析するかどうか
            
        Returns:
            分析結果辞書
        """
        logger.info(f"Starting analysis request for company: {company_code}")
        start_time = time.time()
        
        try:
            # 1. 企業情報の取得
            company = self._get_or_create_company(company_code)
            if not company:
                return {
                    'success': False,
                    'error': f'企業コード {company_code} の企業情報が見つかりません'
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
    
    def search_companies(self, query: str, limit: int = 20) -> Dict:
        """
        企業検索
        
        Args:
            query: 検索クエリ（企業名または証券コード）
            limit: 検索結果の上限
            
        Returns:
            検索結果辞書
        """
        try:
            # キャッシュキーを生成
            cache_key = f"company_search_{query}_{limit}"
            
            if self.enable_cache:
                cached_result = cache.get(cache_key)
                if cached_result:
                    return cached_result
            
            # company_masterから検索
            from company_master.models import CompanyMaster
            
            companies = CompanyMaster.objects.filter(
                models.Q(name__icontains=query) | 
                models.Q(code__icontains=query)
            )[:limit]
            
            results = []
            for company in companies:
                # 対応する決算分析企業があるかチェック
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
            
            result = {
                'success': True,
                'results': results,
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
    
    def _get_or_create_company(self, company_code: str) -> Optional[CompanyEarnings]:
        """企業情報を取得または作成"""
        try:
            # 既存の企業情報を検索
            company = CompanyEarnings.objects.filter(company_code=company_code).first()
            if company:
                return company
            
            # company_masterから情報を取得して作成
            from company_master.models import CompanyMaster
            
            master_company = CompanyMaster.objects.filter(code=company_code).first()
            if not master_company:
                logger.warning(f"Company {company_code} not found in company_master")
                return None
            
            # 新規作成
            company = CompanyEarnings.objects.create(
                edinet_code=f'E{company_code.zfill(5)}',  # 仮のEDINETコード
                company_code=company_code,
                company_name=master_company.name,
                fiscal_year_end_month=3,  # デフォルトは3月決算
                is_active=True
            )
            
            logger.info(f"Created new company entry for {company_code}")
            return company
            
        except Exception as e:
            logger.error(f"Error in _get_or_create_company for {company_code}: {str(e)}")
            return None
    
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

            for field in latest_report._meta.fields:
                name = field.name
                value = getattr(latest_report, name)
                print(f"{name}: {value}")
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
                    'error': '分析対象の決算書類が見つかりませんでした'
                }
            
            # 2. 最新の書類を分析
            latest_document = documents[0]
            
            # 書類の内容を取得
            document_content = self.edinet_service.get_document_content(latest_document['document_id'])
            if not document_content:
                return {
                    'success': False,
                    'error': '決算書類の取得に失敗しました'
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
    
    def _find_latest_documents(self, company: CompanyEarnings) -> list:
        """最新の決算書類を検索"""
        try:
            # 過去30日分の書類を検索
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
            
            all_documents = []
            current_date = start_date
            
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                documents = self.edinet_service.get_document_list(date_str, company.company_code)
                all_documents.extend(documents)
                current_date += timedelta(days=1)
                
                # APIレート制限対策
                time.sleep(self.edinet_service.session.headers.get('rate_limit_delay', 1))
            
            # 日付順でソート（新しい順）
            all_documents.sort(key=lambda x: x.get('submission_date', ''), reverse=True)
            
            return all_documents[:5]  # 最新5件まで
            
        except Exception as e:
            logger.error(f"Error finding latest documents for {company.company_code}: {str(e)}")
            return []
    
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
        doc_desc = document_info.get('doc_description', '').lower()
        if '第1四半期' in doc_desc:
            quarter = 'Q1'
        elif '第2四半期' in doc_desc:
            quarter = 'Q2'
        elif '第3四半期' in doc_desc:
            quarter = 'Q3'
        else:
            quarter = 'Q4'
        
        # 会計年度の抽出（修正版）
        submission_date = document_info.get('submission_date', '')
        date_part = submission_date
        
        if submission_date:
            try:
                # 日付部分のみを抽出（時刻部分を除去）
                date_part = submission_date.split(' ')[0] if ' ' in submission_date else submission_date
                date_part = date_part.split('T')[0] if 'T' in date_part else date_part
                
                fiscal_year = str(datetime.strptime(date_part, '%Y-%m-%d').year)
            except ValueError as e:
                logger.warning(f"Failed to parse submission_date '{submission_date}': {str(e)}")
                fiscal_year = str(datetime.now().year)
        else:
            fiscal_year = str(datetime.now().year)
            date_part = None
        
        return EarningsReport.objects.create(
            company=company,
            report_type=report_type,
            fiscal_year=fiscal_year,
            quarter=quarter,
            document_id=document_info['document_id'],
            submission_date=date_part,  # 修正: 時刻部分を除去した日付のみ
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
        """分析結果をフォーマット"""
        try:
            report = latest_analysis['report']
                        
            analysis_date = latest_analysis.get('analysis_date')
            if isinstance(analysis_date, str):
                try:
                    analysis_date = datetime.fromisoformat(analysis_date)
                except ValueError:
                    analysis_date = datetime.strptime(analysis_date, '%Y-%m-%d') 
                    
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
                    'submission_date': report.submission_date.isoformat() if report.submission_date else None,
                    'report_type': report.get_report_type_display()
                },
                'analysis_date': latest_analysis['analysis_date'].isoformat(),
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
            