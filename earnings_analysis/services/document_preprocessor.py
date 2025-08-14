# earnings_analysis/services/document_preprocessor.py
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import re
from django.conf import settings

# Langextractの仮想的なインポート（実際の実装に合わせて調整）
try:
    import langextract
    LANGEXTRACT_AVAILABLE = True
except ImportError:
    LANGEXTRACT_AVAILABLE = False
    logging.warning("Langextractが利用できません。代替処理を使用します。")

logger = logging.getLogger(__name__)

@dataclass
class DocumentSection:
    """文書セクション"""
    title: str
    content: str
    importance_score: float
    section_type: str  # 'financial', 'business', 'risk', 'general'
    keywords: List[str]
    summary: str

@dataclass
class PreprocessingConfig:
    """前処理設定"""
    enable_summarization: bool = True
    enable_keyword_extraction: bool = True
    enable_importance_ranking: bool = True
    max_summary_length: int = 200
    min_section_length: int = 50
    target_sections: List[str] = None
    financial_focus: bool = True

class LangextractDocumentPreprocessor:
    """Langextract統合文書前処理システム"""
    
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        self.config = config or PreprocessingConfig()
        self.langextract_available = LANGEXTRACT_AVAILABLE
        
        if not self.langextract_available:
            logger.warning("Langextractが利用できません。基本的な前処理のみ実行します。")
    
    def preprocess_document(self, text_sections: Dict[str, str], 
                          document_info: Dict[str, str]) -> Dict[str, Any]:
        """文書の前処理実行"""
        try:
            # 1. セクション分析と重要度評価
            analyzed_sections = self._analyze_sections(text_sections, document_info)
            
            # 2. 重要セクションの抽出
            important_sections = self._extract_important_sections(analyzed_sections)
            
            # 3. 要約生成（Langextract使用）
            summaries = self._generate_summaries(important_sections)
            
            # 4. キーワード抽出
            keywords = self._extract_keywords(important_sections)
            
            # 5. 感情分析対象テキストの最適化
            optimized_text = self._optimize_for_sentiment_analysis(
                important_sections, summaries, keywords
            )
            
            return {
                'original_sections': text_sections,
                'analyzed_sections': analyzed_sections,
                'important_sections': important_sections,
                'summaries': summaries,
                'keywords': keywords,
                'optimized_text': optimized_text,
                'preprocessing_metadata': {
                    'langextract_used': self.langextract_available,
                    'sections_analyzed': len(analyzed_sections),
                    'important_sections_count': len(important_sections),
                    'total_keywords': len(keywords),
                    'optimization_ratio': len(optimized_text) / len(' '.join(text_sections.values())) if text_sections else 0
                }
            }
            
        except Exception as e:
            logger.error(f"文書前処理エラー: {e}")
            # フォールバック：基本的な前処理
            return self._basic_preprocessing(text_sections, document_info)
    
    def _analyze_sections(self, text_sections: Dict[str, str], 
                        document_info: Dict[str, str]) -> List[DocumentSection]:
        """セクション分析"""
        analyzed_sections = []
        
        for section_name, content in text_sections.items():
            if len(content.strip()) < self.config.min_section_length:
                continue
            
            # セクション種別の判定
            section_type = self._classify_section_type(section_name, content)
            
            # 重要度スコア計算
            importance_score = self._calculate_section_importance(
                section_name, content, section_type, document_info
            )
            
            # キーワード抽出
            keywords = self._extract_section_keywords(content)
            
            # 要約生成
            summary = self._generate_section_summary(content, section_name)
            
            analyzed_sections.append(DocumentSection(
                title=section_name,
                content=content,
                importance_score=importance_score,
                section_type=section_type,
                keywords=keywords,
                summary=summary
            ))
        
        # 重要度順でソート
        analyzed_sections.sort(key=lambda x: x.importance_score, reverse=True)
        return analyzed_sections
    
    def _classify_section_type(self, section_name: str, content: str) -> str:
        """セクション種別分類"""
        section_name_lower = section_name.lower()
        content_lower = content.lower()
        
        # 財務関連
        financial_keywords = [
            '売上', '利益', '収益', '損益', '貸借', 'キャッシュフロー',
            '財務', '経営成績', '財政状態', '業績'
        ]
        if any(keyword in section_name_lower or keyword in content_lower 
               for keyword in financial_keywords):
            return 'financial'
        
        # 事業関連
        business_keywords = [
            '事業', 'ビジネス', '戦略', '市場', '競合', '製品', 'サービス'
        ]
        if any(keyword in section_name_lower or keyword in content_lower 
               for keyword in business_keywords):
            return 'business'
        
        # リスク関連
        risk_keywords = [
            'リスク', '課題', '問題', '懸念', '不確実', '脅威'
        ]
        if any(keyword in section_name_lower or keyword in content_lower 
               for keyword in risk_keywords):
            return 'risk'
        
        return 'general'
    
    def _calculate_section_importance(self, section_name: str, content: str, 
                                    section_type: str, document_info: Dict) -> float:
        """セクション重要度計算"""
        base_score = 1.0
        
        # セクション種別による重み
        type_weights = {
            'financial': 1.5,
            'business': 1.3,
            'risk': 1.2,
            'general': 1.0
        }
        base_score *= type_weights.get(section_type, 1.0)
        
        # セクション名による重み
        important_section_patterns = [
            r'経営成績', r'財政状態', r'業績', r'売上', r'利益',
            r'事業.*概況', r'事業.*状況', r'経営方針'
        ]
        for pattern in important_section_patterns:
            if re.search(pattern, section_name):
                base_score *= 1.3
                break
        
        # 内容の分析
        # 数値データの密度
        numbers = re.findall(r'[0-9,]+(?:円|%|億|千|万)', content)
        if len(numbers) > 5:
            base_score *= 1.2
        
        # 感情語彙の密度
        emotion_words = [
            '増加', '減少', '改善', '悪化', '向上', '低下', 
            '成長', '拡大', '縮小', '好調', '不振'
        ]
        emotion_count = sum(1 for word in emotion_words if word in content)
        if emotion_count > 3:
            base_score *= 1.1
        
        # 内容の長さによる調整
        content_length = len(content)
        if content_length > 1000:
            base_score *= 1.1
        elif content_length < 200:
            base_score *= 0.8
        
        return min(3.0, base_score)
    
    def _extract_section_keywords(self, content: str) -> List[str]:
        """セクションからキーワード抽出"""
        if self.langextract_available:
            try:
                # Langextractを使用したキーワード抽出
                return self._langextract_keywords(content)
            except Exception as e:
                logger.warning(f"Langextractキーワード抽出エラー: {e}")
        
        # フォールバック：基本的なキーワード抽出
        return self._basic_keyword_extraction(content)
    
    def _langextract_keywords(self, content: str) -> List[str]:
        """Langextractによるキーワード抽出"""
        if not self.langextract_available:
            return []
        
        try:
            # Langextractの実際のAPIに合わせて調整
            # 例：extractor = langextract.KeywordExtractor()
            # keywords = extractor.extract(content, max_keywords=10)
            
            # 仮実装
            keywords = []
            # 実際の実装では langextract のドキュメントに従う
            
            return keywords[:10]  # 上位10個
            
        except Exception as e:
            logger.error(f"Langextractキーワード抽出エラー: {e}")
            return []
    
    def _basic_keyword_extraction(self, content: str) -> List[str]:
        """基本的なキーワード抽出"""
        # 財務・経営関連の重要語彙
        important_patterns = [
            r'売上(?:高)?', r'利益', r'収益', r'損失', r'純益',
            r'増収', r'減収', r'増益', r'減益', r'黒字', r'赤字',
            r'成長', r'拡大', r'改善', r'向上', r'回復',
            r'課題', r'リスク', r'懸念', r'問題'
        ]
        
        keywords = []
        for pattern in important_patterns:
            matches = re.findall(pattern, content)
            keywords.extend(matches)
        
        # 数値データ
        numerical_data = re.findall(r'[0-9,]+(?:円|%|億|千|万)', content)
        keywords.extend(numerical_data[:5])  # 最大5個
        
        return list(set(keywords))[:10]  # 重複除去して最大10個
    
    def _generate_section_summary(self, content: str, section_name: str) -> str:
        """セクション要約生成"""
        if self.langextract_available and self.config.enable_summarization:
            try:
                return self._langextract_summary(content, section_name)
            except Exception as e:
                logger.warning(f"Langextract要約生成エラー: {e}")
        
        # フォールバック：基本的な要約
        return self._basic_summarization(content)
    
    def _langextract_summary(self, content: str, section_name: str) -> str:
        """Langextractによる要約生成"""
        if not self.langextract_available:
            return ""
        
        try:
            # Langextractの実際のAPIに合わせて調整
            # 例：summarizer = langextract.Summarizer()
            # summary = summarizer.summarize(content, max_length=self.config.max_summary_length)
            
            # 仮実装
            summary = ""
            # 実際の実装では langextract のドキュメントに従う
            
            return summary
            
        except Exception as e:
            logger.error(f"Langextract要約生成エラー: {e}")
            return ""
    
    def _basic_summarization(self, content: str) -> str:
        """基本的な要約生成"""
        sentences = re.split(r'[。！？]', content)
        
        # 重要な文章を抽出
        important_sentences = []
        for sentence in sentences:
            if len(sentence.strip()) < 20:
                continue
            
            # 数値や重要語彙を含む文章を優先
            score = 0
            if re.search(r'[0-9,]+(?:円|%)', sentence):
                score += 2
            if any(word in sentence for word in ['売上', '利益', '成長', '改善']):
                score += 1
            
            if score > 0:
                important_sentences.append((sentence.strip(), score))
        
        # スコア順でソートして上位を選択
        important_sentences.sort(key=lambda x: x[1], reverse=True)
        
        summary_parts = [sent[0] for sent in important_sentences[:3]]
        summary = '。'.join(summary_parts)
        
        if len(summary) > self.config.max_summary_length:
            summary = summary[:self.config.max_summary_length] + '...'
        
        return summary
    
    def _extract_important_sections(self, analyzed_sections: List[DocumentSection]) -> List[DocumentSection]:
        """重要セクションの抽出"""
        # 重要度閾値以上のセクションを抽出
        threshold = 1.2
        important_sections = [s for s in analyzed_sections if s.importance_score >= threshold]
        
        # 最低でも上位3セクションは含める
        if len(important_sections) < 3:
            important_sections = analyzed_sections[:3]
        
        # 最大10セクションまで
        return important_sections[:10]
    
    def _generate_summaries(self, sections: List[DocumentSection]) -> Dict[str, str]:
        """セクション要約の統合"""
        summaries = {}
        
        for section in sections:
            if section.summary:
                summaries[section.title] = section.summary
        
        # 全体要約の生成
        if self.langextract_available:
            try:
                combined_content = ' '.join([s.content for s in sections])
                overall_summary = self._langextract_summary(combined_content, "全体")
                if overall_summary:
                    summaries['全体要約'] = overall_summary
            except Exception as e:
                logger.warning(f"全体要約生成エラー: {e}")
        
        return summaries
    
    def _extract_keywords(self, sections: List[DocumentSection]) -> List[str]:
        """統合キーワード抽出"""
        all_keywords = []
        
        for section in sections:
            all_keywords.extend(section.keywords)
        
        # 重複除去と頻度計算
        keyword_count = {}
        for keyword in all_keywords:
            keyword_count[keyword] = keyword_count.get(keyword, 0) + 1
        
        # 頻度順でソート
        sorted_keywords = sorted(keyword_count.items(), key=lambda x: x[1], reverse=True)
        
        return [keyword for keyword, count in sorted_keywords[:20]]
    
    def _optimize_for_sentiment_analysis(self, sections: List[DocumentSection], 
                                       summaries: Dict[str, str], 
                                       keywords: List[str]) -> str:
        """感情分析用テキストの最適化"""
        optimized_parts = []
        
        # 1. 重要セクションの内容（重要度による重み付き）
        for section in sections:
            if section.importance_score >= 1.5:
                # 高重要度セクションは全文を含める
                optimized_parts.append(f"[{section.title}] {section.content}")
            else:
                # 中程度の重要度セクションは要約を使用
                summary = summaries.get(section.title, section.content[:300])
                optimized_parts.append(f"[{section.title}] {summary}")
        
        # 2. 全体要約の追加
        if '全体要約' in summaries:
            optimized_parts.insert(0, f"[全体要約] {summaries['全体要約']}")
        
        # 3. 重要キーワードの文脈を追加
        for keyword in keywords[:5]:  # 上位5キーワード
            for section in sections:
                if keyword in section.content:
                    # キーワードを含む文章を抽出
                    sentences = re.split(r'[。！？]', section.content)
                    for sentence in sentences:
                        if keyword in sentence and len(sentence.strip()) > 20:
                            optimized_parts.append(f"[キーワード文脈: {keyword}] {sentence.strip()}")
                            break
                    break
        
        return '\n\n'.join(optimized_parts)
    
    def _basic_preprocessing(self, text_sections: Dict[str, str], 
                           document_info: Dict[str, str]) -> Dict[str, Any]:
        """基本的な前処理（フォールバック）"""
        combined_text = ' '.join(text_sections.values())
        
        # 簡単なキーワード抽出
        basic_keywords = self._basic_keyword_extraction(combined_text)
        
        # 簡単な要約
        basic_summary = self._basic_summarization(combined_text)
        
        return {
            'original_sections': text_sections,
            'analyzed_sections': [],
            'important_sections': [],
            'summaries': {'基本要約': basic_summary},
            'keywords': basic_keywords,
            'optimized_text': combined_text,
            'preprocessing_metadata': {
                'langextract_used': False,
                'sections_analyzed': len(text_sections),
                'fallback_used': True
            }
        }


# 統合サービスクラス
class IntegratedDocumentAnalyzer:
    """統合文書分析サービス"""
    
    def __init__(self):
        self.preprocessor = LangextractDocumentPreprocessor()
        # AI強化分析器は前述のクラスを使用
    
    def analyze_document_comprehensive(self, text_sections: Dict[str, str], 
                                     document_info: Dict[str, str]) -> Dict[str, Any]:
        """包括的文書分析"""
        try:
            # 1. 文書前処理
            preprocessing_result = self.preprocessor.preprocess_document(
                text_sections, document_info
            )
            
            # 2. 最適化されたテキストでAI強化感情分析
            from .ai_enhanced_sentiment import AIEnhancedSentimentAnalyzer
            ai_analyzer = AIEnhancedSentimentAnalyzer()
            
            sentiment_result = ai_analyzer.analyze_text_enhanced(
                preprocessing_result['optimized_text'],
                document_info=document_info
            )
            
            # 3. 結果統合
            comprehensive_result = {
                'preprocessing': preprocessing_result,
                'sentiment_analysis': sentiment_result,
                'integrated_insights': self._generate_integrated_insights(
                    preprocessing_result, sentiment_result, document_info
                ),
                'analysis_metadata': {
                    'preprocessing_used': True,
                    'ai_enhancement_used': sentiment_result.get('ai_enhancement_metadata', {}).get('ai_analysis_performed', False),
                    'optimization_effective': len(preprocessing_result['optimized_text']) < len(' '.join(text_sections.values())),
                    'total_processing_time': (
                        preprocessing_result.get('preprocessing_metadata', {}).get('processing_time', 0) +
                        sentiment_result.get('ai_enhancement_metadata', {}).get('processing_time', 0)
                    )
                }
            }
            
            return comprehensive_result
            
        except Exception as e:
            logger.error(f"包括的文書分析エラー: {e}")
            raise
    
    def _generate_integrated_insights(self, preprocessing_result: Dict, 
                                    sentiment_result: Dict, 
                                    document_info: Dict) -> Dict[str, Any]:
        """統合見解生成"""
        insights = {
            'document_structure_analysis': self._analyze_document_structure(preprocessing_result),
            'content_quality_assessment': self._assess_content_quality(preprocessing_result),
            'sentiment_confidence': self._calculate_overall_confidence(preprocessing_result, sentiment_result),
            'key_findings': self._extract_key_findings(preprocessing_result, sentiment_result),
            'recommendation': self._generate_analysis_recommendation(preprocessing_result, sentiment_result)
        }
        
        return insights
    
    def _analyze_document_structure(self, preprocessing_result: Dict) -> Dict[str, Any]:
        """文書構造分析"""
        sections = preprocessing_result.get('analyzed_sections', [])
        
        structure_analysis = {
            'total_sections': len(sections),
            'financial_sections': len([s for s in sections if s.section_type == 'financial']),
            'business_sections': len([s for s in sections if s.section_type == 'business']),
            'risk_sections': len([s for s in sections if s.section_type == 'risk']),
            'avg_importance_score': sum(s.importance_score for s in sections) / len(sections) if sections else 0,
            'high_importance_sections': len([s for s in sections if s.importance_score >= 2.0])
        }
        
        return structure_analysis
    
    def _assess_content_quality(self, preprocessing_result: Dict) -> Dict[str, Any]:
        """コンテンツ品質評価"""
        keywords = preprocessing_result.get('keywords', [])
        summaries = preprocessing_result.get('summaries', {})
        
        quality_assessment = {
            'keyword_diversity': len(set(keywords)),
            'summary_coverage': len(summaries),
            'information_density': 'high' if len(keywords) > 15 else 'medium' if len(keywords) > 8 else 'low',
            'analysis_readiness': 'ready' if len(keywords) > 5 else 'limited'
        }
        
        return quality_assessment
    
    def _calculate_overall_confidence(self, preprocessing_result: Dict, sentiment_result: Dict) -> float:
        """全体的な信頼度計算"""
        confidence_factors = []
        
        # 前処理の品質
        sections_count = len(preprocessing_result.get('analyzed_sections', []))
        if sections_count >= 5:
            confidence_factors.append(0.9)
        elif sections_count >= 3:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.5)
        
        # キーワードの多様性
        keywords_count = len(preprocessing_result.get('keywords', []))
        if keywords_count >= 10:
            confidence_factors.append(0.8)
        elif keywords_count >= 5:
            confidence_factors.append(0.6)
        else:
            confidence_factors.append(0.4)
        
        # AI分析の信頼度
        ai_metadata = sentiment_result.get('ai_enhancement_metadata', {})
        if ai_metadata.get('ai_analysis_performed', False):
            ai_confidence = sentiment_result.get('integration_confidence', 0.5)
            confidence_factors.append(ai_confidence)
        else:
            confidence_factors.append(0.6)  # 辞書ベースの標準信頼度
        
        return sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.5
    
    def _extract_key_findings(self, preprocessing_result: Dict, sentiment_result: Dict) -> List[str]:
        """主要発見事項の抽出"""
        findings = []
        
        # 感情分析結果から
        overall_score = sentiment_result.get('overall_score', 0)
        if abs(overall_score) > 0.5:
            sentiment_text = 'ポジティブ' if overall_score > 0 else 'ネガティブ'
            findings.append(f"強い{sentiment_text}傾向を検出（スコア: {overall_score:.2f}）")
        
        # 重要セクションから
        important_sections = preprocessing_result.get('important_sections', [])
        if important_sections:
            high_importance = [s for s in important_sections if s.importance_score >= 2.0]
            if high_importance:
                findings.append(f"{len(high_importance)}個の高重要度セクションを特定")
        
        # キーワード分析から
        keywords = preprocessing_result.get('keywords', [])
        financial_keywords = [k for k in keywords if any(term in k for term in ['売上', '利益', '収益'])]
        if financial_keywords:
            findings.append(f"主要財務指標キーワード: {', '.join(financial_keywords[:3])}")
        
        return findings
    
    def _generate_analysis_recommendation(self, preprocessing_result: Dict, sentiment_result: Dict) -> str:
        """分析推奨事項生成"""
        confidence = self._calculate_overall_confidence(preprocessing_result, sentiment_result)
        
        if confidence >= 0.8:
            return "高い信頼性での分析が完了しました。結果を投資判断の参考としてご活用ください。"
        elif confidence >= 0.6:
            return "中程度の信頼性での分析です。他の情報と合わせて総合的に判断することを推奨します。"
        else:
            return "限定的な信頼性での分析です。追加の詳細分析や専門家の意見を求めることを推奨します。"