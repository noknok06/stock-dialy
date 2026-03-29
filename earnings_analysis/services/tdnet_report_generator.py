# earnings_analysis/services/tdnet_report_generator.py

from typing import Dict, Any, Optional
from django.utils import timezone
from django.db import transaction
from .gemini_service import GeminiReportGenerator
from .pdf_processor import PDFProcessor
from ..models import TDNETDisclosure, TDNETReport, TDNETReportSection
import logging
import uuid

logger = logging.getLogger('earnings_analysis.tdnet')


class TDNETReportGeneratorService:
    """TDNETレポート統合生成サービス"""
    
    def __init__(self):
        self.gemini_generator = GeminiReportGenerator()
        self.pdf_processor = PDFProcessor()
    
    def generate_report_from_pdf_url(self,
                                     pdf_url: str,
                                     company_code: str,
                                     company_name: str,
                                     disclosure_type: str,
                                     title: str,
                                     user,
                                     max_pdf_pages: int = 50) -> Dict[str, Any]:
        """PDF URLから直接レポート生成"""
        try:
            logger.info(f"PDF処理開始: {pdf_url}")
            pdf_result = self.pdf_processor.process_pdf_url(pdf_url, max_pdf_pages)
            
            if not pdf_result['success']:
                return {
                    'success': False,
                    'disclosure': None,
                    'report': None,
                    'message': '',
                    'error': f"PDF処理失敗: {pdf_result['error']}"
                }
            
            extracted_text = pdf_result['text']
            pdf_path = pdf_result['pdf_path']

            # PDFテキストから次期業績予想を抽出して EarningsForecast に保存（Gemini不使用）
            self._extract_and_save_forecast_from_pdf(
                extracted_text, company_code, company_name, timezone.now()
            )

            disclosure_id = f"MANUAL-{company_code}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            
            disclosure = TDNETDisclosure.objects.create(
                disclosure_id=disclosure_id,
                company_code=company_code,
                company_name=company_name,
                disclosure_date=timezone.now(),
                disclosure_type=disclosure_type,
                title=title,
                summary=extracted_text[:500],
                raw_data={
                    'pdf_url': pdf_url,
                    'extracted_text': extracted_text[:2000],
                    'total_pages': pdf_result['pages'],
                    'processed_pages': pdf_result['processed_pages']
                },
                pdf_url=pdf_url,
                pdf_cached=False,   # テキスト抽出後にPDFは破棄済み
                pdf_file_path='',   # ファイルは保存しない
                is_processed=False,
                report_generated=False,
            )
            
            try:
                from company_master.models import CompanyMaster
                company_master = CompanyMaster.objects.get(code=company_code)
                disclosure.company_master = company_master
                disclosure.save()
            except Exception as e:
                logger.warning(f"企業マスタ連携スキップ: {e}")
            
            disclosure_dict = {
                'company_name': company_name,
                'company_code': company_code,
                'disclosure_date': timezone.now().isoformat(),
                'title': title,
                'summary': extracted_text[:1000],
                'content': extracted_text[:20000],
            }
            
            generation_result = self.gemini_generator.generate_report(
                disclosure_dict,
                disclosure_type
            )
            
            if not generation_result['success']:
                return {
                    'success': False,
                    'disclosure': disclosure,
                    'report': None,
                    'message': '',
                    'error': f"レポート生成失敗: {generation_result['error']}"
                }
            
            report = self._save_report(
                disclosure=disclosure,
                report_type=disclosure_type,
                generation_result=generation_result,
                user=user
            )
            
            disclosure.report_generated = True
            disclosure.is_processed = True
            disclosure.save(update_fields=['report_generated', 'is_processed', 'updated_at'])
            
            return {
                'success': True,
                'disclosure': disclosure,
                'report': report,
                'message': 'レポートを生成しました',
                'error': None
            }
            
        except Exception as e:
            logger.error(f"レポート生成エラー: {e}")
            return {
                'success': False,
                'disclosure': None,
                'report': None,
                'message': '',
                'error': str(e)
            }
    
    def generate_report_from_disclosure(self,
                                       disclosure_id: str,
                                       report_type: str,
                                       user) -> Dict[str, Any]:
        """既存の開示情報からレポート生成"""
        try:
            disclosure = TDNETDisclosure.objects.filter(
                disclosure_id=disclosure_id
            ).first()
            
            if not disclosure:
                return {
                    'success': False,
                    'disclosure': None,
                    'report': None,
                    'message': '',
                    'error': '開示情報が見つかりません'
                }
            
            existing_report = TDNETReport.objects.filter(
                disclosure=disclosure,
                report_type=report_type
            ).first()
            
            if existing_report:
                return {
                    'success': True,
                    'disclosure': disclosure,
                    'report': existing_report,
                    'message': '既存のレポートを返却しました',
                    'error': None
                }
            
            if disclosure.pdf_file_path and not disclosure.raw_data.get('extracted_text'):
                pdf_result = self.pdf_processor.extract_text_from_pdf(disclosure.pdf_file_path)
                if pdf_result['success']:
                    extracted_text = pdf_result['text']
                    disclosure.raw_data['extracted_text'] = extracted_text[:2000]
                    disclosure.save()
                else:
                    extracted_text = disclosure.summary
            else:
                extracted_text = disclosure.raw_data.get('extracted_text', disclosure.summary)
            
            disclosure_dict = {
                'company_name': disclosure.company_name,
                'company_code': disclosure.company_code,
                'disclosure_date': disclosure.disclosure_date.isoformat(),
                'title': disclosure.title,
                'summary': disclosure.summary,
                'content': extracted_text[:20000] if extracted_text else disclosure.summary,
            }
            
            generation_result = self.gemini_generator.generate_report(
                disclosure_dict,
                report_type
            )
            
            if not generation_result['success']:
                return {
                    'success': False,
                    'disclosure': disclosure,
                    'report': None,
                    'message': '',
                    'error': f"レポート生成失敗: {generation_result['error']}"
                }
            
            report = self._save_report(
                disclosure=disclosure,
                report_type=report_type,
                generation_result=generation_result,
                user=user
            )
            
            disclosure.report_generated = True
            disclosure.is_processed = True
            disclosure.save(update_fields=['report_generated', 'is_processed', 'updated_at'])
            
            return {
                'success': True,
                'disclosure': disclosure,
                'report': report,
                'message': 'レポートを生成しました',
                'error': None
            }
            
        except Exception as e:
            logger.error(f"レポート生成エラー: {e}")
            return {
                'success': False,
                'disclosure': None,
                'report': None,
                'message': '',
                'error': str(e)
            }
    
    @transaction.atomic
    def _save_report(self,
                    disclosure: TDNETDisclosure,
                    report_type: str,
                    generation_result: Dict,
                    user) -> TDNETReport:
        """レポートをDB保存"""
        report_id = f"TDNET-{disclosure.company_code}-{disclosure.disclosure_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
        report_data = generation_result['data']
        
        report = TDNETReport.objects.create(
            report_id=report_id,
            disclosure=disclosure,
            title=f"{disclosure.company_name} - {disclosure.title}",
            report_type=report_type,
            overall_score=report_data.get('overall_score', 50),
            signal=report_data.get('signal', 'neutral'),
            one_line_summary=report_data.get('one_line_summary', '')[:100],
            summary=report_data.get('summary', ''),
            key_points=report_data.get('key_points', []),
            score_details=report_data.get('score_details', {}),
            analysis='',
            status='draft',
            generated_by=user,
            generation_model=self.gemini_generator.model_name,
            generation_prompt=generation_result.get('prompt', ''),
            generation_token_count=generation_result.get('token_count', 0),
        )
        
        sections_data = report_data.get('sections', [])
        for i, section_data in enumerate(sections_data):
            TDNETReportSection.objects.create(
                report=report,
                section_type=section_data.get('section_type', 'other'),
                title=section_data.get('title', f'セクション{i+1}'),
                content=section_data.get('content', ''),
                order=i,
                data=section_data.get('data', {})
            )
        
        logger.info(f"レポート保存完了: {report_id}, score={report.overall_score}, signal={report.signal}")
        return report
    
    def regenerate_report(self, report_id: str, user) -> Dict[str, Any]:
        """レポート再生成"""
        try:
            report = TDNETReport.objects.filter(report_id=report_id).first()
            if not report:
                return {'success': False, 'report': None, 'message': '', 'error': 'レポートが見つかりません'}
            
            report.sections.all().delete()
            
            extracted_text = report.disclosure.raw_data.get('extracted_text', report.disclosure.summary)
            
            disclosure_dict = {
                'company_name': report.disclosure.company_name,
                'company_code': report.disclosure.company_code,
                'disclosure_date': report.disclosure.disclosure_date.isoformat(),
                'title': report.disclosure.title,
                'summary': report.disclosure.summary,
                'content': extracted_text[:20000] if extracted_text else report.disclosure.summary,
            }
            
            generation_result = self.gemini_generator.generate_report(
                disclosure_dict,
                report.report_type
            )
            
            if not generation_result['success']:
                return {'success': False, 'report': None, 'message': '', 'error': f"再生成失敗: {generation_result['error']}"}
            
            report_data = generation_result['data']
            report.overall_score = report_data.get('overall_score', 50)
            report.signal = report_data.get('signal', 'neutral')
            report.one_line_summary = report_data.get('one_line_summary', '')[:100]
            report.summary = report_data.get('summary', '')
            report.key_points = report_data.get('key_points', [])
            report.score_details = report_data.get('score_details', {})
            report.generation_prompt = generation_result.get('prompt', '')
            report.generation_token_count = generation_result.get('token_count', 0)
            report.save()
            
            for i, section_data in enumerate(report_data.get('sections', [])):
                TDNETReportSection.objects.create(
                    report=report,
                    section_type=section_data.get('section_type', 'other'),
                    title=section_data.get('title', f'セクション{i+1}'),
                    content=section_data.get('content', ''),
                    order=i,
                    data=section_data.get('data', {})
                )
            
            return {'success': True, 'report': report, 'message': 'レポートを再生成しました', 'error': None}
            
        except Exception as e:
            logger.error(f"レポート再生成エラー: {e}")
            return {'success': False, 'report': None, 'message': '', 'error': str(e)}
    
    def publish_report(self, report_id: str) -> Dict[str, Any]:
        """レポート公開"""
        try:
            report = TDNETReport.objects.filter(report_id=report_id).first()
            if not report:
                return {'success': False, 'report': None, 'message': 'レポートが見つかりません'}
            
            if report.status == 'published':
                return {'success': True, 'report': report, 'message': '既に公開されています'}
            
            report.publish()
            return {'success': True, 'report': report, 'message': 'レポートを公開しました'}
            
        except Exception as e:
            logger.error(f"レポート公開エラー: {e}")
            return {'success': False, 'report': None, 'message': str(e)}
    
    def unpublish_report(self, report_id: str) -> Dict[str, Any]:
        """レポート非公開"""
        try:
            report = TDNETReport.objects.filter(report_id=report_id).first()
            if not report:
                return {'success': False, 'report': None, 'message': 'レポートが見つかりません'}

            if report.status != 'published':
                return {'success': True, 'report': report, 'message': '既に非公開です'}

            report.unpublish()
            return {'success': True, 'report': report, 'message': 'レポートを非公開にしました'}

        except Exception as e:
            logger.error(f"レポート非公開エラー: {e}")
            return {'success': False, 'report': None, 'message': str(e)}

    def _extract_and_save_forecast_from_pdf(self, text: str, company_code: str,
                                             company_name: str, disclosure_date) -> None:
        """PDFテキストから次期業績予想を regex で抽出し EarningsForecast に保存する。

        標準的な決算短信には「次期の業績予想」セクションが定型フォーマットで記載される。
        Geminiを使わない補完手段のため失敗してもレポート生成には影響しない。
        """
        import re
        from decimal import Decimal
        from ..models.forecast import EarningsForecast
        from .forecast_reliability_service import ForecastReliabilityService

        SECTION_MARKERS = ['次期の業績予想', '来期業績予想', '翌期業績予想', '次期業績予想',
                           '来期の業績予想', '翌期の業績予想']
        # 売上高 営業利益 経常利益 純利益 の4列数値が続く行を検出
        NUMBER_ROW = re.compile(r'([\d,]{4,})\s+([-\d,]+)\s+([-\d,]+)\s+([-\d,]+)')

        def _clean_num(s: str) -> Optional[Decimal]:
            try:
                return Decimal(s.replace(',', ''))
            except Exception:
                return None

        try:
            # 予想セクションを探す
            section_text = None
            for marker in SECTION_MARKERS:
                idx = text.find(marker)
                if idx != -1:
                    section_text = text[idx:idx + 600]
                    break

            if not section_text:
                return

            m = NUMBER_ROW.search(section_text)
            if not m:
                return

            net_sales = _clean_num(m.group(1))
            operating_income = _clean_num(m.group(2))
            ordinary_income = _clean_num(m.group(3))
            net_income = _clean_num(m.group(4))

            if net_sales is None and operating_income is None:
                return

            # 開示日の翌年度を来期として登録
            fiscal_year_forecast = disclosure_date.year + 1

            # 決算短信PDFの数値は百万円単位 → 円単位に変換（XBRLと統一）
            def _to_yen(v):
                return v * Decimal('1000000') if v is not None else None

            EarningsForecast.objects.update_or_create(
                company_code=company_code,
                fiscal_year=fiscal_year_forecast,
                period_type='annual',
                defaults={
                    'company_name': company_name,
                    'forecast_net_sales': _to_yen(net_sales),
                    'forecast_operating_income': _to_yen(operating_income),
                    'forecast_ordinary_income': _to_yen(ordinary_income),
                    'forecast_net_income': _to_yen(net_income),
                    'forecast_announced_date': disclosure_date.date()
                        if hasattr(disclosure_date, 'date') else disclosure_date,
                    'source': 'tdnet',
                }
            )
            ForecastReliabilityService().calculate_reliability(company_code)
            logger.info(f"PDFから来期予想抽出・保存: {company_code} FY{fiscal_year_forecast}")

        except Exception as e:
            logger.warning(f"PDF予想抽出エラー ({company_code}): {e}")