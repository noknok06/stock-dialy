# earnings_analysis/services/langextract_sentiment.py（完全動作版）
import logging
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.utils import timezone
import os

logger = logging.getLogger(__name__)

class LangExtractSentimentAnalyzer:
    """LangExtractを使った高度感情分析（完全動作版）"""
    
    def __init__(self):
        self.langextract_available = False
        self.langextract = None
        self._initialize_langextract()
    
    def _initialize_langextract(self):
        """LangExtractの初期化"""
        try:
            import langextract as lx
            self.langextract = lx
            self.langextract_available = True
            logger.info("LangExtract初期化成功")
            
            # APIキーの確認
            api_key = getattr(settings, 'GEMINI_API_KEY', None) or os.getenv('GEMINI_API_KEY')
            if not api_key:
                logger.warning("GEMINI_API_KEYが設定されていません。環境変数またはsettings.pyで設定してください。")
                self.api_key = None
            else:
                self.api_key = api_key
                logger.info("Gemini APIキー確認完了")
                
        except ImportError:
            logger.warning("LangExtractがインストールされていません: pip install langextract")
            self.langextract_available = False
        except Exception as e:
            logger.error(f"LangExtract初期化エラー: {e}")
            self.langextract_available = False
    
    def analyze_document_sentiment(self, document_text: str, document_info: Dict) -> Dict[str, Any]:
        """文書の感情分析（LangExtract完全版）"""
        
        if not self.langextract_available:
            logger.info("LangExtractが利用できません - 代替分析を実行")
            return self._fallback_analysis(document_info)
        
        if not self.api_key:
            logger.warning("APIキーが設定されていません - 代替分析を実行")
            return self._fallback_analysis(document_info)
        
        try:
            # Step 1: 重要セクションの抽出
            logger.info("LangExtract: 重要セクション抽出開始")
            key_sections = self._extract_key_sections(document_text)
            
            # Step 2: 詳細感情分析
            logger.info("LangExtract: 詳細感情分析開始")
            sentiment_analysis = self._analyze_sentiment_detailed(key_sections, document_info)
            
            # Step 3: 投資家向け見解生成
            logger.info("LangExtract: 投資家向け見解生成開始")
            investment_insights = self._generate_investment_insights(sentiment_analysis, document_info)
            
            # 結果統合
            final_result = self._combine_langextract_results(
                key_sections, sentiment_analysis, investment_insights, document_info
            )
            
            logger.info("LangExtract感情分析完了")
            return final_result
            
        except Exception as e:
            logger.error(f"LangExtract分析エラー: {e}")
            return self._fallback_analysis(document_info)
    
    def _extract_key_sections(self, text: str) -> Dict[str, Any]:
        """重要セクションの抽出"""
        
        # 抽出プロンプト
        prompt_description = """
        決算書類から投資判断に重要な以下の情報を抽出してください：
        1. 業績表現 - 売上、利益、成長に関する具体的な記述とその感情的トーン
        2. リスク要因 - 懸念事項、課題、困難な状況の記述
        3. 将来見通し - 計画、予測、方針に関する記述と楽観性/悲観性
        4. 経営姿勢 - 経営陣の自信度や方針を示す表現
        """
        
        # Few-shot Examples
        examples = [
            self.langextract.data.ExampleData(
                text="売上高は前年同期比15%増の1,200億円となり、過去最高益を記録しました。",
                extractions=[
                    self.langextract.data.Extraction(
                        extraction_class="業績表現",
                        extraction_text="売上高は前年同期比15%増の1,200億円となり、過去最高益を記録しました",
                        attributes={
                            "sentiment_tone": "非常にポジティブ",
                            "confidence_level": "高",
                            "impact_weight": 0.9,
                            "keywords": ["15%増", "過去最高益"],
                            "financial_metrics": "売上高1,200億円"
                        }
                    )
                ]
            ),
            self.langextract.data.ExampleData(
                text="市場環境の悪化により、今期の業績は厳しい状況が続くと予想されます。",
                extractions=[
                    self.langextract.data.Extraction(
                        extraction_class="リスク要因",
                        extraction_text="市場環境の悪化により、今期の業績は厳しい状況が続くと予想されます",
                        attributes={
                            "sentiment_tone": "ネガティブ",
                            "risk_type": "市場リスク",
                            "impact_weight": -0.7,
                            "time_horizon": "今期"
                        }
                    )
                ]
            ),
            self.langextract.data.ExampleData(
                text="来年度は新規事業の展開により、さらなる成長を目指してまいります。",
                extractions=[
                    self.langextract.data.Extraction(
                        extraction_class="将来見通し",
                        extraction_text="来年度は新規事業の展開により、さらなる成長を目指してまいります",
                        attributes={
                            "sentiment_tone": "ポジティブ",
                            "outlook_type": "成長戦略",
                            "confidence_level": "中",
                            "time_horizon": "来年度",
                            "strategy": "新規事業展開"
                        }
                    )
                ]
            ),
            self.langextract.data.ExampleData(
                text="減収となったものの、コスト削減効果により収益性の改善が見られました。",
                extractions=[
                    self.langextract.data.Extraction(
                        extraction_class="業績表現",
                        extraction_text="減収となったものの、コスト削減効果により収益性の改善が見られました",
                        attributes={
                            "sentiment_tone": "混合（ネガティブからポジティブ転換）",
                            "improvement_signal": True,
                            "impact_weight": 0.3,
                            "keywords": ["減収", "改善"],
                            "context_type": "改善パターン"
                        }
                    )
                ]
            )
        ]
        
        try:
            # LangExtract実行
            result = self.langextract.extract(
                text_or_documents=text,
                prompt_description=prompt_description,
                examples=examples,
                model_id="gemini-2.5-flash",
                api_key=self.api_key
            )
            
            return {
                'extraction_successful': True,
                'extractions': result.extractions if hasattr(result, 'extractions') else [],
                'document_metadata': result.document_metadata if hasattr(result, 'document_metadata') else {},
                'method': 'langextract_gemini'
            }
            
        except Exception as e:
            logger.error(f"LangExtractセクション抽出エラー: {e}")
            return {
                'extraction_successful': False,
                'error': str(e),
                'method': 'langextract_failed'
            }
    
    def _analyze_sentiment_detailed(self, sections_data: Dict, document_info: Dict) -> Dict[str, Any]:
        """詳細感情分析"""
        
        if not sections_data.get('extraction_successful'):
            return {'analysis_successful': False, 'error': 'セクション抽出失敗'}
        
        # 抽出されたセクションから感情分析
        extractions = sections_data.get('extractions', [])
        
        if not extractions:
            return {'analysis_successful': False, 'error': '抽出データなし'}
        
        # 感情分析プロンプト
        prompt_description = """
        抽出された決算書類の重要な表現から、投資家視点での総合的な感情分析を行ってください。
        以下の観点で分析してください：
        1. 全体的な感情スコア（-1.0 to 1.0）
        2. 経営陣の自信度レベル
        3. 投資魅力度
        4. リスク認識レベル
        5. 将来への楽観度
        """
        
        # 抽出データをテキストに変換
        analysis_text = "\n".join([
            f"[{ext.extraction_class}] {ext.extraction_text}"
            for ext in extractions
        ])
        
        examples = [
            self.langextract.data.ExampleData(
                text="[業績表現] 売上高は大幅に増加し、過去最高益を達成しました\n[将来見通し] 来期もさらなる成長を期待しています",
                extractions=[
                    self.langextract.data.Extraction(
                        extraction_class="感情分析結果",
                        extraction_text="売上高は大幅に増加し、過去最高益を達成しました。来期もさらなる成長を期待しています",
                        attributes={
                            "overall_sentiment_score": 0.8,
                            "sentiment_label": "positive",
                            "management_confidence": "高",
                            "investment_appeal": "非常に高い",
                            "risk_level": "低",
                            "future_optimism": "高",
                            "key_factors": ["大幅増加", "過去最高益", "さらなる成長"],
                            "analysis_confidence": 0.9
                        }
                    )
                ]
            ),
            self.langextract.data.ExampleData(
                text="[リスク要因] 市場環境の悪化により厳しい状況\n[業績表現] 減収減益となりました",
                extractions=[
                    self.langextract.data.Extraction(
                        extraction_class="感情分析結果",
                        extraction_text="市場環境の悪化により厳しい状況。減収減益となりました",
                        attributes={
                            "overall_sentiment_score": -0.6,
                            "sentiment_label": "negative",
                            "management_confidence": "低",
                            "investment_appeal": "低",
                            "risk_level": "高",
                            "future_optimism": "低",
                            "key_factors": ["市場環境悪化", "厳しい状況", "減収減益"],
                            "analysis_confidence": 0.8
                        }
                    )
                ]
            )
        ]
        
        try:
            result = self.langextract.extract(
                text_or_documents=analysis_text,
                prompt_description=prompt_description,
                examples=examples,
                model_id="gemini-2.5-flash",
                api_key=self.api_key
            )
            
            # 結果の解析
            if hasattr(result, 'extractions') and result.extractions:
                analysis_result = result.extractions[0]
                attributes = analysis_result.attributes if hasattr(analysis_result, 'attributes') else {}
                
                return {
                    'analysis_successful': True,
                    'overall_score': attributes.get('overall_sentiment_score', 0.0),
                    'sentiment_label': attributes.get('sentiment_label', 'neutral'),
                    'management_confidence': attributes.get('management_confidence', '中'),
                    'investment_appeal': attributes.get('investment_appeal', '中'),
                    'risk_level': attributes.get('risk_level', '中'),
                    'future_optimism': attributes.get('future_optimism', '中'),
                    'key_factors': attributes.get('key_factors', []),
                    'analysis_confidence': attributes.get('analysis_confidence', 0.5),
                    'method': 'langextract_sentiment'
                }
            else:
                return {'analysis_successful': False, 'error': '感情分析結果なし'}
                
        except Exception as e:
            logger.error(f"LangExtract感情分析エラー: {e}")
            return {'analysis_successful': False, 'error': str(e)}
    
    def _generate_investment_insights(self, sentiment_data: Dict, document_info: Dict) -> Dict[str, Any]:
        """投資家向け見解生成"""
        
        if not sentiment_data.get('analysis_successful'):
            return {'insights_successful': False, 'error': '感情分析失敗'}
        
        company_name = document_info.get('company_name', '企業')
        overall_score = sentiment_data.get('overall_score', 0.0)
        sentiment_label = sentiment_data.get('sentiment_label', 'neutral')
        
        prompt_description = f"""
        {company_name}の決算書類の感情分析結果に基づいて、投資家向けの具体的で実用的な投資判断ポイントを3-5個生成してください。
        各ポイントは投資判断に直接役立つ内容にしてください。
        """
        
        # 感情分析結果をテキスト化
        insight_input = f"""
        企業名: {company_name}
        感情スコア: {overall_score}
        感情ラベル: {sentiment_label}
        経営陣の自信度: {sentiment_data.get('management_confidence', '不明')}
        投資魅力度: {sentiment_data.get('investment_appeal', '不明')}
        リスクレベル: {sentiment_data.get('risk_level', '不明')}
        将来楽観度: {sentiment_data.get('future_optimism', '不明')}
        主要因子: {', '.join(sentiment_data.get('key_factors', []))}
        """
        
        examples = [
            self.langextract.data.ExampleData(
                text="企業名: テクノロジー株式会社\n感情スコア: 0.8\n感情ラベル: positive\n経営陣の自信度: 高\n投資魅力度: 非常に高い",
                extractions=[
                    self.langextract.data.Extraction(
                        extraction_class="投資判断ポイント",
                        extraction_text="強力な成長モメンタム",
                        attributes={
                            "title": "強力な成長モメンタム",
                            "description": "過去最高益の達成と経営陣の高い自信度から、持続的な成長期待が持てる投資先として評価されます",
                            "investment_action": "買い検討",
                            "time_horizon": "中長期",
                            "confidence": "高"
                        }
                    ),
                    self.langextract.data.Extraction(
                        extraction_class="投資判断ポイント",
                        extraction_text="市場評価向上期待",
                        attributes={
                            "title": "市場評価向上期待",
                            "description": "強いポジティブシグナルにより、株価の再評価が期待される局面にあります",
                            "investment_action": "ポジション拡大検討",
                            "time_horizon": "短中期",
                            "confidence": "中高"
                        }
                    )
                ]
            ),
            self.langextract.data.ExampleData(
                text="企業名: 製造業株式会社\n感情スコア: -0.6\n感情ラベル: negative\n経営陣の自信度: 低\nリスクレベル: 高",
                extractions=[
                    self.langextract.data.Extraction(
                        extraction_class="投資判断ポイント",
                        extraction_text="慎重なリスク評価が必要",
                        attributes={
                            "title": "慎重なリスク評価が必要",
                            "description": "現在の困難な状況を踏まえ、投資前に詳細なリスク分析と回復計画の確認が重要です",
                            "investment_action": "様子見",
                            "time_horizon": "短期",
                            "confidence": "高"
                        }
                    ),
                    self.langextract.data.Extraction(
                        extraction_class="投資判断ポイント",
                        extraction_text="構造改革の機会",
                        attributes={
                            "title": "構造改革の機会",
                            "description": "現在の困難は将来の抜本的改革への契機となる可能性があり、長期投資家には検討余地があります",
                            "investment_action": "長期観点での検討",
                            "time_horizon": "長期",
                            "confidence": "中"
                        }
                    )
                ]
            )
        ]
        
        try:
            result = self.langextract.extract(
                text_or_documents=insight_input,
                prompt_description=prompt_description,
                examples=examples,
                model_id="gemini-2.5-flash",
                api_key=self.api_key
            )
            
            if hasattr(result, 'extractions') and result.extractions:
                insights = []
                for extraction in result.extractions:
                    if hasattr(extraction, 'attributes'):
                        attributes = extraction.attributes
                        insights.append({
                            'title': attributes.get('title', extraction.extraction_text[:30]),
                            'description': attributes.get('description', extraction.extraction_text),
                            'investment_action': attributes.get('investment_action', '検討'),
                            'time_horizon': attributes.get('time_horizon', '中期'),
                            'confidence': attributes.get('confidence', '中'),
                            'source': 'langextract_generated'
                        })
                
                return {
                    'insights_successful': True,
                    'investment_points': insights,
                    'total_points': len(insights),
                    'generation_method': 'langextract_gemini'
                }
            else:
                return {'insights_successful': False, 'error': '見解生成結果なし'}
                
        except Exception as e:
            logger.error(f"LangExtract見解生成エラー: {e}")
            return {'insights_successful': False, 'error': str(e)}
    
    def _combine_langextract_results(self, sections: Dict, sentiment: Dict, insights: Dict, document_info: Dict) -> Dict[str, Any]:
        """LangExtract結果の統合"""
        
        # 基本スコア
        overall_score = sentiment.get('overall_score', 0.0) if sentiment.get('analysis_successful') else 0.0
        sentiment_label = sentiment.get('sentiment_label', 'neutral') if sentiment.get('analysis_successful') else 'neutral'
        
        # 投資家向けポイント
        investment_points = insights.get('investment_points', []) if insights.get('insights_successful') else []
        
        # 統計情報
        extractions_count = len(sections.get('extractions', [])) if sections.get('extraction_successful') else 0
        
        return {
            'overall_score': float(overall_score),
            'sentiment_label': sentiment_label,
            'analysis_method': 'langextract_complete',
            'confidence': sentiment.get('analysis_confidence', 0.8),
            
            # LangExtract特有の詳細分析
            'langextract_analysis': {
                'extraction_successful': sections.get('extraction_successful', False),
                'sentiment_analysis_successful': sentiment.get('analysis_successful', False),
                'insights_generation_successful': insights.get('insights_successful', False),
                'extractions_count': extractions_count,
                'management_confidence': sentiment.get('management_confidence', '不明'),
                'investment_appeal': sentiment.get('investment_appeal', '不明'),
                'risk_level': sentiment.get('risk_level', '不明'),
                'future_optimism': sentiment.get('future_optimism', '不明'),
                'key_factors': sentiment.get('key_factors', [])
            },
            
            # 投資家向け見解（Gemini生成）
            'gemini_investment_points': investment_points,
            'gemini_metadata': {
                'generated_by': 'langextract_gemini',
                'api_available': True,
                'api_success': True,
                'response_quality': 'high' if len(investment_points) >= 3 else 'medium',
                'generation_timestamp': timezone.now().isoformat(),
                'points_count': len(investment_points),
                'model_used': 'gemini-2.5-flash',
                'extraction_method': 'langextract'
            },
            
            # 既存システム互換性
            'keyword_analysis': self._create_keyword_analysis_from_langextract(sections),
            'sample_sentences': self._create_sample_sentences_from_langextract(sections),
            'statistics': self._create_statistics_from_langextract(sections, sentiment),
            
            # メタデータ
            'analysis_metadata': {
                'method': 'langextract_complete',
                'extraction_successful': sections.get('extraction_successful', False),
                'api_calls_made': 3,  # セクション抽出 + 感情分析 + 見解生成
                'analysis_timestamp': timezone.now().isoformat(),
                'model_used': 'gemini-2.5-flash',
                'features_enabled': ['LangExtract抽出', 'Gemini感情分析', 'AI投資見解']
            }
        }
    
    def _create_keyword_analysis_from_langextract(self, sections: Dict) -> Dict:
        """LangExtract結果からキーワード分析を作成"""
        positive_keywords = []
        negative_keywords = []
        
        if sections.get('extraction_successful'):
            for extraction in sections.get('extractions', []):
                if hasattr(extraction, 'attributes'):
                    attributes = extraction.attributes
                    sentiment_tone = attributes.get('sentiment_tone', '').lower()
                    keywords = attributes.get('keywords', [])
                    
                    for keyword in keywords:
                        keyword_data = {
                            'word': keyword,
                            'score': 0.0,
                            'type': 'langextract_extracted',
                            'count': 1,
                            'impact': attributes.get('impact_weight', 0.5),
                            'source': 'langextract'
                        }
                        
                        if 'ポジティブ' in sentiment_tone:
                            keyword_data['score'] = abs(attributes.get('impact_weight', 0.5))
                            positive_keywords.append(keyword_data)
                        elif 'ネガティブ' in sentiment_tone:
                            keyword_data['score'] = -abs(attributes.get('impact_weight', 0.5))
                            negative_keywords.append(keyword_data)
        
        return {
            'positive': positive_keywords,
            'negative': negative_keywords
        }
    
    def _create_sample_sentences_from_langextract(self, sections: Dict) -> Dict:
        """LangExtract結果からサンプル文章を作成"""
        positive_sentences = []
        negative_sentences = []
        
        if sections.get('extraction_successful'):
            for extraction in sections.get('extractions', []):
                if hasattr(extraction, 'attributes'):
                    attributes = extraction.attributes
                    sentiment_tone = attributes.get('sentiment_tone', '').lower()
                    
                    sentence_data = {
                        'text': extraction.extraction_text,
                        'score': attributes.get('impact_weight', 0.0),
                        'highlighted_text': extraction.extraction_text,
                        'keywords': attributes.get('keywords', []),
                        'source': 'langextract'
                    }
                    
                    if 'ポジティブ' in sentiment_tone:
                        positive_sentences.append(sentence_data)
                    elif 'ネガティブ' in sentiment_tone:
                        negative_sentences.append(sentence_data)
        
        return {
            'positive': positive_sentences,
            'negative': negative_sentences
        }
    
    def _create_statistics_from_langextract(self, sections: Dict, sentiment: Dict) -> Dict:
        """LangExtract結果から統計情報を作成"""
        extractions_count = len(sections.get('extractions', [])) if sections.get('extraction_successful') else 0
        
        return {
            'total_words_analyzed': extractions_count,
            'total_occurrences': extractions_count,
            'context_patterns_found': extractions_count,
            'basic_words_found': 0,
            'sentences_analyzed': extractions_count,
            'unique_words_found': extractions_count,
            'positive_words_count': 0,
            'negative_words_count': 0,
            'positive_sentences_count': 0,
            'negative_sentences_count': 0,
            'threshold_positive': 0.15,
            'threshold_negative': -0.15,
            'langextract_extractions': extractions_count,
            'analysis_confidence': sentiment.get('analysis_confidence', 0.5)
        }
    
    def _fallback_analysis(self, document_info: Dict) -> Dict[str, Any]:
        """LangExtract失敗時のフォールバック"""
        return {
            'overall_score': 0.0,
            'sentiment_label': 'neutral',
            'analysis_method': 'langextract_fallback',
            'confidence': 0.3,
            'langextract_analysis': {
                'extraction_successful': False,
                'error': 'LangExtractが利用できません',
                'fallback_used': True
            },
            'gemini_investment_points': [],
            'gemini_metadata': {
                'generated_by': 'langextract_fallback',
                'api_available': False,
                'api_success': False,
                'fallback_used': True,
                'error_message': 'LangExtractまたはAPIキーが利用できません',
                'generation_timestamp': timezone.now().isoformat(),
                'points_count': 0
            },
            'analysis_metadata': {
                'method': 'langextract_fallback',
                'extraction_successful': False,
                'analysis_timestamp': timezone.now().isoformat(),
                'fallback_reason': 'langextract_unavailable'
            }
        }