# earnings_analysis/services/xbrl_extractor.py
import xml.etree.ElementTree as ET
import re
import requests
import zipfile
import io
import logging
from typing import Dict, List, Optional, Tuple
from django.core.cache import cache

logger = logging.getLogger(__name__)

class XBRLTextExtractor:
    """XBRLファイルからテキスト情報を抽出するクラス"""
    
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
        
        # テキスト情報を含む要素名のパターン
        self.text_element_patterns = [
            'BusinessRisks',  # 事業等のリスク
            'BusinessPolicyBusinessEnvironmentIssuesAddressedEtc',  # 経営方針、経営環境
            'ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlows',  # 経営者による財政状態等の分析
            'ResearchAndDevelopmentActivities',  # 研究開発活動
            'OverviewOfGroup',  # 企業集団の状況
            'BusinessDescriptionTextBlock',  # 事業の内容
            'BusinessResultsOfOperationsTextBlock',  # 業績等の概要
            'BusinessRisksTextBlock',  # 事業等のリスク
            'CriticalAccountingPolicies',  # 重要な会計方針
            'OverallBusinessResultsTextBlock',  # 全般的な業績
            'AnalysisOfBusinessResultsTextBlock',  # 業績分析
        ]
    
    def extract_text_from_xbrl_url(self, xbrl_url: str) -> Dict[str, str]:
        """XBRLファイルのURLからテキストを抽出"""
        try:
            # キャッシュチェック
            cache_key = f"xbrl_text_{xbrl_url.split('/')[-1]}"
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"XBRLテキスト キャッシュヒット: {xbrl_url}")
                return cached_result
            
            # XBRLファイルをダウンロード
            logger.info(f"XBRLファイルダウンロード開始: {xbrl_url}")
            response = requests.get(xbrl_url, timeout=60)
            response.raise_for_status()
            
            # ZIPファイルかXMLファイルかを判断
            if xbrl_url.endswith('.zip'):
                extracted_text = self._extract_from_zip(response.content)
            else:
                extracted_text = self._extract_from_xml(response.content)
            
            # キャッシュに保存（1時間）
            cache.set(cache_key, extracted_text, 3600)
            
            logger.info(f"XBRLテキスト抽出完了: {len(extracted_text)} セクション")
            return extracted_text
            
        except Exception as e:
            logger.error(f"XBRLテキスト抽出エラー: {xbrl_url} - {e}")
            return {}
    
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
    
    def _find_elements_by_pattern(self, root: ET.Element, pattern: str) -> List[ET.Element]:
        """パターンに一致する要素を検索"""
        elements = []
        
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
        
        return elements
    
    def _extract_element_text(self, element: ET.Element) -> str:
        """要素からテキストを抽出"""
        text_parts = []
        
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
        
        return cleaned_text
    
    def _extract_additional_text_elements(self, root: ET.Element) -> Dict[str, str]:
        """その他のテキスト要素を抽出"""
        additional_text = {}
        
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
        
        return additional_text
    
    def _clean_text(self, text: str) -> str:
        """テキストクリーニング"""
        if not text:
            return ""
        
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
    """EDINET APIを使用してXBRLファイルを取得・解析するサービス"""
    
    def __init__(self):
        self.extractor = XBRLTextExtractor()
    
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