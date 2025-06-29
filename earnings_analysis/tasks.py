# earnings_analysis/tasks.py
from datetime import datetime, timedelta
import time
import logging
from typing import List, Dict, Optional
from decimal import Decimal

from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings

from .models import (
    CompanyEarnings, EarningsReport, CashFlowAnalysis, 
    SentimentAnalysis, EarningsAlert, AnalysisHistory
)
from .services import EDINETAPIService, XBRLTextExtractor, CashFlowExtractor
from .analyzers import SentimentAnalyzer, CashFlowAnalyzer

logger = logging.getLogger(__name__)


class EarningsAnalysisTask:
    """決算分析の定期処理タスク"""
    
    def __init__(self):
        self.edinet_service = EDINETAPIService()
        self.xbrl_extractor = XBRLTextExtractor()
        self.cashflow_extractor = CashFlowExtractor()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.cashflow_analyzer = CashFlowAnalyzer()
    
    def daily_document_check(self, check_date: Optional[str] = None) -> Dict:
        """
        日次の新着決算書類チェックと分析処理
        
        Args:
            check_date: チェック対象日（YYYY-MM-DD）。未指定時は昨日
            
        Returns:
            処理結果辞書
        """
        if not check_date:
            check_date = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        logger.info(f"Starting daily document check for {check_date}")
        
        results = {
            'check_date': check_date,
            'new_documents': 0,
            'analyzed_companies': 0,
            'errors': [],
            'processing_time': 0
        }
        
        start_time = time.time()
        
        try:
            # 1. 新着書類の取得
            new_documents = self._fetch_new_documents(check_date)
            results['new_documents'] = len(new_documents)
            
            if not new_documents:
                logger.info(f"No new documents found for {check_date}")
                return results
            
            # 2. 対象企業の確認と書類登録
            registered_docs = self._register_documents(new_documents)
            
            # 3. 分析処理の実行
            analyzed_count = 0
            for doc in registered_docs:
                try:
                    success = self._analyze_document(doc)
                    if success:
                        analyzed_count += 1
                    
                    # レート制限対策で少し待機
                    time.sleep(1)
                    
                except Exception as e:
                    error_msg = f"Error analyzing document {doc.document_id}: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
                    
                    # エラーを記録して続行
                    doc.processing_error = str(e)
                    doc.save()
            
            results['analyzed_companies'] = analyzed_count
            
            # 4. 通知処理
            self._send_analysis_notifications(registered_docs)
            
        except Exception as e:
            error_msg = f"Error in daily document check: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
        
        finally:
            results['processing_time'] = round(time.time() - start_time, 2)
            logger.info(f"Daily document check completed in {results['processing_time']} seconds")
        
        return results
    
    def analyze_specific_company(self, edinet_code: str, document_id: str = None) -> Dict:
        """
        特定企業の分析を実行
        
        Args:
            edinet_code: EDINETコード
            document_id: 特定の書類ID（未指定時は最新書類を分析）
            
        Returns:
            分析結果
        """
        try:
            company = CompanyEarnings.objects.get(edinet_code=edinet_code)
        except CompanyEarnings.DoesNotExist:
            return {'error': f'Company not found: {edinet_code}'}
        
        if document_id:
            try:
                report = EarningsReport.objects.get(
                    company=company,
                    document_id=document_id
                )
            except EarningsReport.DoesNotExist:
                return {'error': f'Report not found: {document_id}'}
        else:
            # 最新の未処理書類を取得
            report = EarningsReport.objects.filter(
                company=company,
                is_processed=False
            ).order_by('-submission_date').first()
            
            if not report:
                return {'error': 'No unprocessed reports found'}
        
        # 分析実行
        success = self._analyze_document(report)
        
        if success:
            return {
                'success': True,
                'company': company.company_name,
                'document_id': report.document_id,
                'fiscal_year': report.fiscal_year,
                'quarter': report.quarter
            }
        else:
            return {'error': 'Analysis failed'}
    
    def _fetch_new_documents(self, date: str) -> List[Dict]:
        """指定日の新着書類を取得"""
        try:
            # 分析対象企業の取得
            target_companies = CompanyEarnings.objects.filter(is_active=True)
            
            all_new_docs = []
            for company in target_companies:
                # 企業別に書類を検索
                company_docs = self.edinet_service.get_document_list(
                    date, company.company_code
                )
                
                # 既存書類との重複チェック
                for doc in company_docs:
                    if not EarningsReport.objects.filter(
                        document_id=doc['document_id']
                    ).exists():
                        doc['company'] = company
                        all_new_docs.append(doc)
                
                # レート制限対策
                time.sleep(0.5)
            
            return all_new_docs
            
        except Exception as e:
            logger.error(f"Error fetching new documents: {str(e)}")
            return []
    
    def _register_documents(self, documents: List[Dict]) -> List[EarningsReport]:
        """新着書類をデータベースに登録"""
        registered_docs = []
        
        for doc_info in documents:
            try:
                with transaction.atomic():
                    # 書類種別と四半期の判定
                    report_type, quarter = self._determine_report_details(doc_info)
                    
                    if not report_type or not quarter:
                        continue
                    
                    # 書類レコードの作成
                    report = EarningsReport.objects.create(
                        company=doc_info['company'],
                        report_type=report_type,
                        fiscal_year=self._extract_fiscal_year(doc_info),
                        quarter=quarter,
                        document_id=doc_info['document_id'],
                        submission_date=doc_info['submission_date'],
                        is_processed=False
                    )
                    
                    registered_docs.append(report)
                    logger.info(f"Registered document: {report}")
                    
            except Exception as e:
                logger.error(f"Error registering document {doc_info.get('document_id')}: {str(e)}")
                continue
        
        return registered_docs
    
    def _analyze_document(self, report: EarningsReport) -> bool:
        """個別書類の分析処理"""
        try:
            start_time = time.time()
            
            # 1. 書類内容の取得
            document_content = self.edinet_service.get_document_content(report.document_id)
            if not document_content:
                raise Exception("Failed to fetch document content")
            
            # 2. テキスト抽出
            text_sections = self.xbrl_extractor.extract_text_from_zip(document_content)
            if not text_sections:
                raise Exception("Failed to extract text from document")
            
            # 3. キャッシュフロー分析
            cf_analysis_result = None
            cf_data = self.cashflow_extractor.extract_cashflow_data(
                ' '.join(text_sections.values())
            )
            
            if any(cf_data.values()):
                cf_analysis = self.cashflow_analyzer.analyze_cashflow_pattern(
                    cf_data.get('operating_cf', 0),
                    cf_data.get('investing_cf', 0),
                    cf_data.get('financing_cf', 0)
                )
                
                # 前期比較
                previous_report = EarningsReport.objects.filter(
                    company=report.company,
                    is_processed=True,
                    submission_date__lt=report.submission_date
                ).order_by('-submission_date').first()
                
                if previous_report and hasattr(previous_report, 'cashflow_analysis'):
                    prev_cf = {
                        'operating_cf': float(previous_report.cashflow_analysis.operating_cf or 0),
                        'investing_cf': float(previous_report.cashflow_analysis.investing_cf or 0),
                        'financing_cf': float(previous_report.cashflow_analysis.financing_cf or 0),
                        'free_cf': float(previous_report.cashflow_analysis.free_cf or 0)
                    }
                    
                    changes = self.cashflow_analyzer.compare_with_previous(cf_data, prev_cf)
                    cf_analysis.update(changes)
                
                # CFデータの保存
                cf_analysis_result = CashFlowAnalysis.objects.create(
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
            
            # 4. 感情分析
            sentiment_result = self.sentiment_analyzer.analyze_sentiment(text_sections)
            
            # 前期比較
            previous_sentiment = None
            if previous_report and hasattr(previous_report, 'sentiment_analysis'):
                prev_sentiment = previous_report.sentiment_analysis
                sentiment_change = sentiment_result['sentiment_score'] - float(prev_sentiment.sentiment_score)
                sentiment_result['sentiment_change'] = sentiment_change
            
            # 感情分析結果の保存
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
            
            # 5. 分析履歴の記録
            processing_time = int(time.time() - start_time)
            
            AnalysisHistory.objects.create(
                company=report.company,
                fiscal_year=report.fiscal_year,
                quarter=report.quarter,
                cashflow_summary=self._serialize_cf_summary(cf_analysis_result),
                sentiment_summary=self._serialize_sentiment_summary(sentiment_analysis),
                processing_time_seconds=processing_time
            )
            
            # 6. 企業情報の更新
            report.company.latest_analysis_date = timezone.now().date()
            report.company.latest_fiscal_year = report.fiscal_year
            report.company.latest_quarter = report.quarter
            report.company.save()
            
            # 7. 処理完了フラグの更新
            report.is_processed = True
            report.save()
            
            logger.info(f"Successfully analyzed document: {report}")
            return True
            
        except Exception as e:
            logger.error(f"Error analyzing document {report.document_id}: {str(e)}")
            report.processing_error = str(e)
            report.save()
            return False
    
    def _determine_report_details(self, doc_info: Dict) -> tuple:
        """書類種別と四半期を判定"""
        doc_type = doc_info.get('doc_type_code', '')
        doc_desc = doc_info.get('doc_description', '').lower()
        
        # 書類種別の判定
        if doc_type == '120':
            report_type = 'annual'
        elif doc_type in ['130', '140']:
            report_type = 'quarterly'
        elif doc_type == '350':
            report_type = 'summary'
        else:
            return None, None
        
        # 四半期の判定
        if '第1四半期' in doc_desc or 'q1' in doc_desc:
            quarter = 'Q1'
        elif '第2四半期' in doc_desc or 'q2' in doc_desc:
            quarter = 'Q2'
        elif '第3四半期' in doc_desc or 'q3' in doc_desc:
            quarter = 'Q3'
        elif '通期' in doc_desc or '年次' in doc_desc or 'q4' in doc_desc:
            quarter = 'Q4'
        else:
            quarter = 'Q4'  # デフォルト
        
        return report_type, quarter
    
    def _extract_fiscal_year(self, doc_info: Dict) -> str:
        """会計年度を抽出"""
        period_end = doc_info.get('period_end', '')
        if period_end:
            try:
                year = datetime.strptime(period_end, '%Y-%m-%d').year
                return str(year)
            except ValueError:
                pass
        
        # フォールバック: 提出年度を使用
        submission_date = doc_info.get('submission_date', '')
        if submission_date:
            try:
                year = datetime.strptime(submission_date, '%Y-%m-%d').year
                return str(year)
            except ValueError:
                pass
        
        return str(datetime.now().year)
    
    def _serialize_cf_summary(self, cf_analysis: CashFlowAnalysis) -> str:
        """キャッシュフロー分析結果をJSON形式でシリアライズ"""
        if not cf_analysis:
            return '{}'
        
        import json
        summary = {
            'cf_pattern': cf_analysis.cf_pattern,
            'health_score': cf_analysis.health_score,
            'operating_cf': float(cf_analysis.operating_cf) if cf_analysis.operating_cf else 0,
            'free_cf': float(cf_analysis.free_cf) if cf_analysis.free_cf else 0
        }
        return json.dumps(summary, ensure_ascii=False)
    
    def _serialize_sentiment_summary(self, sentiment_analysis: SentimentAnalysis) -> str:
        """感情分析結果をJSON形式でシリアライズ"""
        import json
        summary = {
            'sentiment_score': float(sentiment_analysis.sentiment_score),
            'confidence_level': sentiment_analysis.confidence_level,
            'positive_expressions': sentiment_analysis.positive_expressions,
            'negative_expressions': sentiment_analysis.negative_expressions,
            'risk_mentions': sentiment_analysis.risk_mentions
        }
        return json.dumps(summary, ensure_ascii=False)
    
    def _send_analysis_notifications(self, reports: List[EarningsReport]) -> None:
        """分析完了通知の送信"""
        # 日記アプリとの連携用に、後で実装
        pass


class EarningsNotificationTask:
    """決算通知タスク"""
    
    def send_upcoming_earnings_alerts(self) -> Dict:
        """決算予定アラートを送信"""
        from .services import EarningsNotificationService
        
        notification_service = EarningsNotificationService()
        upcoming_earnings = notification_service.check_upcoming_earnings(days_ahead=7)
        
        sent_count = 0
        errors = []
        
        for earnings_info in upcoming_earnings:
            try:
                user = earnings_info['user']
                company = earnings_info['company']
                days_until = earnings_info['days_until']
                
                # メール通知
                if hasattr(user, 'email') and user.email:
                    subject = f"【カブログ】{company.company_name}の決算発表予定通知"
                    message = f"""
{user.username} 様

{company.company_name}（{company.company_code}）の決算発表が{days_until}日後に予定されています。

決算情報の分析結果は、発表後に自動的に更新されます。

カブログ 決算分析システム
                    """.strip()
                    
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=False
                    )
                    
                    sent_count += 1
                    
            except Exception as e:
                error_msg = f"Error sending alert to {earnings_info['user'].username}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        return {
            'sent_notifications': sent_count,
            'errors': errors
        }