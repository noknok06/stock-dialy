# earnings_analysis/services/langextract_sentiment_service.py
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from django.conf import settings
from django.utils import timezone
import google.generativeai as genai

# LangExtractのインポート（仮想的な例）
try:
    import langextract
    LANGEXTRACT_AVAILABLE = True
except ImportError:
    LANGEXTRACT_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class SentimentExtraction:
    """感情分析用抽出データ"""
    section_name: str
    key_phrases: List[str]
    context_summary: str
    emotional_indicators: List[Dict[str, Any]]
    financial_metrics_mentioned: List[str]
    management_statements: List[str]

@dataclass
class EnhancedSentimentResult:
    """拡張感情分析結果"""
    overall_score: float
    confidence_level: float
    contextual_factors: List[str]
    section_scores: Dict[str, float]
    key_insights: List[str]
    reasoning: str

class LangExtractSentimentService:
    """LangExtract + Gemini による高度感情分析サービス"""
    
    def __init__(self):
        self.gemini_available = self._initialize_gemini()
        self.langextract_available = LANGEXTRACT_AVAILABLE
        
        # LangExtract用の抽出スキーマ定義
        self.extraction_schema = {
            "sentiment_indicators": {
                "type": "array",
                "description": "文書内の感情を示す重要な表現や文章",
                "items": {
                    "text": "文章内容",
                    "context": "文脈情報",
                    "emotional_tone": "感情的なトーン（positive/negative/neutral）",
                    "intensity": "強度（1-5）",
                    "business_impact": "ビジネスへの影響度"
                }
            },
            "key_financial_statements": {
                "type": "array", 
                "description": "財務に関する重要な発言や数値",
                "items": {
                    "statement": "発言内容",
                    "metric_type": "指標の種類",
                    "sentiment_context": "感情的文脈"
                }
            },
            "management_outlook": {
                "type": "object",
                "description": "経営陣の見通しや姿勢",
                "properties": {
                    "forward_looking_statements": "将来見通し発言",
                    "risk_mentions": "リスクへの言及", 
                    "growth_confidence": "成長への確信度",
                    "operational_tone": "運営に関するトーン"
                }
            },
            "contextual_modifiers": {
                "type": "array",
                "description": "感情を修飾する文脈的要素",
                "items": {
                    "modifier": "修飾表現",
                    "impact_on_sentiment": "感情への影響",
                    "business_significance": "ビジネス上の重要度"
                }
            }
        }
    
    def _initialize_gemini(self) -> bool:
        """Gemini API初期化"""
        try:
            api_key = getattr(settings, 'GEMINI_API_KEY', None)
            if not api_key:
                logger.warning("GEMINI_API_KEY not configured")
                return False
            
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            return True
        except Exception as e:
            logger.error(f"Gemini initialization failed: {e}")
            return False
    
    async def extract_sentiment_elements(self, text_sections: Dict[str, str]) -> List[SentimentExtraction]:
        """LangExtractを使用して感情分析に重要な要素を抽出"""
        extractions = []
        
        if not self.langextract_available:
            logger.warning("LangExtract not available, using fallback extraction")
            return self._fallback_extraction(text_sections)
        
        try:
            # 各セクションから重要要素を抽出
            for section_name, text in text_sections.items():
                logger.info(f"Extracting sentiment elements from section: {section_name}")
                
                # LangExtractで構造化抽出
                extractor = langextract.extract(
                    text=text,
                    schema=self.extraction_schema,
                    instruction=self._get_extraction_instruction()
                )
                
                extracted_data = await extractor.run()
                
                # SentimentExtractionオブジェクトに変換
                extraction = SentimentExtraction(
                    section_name=section_name,
                    key_phrases=self._extract_key_phrases(extracted_data),
                    context_summary=self._create_context_summary(extracted_data),
                    emotional_indicators=extracted_data.get('sentiment_indicators', []),
                    financial_metrics_mentioned=self._extract_financial_metrics(extracted_data),
                    management_statements=self._extract_management_statements(extracted_data)
                )
                
                extractions.append(extraction)
                
        except Exception as e:
            logger.error(f"LangExtract extraction failed: {e}")
            return self._fallback_extraction(text_sections)
        
        return extractions
    
    def _get_extraction_instruction(self) -> str:
        """LangExtract用の抽出指示"""
        return """
        あなたは金融アナリストとして、企業の決算書類から感情分析に重要な情報を抽出してください。

        以下の観点で情報を抽出してください：
        1. 経営陣の感情的なトーン（楽観的/悲観的/中立的）
        2. 業績に関する表現の感情的ニュアンス
        3. 将来見通しの確信度や不安要素
        4. リスクや課題への言及の仕方
        5. 成長や改善への期待感
        6. 否定的要素を和らげる表現や文脈
        7. 強調される ポジティブ/ネガティブ要素

        特に注意すべきポイント：
        - 「〜ものの」「〜が」などの逆接表現
        - 「改善」「回復」などの転換を示す表現
        - 数値と組み合わされた感情表現
        - 比較表現に含まれる感情的ニュアンス
        """
    
    async def analyze_with_gemini(self, extractions: List[SentimentExtraction], 
                                document_info: Dict[str, str]) -> EnhancedSentimentResult:
        """抽出されたデータをもとにGeminiで文脈考慮の感情分析"""
        
        if not self.gemini_available:
            return self._fallback_gemini_analysis(extractions)
        
        try:
            # 抽出データを統合してプロンプト構築
            analysis_prompt = self._build_gemini_analysis_prompt(extractions, document_info)
            
            logger.info("Starting Gemini contextual sentiment analysis")
            response = self.model.generate_content(analysis_prompt)
            
            if response and response.text:
                return self._parse_gemini_sentiment_response(response.text, extractions)
            else:
                logger.warning("Empty response from Gemini")
                return self._fallback_gemini_analysis(extractions)
                
        except Exception as e:
            logger.error(f"Gemini sentiment analysis failed: {e}")
            return self._fallback_gemini_analysis(extractions)
    
    def _build_gemini_analysis_prompt(self, extractions: List[SentimentExtraction], 
                                    document_info: Dict[str, str]) -> str:
        """Gemini用の感情分析プロンプト構築"""
        
        # 抽出データを整理
        all_emotional_indicators = []
        all_key_phrases = []
        section_summaries = []
        
        for extraction in extractions:
            all_emotional_indicators.extend(extraction.emotional_indicators)
            all_key_phrases.extend(extraction.key_phrases)
            section_summaries.append(f"【{extraction.section_name}】{extraction.context_summary}")
        
        prompt = f"""
あなたは経験豊富な金融アナリストとして、企業決算書類の感情分析を行ってください。

【企業情報】
企業名: {document_info.get('company_name', '不明')}
書類種別: {document_info.get('doc_description', '不明')}
提出日: {document_info.get('submit_date', '不明')}

【抽出された重要要素】

《感情的指標》
{self._format_emotional_indicators(all_emotional_indicators)}

《重要フレーズ》
{', '.join(all_key_phrases[:20])}

《セクション別要約》
{chr(10).join(section_summaries)}

【分析指示】
以下の基準で総合的な感情スコアを算出してください：

1. **文脈的解釈**: 単語の表面的な意味だけでなく、文脈での真の意図を評価
2. **修飾要素の考慮**: 「〜ものの」「ただし」「しかしながら」などの逆接表現の影響
3. **強調度の評価**: 「大幅に」「著しく」「極めて」などの程度副詞の重み
4. **時系列的変化**: 「改善」「回復」「悪化」などの変化を示す表現の評価
5. **経営陣の意図**: 伝えたいメッセージの背景にある感情的トーン

【出力形式】
以下のJSON形式で回答してください：

{{
    "overall_sentiment_score": (数値: -1.0 から +1.0),
    "confidence_level": (数値: 0.0 から 1.0),
    "contextual_factors": [
        "文脈要因1",
        "文脈要因2",
        "..."
    ],
    "section_scores": {{
        "セクション名1": スコア,
        "セクション名2": スコア
    }},
    "key_insights": [
        "重要な洞察1",
        "重要な洞察2", 
        "..."
    ],
    "reasoning": "スコア算出の根拠と論理"
}}

**重要**: 従来の辞書ベース分析では捉えられない文脈的ニュアンスを特に重視してください。
"""
        return prompt
    
    def _format_emotional_indicators(self, indicators: List[Dict[str, Any]]) -> str:
        """感情指標をフォーマット"""
        if not indicators:
            return "（感情指標が検出されませんでした）"
        
        formatted = []
        for i, indicator in enumerate(indicators[:10], 1):  # 上位10個まで
            text = indicator.get('text', '')
            tone = indicator.get('emotional_tone', '')
            intensity = indicator.get('intensity', 0)
            
            formatted.append(f"{i}. {text} [トーン: {tone}, 強度: {intensity}]")
        
        return '\n'.join(formatted)
    
    def _parse_gemini_sentiment_response(self, response_text: str, 
                                       extractions: List[SentimentExtraction]) -> EnhancedSentimentResult:
        """Geminiの応答を解析してEnhancedSentimentResultに変換"""
        try:
            import json
            import re
            
            # JSONブロックを抽出
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_data = json.loads(json_match.group())
            else:
                raise ValueError("JSON response not found")
            
            return EnhancedSentimentResult(
                overall_score=float(response_data.get('overall_sentiment_score', 0.0)),
                confidence_level=float(response_data.get('confidence_level', 0.5)),
                contextual_factors=response_data.get('contextual_factors', []),
                section_scores=response_data.get('section_scores', {}),
                key_insights=response_data.get('key_insights', []),
                reasoning=response_data.get('reasoning', '')
            )
            
        except Exception as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            return self._fallback_gemini_analysis(extractions)
    
    def _fallback_extraction(self, text_sections: Dict[str, str]) -> List[SentimentExtraction]:
        """LangExtract利用不可時のフォールバック抽出"""
        extractions = []
        
        for section_name, text in text_sections.items():
            # 簡易的な重要フレーズ抽出
            key_phrases = self._simple_phrase_extraction(text)
            
            extraction = SentimentExtraction(
                section_name=section_name,
                key_phrases=key_phrases,
                context_summary=text[:500] + "..." if len(text) > 500 else text,
                emotional_indicators=[],
                financial_metrics_mentioned=[],
                management_statements=[]
            )
            extractions.append(extraction)
            
        return extractions
    
    def _fallback_gemini_analysis(self, extractions: List[SentimentExtraction]) -> EnhancedSentimentResult:
        """Gemini利用不可時のフォールバック分析"""
        return EnhancedSentimentResult(
            overall_score=0.0,
            confidence_level=0.3,
            contextual_factors=["フォールバック分析"],
            section_scores={},
            key_insights=["詳細分析が利用できませんでした"],
            reasoning="LangExtract/Geminiが利用できないため、基本分析を実行しました"
        )
    
    def _simple_phrase_extraction(self, text: str) -> List[str]:
        """簡易フレーズ抽出"""
        import re
        
        # 重要そうなフレーズパターン
        patterns = [
            r'[増減][収益][^。]*',
            r'[改善悪化][^。]*', 
            r'[成長発展][^。]*',
            r'[前年同期比][^。]*',
            r'[予想見通し][^。]*'
        ]
        
        phrases = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            phrases.extend(matches[:3])  # 各パターンから最大3個
            
        return phrases[:10]  # 合計最大10個
    
    def _extract_key_phrases(self, extracted_data: Dict) -> List[str]:
        """抽出データから重要フレーズを取得"""
        phrases = []
        
        for indicator in extracted_data.get('sentiment_indicators', []):
            if 'text' in indicator:
                phrases.append(indicator['text'])
        
        for statement in extracted_data.get('key_financial_statements', []):
            if 'statement' in statement:
                phrases.append(statement['statement'])
                
        return phrases
    
    def _create_context_summary(self, extracted_data: Dict) -> str:
        """抽出データから文脈要約を作成"""
        summaries = []
        
        outlook = extracted_data.get('management_outlook', {})
        if outlook.get('forward_looking_statements'):
            summaries.append(f"将来見通し: {outlook['forward_looking_statements']}")
        
        if outlook.get('growth_confidence'):
            summaries.append(f"成長確信度: {outlook['growth_confidence']}")
            
        return " / ".join(summaries) if summaries else "要約作成不可"
    
    def _extract_financial_metrics(self, extracted_data: Dict) -> List[str]:
        """抽出データから財務指標を取得"""
        metrics = []
        
        for statement in extracted_data.get('key_financial_statements', []):
            if 'metric_type' in statement:
                metrics.append(statement['metric_type'])
                
        return list(set(metrics))  # 重複除去
    
    def _extract_management_statements(self, extracted_data: Dict) -> List[str]:
        """抽出データから経営発言を取得"""
        statements = []
        
        outlook = extracted_data.get('management_outlook', {})
        for key, value in outlook.items():
            if value and isinstance(value, str):
                statements.append(value)
                
        return statements

# 既存のSentimentAnalysisServiceとの統合クラス
class HybridSentimentAnalysisService:
    """従来の辞書ベース + LangExtract/Gemini のハイブリッド分析"""
    
    def __init__(self):
        from .sentiment_analyzer import TransparentSentimentAnalyzer
        self.traditional_analyzer = TransparentSentimentAnalyzer()
        self.langextract_service = LangExtractSentimentService()
    
    async def analyze_hybrid(self, text_sections: Dict[str, str], 
                           document_info: Dict[str, str]) -> Dict[str, Any]:
        """ハイブリッド感情分析実行"""
        
        # 1. 従来の辞書ベース分析
        traditional_result = self.traditional_analyzer.analyze_text_sections(
            text_sections, document_info=document_info
        )
        
        # 2. LangExtract + Gemini 分析
        try:
            extractions = await self.langextract_service.extract_sentiment_elements(text_sections)
            enhanced_result = await self.langextract_service.analyze_with_gemini(
                extractions, document_info
            )
            
            # 3. 結果統合
            hybrid_result = self._merge_analysis_results(traditional_result, enhanced_result)
            hybrid_result['analysis_method'] = 'hybrid_langextract_gemini'
            
        except Exception as e:
            logger.error(f"Enhanced analysis failed, using traditional only: {e}")
            hybrid_result = traditional_result
            hybrid_result['analysis_method'] = 'traditional_fallback'
        
        return hybrid_result
    
    def _merge_analysis_results(self, traditional: Dict[str, Any], 
                              enhanced: EnhancedSentimentResult) -> Dict[str, Any]:
        """従来結果と拡張結果をマージ"""
        
        # 重み付き平均でスコア統合（Geminiの結果により高い重みを付与）
        traditional_weight = 0.3
        enhanced_weight = 0.7
        
        merged_score = (
            traditional['overall_score'] * traditional_weight + 
            enhanced.overall_score * enhanced_weight
        )
        
        # 新しい感情ラベル決定
        if merged_score > 0.15:
            sentiment_label = 'positive'
        elif merged_score < -0.15:
            sentiment_label = 'negative'
        else:
            sentiment_label = 'neutral'
        
        # 結果統合
        merged_result = traditional.copy()
        merged_result.update({
            'overall_score': round(merged_score, 3),
            'sentiment_label': sentiment_label,
            'enhanced_analysis': {
                'langextract_gemini_score': enhanced.overall_score,
                'confidence_level': enhanced.confidence_level,
                'contextual_factors': enhanced.contextual_factors,
                'key_insights': enhanced.key_insights,
                'reasoning': enhanced.reasoning,
                'section_scores': enhanced.section_scores
            },
            'score_breakdown': {
                'traditional_score': traditional['overall_score'],
                'enhanced_score': enhanced.overall_score,
                'merged_score': merged_score,
                'traditional_weight': traditional_weight,
                'enhanced_weight': enhanced_weight
            }
        })
        
        return merged_result