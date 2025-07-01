# earnings_analysis/analysis_service.py（v2効率化版）

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
    """オンデマンド決算分析サービス（v2効率化版）"""
    
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
        企業の分析結果を取得または新規分析を実行（v2効率化版）
        
        Args:
            company_code: 証券コード（例: "7203"）
            force_refresh: 強制的に再分析するかどうか
            
        Returns:
            分析結果辞書
        """
        logger.info(f"Starting v2 efficient analysis request for company: {company_code}")
        start_time = time.time()
        
        try:
            # 1. 企業情報の取得・作成（v2効率化版）
            company = self._get_or_create_company_efficient_v2(company_code)
            if not company:
                return {
                    'success': False,
                    'error': f'企業コード {company_code} の企業情報を取得できませんでした（v2検索でも発見不能）'
                }
            
            # 2. キャッシュチェック（強制更新でない場合）
            if not force_refresh and self.enable_cache:
                cached_result = self._get_cached_analysis(company_code)
                if cached_result:
                    logger.info(f"Returning cached analysis for {company_code}")
                    cached_result['from_cache'] = True
                    cached_result['cache_version'] = 'v2'
                    return cached_result
            
            # 3. 既存の分析結果チェック
            latest_analysis = self._get_latest_analysis(company)
            if latest_analysis and not force_refresh:
                # 最新分析が1週間以内なら既存結果を返す
                if latest_analysis['analysis_date'] > timezone.now().date() - timedelta(days=7):
                    result = self._format_analysis_result(company, latest_analysis)
                    result['from_existing'] = True
                    result['analysis_version'] = 'v2'
                    self._cache_analysis_result(company_code, result)
                    return result
            
            # 4. 新規分析の実行（v2効率化版）
            logger.info(f"Performing v2 efficient new analysis for {company_code}")
            analysis_result = self._perform_efficient_analysis_v2(company)
            
            # 5. 結果のキャッシュ
            if self.enable_cache and analysis_result['success']:
                self._cache_analysis_result(company_code, analysis_result)
            
            processing_time = time.time() - start_time
            analysis_result['processing_time'] = round(processing_time, 2)
            analysis_result['analysis_method'] = 'v2_efficient_search'
            analysis_result['analysis_version'] = 'v2'
            
            logger.info(f"Completed v2 efficient analysis for {company_code} in {processing_time:.2f} seconds")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in v2 efficient analysis for {company_code}: {str(e)}")
            return {
                'success': False,
                'error': f'v2分析処理中にエラーが発生しました: {str(e)}',
                'processing_time': time.time() - start_time,
                'analysis_version': 'v2'
            }

    def _get_or_create_company_efficient_v2(self, company_code: str) -> Optional[CompanyEarnings]:
        """企業情報を効率的に取得または作成（v2版）"""
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
                logger.info("company_master not available, will search via v2 EDINET API")
            
            # 3. マスタにない場合は、v2効率的なEDINET API検索
            if not company_info:
                logger.info(f"Company {company_code} not found in master, performing v2 efficient EDINET search...")
                company_info = self.edinet_service.get_company_info_by_code(company_code)
                
                if not company_info:
                    logger.warning(f"Company {company_code} not found via v2 efficient EDINET search either")
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
                
                # v2効率性の情報をログに記録
                if company_info.get('found_documents_count'):
                    logger.info(f"v2 efficient search found {company_info['found_documents_count']} documents")
                
                if company_info.get('search_efficiency'):
                    logger.info(f"v2 search efficiency: {company_info['search_efficiency']}")
                
                if company_info.get('search_method'):
                    logger.info(f"v2 search method: {company_info['search_method']}")
                
                return company
                
        except Exception as e:
            logger.error(f"Error in _get_or_create_company_efficient_v2 for {company_code}: {str(e)}")
            return None

    def _perform_efficient_analysis_v2(self, company: CompanyEarnings) -> Dict:
        """v2効率的な新規分析を実行"""
        try:
            logger.info(f"Starting v2 efficient analysis for {company.company_name}")
            
            # 1. v2効率的な最新書類検索（大幅改善）
            documents = self._find_latest_documents_efficiently_v2(company)
            if not documents:
                return {
                    'success': False,
                    'error': f'{company.company_name}の分析対象の決算書類が見つかりませんでした。v2効率的検索でも書類を発見できませんでした。'
                }
            
            logger.info(f"v2 efficient search found {len(documents)} documents for analysis")
            
            # 2. 最適な書類を選択（v2改良版）
            selected_document = self._select_optimal_document_for_analysis_v2(documents)
            
            logger.info(f"Selected document for v2 analysis: {selected_document.get('document_id')} - {selected_document.get('doc_description', '')[:50]}...")
            
            # 3. 書類の内容を取得
            document_content = self.edinet_service.get_document_content(selected_document['document_id'])
            if not document_content:
                return {
                    'success': False,
                    'error': f'決算書類（{selected_document["document_id"]}）の取得に失敗しました'
                }
            
            # 4. テキスト抽出
            text_sections = self.xbrl_extractor.extract_text_from_zip(document_content)
            if not text_sections:
                return {
                    'success': False,
                    'error': '決算書類からテキストの抽出に失敗しました'
                }
            
            # 5. 報告書レコードの作成（v2改良版）
            report = self._create_earnings_report_efficient_v2(company, selected_document)
            
            # 6. キャッシュフロー分析
            cf_analysis = self._analyze_cashflow(report, text_sections)
            
            # 7. 感情分析
            sentiment_analysis = self._analyze_sentiment(report, text_sections)
            
            # 8. 分析履歴の記録
            self._record_analysis_history(company, cf_analysis, sentiment_analysis)
            
            # 9. 企業情報の更新
            company.latest_analysis_date = timezone.now().date()
            company.latest_fiscal_year = report.fiscal_year
            company.latest_quarter = report.quarter
            company.save()
            
            # 10. 処理完了フラグ
            report.is_processed = True
            report.save()
            
            # 11. 結果のフォーマット
            result = self._format_analysis_result(company, {
                'report': report,
                'analysis_date': timezone.now().date()
            })
            
            # v2効率性の情報を追加
            result['analysis_efficiency'] = {
                'documents_found': len(documents),
                'search_method': 'v2_efficient_index_search',
                'selected_document_type': selected_document.get('doc_type_code'),
                'selected_document_date': selected_document.get('submission_date'),
                'analysis_version': 'v2'
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in _perform_efficient_analysis_v2 for {company.company_code}: {str(e)}")
            return {
                'success': False,
                'error': f'v2効率的分析処理中にエラーが発生しました: {str(e)}'
            }

    def _find_latest_documents_efficiently_v2(self, company: CompanyEarnings) -> list:
        """v2効率的な最新書類検索（インデックス利用版）"""
        try:
            logger.info(f"Starting v2 efficient document search for {company.company_name} ({company.company_code})")
            
            # v2効率的な検索を使用（インデックス利用で一括書類検索）
            documents = self.edinet_service.find_latest_documents_for_analysis(company.company_code)
            
            if not documents:
                logger.warning(f"No documents found with v2 efficient search for {company.company_name}")
                return []
            
            logger.info(f"v2 efficient search found {len(documents)} documents for {company.company_name}")
            
            # 詳細ログ出力
            for i, doc in enumerate(documents[:3]):
                doc_desc = doc.get('doc_description', '') or doc.get('docDescription', '')
                doc_date = doc.get('submission_date', '') or doc.get('submitDateTime', '')
                doc_type = doc.get('doc_type_code', '') or doc.get('docTypeCode', '')
                
                logger.info(f"  {i+1}. [{doc_type}] {doc_desc[:60]}... ({doc_date})")
            
            return documents
            
        except Exception as e:
            logger.error(f"Error in v2 efficient document search for {company.company_code}: {str(e)}")
            return []

    def _select_optimal_document_for_analysis_v2(self, documents: list) -> Dict:
        """
        分析に最適な書類を選択（v2改良版）
        
        優先順位:
        1. 有価証券報告書（最も詳細）
        2. 四半期報告書（詳細度中）  
        3. 決算短信（速報性重視）
        
        v2版では日付も考慮して最適化
        """
        if not documents:
            raise ValueError("No documents provided for selection")
        
        # 書類を種別ごとに分類
        annual_reports = []      # 有価証券報告書
        quarterly_reports = []   # 四半期報告書
        earnings_summaries = []  # 決算短信
        other_docs = []         # その他
        
        for doc in documents:
            doc_type = doc.get('doc_type_code', '') or doc.get('docTypeCode', '')
            doc_desc = (doc.get('doc_description', '') or doc.get('docDescription', '')).lower()
            
            if doc_type == '120':  # 有価証券報告書
                annual_reports.append(doc)
            elif doc_type in ['130', '140']:  # 四半期報告書
                quarterly_reports.append(doc)
            elif doc_type == '350' or '短信' in doc_desc:  # 決算短信
                earnings_summaries.append(doc)
            else:
                other_docs.append(doc)
        
        # 各カテゴリを日付順でソート（v2改良）
        for category in [annual_reports, quarterly_reports, earnings_summaries, other_docs]:
            category.sort(key=lambda x: x.get('submission_date', '') or x.get('submitDateTime', ''), reverse=True)
        
        # 優先順位に従って選択
        if annual_reports:
            selected = annual_reports[0]
            logger.info("v2 selected document type: 有価証券報告書（最も詳細な分析が可能）")
        elif quarterly_reports:
            selected = quarterly_reports[0]
            logger.info("v2 selected document type: 四半期報告書（詳細な分析が可能）")
        elif earnings_summaries:
            selected = earnings_summaries[0]
            logger.info("v2 selected document type: 決算短信（基本的な分析が可能）")
        else:
            selected = documents[0]
            logger.info("v2 selected document type: その他（分析精度が限定的な可能性）")
        
        return selected

    def _create_earnings_report_efficient_v2(self, company: CompanyEarnings, document_info: Dict) -> EarningsReport:
        """v2効率的な決算報告書レコード作成"""
        # 書類種別の判定
        doc_type = document_info.get('doc_type_code', '') or document_info.get('docTypeCode', '')
        if doc_type == '120':
            report_type = 'annual'
        elif doc_type in ['130', '140']:
            report_type = 'quarterly'
        else:
            report_type = 'summary'
        
        # 四半期の判定（v2改良版）
        doc_desc = (document_info.get('doc_description', '') or document_info.get('docDescription', '') or '').lower()
        
        # より詳細な四半期判定
        if '第1四半期' in doc_desc or '第１四半期' in doc_desc:
            quarter = 'Q1'
        elif '第2四半期' in doc_desc or '第２四半期' in doc_desc:
            quarter = 'Q2'
        elif '第3四半期' in doc_desc or '第３四半期' in doc_desc:
            quarter = 'Q3'
        elif '通期' in doc_desc or '年次' in doc_desc or '年度' in doc_desc:
            quarter = 'Q4'
        else:
            # 月から推定（v2新機能）
            import re
            month_pattern = r'(\d{1,2})月'
            month_match = re.search(month_pattern, doc_desc)
            if month_match:
                month = int(month_match.group(1))
                if month in [1, 2, 3]:
                    quarter = 'Q4'  # 年度末
                elif month in [4, 5, 6]:
                    quarter = 'Q1'
                elif month in [7, 8, 9]:
                    quarter = 'Q2'
                elif month in [10, 11, 12]:
                    quarter = 'Q3'
                else:
                    quarter = 'Q4'
            else:
                quarter = 'Q4'  # デフォルト
        
        # 会計年度の抽出（v2改良版）
        submission_date = document_info.get('submission_date', '') or document_info.get('submitDateTime', '')
        
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
        
        document_id = document_info.get('document_id', '') or document_info.get('docID', '')
        
        return EarningsReport.objects.create(
            company=company,
            report_type=report_type,
            fiscal_year=fiscal_year,
            quarter=quarter,
            document_id=document_id,
            submission_date=submission_date_obj,
            is_processed=False
        )

    # 企業検索もv2効率化
    def search_companies(self, query: str, limit: int = 20) -> Dict:
        """企業検索（v2効率化版）"""
        try:
            from django.db.models import Q
            # v2キャッシュキーを生成
            cache_key = f"company_search_v2_efficient_{query}_{limit}"
            
            if self.enable_cache:
                cached_result = cache.get(cache_key)
                if cached_result:
                    cached_result['from_cache'] = True
                    cached_result['search_version'] = 'v2'
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
                    'industry': 'v2分析済み企業',
                    'market': '東証',
                    'has_analysis': latest_report is not None,
                    'latest_analysis_date': latest_report.submission_date.isoformat() if latest_report else None,
                    'source': 'existing_v2_analysis'
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
                        'latest_analysis_date': earnings_company.latest_analysis_date.isoformat() if earnings_company and earnings_company.latest_analysis_date else None,
                        'source': 'company_master'
                    })
                    
            except ImportError:
                # company_masterアプリがない場合はスキップ
                logger.info("company_master not available for v2 search")
            
            # 3. 直接的な証券コード入力の場合（v2効率的検索準備）
            if query.isdigit() and len(query) == 4:
                found_codes = [r['company_code'] for r in results]
                if query not in found_codes:
                    results.append({
                        'company_code': query,
                        'company_name': f'企業コード{query}（v2分析対応）',
                        'industry': '不明',
                        'market': '東証',
                        'has_analysis': False,
                        'latest_analysis_date': None,
                        'source': 'user_input_v2',
                        'analysis_ready': True,  # v2効率的分析が可能
                        'search_version': 'v2'
                    })
            
            result = {
                'success': True,
                'results': results[:limit],
                'total_count': len(results),
                'search_method': 'v2_efficient',
                'search_version': 'v2'
            }
            
            # 検索結果をキャッシュ（短時間）
            if self.enable_cache:
                cache.set(cache_key, result, self.cache_settings.get('SEARCH_RESULTS_TIMEOUT', 300))
            
            return result
            
        except Exception as e:
            logger.error(f"Error in v2 efficient search_companies: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'results': [],
                'search_version': 'v2'
            }

    # 既存のメソッドはそのまま維持（_analyze_cashflow, _analyze_sentiment等）
    def _analyze_cashflow(self, report: EarningsReport, text_sections: Dict) -> Optional[CashFlowAnalysis]:
        """キャッシュフロー分析を実行（既存メソッド）"""
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
        """感情分析を実行（既存メソッド）"""
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
    
    # その他の既存メソッドも維持
    def _get_cached_analysis(self, company_code: str) -> Optional[Dict]:
        """キャッシュされた分析結果を取得"""
        if not self.enable_cache:
            return None
        
        cache_key = f"{self.cache_settings.get('CACHE_KEY_PREFIX', 'earnings_analysis_v2')}_{company_code}"
        return cache.get(cache_key)
    
    def _cache_analysis_result(self, company_code: str, result: Dict) -> None:
        """分析結果をキャッシュ（v2版）"""
        if not self.enable_cache:
            return
        
        cache_key = f"{self.cache_settings.get('CACHE_KEY_PREFIX', 'earnings_analysis_v2')}_{company_code}"
        timeout = self.cache_settings.get('COMPANY_ANALYSIS_TIMEOUT', 86400)  # 24時間
        
        # v2メタデータを追加
        result['cache_version'] = 'v2'
        result['cached_at'] = timezone.now().isoformat()
        
        cache.set(cache_key, result, timeout)
        logger.debug(f"Cached v2 analysis result for {company_code}")
    
    def _get_latest_analysis(self, company: CompanyEarnings) -> Optional[Dict]:
        """最新の分析結果を取得（既存メソッド）"""
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

    def _get_previous_cashflow(self, company: CompanyEarnings) -> Optional[Dict]:
        """前期のキャッシュフローデータを取得（既存メソッド）"""
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
        """前期の感情分析データを取得（既存メソッド）"""
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
        """分析履歴を記録（既存メソッド）"""
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
        """分析結果をフォーマット（既存メソッド - 変更なし）"""
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
                'analysis_date': analysis_date_iso,
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

    # v2効率化メソッド
    def get_analysis_efficiency_stats(self) -> Dict:
        """v2分析効率の統計情報を取得"""
        try:
            # 過去30日の分析実行統計
            thirty_days_ago = timezone.now().date() - timedelta(days=30)
            
            recent_analyses = EarningsReport.objects.filter(
                created_at__gte=thirty_days_ago,
                is_processed=True
            ).count()
            
            # キャッシュヒット率
            cache_hits = cache.get('analysis_cache_hits_v2', 0)
            cache_total = cache.get('analysis_cache_total_v2', 1)
            cache_hit_rate = (cache_hits / cache_total) * 100 if cache_total > 0 else 0
            
            # v2パフォーマンス統計
            edinet_stats = self.edinet_service.get_search_performance_stats()
            
            return {
                'recent_analyses_count': recent_analyses,
                'cache_hit_rate': round(cache_hit_rate, 1),
                'v2_cached_dates': edinet_stats.get('cached_dates_count', 0),
                'efficiency_improvements': [
                    'v2インデックス事前構築による超高速化',
                    'バッチ書類検索による効率化',
                    'インテリジェント書類選択',
                    '効率的キャッシュ戦略v2',
                    'API呼び出し最適化v2'
                ],
                'version': 'v2'
            }
            
        except Exception as e:
            logger.error(f"Error getting v2 efficiency stats: {str(e)}")
            return {
                'recent_analyses_count': 0,
                'cache_hit_rate': 0,
                'efficiency_improvements': [],
                'version': 'v2'
            }

    def get_portfolio_analysis(self) -> Dict:
        """ポートフォリオ分析（既存メソッド）"""
        try:
            # stockdiaryから保有銘柄を取得
            from stockdiary.models import StockDiary
            
            # ユーザーの保有銘柄（売却していないもの）
            held_stocks = StockDiary.objects.filter(
                sell_date__isnull=True,
                stock_symbol__isnull=False
            ).exclude(stock_symbol='').values_list('stock_symbol', flat=True).distinct()
            
            portfolio_analysis = []
            
            for stock_symbol in held_stocks:
                try:
                    # 4桁の場合は証券コードとして扱う
                    if len(stock_symbol) == 4 and stock_symbol.isdigit():
                        # 分析状況のみ取得（実際の分析は実行しない）
                        company = CompanyEarnings.objects.filter(
                            company_code=stock_symbol
                        ).first()
                        
                        if company:
                            # 最新分析データの要約を取得
                            latest_report = EarningsReport.objects.filter(
                                company=company,
                                is_processed=True
                            ).order_by('-submission_date').first()
                            
                            analysis_summary = {
                                'stock_symbol': stock_symbol,
                                'company_name': company.company_name,
                                'has_analysis': latest_report is not None,
                                'latest_analysis_date': company.latest_analysis_date.isoformat() if company.latest_analysis_date else None,
                                'cf_pattern': None,
                                'health_score': None,
                                'sentiment_score': None,
                                'confidence_level': None
                            }
                            
                            if latest_report:
                                if hasattr(latest_report, 'cashflow_analysis'):
                                    cf = latest_report.cashflow_analysis
                                    analysis_summary.update({
                                        'cf_pattern': cf.cf_pattern,
                                        'health_score': cf.health_score
                                    })
                                
                                if hasattr(latest_report, 'sentiment_analysis'):
                                    sentiment = latest_report.sentiment_analysis
                                    analysis_summary.update({
                                        'sentiment_score': float(sentiment.sentiment_score),
                                        'confidence_level': sentiment.confidence_level
                                    })
                            
                            portfolio_analysis.append(analysis_summary)
                    
                except Exception as e:
                    logger.warning(f"Error analyzing stock {stock_symbol}: {str(e)}")
                    continue
            
            return {
                'success': True,
                'data': {
                    'portfolio_analysis': portfolio_analysis,
                    'total_stocks': len(held_stocks),
                    'analyzed_stocks': len(portfolio_analysis)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting portfolio analysis: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }