"""
XBRL 財務分析サービス（AI 不使用・ルールベースのみ）

EDINETXBRLService → FinancialAnalyzer の順に呼び出し、
CompanyFinancialData に永続保存した上で指標 dict を返す。
"""
import logging
from decimal import Decimal
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class XBRLAnalysisService:
    """
    EDINET の XBRL から財務指標を抽出・算出するサービス。
    感情分析（Gemini API）は一切使用しない。
    """

    def __init__(self):
        from .xbrl_extractor import EDINETXBRLService
        from .financial_analyzer import FinancialAnalyzer
        self.xbrl_service = EDINETXBRLService()
        self.financial_analyzer = FinancialAnalyzer()

    def analyze_document(self, document) -> Dict[str, Any]:
        """
        DocumentMetadata を受け取り、XBRL 財務分析を実行する。
        Returns:
            {
                'ok': bool,
                'error': str | None,
                'financial_data': dict,   # 生データ（円単位）
                'ratios': dict,            # 計算済み比率
                'cf_pattern': dict,        # CF パターン情報
                'health_score': float,     # 0-100
                'risk_level': str,
                'investment_stance': str,
                'data_completeness': float,
            }
        """
        doc_info = {
            'company_name': document.company_name,
            'doc_description': getattr(document, 'doc_description', ''),
            'doc_type_code': document.doc_type_code,
            'submit_date': (
                document.submit_date_time.strftime('%Y-%m-%d')
                if document.submit_date_time else ''
            ),
            'securities_code': document.securities_code or '',
        }

        # ① XBRL から財務データ取得
        try:
            xbrl_data = self.xbrl_service.get_comprehensive_analysis_from_document(document)
        except Exception as e:
            logger.error(f"XBRL 取得失敗: {document.doc_id} — {e}")
            return {'ok': False, 'error': f'XBRL 取得に失敗しました: {e}'}

        financial_data = xbrl_data.get('financial_data', {})
        text_sections = xbrl_data.get('text_sections', {})

        if not financial_data:
            return {'ok': False, 'error': 'XBRL から財務データを取得できませんでした（書類種別または XBRL 構造が非対応の可能性）'}

        # ② 財務分析（ルールベース）
        try:
            analysis = self.financial_analyzer.analyze_comprehensive_financial_health(
                financial_data, text_sections, doc_info
            )
        except Exception as e:
            logger.error(f"財務分析失敗: {document.doc_id} — {e}")
            return {'ok': False, 'error': f'財務分析中にエラーが発生しました: {e}'}

        # ③ CompanyFinancialData に永続保存
        fin_record = None
        try:
            from .comprehensive_analyzer import ComprehensiveAnalysisService
            fin_record = ComprehensiveAnalysisService()._save_financial_data(document, financial_data)
        except Exception as e:
            logger.warning(f"財務データ保存失敗（分析結果は返す）: {document.doc_id} — {e}")

        # ④ 結果を整理して返す
        return self._build_result(financial_data, analysis, fin_record)

    # ------------------------------------------------------------------
    def _build_result(self, financial_data: dict, analysis: dict, fin_record) -> Dict[str, Any]:
        overall_health = analysis.get('overall_health', {})
        ratios_raw = analysis.get('financial_ratios', {}).get('ratios', {})
        cf_analysis = analysis.get('cashflow_analysis', {})
        pattern = cf_analysis.get('pattern')

        # ROE を追加算出（当期純利益 / 純資産）
        roe = None
        net_income = financial_data.get('net_income')
        net_assets = financial_data.get('net_assets')
        if net_income is not None and net_assets and Decimal(str(net_assets)) != 0:
            roe = float(Decimal(str(net_income)) / Decimal(str(net_assets)) * 100)

        # 負債比率（総負債 / 総資産）
        debt_ratio = None
        total_liabilities = financial_data.get('total_liabilities')
        total_assets = financial_data.get('total_assets')
        if total_liabilities is not None and total_assets and Decimal(str(total_assets)) != 0:
            debt_ratio = float(Decimal(str(total_liabilities)) / Decimal(str(total_assets)) * 100)

        ratios = dict(ratios_raw)
        if roe is not None:
            ratios['roe'] = round(roe, 2)
        if debt_ratio is not None:
            ratios['debt_ratio'] = round(debt_ratio, 2)

        cf_pattern_dict = None
        if pattern:
            cf_pattern_dict = {
                'name': getattr(pattern, 'name', ''),
                'description': getattr(pattern, 'description', ''),
                'risk_level': getattr(pattern, 'risk_level', 'medium'),
                'interpretation': getattr(pattern, 'interpretation', ''),
                'operating_cf': getattr(pattern, 'operating_cf', ''),
                'investing_cf': getattr(pattern, 'investing_cf', ''),
                'financing_cf': getattr(pattern, 'financing_cf', ''),
            }

        health_score = None
        if isinstance(overall_health, dict):
            health_score = overall_health.get('overall_score')
        if health_score is None and fin_record:
            pass  # fin_record には health_score フィールドがない

        return {
            'ok': True,
            'error': None,
            'financial_data': {
                k: float(v) if v is not None else None
                for k, v in financial_data.items()
            },
            'ratios': ratios,
            'cf_pattern': cf_pattern_dict,
            'health_score': round(float(health_score), 1) if health_score is not None else None,
            'risk_level': overall_health.get('risk_level', 'medium') if isinstance(overall_health, dict) else 'medium',
            'investment_stance': analysis.get('investment_recommendations', {}).get('stance', 'cautious'),
            'strengths': cf_analysis.get('strengths', [])[:3],
            'concerns': cf_analysis.get('concerns', [])[:3],
            'data_completeness': fin_record.data_completeness if fin_record else None,
        }
