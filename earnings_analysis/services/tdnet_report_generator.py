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
    """
    TDNETレポート統合生成サービス（PDF URL版）
    
    PDF URLから直接レポートを生成
    """
    
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
        """
        PDF URLから直接レポート生成
        
        Args:
            pdf_url: PDF URL
            company_code: 証券コード
            company_name: 企業名
            disclosure_type: 開示種別
            title: タイトル
            user: 生成者（管理者ユーザー）
            max_pdf_pages: PDFから読み取る最大ページ数
        
        Returns:
            {
                'success': True/False,
                'disclosure': TDNETDisclosureオブジェクト,
                'report': TDNETReportオブジェクト,
                'message': メッセージ,
                'error': エラーメッセージ（失敗時）
            }
        """
        try:
            # 1. PDFダウンロード＆テキスト抽出
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
            
            logger.info(f"PDF処理完了: {len(extracted_text)}文字抽出")
            
            # 2. 開示情報をDB保存
            disclosure_id = f"MANUAL-{company_code}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            
            disclosure = TDNETDisclosure.objects.create(
                disclosure_id=disclosure_id,
                company_code=company_code,
                company_name=company_name,
                disclosure_date=timezone.now(),
                disclosure_type=disclosure_type,
                title=title,
                summary=extracted_text[:500],  # 最初の500文字を概要に
                raw_data={
                    'pdf_url': pdf_url,
                    'extracted_text': extracted_text[:2000],  # 最初の2000文字を保存
                    'total_pages': pdf_result['pages'],
                    'processed_pages': pdf_result['processed_pages']
                },
                pdf_url=pdf_url,
                pdf_cached=True,
                pdf_file_path=pdf_path,
                is_processed=False,
                report_generated=False,
            )
            
            # company_masterとの連携
            try:
                from company_master.models import CompanyMaster
                company_master = CompanyMaster.objects.get(code=company_code)
                disclosure.company_master = company_master
                disclosure.save()
            except Exception as e:
                logger.warning(f"企業マスタ連携スキップ: {e}")
            
            logger.info(f"開示情報保存完了: {disclosure_id}")
            
            # 3. レポート生成
            logger.info(f"レポート生成開始: type={disclosure_type}")
            
            # 開示情報を辞書形式に変換
            disclosure_dict = {
                'company_name': company_name,
                'company_code': company_code,
                'disclosure_date': timezone.now().isoformat(),
                'title': title,
                'summary': extracted_text[:1000],  # 最初の1000文字を概要に
                'content': extracted_text[:30000],  # 最初の30000文字をコンテンツに（詳細分析のため増量）
            }
            
            # GEMINI APIでレポート生成
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
            
            # 4. レポート保存
            report = self._save_report(
                disclosure=disclosure,
                report_type=disclosure_type,
                generation_result=generation_result,
                user=user
            )
            
            # 5. 開示情報のステータス更新
            disclosure.report_generated = True
            disclosure.is_processed = True
            disclosure.save(update_fields=['report_generated', 'is_processed', 'updated_at'])
            
            logger.info(f"レポート生成完了: {report.report_id}")
            
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
        """
        既存の開示情報からレポート生成
        
        Args:
            disclosure_id: 開示ID
            report_type: レポート種別
            user: 生成者（管理者ユーザー）
        
        Returns:
            {
                'success': True/False,
                'disclosure': TDNETDisclosureオブジェクト,
                'report': TDNETReportオブジェクト or None,
                'message': メッセージ,
                'error': エラーメッセージ（失敗時）
            }
        """
        try:
            # 1. 開示情報取得
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
            
            # 2. 既存レポートチェック
            existing_report = TDNETReport.objects.filter(
                disclosure=disclosure,
                report_type=report_type
            ).first()
            
            if existing_report:
                logger.info(f"既存レポートが存在: {existing_report.report_id}")
                return {
                    'success': True,
                    'disclosure': disclosure,
                    'report': existing_report,
                    'message': '既存のレポートを返却しました',
                    'error': None
                }
            
            # 3. PDFテキストを取得
            if disclosure.pdf_file_path and not disclosure.raw_data.get('extracted_text'):
                # PDFが保存されているがテキストが未抽出の場合
                pdf_result = self.pdf_processor.extract_text_from_pdf(disclosure.pdf_file_path)
                if pdf_result['success']:
                    extracted_text = pdf_result['text']
                    # raw_dataに保存
                    disclosure.raw_data['extracted_text'] = extracted_text[:2000]
                    disclosure.save()
                else:
                    extracted_text = disclosure.summary
            else:
                # raw_dataから取得
                extracted_text = disclosure.raw_data.get('extracted_text', disclosure.summary)
            
            # 4. レポート生成
            logger.info(f"レポート生成開始: {disclosure_id}, type={report_type}")
            
            # 開示情報を辞書形式に変換
            disclosure_dict = {
                'company_name': disclosure.company_name,
                'company_code': disclosure.company_code,
                'disclosure_date': disclosure.disclosure_date.isoformat(),
                'title': disclosure.title,
                'summary': disclosure.summary,
                'content': extracted_text[:30000] if extracted_text else disclosure.summary,
            }
            
            # GEMINI APIでレポート生成
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
            
            # 5. レポート保存
            report = self._save_report(
                disclosure=disclosure,
                report_type=report_type,
                generation_result=generation_result,
                user=user
            )
            
            # 6. 開示情報のステータス更新
            disclosure.report_generated = True
            disclosure.is_processed = True
            disclosure.save(update_fields=['report_generated', 'is_processed', 'updated_at'])
            
            logger.info(f"レポート生成完了: {report.report_id}")
            
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
        
        # レポートIDを生成
        report_id = f"TDNET-{disclosure.company_code}-{disclosure.disclosure_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
        
        # レポートデータ
        report_data = generation_result['data']
        
        # TDNETReportオブジェクト作成
        report = TDNETReport.objects.create(
            report_id=report_id,
            disclosure=disclosure,
            title=f"{disclosure.company_name} - {disclosure.title}",
            report_type=report_type,
            summary=report_data.get('summary', ''),
            key_points=report_data.get('key_points', []),
            analysis='',  # セクションで詳細を記載
            status='draft',  # 下書きとして保存
            generated_by=user,
            generation_model=self.gemini_generator.model_name,
            generation_prompt=generation_result.get('prompt', ''),
            generation_token_count=generation_result.get('token_count', 0),
        )
        
        # セクション保存
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
        
        logger.info(f"レポート保存完了: {report_id}, セクション{len(sections_data)}個")
        
        return report
    
    def regenerate_report(self, report_id: str, user) -> Dict[str, Any]:
        """
        レポート再生成
        
        Args:
            report_id: レポートID
            user: 再生成者
        
        Returns:
            生成結果辞書
        """
        try:
            # 既存レポート取得
            report = TDNETReport.objects.filter(report_id=report_id).first()
            if not report:
                return {
                    'success': False,
                    'report': None,
                    'message': '',
                    'error': 'レポートが見つかりません'
                }
            
            # 既存セクション削除
            report.sections.all().delete()
            
            # 再生成
            disclosure_dict = {
                'company_name': report.disclosure.company_name,
                'company_code': report.disclosure.company_code,
                'disclosure_date': report.disclosure.disclosure_date.isoformat(),
                'title': report.disclosure.title,
                'summary': report.disclosure.summary,
                'content': report.disclosure.summary or report.disclosure.title,
            }
            
            generation_result = self.gemini_generator.generate_report(
                disclosure_dict,
                report.report_type
            )
            
            if not generation_result['success']:
                return {
                    'success': False,
                    'report': None,
                    'message': '',
                    'error': f"再生成失敗: {generation_result['error']}"
                }
            
            # レポート更新
            report_data = generation_result['data']
            report.summary = report_data.get('summary', '')
            report.key_points = report_data.get('key_points', [])
            report.generation_prompt = generation_result.get('prompt', '')
            report.generation_token_count = generation_result.get('token_count', 0)
            report.save()
            
            # セクション再作成
            for i, section_data in enumerate(report_data.get('sections', [])):
                TDNETReportSection.objects.create(
                    report=report,
                    section_type=section_data.get('section_type', 'other'),
                    title=section_data.get('title', f'セクション{i+1}'),
                    content=section_data.get('content', ''),
                    order=i,
                    data=section_data.get('data', {})
                )
            
            logger.info(f"レポート再生成完了: {report_id}")
            
            return {
                'success': True,
                'report': report,
                'message': 'レポートを再生成しました',
                'error': None
            }
            
        except Exception as e:
            logger.error(f"レポート再生成エラー: {e}")
            return {
                'success': False,
                'report': None,
                'message': '',
                'error': str(e)
            }
    
    def publish_report(self, report_id: str) -> Dict[str, Any]:
        """
        レポート公開
        
        Args:
            report_id: レポートID
        
        Returns:
            {
                'success': True/False,
                'report': TDNETReportオブジェクト or None,
                'message': メッセージ
            }
        """
        try:
            report = TDNETReport.objects.filter(report_id=report_id).first()
            if not report:
                return {
                    'success': False,
                    'report': None,
                    'message': 'レポートが見つかりません'
                }
            
            if report.status == 'published':
                return {
                    'success': True,
                    'report': report,
                    'message': '既に公開されています'
                }
            
            report.publish()
            
            logger.info(f"レポート公開: {report_id}")
            
            return {
                'success': True,
                'report': report,
                'message': 'レポートを公開しました'
            }
            
        except Exception as e:
            logger.error(f"レポート公開エラー: {e}")
            return {
                'success': False,
                'report': None,
                'message': str(e)
            }
    
    def unpublish_report(self, report_id: str) -> Dict[str, Any]:
        """
        レポート非公開
        
        Args:
            report_id: レポートID
        
        Returns:
            操作結果辞書
        """
        try:
            report = TDNETReport.objects.filter(report_id=report_id).first()
            if not report:
                return {
                    'success': False,
                    'report': None,
                    'message': 'レポートが見つかりません'
                }
            
            if report.status != 'published':
                return {
                    'success': True,
                    'report': report,
                    'message': '既に非公開です'
                }
            
            report.unpublish()
            
            logger.info(f"レポート非公開: {report_id}")
            
            return {
                'success': True,
                'report': report,
                'message': 'レポートを非公開にしました'
            }
            
        except Exception as e:
            logger.error(f"レポート非公開エラー: {e}")
            return {
                'success': False,
                'report': None,
                'message': str(e)
            }