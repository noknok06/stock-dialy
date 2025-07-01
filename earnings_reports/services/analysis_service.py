"""
earnings_reports/services/analysis_service.py
決算書類の分析サービス
"""

import re
import zipfile
import io
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from django.conf import settings
from django.utils import timezone

from ..models import Analysis, SentimentAnalysis, CashFlowAnalysis
from .edinet_service import EDINETService

logger = logging.getLogger('earnings_analysis')


class EarningsAnalysisService:
    """決算分析サービス"""
    
    def __init__(self):
        """初期化"""
        self.edinet_service = EDINETService(settings.EDINET_API_KEY)
        
        # 感情分析用キーワード辞書
        self.sentiment_keywords = {
            'positive': [
                '成長', '拡大', '増加', '向上', '改善', '好調', '堅調', '順調',
                '強化', '拡充', '積極的', '前向き', '期待', '自信', '確信',
                '革新', '変革', '進歩', '発展', '躍進', '飛躍', '突破'
            ],
            'negative': [
                '減少', '低下', '悪化', '困難', '課題', '問題', '懸念', '不安',
                '厳しい', '苦戦', '低迷', '停滞', '遅れ', '縮小', '減退',
                'リスク', '脅威', '危機', '損失', '赤字', '不振', '不調'
            ],
            'confidence': [
                '確実', '確信', '自信', '見通し', '計画通り', '予定通り',
                '達成', '実現', '可能', '期待', '目標', '戦略的', '安定'
            ],
            'uncertainty': [
                '不確実', '不透明', '未定', '検討中', '様子見', '慎重',
                '困難', '予測困難', '判断', '状況次第', '不明', '未確定'
            ],
            'growth': [
                '成長戦略', '事業拡大', '新規事業', '投資', 'DX', 'デジタル',
                '海外展開', 'グローバル', 'イノベーション', '新商品', '新サービス'
            ],
            'risk': [
                'リスク', '不確実性', '変動', '影響', '懸念', '課題',
                '競争激化', '原材料高', '人手不足', '為替', '金利',
                'コロナ', 'パンデミック', '地政学', '規制', '法改正'
            ]
        }
    
    def execute_analysis(self, analysis: Analysis) -> bool:
        """
        分析実行メイン関数
        
        Args:
            analysis: 分析オブジェクト
            
        Returns:
            bool: 成功した場合True
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"分析開始: {analysis.document.company.name} - {analysis.document.doc_description}")
            
            # 1. 書類ダウンロード
            document_content = self._download_document(analysis.document.doc_id)
            if not document_content:
                raise Exception("書類のダウンロードに失敗しました")
            
            # 2. テキスト抽出
            extracted_text = self._extract_text_from_zip(document_content)
            if not extracted_text:
                raise Exception("テキストの抽出に失敗しました")
            
            # 3. 感情分析実行
            if analysis.settings_json.get('include_sentiment', True):
                sentiment_result = self._perform_sentiment_analysis(extracted_text, analysis.settings_json)
                self._save_sentiment_analysis(analysis, sentiment_result)
            
            # 4. キャッシュフロー分析実行
            if analysis.settings_json.get('include_cashflow', True):
                cashflow_result = self._perform_cashflow_analysis(extracted_text, analysis.settings_json)
                self._save_cashflow_analysis(analysis, cashflow_result)
            
            # 5. 総合スコア計算
            overall_score = self._calculate_overall_score(analysis)
            
            # 6. 分析完了
            analysis.status = 'completed'
            analysis.overall_score = overall_score
            analysis.confidence_level = self._determine_confidence_level(analysis)
            analysis.processing_time = (datetime.now() - start_time).total_seconds()
            analysis.save()
            
            logger.info(f"分析完了: {analysis.document.company.name} - スコア: {overall_score}")
            return True
            
        except Exception as e:
            logger.error(f"分析エラー: {str(e)}")
            analysis.status = 'failed'
            analysis.error_message = str(e)
            analysis.processing_time = (datetime.now() - start_time).total_seconds()
            analysis.save()
            return False
    
    def _download_document(self, doc_id: str) -> Optional[bytes]:
        """書類ダウンロード"""
        try:
            return self.edinet_service.download_document(doc_id)
        except Exception as e:
            logger.error(f"書類ダウンロードエラー: {str(e)}")
            return None
    
    def _extract_text_from_zip(self, zip_content: bytes) -> str:
        """
        ZIPファイルからテキストを抽出
        
        Args:
            zip_content: ZIPファイルのバイナリデータ
            
        Returns:
            str: 抽出されたテキスト
        """
        extracted_text = ""
        
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
                # XBRLファイルを優先的に処理
                for file_info in zip_file.filelist:
                    filename = file_info.filename.lower()
                    
                    # 対象ファイルの判定
                    if any(ext in filename for ext in ['.xbrl', '.xml', '.htm', '.html']):
                        try:
                            file_content = zip_file.read(file_info.filename)
                            
                            # エンコーディング判定・変換
                            text = self._decode_file_content(file_content)
                            
                            # XMLタグを除去して純粋なテキストを抽出
                            clean_text = self._clean_xml_text(text)
                            
                            if clean_text:
                                extracted_text += clean_text + "\n\n"
                                
                        except Exception as e:
                            logger.warning(f"ファイル{filename}の処理エラー: {str(e)}")
                            continue
            
            logger.info(f"テキスト抽出完了: {len(extracted_text)}文字")
            return extracted_text
            
        except Exception as e:
            logger.error(f"テキスト抽出エラー: {str(e)}")
            return ""
    
    def _decode_file_content(self, content: bytes) -> str:
        """ファイル内容のデコード"""
        encodings = ['utf-8', 'shift_jis', 'euc-jp', 'iso-2022-jp']
        
        for encoding in encodings:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        
        # すべて失敗した場合はerrors='ignore'で強制デコード
        return content.decode('utf-8', errors='ignore')
    
    def _clean_xml_text(self, xml_text: str) -> str:
        """XMLテキストからタグを除去して純粋なテキストを抽出"""
        
        # XMLタグを除去
        text = re.sub(r'<[^>]+>', '', xml_text)
        
        # HTMLエンティティをデコード
        text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&apos;', "'")
        
        # 余分な空白・改行を整理
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        
        # 意味のないテキストを除去
        text = re.sub(r'^[0-9\s\-\.\,]+$', '', text, flags=re.MULTILINE)
        
        return text.strip()
    
    def _perform_sentiment_analysis(self, text: str, settings: Dict) -> Dict:
        """
        感情分析実行
        
        Args:
            text: 分析対象テキスト
            settings: 分析設定
            
        Returns:
            Dict: 感情分析結果
        """
        result = {
            'positive_score': 0.0,
            'negative_score': 0.0,
            'neutral_score': 0.0,
            'confidence_keywords_count': 0,
            'uncertainty_keywords_count': 0,
            'growth_keywords_count': 0,
            'risk_keywords_count': 0,
            'risk_severity': 'low',
            'key_phrases': [],
            'risk_phrases': []
        }
        
        # テキストを小文字に変換して検索
        text_lower = text.lower()
        
        # 各カテゴリのキーワードカウント
        for category, keywords in self.sentiment_keywords.items():
            count = sum(text_lower.count(keyword) for keyword in keywords)
            
            if category == 'positive':
                result['positive_score'] = min(100, count * 2)  # 最大100
            elif category == 'negative':
                result['negative_score'] = min(100, count * 2)
            elif category == 'confidence':
                result['confidence_keywords_count'] = count
            elif category == 'uncertainty':
                result['uncertainty_keywords_count'] = count
            elif category == 'growth':
                result['growth_keywords_count'] = count
            elif category == 'risk':
                result['risk_keywords_count'] = count
        
        # ニュートラルスコア計算
        total_sentiment = result['positive_score'] + result['negative_score']
        result['neutral_score'] = max(0, 100 - total_sentiment)
        
        # スコア正規化
        if total_sentiment > 0:
            result['positive_score'] = (result['positive_score'] / total_sentiment) * 100
            result['negative_score'] = (result['negative_score'] / total_sentiment) * 100
            result['neutral_score'] = 0
        else:
            result['neutral_score'] = 100
        
        # リスク深刻度判定
        risk_count = result['risk_keywords_count']
        if risk_count >= 10:
            result['risk_severity'] = 'critical'
        elif risk_count >= 5:
            result['risk_severity'] = 'high'
        elif risk_count >= 2:
            result['risk_severity'] = 'medium'
        else:
            result['risk_severity'] = 'low'
        
        # 重要フレーズ抽出
        result['key_phrases'] = self._extract_key_phrases(text, 'positive')
        result['risk_phrases'] = self._extract_key_phrases(text, 'risk')
        
        # カスタムキーワード分析
        custom_keywords = settings.get('custom_keywords', [])
        if custom_keywords:
            custom_counts = {}
            for keyword in custom_keywords:
                custom_counts[keyword] = text_lower.count(keyword.lower())
            result['custom_keyword_counts'] = custom_counts
        
        return result
    
    def _extract_key_phrases(self, text: str, category: str, max_phrases: int = 10) -> List[str]:
        """重要フレーズの抽出"""
        
        keywords = self.sentiment_keywords.get(category, [])
        phrases = []
        
        for keyword in keywords:
            # キーワード周辺のテキストを抽出
            pattern = f'.{{0,50}}{re.escape(keyword)}.{{0,50}}'
            matches = re.findall(pattern, text, re.IGNORECASE)
            
            for match in matches[:2]:  # 各キーワードにつき最大2フレーズ
                clean_phrase = re.sub(r'\s+', ' ', match).strip()
                if len(clean_phrase) > 10 and clean_phrase not in phrases:
                    phrases.append(clean_phrase)
        
        return phrases[:max_phrases]
    
    def _perform_cashflow_analysis(self, text: str, settings: Dict) -> Dict:
        """
        キャッシュフロー分析実行
        
        Args:
            text: 分析対象テキスト
            settings: 分析設定
            
        Returns:
            Dict: キャッシュフロー分析結果
        """
        result = {
            'operating_cf': None,
            'investing_cf': None,
            'financing_cf': None,
            'free_cf': None,
            'pattern': 'other',
            'pattern_score': 0.0,
            'operating_cf_growth': None,
            'investing_cf_growth': None,
            'financing_cf_growth': None,
            'cf_adequacy_ratio': None,
            'cf_quality_score': 50.0,
            'interpretation': '',
            'risk_factors': []
        }
        
        # キャッシュフロー金額の抽出
        cf_amounts = self._extract_cashflow_amounts(text)
        result.update(cf_amounts)
        
        # パターン分類
        if all(cf_amounts[key] is not None for key in ['operating_cf', 'investing_cf', 'financing_cf']):
            pattern_info = self._classify_cashflow_pattern(
                cf_amounts['operating_cf'],
                cf_amounts['investing_cf'],
                cf_amounts['financing_cf']
            )
            result.update(pattern_info)
        
        # 品質スコア計算
        result['cf_quality_score'] = self._calculate_cf_quality_score(result)
        
        # 解釈生成
        result['interpretation'] = self._generate_cf_interpretation(result)
        
        # リスク要因の特定
        result['risk_factors'] = self._identify_cf_risk_factors(result)
        
        return result
    
    def _extract_cashflow_amounts(self, text: str) -> Dict:
        """テキストからキャッシュフロー金額を抽出"""
        
        cf_amounts = {
            'operating_cf': None,
            'investing_cf': None,
            'financing_cf': None,
            'free_cf': None
        }
        
        # キャッシュフロー関連の正規表現パターン
        patterns = {
            'operating_cf': [
                r'営業活動.*?キャッシュ.*?フロー.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'営業.*?CF.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'Operating.*?cash.*?flow.*?([△▲\-]?\d{1,3}(?:,\d{3})*)'
            ],
            'investing_cf': [
                r'投資活動.*?キャッシュ.*?フロー.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'投資.*?CF.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'Investing.*?cash.*?flow.*?([△▲\-]?\d{1,3}(?:,\d{3})*)'
            ],
            'financing_cf': [
                r'財務活動.*?キャッシュ.*?フロー.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'財務.*?CF.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'Financing.*?cash.*?flow.*?([△▲\-]?\d{1,3}(?:,\d{3})*)'
            ],
            'free_cf': [
                r'フリー.*?キャッシュ.*?フロー.*?([△▲\-]?\d{1,3}(?:,\d{3})*)',
                r'Free.*?cash.*?flow.*?([△▲\-]?\d{1,3}(?:,\d{3})*)'
            ]
        }
        
        for cf_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
                
                if matches:
                    # 最初にマッチした金額を使用
                    amount_str = matches[0].replace(',', '').replace('△', '-').replace('▲', '-')
                    
                    try:
                        cf_amounts[cf_type] = int(amount_str)
                        break
                    except ValueError:
                        continue
        
        return cf_amounts
    
    def _classify_cashflow_pattern(self, operating_cf: int, investing_cf: int, financing_cf: int) -> Dict:
        """キャッシュフローパターンの分類"""
        
        # パターン判定
        if operating_cf > 0 and investing_cf < 0 and financing_cf < 0:
            pattern = 'ideal'
            score = 80
        elif operating_cf > 0 and investing_cf < 0 and financing_cf > 0:
            pattern = 'growth'
            score = 60
        elif operating_cf > 0 and investing_cf > 0 and financing_cf < 0:
            pattern = 'restructuring'
            score = 40
        elif operating_cf < 0 and investing_cf > 0 and financing_cf > 0:
            pattern = 'danger'
            score = -20
        else:
            pattern = 'other'
            score = 30
        
        return {
            'pattern': pattern,
            'pattern_score': score
        }
    
    def _calculate_cf_quality_score(self, cf_data: Dict) -> float:
        """キャッシュフロー品質スコア計算"""
        
        score = 50.0  # ベーススコア
        
        # 営業CFがプラスなら加点
        if cf_data.get('operating_cf', 0) > 0:
            score += 20
        
        # パターンスコアを反映
        pattern_score = cf_data.get('pattern_score', 0)
        score += pattern_score * 0.3
        
        # フリーCFがプラスなら加点
        if cf_data.get('free_cf', 0) > 0:
            score += 15
        
        return max(0, min(100, score))
    
    def _generate_cf_interpretation(self, cf_data: Dict) -> str:
        """キャッシュフロー解釈文生成"""
        
        pattern = cf_data.get('pattern', 'other')
        operating_cf = cf_data.get('operating_cf')
        investing_cf = cf_data.get('investing_cf')
        financing_cf = cf_data.get('financing_cf')
        
        interpretations = {
            'ideal': '理想的なキャッシュフローパターンです。本業で稼いだ資金で投資を行い、借入金の返済も行っている健全な状態です。',
            'growth': '成長企業型のパターンです。本業で稼ぎつつ積極的な投資を行い、必要に応じて資金調達も行っています。',
            'restructuring': '事業再構築段階の可能性があります。資産売却等で得た資金で借入金を返済している状況です。',
            'danger': '要注意パターンです。本業が赤字で、資産売却と借入で資金繰りを行っている状況です。',
            'other': 'その他のパターンです。個別の状況分析が必要です。'
        }
        
        base_interpretation = interpretations.get(pattern, '')
        
        # 金額の規模についてのコメント追加
        if operating_cf is not None:
            if operating_cf > 100000:  # 10億円以上
                base_interpretation += ' 営業キャッシュフローの規模は大きく、安定性が期待できます。'
            elif operating_cf > 0:
                base_interpretation += ' 営業キャッシュフローはプラスを維持しています。'
            else:
                base_interpretation += ' 営業キャッシュフローがマイナスとなっており、注意が必要です。'
        
        return base_interpretation
    
    def _identify_cf_risk_factors(self, cf_data: Dict) -> List[str]:
        """キャッシュフローリスク要因の特定"""
        
        risk_factors = []
        
        # 営業CFがマイナス
        if cf_data.get('operating_cf', 0) < 0:
            risk_factors.append('営業キャッシュフローがマイナス')
        
        # フリーCFがマイナス
        if cf_data.get('free_cf', 0) < 0:
            risk_factors.append('フリーキャッシュフローがマイナス')
        
        # 危険パターン
        if cf_data.get('pattern') == 'danger':
            risk_factors.append('危険な資金繰りパターン')
        
        # 品質スコアが低い
        if cf_data.get('cf_quality_score', 50) < 30:
            risk_factors.append('キャッシュフロー品質が低い')
        
        return risk_factors
    
    def _calculate_overall_score(self, analysis: Analysis) -> float:
        """総合スコア計算"""
        
        score = 0.0
        weight_sum = 0.0
        
        # 感情分析スコア
        if hasattr(analysis, 'sentiment'):
            sentiment = analysis.sentiment
            sentiment_score = sentiment.positive_score - sentiment.negative_score
            score += sentiment_score * 0.4
            weight_sum += 0.4
        
        # キャッシュフロースコア
        if hasattr(analysis, 'cashflow'):
            cashflow = analysis.cashflow
            cf_score = cashflow.pattern_score or 0
            score += cf_score * 0.6
            weight_sum += 0.6
        
        # 重み付き平均
        if weight_sum > 0:
            return score / weight_sum
        else:
            return 0.0
    
    def _determine_confidence_level(self, analysis: Analysis) -> str:
        """信頼性レベル判定"""
        
        # データの充実度で判定
        has_sentiment = hasattr(analysis, 'sentiment')
        has_cashflow = hasattr(analysis, 'cashflow')
        
        if has_sentiment and has_cashflow:
            return 'high'
        elif has_sentiment or has_cashflow:
            return 'medium'
        else:
            return 'low'
    
    def _save_sentiment_analysis(self, analysis: Analysis, sentiment_result: Dict):
        """感情分析結果保存"""
        
        SentimentAnalysis.objects.update_or_create(
            analysis=analysis,
            defaults=sentiment_result
        )
    
    def _save_cashflow_analysis(self, analysis: Analysis, cashflow_result: Dict):
        """キャッシュフロー分析結果保存"""
        
        CashFlowAnalysis.objects.update_or_create(
            analysis=analysis,
            defaults=cashflow_result
        )