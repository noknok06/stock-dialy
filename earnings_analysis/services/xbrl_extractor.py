# earnings_analysis/services/xbrl_extractor.py の完全版

import xml.etree.ElementTree as ET
import re
import requests
import zipfile
import io
import logging
from typing import Dict, List, Optional, Tuple
from django.core.cache import cache
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

class CashFlowExtractor:
    """キャッシュフロー計算書専用の抽出クラス（既存システム統合版）"""
    
    def __init__(self):
        # キャッシュフロー要素の詳細マッピング（IFRS・日本基準対応）
        self.cashflow_elements = {
            'operating_cf': [
                # IFRS標準
                'NetCashProvidedByUsedInOperatingActivitiesIFRS',
                'CashFlowsFromUsedInOperatingActivitiesIFRS',
                
                # 日本基準
                'NetCashProvidedByUsedInOperatingActivities',
                'CashFlowsFromOperatingActivities',
                'OperatingActivitiesCashFlow',
                
                # 四半期固有
                'NetCashProvidedByUsedInOperatingActivitiesInterimPeriod',
                'OperatingActivitiesCashFlowSummary',
                
                # 日本語要素
                '営業活動によるキャッシュ・フロー',
                '営業活動によるキャッシュフロー', 
                '営業キャッシュフロー',
                '営業CF',
            ],
            
            'investing_cf': [
                # IFRS標準
                'NetCashProvidedByUsedInInvestingActivitiesIFRS',
                'CashFlowsFromUsedInInvestingActivitiesIFRS',
                
                # 日本基準
                'NetCashProvidedByUsedInInvestingActivities',
                'CashFlowsFromInvestingActivities',
                'InvestingActivitiesCashFlow',
                
                # 四半期固有
                'NetCashProvidedByUsedInInvestingActivitiesInterimPeriod',
                'InvestingActivitiesCashFlowSummary',
                
                # 日本語要素
                '投資活動によるキャッシュ・フロー',
                '投資活動によるキャッシュフロー',
                '投資キャッシュフロー',
                '投資CF',
            ],
            
            'financing_cf': [
                # IFRS標準
                'NetCashProvidedByUsedInFinancingActivitiesIFRS',
                'CashFlowsFromUsedInFinancingActivitiesIFRS',
                
                # 日本基準
                'NetCashProvidedByUsedInFinancingActivities', 
                'CashFlowsFromFinancingActivities',
                'FinancingActivitiesCashFlow',
                
                # 四半期固有
                'NetCashProvidedByUsedInFinancingActivitiesInterimPeriod',
                'FinancingActivitiesCashFlowSummary',
                
                # 日本語要素
                '財務活動によるキャッシュ・フロー',
                '財務活動によるキャッシュフロー',
                '財務キャッシュフロー',
                '財務CF',
            ]
        }

    def extract_cashflow_for_comprehensive_analysis(self, root: ET.Element) -> Dict[str, Decimal]:
        """包括分析用のキャッシュフローデータ抽出（既存システム互換）"""
        financial_data = {}
        
        try:
            for cf_type, element_patterns in self.cashflow_elements.items():
                cf_data = self._extract_single_cf_item_enhanced(root, cf_type, element_patterns)
                
                if cf_data['value'] is not None:
                    financial_data[cf_type] = cf_data['value']
                    logger.info(f"{cf_type} 抽出成功: {cf_data['value']} "
                              f"(要素: {cf_data['source_element']}, "
                              f"単位: {cf_data['unit_info']['detected_unit']}, "
                              f"信頼度: {cf_data['confidence_score']:.3f})")
                else:
                    logger.warning(f"{cf_type} の抽出に失敗しました")
            
            logger.info(f"キャッシュフローデータ抽出完了: {len(financial_data)}項目")
            
        except Exception as e:
            logger.error(f"キャッシュフローデータ抽出エラー: {e}")
            
        return financial_data

    def _extract_single_cf_item_enhanced(self, root: ET.Element, cf_type: str, element_patterns: List[str]) -> Dict[str, any]:
        """単一キャッシュフロー項目の高精度抽出"""
        extraction_result = {
            'value': None,
            'source_element': None,
            'confidence_score': 0.0,
            'unit_info': {},
            'candidates_count': 0
        }
        
        try:
            # 候補要素の検索
            candidates = []
            
            for pattern in element_patterns:
                elements = self._find_cf_elements_smart(root, pattern)
                
                for element in elements:
                    candidate = self._analyze_cf_element_detailed(element, cf_type, pattern)
                    if candidate['is_valid']:
                        candidates.append(candidate)
            
            extraction_result['candidates_count'] = len(candidates)
            
            # 最適候補の選択
            if candidates:
                best_candidate = self._select_best_cf_candidate(candidates, cf_type)
                
                extraction_result.update({
                    'value': best_candidate['final_value'],
                    'source_element': best_candidate['element_tag'],
                    'confidence_score': best_candidate['confidence_score'],
                    'unit_info': best_candidate['unit_analysis']
                })
            
        except Exception as e:
            logger.error(f"{cf_type} 抽出エラー: {e}")
            
        return extraction_result

    def _find_cf_elements_smart(self, root: ET.Element, pattern: str) -> List[ET.Element]:
        """スマートなキャッシュフロー要素検索"""
        elements = []
        
        try:
            # 1. 直接マッチング
            for elem in root.iter():
                if pattern in elem.tag:
                    elements.append(elem)
            
            # 2. 名前空間考慮検索
            namespaces = [
                'http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/',
                'http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/', 
                'http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/',
            ]
            
            for ns in namespaces:
                try:
                    found = root.findall(f".//{{{ns}*}}{pattern}")
                    elements.extend(found)
                    found = root.findall(f".//{{*}}{pattern}")
                    elements.extend(found)
                except:
                    continue
            
            # 3. 日本語テキスト検索
            if any(char in pattern for char in ['営業', '投資', '財務']):
                for elem in root.iter():
                    if elem.text and pattern in elem.text:
                        elements.append(elem)
            
            # 重複除去
            unique_elements = list({(elem.tag, elem.text): elem for elem in elements}.values())
            
            return unique_elements
            
        except Exception as e:
            logger.debug(f"要素検索エラー ({pattern}): {e}")
            return []

    def _analyze_cf_element_detailed(self, element: ET.Element, cf_type: str, pattern: str) -> Dict[str, any]:
        """キャッシュフロー要素の詳細分析（単位問題対応強化版）"""
        analysis = {
            'element': element,
            'element_tag': element.tag,
            'pattern': pattern,
            'raw_value': None,
            'final_value': None,
            'is_valid': False,
            'confidence_score': 0.0,
            'unit_analysis': {}
        }
        
        try:
            # 数値抽出
            text = element.text
            if not text or not text.strip():
                return analysis
            
            raw_value = self._extract_numeric_value_robust(text)
            if raw_value is None:
                return analysis
            
            analysis['raw_value'] = raw_value
            
            # 単位分析（強化版）
            unit_analysis = self._analyze_unit_information_enhanced(element, text, raw_value)
            analysis['unit_analysis'] = unit_analysis
            
            # 最終値計算（現実性チェック付き）
            final_value = self._calculate_final_value_with_reality_check(
                raw_value, unit_analysis, cf_type, element.tag
            )
            analysis['final_value'] = final_value
            
            # 信頼度スコア
            confidence_score = self._calculate_enhanced_confidence_score(
                element, pattern, unit_analysis, cf_type
            )
            analysis['confidence_score'] = confidence_score
            
            # 妥当性判定
            if self._is_cf_value_realistic_strict(final_value, cf_type):
                analysis['is_valid'] = True
            
        except Exception as e:
            logger.debug(f"要素分析エラー ({pattern}): {e}")
            
        return analysis

    def _extract_numeric_value_robust(self, text: str) -> Optional[Decimal]:
        """堅牢な数値抽出"""
        try:
            # 前処理
            cleaned = text.strip()
            
            # 負の値の検出
            is_negative = any(marker in cleaned for marker in ['-', '△', '▲', '（', '('])
            
            # 数値パターンの抽出
            numeric_part = re.sub(r'[,\s\u3000△▲（）()]+', '', cleaned)
            
            # 数値の抽出（小数点対応）
            number_match = re.search(r'(\d+(?:\.\d+)?)', numeric_part)
            if number_match:
                number_str = number_match.group(1)
                base_value = Decimal(number_str)
                
                return -base_value if is_negative else base_value
            
            return None
            
        except (InvalidOperation, ValueError):
            return None

    def _analyze_unit_information_enhanced(self, element: ET.Element, text: str, raw_value: Decimal) -> Dict[str, any]:
        """強化版単位分析（現実性も考慮）"""
        unit_info = {
            'detected_unit': 'yen',
            'unit_multiplier': Decimal('1'),
            'decimals_attr': element.get('decimals'),
            'confidence': 0.0,
            'detection_method': 'default',
            'reality_check_passed': False
        }
        
        try:
            abs_raw_value = abs(raw_value)
            
            # 1. XBRL属性からの単位判定（現実性チェック付き）
            decimals = element.get('decimals')
            if decimals:
                decimal_value = int(decimals)
                
                if decimal_value == -6:  # 百万円単位
                    # 値の大きさで現実性をチェック
                    if abs_raw_value < 100000:  # 10万未満なら百万円単位として妥当
                        unit_info.update({
                            'detected_unit': 'million_yen',
                            'unit_multiplier': Decimal('1000000'),
                            'confidence': 0.9,
                            'detection_method': 'decimals_with_reality_check',
                            'reality_check_passed': True
                        })
                    elif abs_raw_value > 1000000000000:  # 1兆超なら既に適切な単位の可能性
                        unit_info.update({
                            'detected_unit': 'yen',
                            'unit_multiplier': Decimal('1'),
                            'confidence': 0.8,
                            'detection_method': 'decimals_override_by_size',
                            'reality_check_passed': True
                        })
                    else:  # 中間値：慎重に判定
                        # 百万円変換したときの現実性をチェック
                        test_value = abs_raw_value * Decimal('1000000')
                        if test_value <= Decimal('100000000000000'):  # 100兆円以下
                            unit_info.update({
                                'detected_unit': 'million_yen',
                                'unit_multiplier': Decimal('1000000'),
                                'confidence': 0.7,
                                'detection_method': 'decimals_cautious',
                                'reality_check_passed': True
                            })
                        else:
                            unit_info.update({
                                'detected_unit': 'yen',
                                'unit_multiplier': Decimal('1'),
                                'confidence': 0.6,
                                'detection_method': 'decimals_reality_failed',
                                'reality_check_passed': False
                            })
                
                elif decimal_value == -3:  # 千円単位
                    if abs_raw_value < 10000000:  # 1000万未満
                        unit_info.update({
                            'detected_unit': 'thousand_yen',
                            'unit_multiplier': Decimal('1000'),
                            'confidence': 0.9,
                            'detection_method': 'decimals_thousand',
                            'reality_check_passed': True
                        })
            
            # 2. テキスト内容からの単位判定
            text_lower = text.lower()
            unit_patterns = {
                r'百万円|million': ('million_yen', Decimal('1000000'), 0.95),
                r'千円|thousand': ('thousand_yen', Decimal('1000'), 0.95),
                r'億円|hundred.?million': ('hundred_million_yen', Decimal('100000000'), 0.9),
                r'兆円|trillion': ('trillion_yen', Decimal('1000000000000'), 0.85),
            }
            
            for pattern, (unit_name, multiplier, confidence) in unit_patterns.items():
                if re.search(pattern, text):
                    if confidence > unit_info['confidence']:
                        # 現実性チェック
                        test_value = abs_raw_value * multiplier
                        if Decimal('1000000') <= test_value <= Decimal('100000000000000'):
                            unit_info.update({
                                'detected_unit': unit_name,
                                'unit_multiplier': multiplier,
                                'confidence': confidence,
                                'detection_method': 'text_content',
                                'reality_check_passed': True
                            })
            
        except Exception as e:
            logger.debug(f"単位分析エラー: {e}")
            
        return unit_info

    def _calculate_final_value_with_reality_check(self, raw_value: Decimal, unit_info: Dict, 
                                                cf_type: str, element_tag: str) -> Decimal:
        """現実性チェック付きの最終値計算"""
        try:
            # 基本的な単位変換
            base_value = raw_value * unit_info['unit_multiplier']
            
            # 現実的な範囲
            realistic_ranges = {
                'operating_cf': (Decimal('1000000'), Decimal('50000000000000')),    # 100万-50兆円
                'investing_cf': (Decimal('1000000'), Decimal('30000000000000')),    # 100万-30兆円  
                'financing_cf': (Decimal('1000000'), Decimal('30000000000000')),    # 100万-30兆円
            }
            
            min_val, max_val = realistic_ranges.get(cf_type, (Decimal('1000000'), Decimal('100000000000000')))
            abs_value = abs(base_value)
            
            # 段階的な現実性調整
            if abs_value > max_val:
                # 過大な値の段階的調整
                adjustment_factors = [
                    Decimal('0.001'),    # 1/1000
                    Decimal('0.000001'), # 1/1,000,000
                    Decimal('0.000000001'), # 1/1,000,000,000
                ]
                
                for factor in adjustment_factors:
                    adjusted_value = base_value * factor
                    if min_val <= abs(adjusted_value) <= max_val:
                        logger.info(f"{cf_type} 自動調整({factor}): {base_value} → {adjusted_value}")
                        return adjusted_value
                
                # 最終フォールバック
                final_value = base_value / Decimal('1000000')
                logger.warning(f"{cf_type} 強制調整: {base_value} → {final_value}")
                return final_value
                
            elif abs_value < min_val and abs_value > 0:
                # 過小な値の調整
                expansion_factors = [Decimal('1000'), Decimal('1000000')]
                
                for factor in expansion_factors:
                    expanded_value = base_value * factor
                    if min_val <= abs(expanded_value) <= max_val:
                        logger.info(f"{cf_type} 自動拡大({factor}): {base_value} → {expanded_value}")
                        return expanded_value
            
            return base_value
            
        except Exception as e:
            logger.error(f"最終値計算エラー ({cf_type}): {e}")
            return raw_value

    def _calculate_enhanced_confidence_score(self, element: ET.Element, pattern: str, 
                                           unit_info: Dict, cf_type: str) -> float:
        """強化版信頼度スコア計算"""
        score = 0.0
        
        try:
            element_tag = element.tag.lower()
            
            # 1. パターンマッチング精度 (0.4)
            if pattern.lower() in element_tag:
                if 'ifrs' in element_tag:
                    score += 0.35  # IFRS要素は高評価
                else:
                    score += 0.3
            elif cf_type.replace('_', '') in element_tag:
                score += 0.2
            else:
                score += 0.1
            
            # 2. 単位情報の信頼性 (0.3)
            unit_confidence = unit_info.get('confidence', 0.0)
            reality_check = unit_info.get('reality_check_passed', False)
            
            if reality_check:
                score += unit_confidence * 0.3
            else:
                score += unit_confidence * 0.15  # 現実性チェック失敗で減点
            
            # 3. 要素の属性完全性 (0.2)
            if element.get('decimals'):
                score += 0.1
            if element.get('contextRef'):
                score += 0.1
            
            # 4. キャッシュフロー特有のボーナス (0.1)
            if 'net' in element_tag and 'cash' in element_tag:
                score += 0.05
            if 'activities' in element_tag:
                score += 0.05
            
        except Exception as e:
            logger.debug(f"信頼度計算エラー: {e}")
            
        return min(score, 1.0)

    def _select_best_cf_candidate(self, candidates: List[Dict], cf_type: str) -> Dict:
        """最適なキャッシュフロー候補の選択"""
        if len(candidates) == 1:
            return candidates[0]
        
        # 複合スコアで評価
        def evaluate_candidate(candidate):
            base_score = candidate['confidence_score']
            
            # 現実性ボーナス
            if self._is_cf_value_realistic_strict(candidate['final_value'], cf_type):
                base_score += 0.2
            
            # 単位の現実性チェック通過ボーナス
            if candidate['unit_analysis'].get('reality_check_passed', False):
                base_score += 0.1
            
            # IFRS要素ボーナス
            if 'ifrs' in candidate['element_tag'].lower():
                base_score += 0.05
            
            return base_score
        
        # 評価・ソート
        scored_candidates = [(evaluate_candidate(c), c) for c in candidates]
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        best_candidate = scored_candidates[0][1]
        
        logger.info(f"{cf_type} 最適候補選択: {best_candidate['pattern']} "
                  f"(最終値: {best_candidate['final_value']}, "
                  f"評価スコア: {scored_candidates[0][0]:.3f})")
        
        return best_candidate

    def _is_cf_value_realistic_strict(self, value: Decimal, cf_type: str) -> bool:
        """厳格な現実性チェック"""
        if value is None:
            return False
            
        abs_value = abs(value)
        
        # 基本範囲チェック
        if abs_value < Decimal('100000'):  # 10万円未満
            return False
        if abs_value > Decimal('100000000000000'):  # 100兆円超
            return False
        
        # CF種別固有の現実的範囲
        realistic_ranges = {
            'operating_cf': (Decimal('1000000'), Decimal('50000000000000')),
            'investing_cf': (Decimal('1000000'), Decimal('30000000000000')),
            'financing_cf': (Decimal('1000000'), Decimal('30000000000000')),
        }
        
        min_val, max_val = realistic_ranges.get(cf_type, (Decimal('1000000'), Decimal('50000000000000')))
        
        return min_val <= abs_value <= max_val


class XBRLFinancialExtractor:
    """XBRLファイルから財務データを抽出するクラス（完全版）"""
    
    def __init__(self):
        # キャッシュフロー専用抽出器
        try:
            self.cashflow_extractor = CashFlowExtractor()
        except:
            # フォールバック：CashFlowExtractorが利用できない場合
            self.cashflow_extractor = None
            logger.warning("CashFlowExtractor初期化失敗、基本機能で代替")
        
        # テキスト要素パターンの定義
        self.text_element_patterns = [
            'BusinessRisks',
            'BusinessRisksTextBlock',
            'BusinessPolicyBusinessEnvironmentIssuesAddressedEtc',
            'ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlows',
            'ResearchAndDevelopmentActivities',
            'OverviewOfGroup',
            'BusinessDescriptionTextBlock',
            'BusinessResultsOfOperationsTextBlock',
            'CriticalAccountingPolicies',
            'OverallBusinessResultsTextBlock',
            'AnalysisOfBusinessResultsTextBlock',
            'CashFlowsTextBlock',
            'FinancialPositionTextBlock',
            'ManagementPolicyTextBlock',
            'BusinessEnvironmentTextBlock',
            'CorporateGovernanceTextBlock',
            'InternalControlSystemTextBlock',
            'ComplianceTextBlock',
            'RiskManagementTextBlock',
            'DividendPolicyTextBlock',
            'CapitalStructureTextBlock',
            'LiquidityAndCapitalResourcesTextBlock',
            'ContractualObligationsTextBlock',
            'OffBalanceSheetArrangementsTextBlock',
            'CriticalAccountingEstimatesTextBlock',
            'NewAccountingPronouncementsTextBlock',
            'SegmentInformationTextBlock',
            'GeographicInformationTextBlock',
            'ProductServiceInformationTextBlock',
            'CustomerInformationTextBlock',
            'SeasonalityTextBlock',
            'InflationTextBlock',
            'EnvironmentalTextBlock',
            'LegalProceedingsTextBlock',
            'UnregisteredSalesOfEquitySecuritiesTextBlock',
            'RepurchasesOfEquitySecuritiesTextBlock',
            'SelectedFinancialDataTextBlock',
            'ManagementDiscussionAndAnalysisTextBlock',
        ]
        
        # 財務要素の定義
        self.financial_elements = {
            # キャッシュフロー
            'operating_cf': [
                'NetCashProvidedByUsedInOperatingActivitiesIFRS',
                'NetCashProvidedByUsedInOperatingActivities',
                'CashFlowsFromOperatingActivities',
                'OperatingActivitiesCashFlow',
                '営業活動によるキャッシュ・フロー',
                '営業活動によるキャッシュフロー',
            ],
            'investing_cf': [
                'NetCashProvidedByUsedInInvestingActivitiesIFRS',
                'NetCashProvidedByUsedInInvestingActivities',
                'CashFlowsFromInvestingActivities',
                'InvestingActivitiesCashFlow',
                '投資活動によるキャッシュ・フロー',
                '投資活動によるキャッシュフロー',
            ],
            'financing_cf': [
                'NetCashProvidedByUsedInFinancingActivitiesIFRS',
                'NetCashProvidedByUsedInFinancingActivities',
                'CashFlowsFromFinancingActivities',
                'FinancingActivitiesCashFlow',
                '財務活動によるキャッシュ・フロー',
                '財務活動によるキャッシュフロー',
            ],
            # その他の財務データ
            'net_sales': ['NetSales', 'Sales', 'Revenue', '売上高'],
            'operating_income': ['OperatingIncome', 'OperatingProfit', '営業利益'],
            'net_income': ['NetIncome', 'ProfitLoss', '当期純利益'],
            'total_assets': ['TotalAssets', 'Assets', '資産合計'],
            'total_liabilities': ['TotalLiabilities', 'Liabilities', '負債合計'],
            'net_assets': ['NetAssets', 'TotalEquity', '純資産合計'],
        }
        
        self.namespaces = {
            'xbrl': 'http://www.xbrl.org/2003/instance',
            'xbrli': 'http://www.xbrl.org/2003/instance',
            'jppfs': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2019-11-01/',
            'jpcrp': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2019-11-01/',
            'jpdei': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2019-11-01/',
        }

    def _extract_from_xml(self, xml_content: bytes) -> Dict[str, str]:
        """XMLファイルからテキストを抽出"""
        extracted_text = {}
        
        try:
            # XMLパース
            root = ET.fromstring(xml_content)
            
            # 各テキスト要素を検索
            for pattern in self.text_element_patterns:
                elements = self._find_elements_by_pattern(root, pattern)
                
                for element in elements:
                    text_content = self._extract_element_text(element)
                    if text_content and len(text_content.strip()) > 50:  # 50文字以上のテキストのみ
                        section_name = self._get_section_name(pattern)
                        extracted_text[section_name] = text_content
            
            # その他のテキスト要素も検索
            additional_text = self._extract_additional_text_elements(root)
            extracted_text.update(additional_text)
            
        except ET.ParseError as e:
            logger.error(f"XML解析エラー: {e}")
        except Exception as e:
            logger.error(f"テキスト抽出エラー: {e}")
            
        return extracted_text
    
    def _extract_from_zip(self, zip_content: bytes) -> Dict[str, str]:
        """ZIPファイルからXBRLテキストを抽出"""
        extracted_text = {}
        
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
                for file_info in zip_file.filelist:
                    if file_info.filename.endswith('.xbrl'):
                        # XBRLファイルを読み込み
                        with zip_file.open(file_info) as xbrl_file:
                            xbrl_content = xbrl_file.read()
                            file_text = self._extract_from_xml(xbrl_content)
                            extracted_text.update(file_text)
                            
        except Exception as e:
            logger.error(f"ZIP展開エラー: {e}")
            
        return extracted_text
    
    def _extract_comprehensive_from_zip(self, zip_content: bytes) -> Dict[str, any]:
        """ZIPファイルから財務データとテキストを抽出（緊急修正版）"""
        comprehensive_data = {'financial_data': {}, 'text_sections': {}, 'table_unit': 'yen'}
        
        try:
            import zipfile
            import io
            
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
                logger.info(f"ZIP展開開始: {len(zip_file.filelist)}ファイル")
                
                # XBRLファイルを優先順位付きで処理
                xbrl_files = [f for f in zip_file.filelist if f.filename.endswith('.xbrl')]
                
                if not xbrl_files:
                    logger.warning("XBRLファイルが見つかりません")
                    return comprehensive_data
                
                # ファイル優先順位付け
                prioritized_files = self._prioritize_xbrl_files_emergency(xbrl_files)
                
                best_financial_data = {}
                all_text_sections = {}
                
                for file_info in prioritized_files:
                    try:
                        logger.info(f"XBRLファイル処理: {file_info.filename}")
                        
                        with zip_file.open(file_info) as xbrl_file:
                            xbrl_content = xbrl_file.read()
                            file_data = self._extract_comprehensive_from_xml(xbrl_content)
                            
                            # 財務データのマージ（上書き防止）
                            file_financial = file_data.get('financial_data', {})
                            for key, value in file_financial.items():
                                if value is not None and (key not in best_financial_data or best_financial_data[key] is None):
                                    best_financial_data[key] = value
                                    logger.info(f"  財務データ取得: {key} = {value}")
                            
                            # テキストデータのマージ
                            file_text = file_data.get('text_sections', {})
                            all_text_sections.update(file_text)
                            
                    except Exception as e:
                        logger.error(f"XBRLファイル処理エラー ({file_info.filename}): {e}")
                        continue
                
                comprehensive_data['financial_data'] = best_financial_data
                comprehensive_data['text_sections'] = all_text_sections
                
                logger.info(f"ZIP処理完了: 財務データ{len(best_financial_data)}項目, "
                          f"テキスト{len(all_text_sections)}セクション")
                
        except Exception as e:
            logger.error(f"ZIP包括展開エラー: {e}")
            
        return comprehensive_data

    def _find_elements_by_pattern(self, root: ET.Element, pattern: str) -> List[ET.Element]:
        """パターンに一致する要素を検索"""
        elements = []
        
        try:
            # 直接検索
            for elem in root.iter():
                if pattern in elem.tag:
                    elements.append(elem)
            
            # 名前空間を考慮した検索
            for ns_prefix, ns_uri in self.namespaces.items():
                try:
                    found = root.findall(f".//{{{ns_uri}}}{pattern}")
                    elements.extend(found)
                except:
                    continue
            
            # 重複除去
            unique_elements = list({(elem.tag, elem.text): elem for elem in elements}.values())
            
        except Exception as e:
            logger.debug(f"要素検索エラー ({pattern}): {e}")
            
        return unique_elements

    def _extract_element_text(self, element: ET.Element) -> str:
        """要素からテキストを抽出"""
        text_parts = []
        
        try:
            # 要素のテキスト
            if element.text:
                text_parts.append(element.text.strip())
            
            # 子要素のテキスト
            for child in element:
                child_text = self._extract_element_text(child)
                if child_text:
                    text_parts.append(child_text)
            
            # 要素の末尾テキスト
            if element.tail:
                text_parts.append(element.tail.strip())
            
            full_text = ' '.join(text_parts)
            
            # テキストクリーニング
            cleaned_text = self._clean_text(full_text)
            
        except Exception as e:
            logger.debug(f"要素テキスト抽出エラー: {e}")
            cleaned_text = ""
        
        return cleaned_text
    
    def _extract_additional_text_elements(self, root: ET.Element) -> Dict[str, str]:
        """その他のテキスト要素を抽出"""
        additional_text = {}
        
        try:
            # テキストを含む可能性のある要素を広く検索
            text_elements = []
            for elem in root.iter():
                # テキストが長い要素を対象
                if elem.text and len(elem.text.strip()) > 100:
                    text_elements.append(elem)
            
            # テキストの長さでソートして上位を採用
            text_elements.sort(key=lambda e: len(e.text.strip()) if e.text else 0, reverse=True)
            
            for i, element in enumerate(text_elements[:10]):  # 上位10要素
                cleaned_text = self._clean_text(element.text)
                if len(cleaned_text) > 100:
                    section_name = f"その他のテキスト_{i+1}"
                    additional_text[section_name] = cleaned_text
        
        except Exception as e:
            logger.debug(f"追加テキスト抽出エラー: {e}")
            
        return additional_text
    
    def _prioritize_xbrl_files_emergency(self, file_list) -> List:
        """XBRLファイルの緊急優先順位付け"""
        def get_priority(file_info):
            filename = file_info.filename.lower()
            
            # 1. 連結財務諸表を最優先
            if any(keyword in filename for keyword in ['consolidated', 'consol', '連結']):
                return 1
            
            # 2. IFRS関連を次に優先
            if any(keyword in filename for keyword in ['ifrs']):
                return 2
            
            # 3. 財務諸表関連
            if any(keyword in filename for keyword in ['financial', '財務']):
                return 3
            
            # 4. 本体ファイル
            if any(keyword in filename for keyword in ['publicdoc', 'main']):
                return 4
            
            # 5. その他
            return 5
        
        sorted_files = sorted(file_list, key=lambda f: (get_priority(f), -f.file_size, f.filename))
        
        logger.info("XBRLファイル優先順位:")
        for i, f in enumerate(sorted_files[:3]):
            logger.info(f"  {i+1}. {f.filename} (優先度:{get_priority(f)})")
            
        return sorted_files

    def _extract_comprehensive_from_xml(self, xml_content: bytes) -> Dict[str, any]:
        """XMLファイルから財務データとテキストを抽出（緊急修正版）"""
        comprehensive_data = {'financial_data': {}, 'text_sections': {}, 'table_unit': 'yen'}
        
        try:
            root = ET.fromstring(xml_content)
            logger.info(f"XML解析開始: ルート要素={root.tag}")
            
            # 財務データ抽出（キャッシュフロー強化版）
            if self.cashflow_extractor:
                # 高精度キャッシュフロー抽出
                try:
                    cashflow_data = self.cashflow_extractor.extract_cashflow_for_comprehensive_analysis(root)
                    comprehensive_data['financial_data'].update(cashflow_data)
                    logger.info(f"高精度キャッシュフロー抽出: {len(cashflow_data)}項目")
                except Exception as e:
                    logger.warning(f"高精度抽出失敗、基本抽出にフォールバック: {e}")
                    basic_financial = self._extract_financial_data_emergency(root)
                    comprehensive_data['financial_data'].update(basic_financial)
            else:
                # 基本財務データ抽出
                basic_financial = self._extract_financial_data_emergency(root)
                comprehensive_data['financial_data'].update(basic_financial)
                logger.info(f"基本財務データ抽出: {len(basic_financial)}項目")
            
            # テキストデータ抽出
            text_sections = self._extract_text_sections_emergency(root)
            comprehensive_data['text_sections'] = text_sections
            
            logger.info(f"XML処理完了: 財務データ{len(comprehensive_data['financial_data'])}項目")
            
        except ET.ParseError as e:
            logger.error(f"XML解析エラー: {e}")
        except Exception as e:
            logger.error(f"包括データ抽出エラー: {e}")
            
        return comprehensive_data

    def _extract_financial_data_emergency(self, root: ET.Element) -> Dict[str, Decimal]:
        """緊急用財務データ抽出（現実性チェック強化版）"""
        financial_data = {}
        
        try:
            for data_type, element_names in self.financial_elements.items():
                values = []
                
                for element_name in element_names:
                    elements = self._find_financial_elements_by_pattern_emergency(root, element_name)
                    
                    for element in elements:
                        value = self._extract_financial_value_emergency(element, data_type)
                        if value is not None:
                            values.append(value)
                
                if values:
                    # 最も現実的な値を選択
                    selected_value = self._select_realistic_value_emergency(values, data_type)
                    financial_data[data_type] = selected_value
                    logger.info(f"財務データ確定: {data_type} = {selected_value}")
            
        except Exception as e:
            logger.error(f"緊急財務データ抽出エラー: {e}")
            
        return financial_data

    def _find_financial_elements_by_pattern_emergency(self, root: ET.Element, pattern: str) -> List[ET.Element]:
        """緊急用要素検索"""
        elements = []
        
        try:
            # 1. 直接検索
            for elem in root.iter():
                if pattern in elem.tag or (elem.text and pattern in elem.text):
                    elements.append(elem)
            
            # 2. 名前空間検索
            for ns_prefix, ns_uri in self.namespaces.items():
                try:
                    found = root.findall(f".//{{{ns_uri}}}{pattern}")
                    elements.extend(found)
                except:
                    continue
            
            # 重複除去
            unique_elements = list({(elem.tag, elem.text): elem for elem in elements}.values())
            
        except Exception as e:
            logger.debug(f"要素検索エラー ({pattern}): {e}")
            
        return unique_elements

    def _extract_financial_value_emergency(self, element: ET.Element, data_type: str) -> Optional[Decimal]:
        """緊急用財務値抽出（単位問題対応）"""
        try:
            text = element.text
            if not text or not text.strip():
                return None
            
            # 数値の正規化
            cleaned_text = re.sub(r'[,\s]+', '', text.strip())
            is_negative = cleaned_text.startswith('-') or '△' in cleaned_text
            
            # 数値部分の抽出
            number_match = re.search(r'[\d\.]+', cleaned_text)
            if not number_match:
                return None
            
            number_str = number_match.group()
            base_value = Decimal(number_str)
            
            # 単位調整（現実性チェック付き）
            final_value = self._apply_unit_conversion_emergency(base_value, element, data_type)
            
            if is_negative:
                final_value = -final_value
            
            return final_value
            
        except (InvalidOperation, ValueError):
            return None

    def _apply_unit_conversion_emergency(self, base_value: Decimal, element: ET.Element, data_type: str) -> Decimal:
        """緊急用単位変換（現実性重視）"""
        try:
            abs_base = abs(base_value)
            decimals = element.get('decimals', '0')
            
            # 現実的な範囲の定義
            realistic_ranges = {
                'operating_cf': (Decimal('1000000'), Decimal('50000000000000')),
                'investing_cf': (Decimal('1000000'), Decimal('30000000000000')),
                'financing_cf': (Decimal('1000000'), Decimal('30000000000000')),
                'net_sales': (Decimal('1000000'), Decimal('100000000000000')),
                'total_assets': (Decimal('10000000'), Decimal('1000000000000000')),
            }
            
            min_val, max_val = realistic_ranges.get(data_type, (Decimal('1000000'), Decimal('100000000000000')))
            
            # decimals属性による単位判定
            if decimals == '-6':  # 百万円単位の可能性
                # 値の大きさで判定
                if abs_base < 100000:  # 10万未満なら百万円単位として妥当
                    adjusted_value = base_value * Decimal('1000000')
                    if min_val <= abs(adjusted_value) <= max_val:
                        logger.info(f"{data_type} 百万円変換: {base_value} → {adjusted_value}")
                        return adjusted_value
                
                # 百万円変換すると異常値になる場合、そのまま使用
                if min_val <= abs_base <= max_val:
                    logger.info(f"{data_type} 変換せず使用: {base_value}")
                    return base_value
                    
            elif decimals == '-3':  # 千円単位
                if abs_base < 10000000:  # 1000万未満
                    adjusted_value = base_value * Decimal('1000')
                    if min_val <= abs(adjusted_value) <= max_val:
                        logger.info(f"{data_type} 千円変換: {base_value} → {adjusted_value}")
                        return adjusted_value
            
            # 異常に大きい値の段階的調整
            if abs_base > max_val:
                for divisor in [Decimal('1000'), Decimal('1000000'), Decimal('1000000000')]:
                    adjusted_value = base_value / divisor
                    if min_val <= abs(adjusted_value) <= max_val:
                        logger.warning(f"{data_type} 異常値調整(/{divisor}): {base_value} → {adjusted_value}")
                        return adjusted_value
            
            return base_value
            
        except Exception as e:
            logger.warning(f"単位変換エラー ({data_type}): {e}")
            return base_value

    def _select_realistic_value_emergency(self, values: List[Decimal], data_type: str) -> Decimal:
        """緊急用現実的な値の選択"""
        if len(values) == 1:
            return values[0]
        
        # 現実的な範囲内の値を優先
        realistic_ranges = {
            'operating_cf': (Decimal('1000000'), Decimal('50000000000000')),
            'investing_cf': (Decimal('1000000'), Decimal('30000000000000')),
            'financing_cf': (Decimal('1000000'), Decimal('30000000000000')),
        }
        
        min_val, max_val = realistic_ranges.get(data_type, (Decimal('1000000'), Decimal('100000000000000')))
        
        # 現実的な値を抽出
        realistic_values = [v for v in values if min_val <= abs(v) <= max_val]
        
        if realistic_values:
            # 現実的な値の中央値を選択
            realistic_values.sort(key=abs)
            selected = realistic_values[len(realistic_values) // 2]
            logger.info(f"{data_type} 現実的な値を選択: {selected} (候補{len(realistic_values)}個)")
            return selected
        else:
            # 現実的な値がない場合は最小値を選択
            values.sort(key=abs)
            selected = values[0]
            logger.warning(f"{data_type} 最小値を選択: {selected} (現実的な候補なし)")
            return selected

    def _extract_text_sections_emergency(self, root: ET.Element) -> Dict[str, str]:
        """緊急用テキスト抽出"""
        text_sections = {}
        
        try:
            # 長いテキストを含む要素を検索
            text_elements = []
            for elem in root.iter():
                if elem.text and len(elem.text.strip()) > 100:
                    text_elements.append(elem)
            
            # 長い順にソート
            text_elements.sort(key=lambda e: len(e.text.strip()), reverse=True)
            
            # 上位10個を取得
            for i, element in enumerate(text_elements[:10]):
                cleaned_text = self._clean_text_emergency(element.text)
                if len(cleaned_text) > 50:
                    section_name = f"テキストセクション_{i+1}"
                    text_sections[section_name] = cleaned_text
                    
        except Exception as e:
            logger.error(f"緊急テキスト抽出エラー: {e}")
            
        return text_sections

    def _clean_text_emergency(self, text: str) -> str:
        """緊急用テキストクリーニング"""
        if not text:
            return ""
        
        # HTMLタグ除去
        text = re.sub(r'<[^>]+>', '', text)
        # 連続する空白を単一のスペースに
        text = re.sub(r'\s+', ' ', text)
        # 不要な文字除去
        text = re.sub(r'[【】「」（）\(\)\[\]〔〕]', '', text)
        
        return text.strip()

    def _get_section_name(self, pattern: str) -> str:
        """要素パターンから日本語セクション名を取得"""
        section_names = {
            'BusinessRisks': '事業等のリスク',
            'BusinessRisksTextBlock': '事業リスク詳細',
            'BusinessPolicyBusinessEnvironmentIssuesAddressedEtc': '経営方針・経営環境',
            'ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlows': '経営者による財政状態分析',
            'ResearchAndDevelopmentActivities': '研究開発活動',
            'OverviewOfGroup': '企業集団の状況',
            'BusinessDescriptionTextBlock': '事業の内容',
            'BusinessResultsOfOperationsTextBlock': '業績概要',
            'CriticalAccountingPolicies': '重要な会計方針',
            'OverallBusinessResultsTextBlock': '全般的業績',
            'AnalysisOfBusinessResultsTextBlock': '業績分析',
            'CashFlowsTextBlock': 'キャッシュフロー',
            'FinancialPositionTextBlock': '財政状態',
            'ManagementPolicyTextBlock': '経営方針',
            'BusinessEnvironmentTextBlock': '事業環境',
            'CorporateGovernanceTextBlock': 'コーポレートガバナンス',
            'InternalControlSystemTextBlock': '内部統制システム',
            'ComplianceTextBlock': 'コンプライアンス',
            'RiskManagementTextBlock': 'リスク管理',
            'DividendPolicyTextBlock': '配当政策',
            'CapitalStructureTextBlock': '資本構成',
            'LiquidityAndCapitalResourcesTextBlock': '流動性と資本源泉',
            'ContractualObligationsTextBlock': '契約上の義務',
            'OffBalanceSheetArrangementsTextBlock': 'オフバランス取引',
            'CriticalAccountingEstimatesTextBlock': '重要な会計上の見積もり',
            'NewAccountingPronouncementsTextBlock': '新しい会計基準',
            'SegmentInformationTextBlock': 'セグメント情報',
            'GeographicInformationTextBlock': '地域別情報',
            'ProductServiceInformationTextBlock': '製品・サービス情報',
            'CustomerInformationTextBlock': '顧客情報',
            'SeasonalityTextBlock': '季節性',
            'InflationTextBlock': 'インフレーション',
            'EnvironmentalTextBlock': '環境',
            'LegalProceedingsTextBlock': '法的手続き',
            'UnregisteredSalesOfEquitySecuritiesTextBlock': '未登録株式売却',
            'RepurchasesOfEquitySecuritiesTextBlock': '自己株式取得',
            'SelectedFinancialDataTextBlock': '主要財務データ',
            'ManagementDiscussionAndAnalysisTextBlock': '経営陣による討議と分析',
        }
        return section_names.get(pattern, pattern)
    
    def _clean_text(self, text: str) -> str:
        """テキストクリーニング"""
        if not text:
            return ""
        
        try:
            # HTMLタグ除去
            text = re.sub(r'<[^>]+>', '', text)
            
            # 特殊文字の正規化
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'[\r\n\t]+', ' ', text)
            
            # 不要な文字除去
            text = re.sub(r'[【】「」（）\(\)\[\]〔〕]', '', text)
            
            # 数字のみの行を除去
            lines = text.split('\n')
            filtered_lines = [line for line in lines if not re.match(r'^\s*[\d,\.]+\s*$', line)]
            text = '\n'.join(filtered_lines)
            
        except Exception as e:
            logger.debug(f"テキストクリーニングエラー: {e}")
            
        return text.strip()


class EDINETXBRLService:
    """EDINET APIを使用してXBRLファイルを取得・解析するサービス（完全版）"""
    
    def __init__(self):
        self.extractor = XBRLFinancialExtractor()
    
    def get_comprehensive_analysis_from_document(self, document) -> Dict[str, any]:
        """DocumentMetadataから包括的な分析データを取得（キャッシュフロー強化版）"""
        try:
            if not document.xbrl_flag:
                logger.warning(f"XBRLファイルが利用できません: {document.doc_id}")
                return {'financial_data': {}, 'text_sections': {}, 'table_unit': 'yen'}
            
            # EDINET APIからXBRLファイルを取得
            from .edinet_api import EdinetAPIClient
            api_client = EdinetAPIClient.create_v2_client()
            
            logger.info(f"包括分析用XBRLファイル取得開始: {document.doc_id}")
            xbrl_data = api_client.get_document(document.doc_id, doc_type=1)
            
            # バイトデータから包括データ抽出
            comprehensive_data = self._extract_comprehensive_from_bytes(xbrl_data)
            
            # キャッシュフロー値の検証ログ
            financial_data = comprehensive_data.get('financial_data', {})
            if financial_data:
                logger.info(f"キャッシュフロー抽出結果: {document.doc_id}")
                logger.info(f"  営業CF: {financial_data.get('operating_cf', 'なし')}")
                logger.info(f"  投資CF: {financial_data.get('investing_cf', 'なし')}")
                logger.info(f"  財務CF: {financial_data.get('financing_cf', 'なし')}")
            
            logger.info(f"包括分析データ抽出完了: {document.doc_id} - 財務データ{len(financial_data)}項目")
            return comprehensive_data
            
        except Exception as e:
            logger.error(f"包括分析データ取得エラー: {document.doc_id} - {e}")
            return {'financial_data': {}, 'text_sections': {}, 'table_unit': 'yen'}
    
    def _extract_comprehensive_from_bytes(self, xbrl_bytes: bytes) -> Dict[str, any]:
        """バイトデータから包括データを抽出"""
        try:
            if xbrl_bytes[:4] == b'PK\x03\x04':
                return self.extractor._extract_comprehensive_from_zip(xbrl_bytes)
            else:
                return self.extractor._extract_comprehensive_from_xml(xbrl_bytes)
                
        except Exception as e:
            logger.error(f"包括データバイト解析エラー: {e}")
            return {'financial_data': {}, 'text_sections': {}, 'table_unit': 'yen'}

    def get_xbrl_text_from_document(self, document) -> Dict[str, str]:
        """DocumentMetadataからXBRLテキストを取得"""
        try:
            if not document.xbrl_flag:
                logger.warning(f"XBRLファイルが利用できません: {document.doc_id}")
                return {}
            
            # EDINET APIからXBRLファイルを取得
            from .edinet_api import EdinetAPIClient
            api_client = EdinetAPIClient.create_v2_client()
            
            # XBRLファイルダウンロード
            logger.info(f"XBRLファイル取得開始: {document.doc_id}")
            xbrl_data = api_client.get_document(document.doc_id, doc_type=1)  # 1=XBRL
            
            # バイトデータからテキスト抽出
            extracted_text = self._extract_text_from_bytes(xbrl_data)
            
            logger.info(f"XBRLテキスト抽出完了: {document.doc_id} - {len(extracted_text)}セクション")
            return extracted_text
            
        except Exception as e:
            logger.error(f"XBRLテキスト取得エラー: {document.doc_id} - {e}")
            return {}
    
    def _extract_text_from_bytes(self, xbrl_bytes: bytes) -> Dict[str, str]:
        """バイトデータからテキストを抽出"""
        try:
            # ZIPファイルかXMLファイルかを判断
            if xbrl_bytes[:4] == b'PK\x03\x04':  # ZIPファイルのマジックナンバー
                return self.extractor._extract_from_zip(xbrl_bytes)
            else:
                # XMLとして解析
                return self.extractor._extract_from_xml(xbrl_bytes)
                
        except Exception as e:
            logger.error(f"XBRLバイトデータ解析エラー: {e}")
            return {}