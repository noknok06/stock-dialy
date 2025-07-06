# earnings_analysis/services/xbrl_extractor.py（財務データ抽出機能追加版）
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

class XBRLFinancialExtractor:
    """XBRLファイルから財務データを抽出するクラス"""
    
    def __init__(self):
        # XBRL名前空間の定義
        self.namespaces = {
            'xbrl': 'http://www.xbrl.org/2003/instance',
            'xbrli': 'http://www.xbrl.org/2003/instance',
            'link': 'http://www.xbrl.org/2003/linkbase',
            'xlink': 'http://www.w3.org/1999/xlink',
            'jppfs': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2019-11-01/',
            'jpcrp': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2019-11-01/',
            'jpdei': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2019-11-01/',
        }
        
        # 財務データ要素のマッピング
        self.financial_elements = {
            # キャッシュフロー計算書
            'operating_cf': [
                'CashFlowsFromOperatingActivities',
                'NetCashProvidedByUsedInOperatingActivities',
                'OperatingCashFlow',
                '営業活動によるキャッシュ・フロー',
            ],
            'investing_cf': [
                'CashFlowsFromInvestingActivities', 
                'NetCashProvidedByUsedInInvestingActivities',
                'InvestingCashFlow',
                '投資活動によるキャッシュ・フロー',
            ],
            'financing_cf': [
                'CashFlowsFromFinancingActivities',
                'NetCashProvidedByUsedInFinancingActivities', 
                'FinancingCashFlow',
                '財務活動によるキャッシュ・フロー',
            ],
            
            # 損益計算書
            'net_sales': [
                'NetSales', 'Sales', 'Revenue', 'NetRevenues',
                '売上高', '営業収益',
            ],
            'operating_income': [
                'OperatingIncome', 'OperatingProfit',
                '営業利益', '営業損失',
            ],
            'ordinary_income': [
                'OrdinaryIncome', 'OrdinaryProfit', 
                '経常利益', '経常損失',
            ],
            'net_income': [
                'NetIncome', 'ProfitLoss', 'NetProfitLoss',
                '当期純利益', '当期純損失',
            ],
            
            # 貸借対照表
            'total_assets': [
                'TotalAssets', 'Assets',
                '資産合計', '総資産',
            ],
            'total_liabilities': [
                'TotalLiabilities', 'Liabilities', 
                '負債合計', '総負債',
            ],
            'net_assets': [
                'NetAssets', 'TotalEquity', 'ShareholdersEquity',
                '純資産合計', '株主資本合計',
            ],
        }
        
        # テキスト情報を含む要素名のパターン（既存）
        self.text_element_patterns = [
            'BusinessRisks',
            'BusinessPolicyBusinessEnvironmentIssuesAddressedEtc',
            'ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlows',
            'ResearchAndDevelopmentActivities',
            'OverviewOfGroup',
            'BusinessDescriptionTextBlock',
            'BusinessResultsOfOperationsTextBlock',
            'BusinessRisksTextBlock',
            'CriticalAccountingPolicies',
            'OverallBusinessResultsTextBlock',
            'AnalysisOfBusinessResultsTextBlock',
        ]
    
    def extract_comprehensive_data_from_xbrl_url(self, xbrl_url: str) -> Dict[str, any]:
        """XBRLファイルから財務データとテキストを包括的に抽出"""
        try:
            # キャッシュチェック
            cache_key = f"xbrl_comprehensive_{xbrl_url.split('/')[-1]}"
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"XBRL包括データ キャッシュヒット: {xbrl_url}")
                return cached_result
            
            # XBRLファイルをダウンロード
            logger.info(f"XBRL包括データダウンロード開始: {xbrl_url}")
            response = requests.get(xbrl_url, timeout=60)
            response.raise_for_status()
            
            # ZIPファイルかXMLファイルかを判断
            if xbrl_url.endswith('.zip'):
                comprehensive_data = self._extract_comprehensive_from_zip(response.content)
            else:
                comprehensive_data = self._extract_comprehensive_from_xml(response.content)
            
            # キャッシュに保存（2時間）
            cache.set(cache_key, comprehensive_data, 7200)
            
            logger.info(f"XBRL包括データ抽出完了: 財務データ{len(comprehensive_data.get('financial_data', {}))}項目, テキスト{len(comprehensive_data.get('text_sections', {}))}セクション")
            return comprehensive_data
            
        except Exception as e:
            logger.error(f"XBRL包括データ抽出エラー: {xbrl_url} - {e}")
            return {'financial_data': {}, 'text_sections': {}}
    
    def _extract_comprehensive_from_zip(self, zip_content: bytes) -> Dict[str, any]:
        """ZIPファイルから財務データとテキストを抽出"""
        comprehensive_data = {'financial_data': {}, 'text_sections': {}}
        
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
                for file_info in zip_file.filelist:
                    if file_info.filename.endswith('.xbrl'):
                        with zip_file.open(file_info) as xbrl_file:
                            xbrl_content = xbrl_file.read()
                            file_data = self._extract_comprehensive_from_xml(xbrl_content)
                            
                            # データをマージ
                            comprehensive_data['financial_data'].update(file_data.get('financial_data', {}))
                            comprehensive_data['text_sections'].update(file_data.get('text_sections', {}))
                            
        except Exception as e:
            logger.error(f"ZIP包括展開エラー: {e}")
            
        return comprehensive_data
    
    def _extract_comprehensive_from_xml(self, xml_content: bytes) -> Dict[str, any]:
        """XMLファイルから財務データとテキストを抽出"""
        comprehensive_data = {'financial_data': {}, 'text_sections': {}}
        
        try:
            # XMLパース
            root = ET.fromstring(xml_content)
            
            # 財務データ抽出
            comprehensive_data['financial_data'] = self._extract_financial_data(root)
            
            # テキストデータ抽出（既存機能）
            comprehensive_data['text_sections'] = self._extract_text_sections(root)
            
            # 会計期間情報の抽出
            comprehensive_data['period_info'] = self._extract_period_info(root)
            
        except ET.ParseError as e:
            logger.error(f"XML包括解析エラー: {e}")
        except Exception as e:
            logger.error(f"包括データ抽出エラー: {e}")
            
        return comprehensive_data
    
    def _extract_financial_data(self, root: ET.Element) -> Dict[str, Decimal]:
        """財務データの抽出"""
        financial_data = {}
        
        for data_type, element_names in self.financial_elements.items():
            values = []
            
            for element_name in element_names:
                # 各要素を検索
                found_elements = self._find_financial_elements_by_pattern(root, element_name)
                
                for element in found_elements:
                    value = self._extract_financial_value(element)
                    if value is not None:
                        values.append(value)
            
            # 最も信頼できる値を選択（通常は最新の値）
            if values:
                # 絶対値が最大の値を採用（より具体的な数値を優先）
                financial_data[data_type] = max(values, key=abs)
                logger.debug(f"財務データ抽出: {data_type} = {financial_data[data_type]}")
        
        return financial_data
    
    def _find_financial_elements_by_pattern(self, root: ET.Element, pattern: str) -> List[ET.Element]:
        """財務要素をパターンで検索"""
        elements = []
        
        # 直接検索
        for elem in root.iter():
            if pattern in elem.tag or (elem.text and pattern in elem.text):
                elements.append(elem)
        
        # 名前空間を考慮した検索
        for ns_prefix, ns_uri in self.namespaces.items():
            try:
                found = root.findall(f".//{{{ns_uri}}}{pattern}")
                elements.extend(found)
            except:
                continue
        
        return elements
        
    def _extract_financial_value(self, element: ET.Element) -> Optional[Decimal]:
            """要素から財務値を抽出"""
            try:
                # 要素のテキストから数値を抽出
                text = element.text
                if not text:
                    return None
                
                # 数値の正規化
                cleaned_text = re.sub(r'[,\s]+', '', text.strip())
                
                # 負の値のチェック
                is_negative = cleaned_text.startswith('-') or '△' in cleaned_text
                
                # 数値部分の抽出
                number_match = re.search(r'[\d\.]+', cleaned_text)
                if not number_match:
                    return None
                
                number_str = number_match.group()
                value = Decimal(number_str)
                
                # 単位の調整（千円、百万円等）
                unit_multiplier = self._determine_unit_multiplier(element, text)
                value *= unit_multiplier
                
                # 異常値チェック（日本企業の現実的な範囲）
                max_reasonable_value = Decimal('1000000000000000')  # 1000兆円を上限
                if abs(value) > max_reasonable_value:
                    logger.warning(f"異常に大きな財務値を検出: {value} → 1/1000に調整")
                    value = value / Decimal('1000')  # 1000で割る
                    
                    # それでも大きすぎる場合はさらに調整
                    if abs(value) > max_reasonable_value:
                        logger.warning(f"さらに異常値を検出: {value} → 1/1000000に調整")
                        value = value / Decimal('1000000')  # さらに100万で割る
                
                if is_negative:
                    value = -value
                    
                logger.debug(f"財務値抽出: {element.tag} = {value} (元テキスト: {text})")
                return value
                
            except (InvalidOperation, ValueError) as e:
                logger.debug(f"財務値抽出エラー: {element.tag} - {e}")
                return None
                        
    def _determine_unit_multiplier(self, element: ET.Element, text: str) -> Decimal:
        """単位倍率の判定"""
        # 属性から単位情報を取得
        unit_ref = element.get('unitRef', '')
        decimals = element.get('decimals', '')
        
        # テキストから単位を推定
        if '千円' in text or 'thousands' in text.lower():
            return Decimal('1000')
        elif '百万円' in text or 'millions' in text.lower():
            return Decimal('1000000')
        elif '億円' in text or 'billions' in text.lower():
            return Decimal('100000000')
        
        # decimals属性から推定
        if decimals:
            try:
                decimal_places = int(decimals)
                if decimal_places == -3:
                    return Decimal('1000')
                elif decimal_places == -6:
                    return Decimal('1000000')
            except ValueError:
                pass
        
        return Decimal('1')  # デフォルトは1（円単位）
    
    def _extract_text_sections(self, root: ET.Element) -> Dict[str, str]:
        """テキストセクションの抽出（既存機能）"""
        extracted_text = {}
        
        for pattern in self.text_element_patterns:
            elements = self._find_elements_by_pattern(root, pattern)
            
            for element in elements:
                text_content = self._extract_element_text(element)
                if text_content and len(text_content.strip()) > 50:
                    section_name = self._get_section_name(pattern)
                    extracted_text[section_name] = text_content
        
        # その他のテキスト要素も検索
        additional_text = self._extract_additional_text_elements(root)
        extracted_text.update(additional_text)
        
        return extracted_text
    
    def _extract_period_info(self, root: ET.Element) -> Dict[str, str]:
        """会計期間情報の抽出"""
        period_info = {}
        
        # 期間情報を検索
        period_patterns = [
            'CurrentPeriodStartDate', 'CurrentPeriodEndDate',
            'FiscalYearStartDate', 'FiscalYearEndDate',
            '当期開始日', '当期終了日',
        ]
        
        for pattern in period_patterns:
            elements = self._find_elements_by_pattern(root, pattern)
            for element in elements:
                if element.text:
                    period_info[pattern] = element.text.strip()
        
        return period_info
    
    # 既存のメソッド（変更なし）
    def _find_elements_by_pattern(self, root: ET.Element, pattern: str) -> List[ET.Element]:
        """パターンに一致する要素を検索"""
        elements = []
        
        for elem in root.iter():
            if pattern in elem.tag:
                elements.append(elem)
        
        for ns_prefix, ns_uri in self.namespaces.items():
            try:
                found = root.findall(f".//{{{ns_uri}}}{pattern}")
                elements.extend(found)
            except:
                continue
        
        return elements
    
    def _extract_element_text(self, element: ET.Element) -> str:
        """要素からテキストを抽出"""
        text_parts = []
        
        if element.text:
            text_parts.append(element.text.strip())
        
        for child in element:
            child_text = self._extract_element_text(child)
            if child_text:
                text_parts.append(child_text)
        
        if element.tail:
            text_parts.append(element.tail.strip())
        
        full_text = ' '.join(text_parts)
        cleaned_text = self._clean_text(full_text)
        
        return cleaned_text
    
    def _extract_additional_text_elements(self, root: ET.Element) -> Dict[str, str]:
        """その他のテキスト要素を抽出"""
        additional_text = {}
        
        text_elements = []
        for elem in root.iter():
            if elem.text and len(elem.text.strip()) > 100:
                text_elements.append(elem)
        
        text_elements.sort(key=lambda e: len(e.text.strip()) if e.text else 0, reverse=True)
        
        for i, element in enumerate(text_elements[:10]):
            cleaned_text = self._clean_text(element.text)
            if len(cleaned_text) > 100:
                section_name = f"その他のテキスト_{i+1}"
                additional_text[section_name] = cleaned_text
        
        return additional_text
    
    def _clean_text(self, text: str) -> str:
        """テキストクリーニング"""
        if not text:
            return ""
        
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[\r\n\t]+', ' ', text)
        text = re.sub(r'[【】「」（）\(\)\[\]〔〕]', '', text)
        
        lines = text.split('\n')
        filtered_lines = [line for line in lines if not re.match(r'^\s*[\d,\.]+\s*$', line)]
        text = '\n'.join(filtered_lines)
        
        return text.strip()
    
    def _get_section_name(self, pattern: str) -> str:
        """要素パターンから日本語セクション名を取得"""
        section_names = {
            'BusinessRisks': '事業等のリスク',
            'BusinessPolicyBusinessEnvironmentIssuesAddressedEtc': '経営方針・経営環境',
            'ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlows': '経営者による分析',
            'ResearchAndDevelopmentActivities': '研究開発活動',
            'OverviewOfGroup': '企業集団の状況',
            'BusinessDescriptionTextBlock': '事業の内容',
            'BusinessResultsOfOperationsTextBlock': '業績概要',
            'BusinessRisksTextBlock': '事業リスク',
            'CriticalAccountingPolicies': '重要な会計方針',
            'OverallBusinessResultsTextBlock': '全般的業績',
            'AnalysisOfBusinessResultsTextBlock': '業績分析',
        }
        return section_names.get(pattern, pattern)


class EDINETXBRLService:
    """EDINET APIを使用してXBRLファイルを取得・解析するサービス（拡張版）"""
    
    def __init__(self):
        self.extractor = XBRLFinancialExtractor()
    
    def get_comprehensive_analysis_from_document(self, document) -> Dict[str, any]:
        """DocumentMetadataから包括的な分析データを取得"""
        try:
            if not document.xbrl_flag:
                logger.warning(f"XBRLファイルが利用できません: {document.doc_id}")
                return {'financial_data': {}, 'text_sections': {}}
            
            # EDINET APIからXBRLファイルを取得
            from .edinet_api import EdinetAPIClient
            api_client = EdinetAPIClient.create_v2_client()
            
            # XBRLファイルダウンロード
            logger.info(f"包括分析用XBRLファイル取得開始: {document.doc_id}")
            xbrl_data = api_client.get_document(document.doc_id, doc_type=1)
            
            # バイトデータから包括データ抽出
            comprehensive_data = self._extract_comprehensive_from_bytes(xbrl_data)
            
            logger.info(f"包括分析データ抽出完了: {document.doc_id} - 財務データ{len(comprehensive_data.get('financial_data', {}))}項目")
            return comprehensive_data
            
        except Exception as e:
            logger.error(f"包括分析データ取得エラー: {document.doc_id} - {e}")
            return {'financial_data': {}, 'text_sections': {}}
    
    def _extract_comprehensive_from_bytes(self, xbrl_bytes: bytes) -> Dict[str, any]:
        """バイトデータから包括データを抽出"""
        try:
            if xbrl_bytes[:4] == b'PK\x03\x04':
                return self.extractor._extract_comprehensive_from_zip(xbrl_bytes)
            else:
                return self.extractor._extract_comprehensive_from_xml(xbrl_bytes)
                
        except Exception as e:
            logger.error(f"包括データバイト解析エラー: {e}")
            return {'financial_data': {}, 'text_sections': {}}
    
    # 既存メソッド（下位互換性のため保持）
    def get_xbrl_text_from_document(self, document) -> Dict[str, str]:
        """テキストのみを取得（既存機能との互換性）"""
        comprehensive_data = self.get_comprehensive_analysis_from_document(document)
        return comprehensive_data.get('text_sections', {})
        
    def debug_xbrl_structure(self, xml_content: bytes, max_elements: int = 50):
        """XBRLファイル構造のデバッグ情報を出力"""
        try:
            root = ET.fromstring(xml_content)
            
            logger.info("=== XBRL構造デバッグ ===")
            logger.info(f"ルート要素: {root.tag}")
            logger.info(f"名前空間: {root.nsmap if hasattr(root, 'nsmap') else 'N/A'}")
            
            # 財務データ関連要素を詳細に調査
            logger.info("\n=== 営業CF関連要素の詳細調査 ===")
            cf_elements = ['CashFlowsFromOperatingActivities', '営業活動', 'OperatingCashFlow']
            
            for pattern in cf_elements:
                elements = self._find_elements_by_pattern(root, pattern)
                logger.info(f"\n'{pattern}' で検索: {len(elements)}個発見")
                
                for i, elem in enumerate(elements[:5]):  # 最初の5個のみ
                    logger.info(f"  要素{i+1}:")
                    logger.info(f"    タグ: {elem.tag}")
                    logger.info(f"    属性: {dict(elem.attrib)}")
                    logger.info(f"    テキスト: '{elem.text}'")
                    logger.info(f"    親要素: {elem.getparent().tag if elem.getparent() is not None else 'None'}")
            
            # 全要素の統計
            logger.info(f"\n=== 全要素統計 ===")
            all_elements = list(root.iter())
            logger.info(f"総要素数: {len(all_elements)}")
            
            # タグ名の頻度分析
            tag_counts = {}
            for elem in all_elements:
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag  # 名前空間を除去
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            # 頻度の高いタグトップ20
            sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
            logger.info("頻度の高いタグ(トップ20):")
            for tag, count in sorted_tags[:20]:
                logger.info(f"  {tag}: {count}回")
            
            # 数値を含む要素の調査
            logger.info(f"\n=== 数値データ要素の調査 ===")
            numeric_elements = []
            for elem in all_elements[:max_elements]:
                if elem.text and elem.text.strip():
                    text = elem.text.strip()
                    if re.search(r'[\d,]+', text):  # 数値を含む要素
                        try:
                            # カンマを除去して数値に変換を試行
                            clean_text = re.sub(r'[,\s]+', '', text)
                            if re.match(r'^-?[\d\.]+$', clean_text):
                                numeric_value = float(clean_text)
                                if abs(numeric_value) > 1000000:  # 100万以上の値
                                    numeric_elements.append({
                                        'tag': elem.tag.split('}')[-1],
                                        'value': numeric_value,
                                        'original_text': text,
                                        'attributes': dict(elem.attrib)
                                    })
                        except (ValueError, TypeError):
                            pass
            
            # 大きな数値の要素をソート
            numeric_elements.sort(key=lambda x: abs(x['value']), reverse=True)
            
            logger.info("大きな数値を持つ要素(トップ10):")
            for elem in numeric_elements[:10]:
                logger.info(f"  {elem['tag']}: {elem['value']:,.0f} (元テキスト: '{elem['original_text']}')")
                logger.info(f"    属性: {elem['attributes']}")
            
        except Exception as e:
            logger.error(f"XBRL構造デバッグエラー: {e}")

    # EDINETXBRLService クラスに追加
    def debug_document_xbrl(self, document) -> Dict[str, any]:
        """書類のXBRL内容をデバッグ"""
        try:
            from .edinet_api import EdinetAPIClient
            api_client = EdinetAPIClient.create_v2_client()
            
            logger.info(f"デバッグ用XBRLファイル取得: {document.doc_id}")
            xbrl_data = api_client.get_document(document.doc_id, doc_type=1)
            
            # 構造解析
            if xbrl_data[:4] == b'PK\x03\x04':
                # ZIPファイルの場合
                self.extractor.debug_xbrl_structure_from_zip(xbrl_data)
            else:
                # XMLファイルの場合
                self.extractor.debug_xbrl_structure(xbrl_data)
            
            return {'status': 'debug_completed'}
            
        except Exception as e:
            logger.error(f"XBRL デバッグエラー: {document.doc_id} - {e}")
            return {'status': 'debug_failed', 'error': str(e)}