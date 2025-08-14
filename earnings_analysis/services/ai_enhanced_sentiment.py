# earnings_analysis/services/ai_enhanced_sentiment.py
import google.generativeai as genai
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from django.conf import settings
from django.utils import timezone
import json
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

from .sentiment_analyzer import TransparentSentimentAnalyzer, AnalysisConfig
from .gemini_insights import GeminiInsightsGenerator

logger = logging.getLogger(__name__)

@dataclass
class AIAnalysisConfig:
    """AI分析設定"""
    enable_ai_scoring: bool = True
    enable_context_analysis: bool = True
    enable_importance_weighting: bool = True
    ai_weight_ratio: float = 0.4  # AI分析の重み（0.0-1.0）
    dictionary_weight_ratio: float = 0.6  # 辞書分析の重み
    max_sentences_per_batch: int = 10
    api_timeout: int = 30
    fallback_on_error: bool = True


class AIEnhancedSentimentAnalyzer:
    """AI強化感情分析エンジン"""
    
    def __init__(self, config: Optional[AIAnalysisConfig] = None):
        self.config = config or AIAnalysisConfig()
        self.dictionary_analyzer = TransparentSentimentAnalyzer()
        self.gemini_model = None
        self.ai_available = False
        
        # Gemini API初期化
        self._initialize_gemini()
    
    def _initialize_gemini(self):
        """Gemini API初期化"""
        try:
            api_key = getattr(settings, 'GEMINI_API_KEY', None)
            if api_key:
                genai.configure(api_key=api_key)
                self.gemini_model = genai.GenerativeModel("gemini-2.5-flash")
                self.ai_available = True
                logger.info("AI強化感情分析：Gemini API初期化成功")
            else:
                logger.warning("AI強化感情分析：GEMINI_API_KEYが設定されていません")
        except Exception as e:
            logger.error(f"AI強化感情分析：Gemini API初期化エラー: {e}")
            self.ai_available = False
    
    def analyze_text_enhanced(self, text: str, session_id: str = None, 
                            document_info: Dict[str, str] = None) -> Dict[str, Any]:
        """AI強化感情分析メイン処理"""
        start_time = time.time()
        
        try:
            # 1. 従来の辞書ベース分析
            dictionary_result = self.dictionary_analyzer.analyze_text(
                text, session_id, document_info
            )
            
            # 2. AI分析（有効な場合のみ）
            ai_result = None
            if self.ai_available and self.config.enable_ai_scoring:
                ai_result = self._perform_ai_analysis(text, dictionary_result, document_info)
            
            # 3. 結果統合
            enhanced_result = self._integrate_results(
                dictionary_result, ai_result, document_info
            )
            
            # 4. メタデータ追加
            enhanced_result['ai_enhancement_metadata'] = {
                'ai_available': self.ai_available,
                'ai_analysis_performed': ai_result is not None,
                'processing_time': time.time() - start_time,
                'integration_method': 'weighted_average' if ai_result else 'dictionary_only',
                'ai_weight_ratio': self.config.ai_weight_ratio if ai_result else 0.0,
                'enhancement_timestamp': timezone.now().isoformat()
            }
            
            return enhanced_result
            
        except Exception as e:
            logger.error(f"AI強化感情分析エラー: {e}")
            if self.config.fallback_on_error:
                return dictionary_result
            else:
                raise
    
    def _perform_ai_analysis(self, text: str, dictionary_result: Dict, 
                           document_info: Dict) -> Optional[Dict]:
        """AI分析実行"""
        try:
            # 文章を重要度別に分割
            sentences = self._extract_important_sentences(text, dictionary_result)
            
            # バッチ処理でAI分析
            ai_scores = self._analyze_sentences_batch(sentences, document_info)
            
            # 文脈を考慮した全体スコア計算
            overall_ai_score = self._calculate_contextual_score(
                sentences, ai_scores, dictionary_result
            )
            
            # 文章重要度分析
            importance_weights = self._analyze_sentence_importance(
                sentences, document_info
            )
            
            return {
                'overall_score': overall_ai_score,
                'sentence_scores': ai_scores,
                'importance_weights': importance_weights,
                'analysis_method': 'ai_contextual',
                'sentences_analyzed': len(sentences),
                'confidence': self._calculate_ai_confidence(ai_scores)
            }
            
        except Exception as e:
            logger.error(f"AI分析実行エラー: {e}")
            return None
    
    def _extract_important_sentences(self, text: str, dictionary_result: Dict) -> List[Dict]:
        """重要文章の抽出"""
        # 辞書分析で検出された重要文章を優先
        important_sentences = []
        
        # サンプル文章から重要なものを抽出
        sample_sentences = dictionary_result.get('sample_sentences', {})
        
        for sentiment_type in ['positive', 'negative']:
            sentences = sample_sentences.get(sentiment_type, [])
            for sentence in sentences[:5]:  # 各感情から最大5文
                important_sentences.append({
                    'text': sentence.get('text', ''),
                    'dictionary_score': sentence.get('score', 0),
                    'keywords': sentence.get('keywords', []),
                    'sentiment_type': sentiment_type
                })
        
        # 追加で一般文章も分析対象に
        all_sentences = self._split_text_to_sentences(text)
        financial_sentences = self._filter_financial_sentences(all_sentences)
        
        for sentence in financial_sentences[:10]:  # 最大10文追加
            if not any(s['text'] == sentence for s in important_sentences):
                important_sentences.append({
                    'text': sentence,
                    'dictionary_score': 0,
                    'keywords': [],
                    'sentiment_type': 'general'
                })
        
        return important_sentences
    
    def _analyze_sentences_batch(self, sentences: List[Dict], 
                               document_info: Dict) -> Dict[str, float]:
        """文章バッチ分析"""
        if not self.gemini_model:
            return {}
        
        ai_scores = {}
        
        # バッチ単位で処理
        for i in range(0, len(sentences), self.config.max_sentences_per_batch):
            batch = sentences[i:i + self.config.max_sentences_per_batch]
            batch_scores = self._analyze_batch_with_gemini(batch, document_info)
            ai_scores.update(batch_scores)
        
        return ai_scores
    
    def _analyze_batch_with_gemini(self, batch: List[Dict], 
                                 document_info: Dict) -> Dict[str, float]:
        """Geminiによるバッチ分析"""
        try:
            prompt = self._build_batch_analysis_prompt(batch, document_info)
            
            response = self.gemini_model.generate_content(prompt)
            
            if hasattr(response, "text") and response.text:
                return self._parse_batch_analysis_response(response.text, batch)
            else:
                logger.warning("Geminiバッチ分析：空の応答")
                return {}
                
        except Exception as e:
            logger.error(f"Geminiバッチ分析エラー: {e}")
            return {}
    
    def _build_batch_analysis_prompt(self, batch: List[Dict], 
                                   document_info: Dict) -> str:
        """バッチ分析用プロンプト構築"""
        company_name = document_info.get('company_name', '企業')
        doc_type = document_info.get('doc_description', '決算書類')
        
        prompt = f"""
あなたは金融アナリストとして、{company_name}の{doc_type}の感情分析を行ってください。

以下の文章それぞれについて、投資家や経営陣の心理状態を考慮し、-1.0から+1.0の感情スコアを付けてください。

評価基準：
- +1.0: 非常にポジティブ（強い成長期待、大幅改善）
- +0.5: ポジティブ（成長期待、改善）
- 0.0: 中立（事実の記述、変化なし）
- -0.5: ネガティブ（懸念、悪化）
- -1.0: 非常にネガティブ（深刻な問題、大幅悪化）

特に注意すべき点：
1. 文脈を考慮した感情判定（「減収の改善」は悪化→改善のポジティブ転換）
2. 否定文の適切な処理（「成長しなかった」はネガティブ）
3. 比較表現の考慮（「前年比」「前期比」などの文脈）
4. 財務用語の正確な理解

分析対象文章：
"""
        
        for i, sentence_data in enumerate(batch, 1):
            sentence = sentence_data['text']
            dict_score = sentence_data.get('dictionary_score', 0)
            keywords = sentence_data.get('keywords', [])
            
            prompt += f"\n{i}. 「{sentence}」\n"
            if keywords:
                prompt += f"   検出キーワード: {', '.join(keywords)}\n"
            if dict_score != 0:
                prompt += f"   辞書分析スコア: {dict_score:.2f}\n"
        
        prompt += """
回答形式：
各文章に対して以下の形式で回答してください：

1: スコア=0.75, 理由=業績向上への期待を示すポジティブな表現
2: スコア=-0.30, 理由=一時的な困難を示すがそれほど深刻ではない
...

必ず数値と簡潔な理由を含めてください。
"""
        
        return prompt
    
    def _parse_batch_analysis_response(self, response_text: str, 
                                     batch: List[Dict]) -> Dict[str, float]:
        """バッチ分析応答の解析"""
        ai_scores = {}
        
        try:
            lines = response_text.strip().split('\n')
            
            for line in lines:
                # 「1: スコア=0.75, 理由=...」形式をパース
                match = re.match(r'(\d+):\s*スコア\s*=\s*([-+]?\d*\.?\d+)', line)
                if match:
                    index = int(match.group(1)) - 1
                    score = float(match.group(2))
                    
                    if 0 <= index < len(batch):
                        sentence_text = batch[index]['text']
                        # スコア範囲チェック
                        score = max(-1.0, min(1.0, score))
                        ai_scores[sentence_text] = score
            
            logger.info(f"AI分析結果：{len(ai_scores)}/{len(batch)}文を解析")
            return ai_scores
            
        except Exception as e:
            logger.error(f"AI分析応答解析エラー: {e}")
            return {}
    
    def _analyze_sentence_importance(self, sentences: List[Dict], 
                                   document_info: Dict) -> Dict[str, float]:
        """文章重要度分析"""
        importance_weights = {}
        
        try:
            if not self.gemini_model:
                # フォールバック：キーワード数ベースの重要度
                for sentence_data in sentences:
                    text = sentence_data['text']
                    keywords = sentence_data.get('keywords', [])
                    base_weight = 1.0
                    
                    # キーワード数による重み調整
                    if len(keywords) >= 3:
                        base_weight = 1.5
                    elif len(keywords) >= 1:
                        base_weight = 1.2
                    
                    # 財務数値を含む場合の重み増加
                    if re.search(r'[0-9,]+[億千万]?円|[0-9]+%', text):
                        base_weight *= 1.3
                    
                    importance_weights[text] = base_weight
                
                return importance_weights
            
            # AI による重要度分析
            prompt = self._build_importance_analysis_prompt(sentences, document_info)
            response = self.gemini_model.generate_content(prompt)
            
            if hasattr(response, "text") and response.text:
                return self._parse_importance_response(response.text, sentences)
            else:
                # フォールバック処理
                return self._calculate_fallback_importance(sentences)
                
        except Exception as e:
            logger.error(f"文章重要度分析エラー: {e}")
            return self._calculate_fallback_importance(sentences)
    
    def _build_importance_analysis_prompt(self, sentences: List[Dict], 
                                        document_info: Dict) -> str:
        """重要度分析プロンプト構築"""
        company_name = document_info.get('company_name', '企業')
        
        prompt = f"""
{company_name}の決算書類の感情分析において、以下の文章の重要度を1.0から3.0の範囲で評価してください。

重要度の基準：
- 3.0: 極めて重要（業績・戦略の核心部分）
- 2.5: 非常に重要（主要な財務指標・経営方針）
- 2.0: 重要（補足的な財務情報・市場動向）
- 1.5: やや重要（一般的な記述・詳細情報）
- 1.0: 標準（形式的な記述・定型文）

評価対象文章：
"""
        
        for i, sentence_data in enumerate(sentences, 1):
            text = sentence_data['text']
            prompt += f"{i}. 「{text}」\n"
        
        prompt += """
回答形式：
1: 重要度=2.5
2: 重要度=1.8
...
"""
        return prompt
    
    def _parse_importance_response(self, response_text: str, 
                                 sentences: List[Dict]) -> Dict[str, float]:
        """重要度分析応答の解析"""
        importance_weights = {}
        
        try:
            lines = response_text.strip().split('\n')
            
            for line in lines:
                match = re.match(r'(\d+):\s*重要度\s*=\s*(\d*\.?\d+)', line)
                if match:
                    index = int(match.group(1)) - 1
                    importance = float(match.group(2))
                    
                    if 0 <= index < len(sentences):
                        sentence_text = sentences[index]['text']
                        # 重要度範囲チェック
                        importance = max(1.0, min(3.0, importance))
                        importance_weights[sentence_text] = importance
            
            return importance_weights
            
        except Exception as e:
            logger.error(f"重要度分析応答解析エラー: {e}")
            return self._calculate_fallback_importance(sentences)
    
    def _calculate_fallback_importance(self, sentences: List[Dict]) -> Dict[str, float]:
        """フォールバック重要度計算"""
        importance_weights = {}
        
        for sentence_data in sentences:
            text = sentence_data['text']
            base_weight = 1.0
            
            # 数値を含む文章の重み増加
            if re.search(r'[0-9,]+', text):
                base_weight += 0.5
            
            # 財務用語を含む文章の重み増加
            financial_terms = ['売上', '利益', '収益', '損失', '増収', '減収', '増益', '減益']
            if any(term in text for term in financial_terms):
                base_weight += 0.3
            
            importance_weights[text] = base_weight
        
        return importance_weights
    
    def _calculate_contextual_score(self, sentences: List[Dict], 
                                  ai_scores: Dict[str, float], 
                                  dictionary_result: Dict) -> float:
        """文脈を考慮した全体スコア計算"""
        if not ai_scores:
            return dictionary_result.get('overall_score', 0.0)
        
        try:
            # AI分析スコアの重み付き平均
            total_score = 0.0
            total_weight = 0.0
            
            for sentence_data in sentences:
                text = sentence_data['text']
                if text in ai_scores:
                    score = ai_scores[text]
                    weight = 1.0  # 基本重み
                    
                    # 辞書分析との一致度による重み調整
                    dict_score = sentence_data.get('dictionary_score', 0)
                    if dict_score != 0:
                        # 辞書分析と一致する場合は信頼度アップ
                        if (score > 0 and dict_score > 0) or (score < 0 and dict_score < 0):
                            weight *= 1.2
                    
                    total_score += score * weight
                    total_weight += weight
            
            if total_weight > 0:
                return total_score / total_weight
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"文脈考慮スコア計算エラー: {e}")
            return dictionary_result.get('overall_score', 0.0)
    
    def _calculate_ai_confidence(self, ai_scores: Dict[str, float]) -> float:
        """AI分析の信頼度計算"""
        if not ai_scores:
            return 0.0
        
        scores = list(ai_scores.values())
        
        # スコアの分散から信頼度を計算
        if len(scores) >= 2:
            import statistics
            variance = statistics.variance(scores)
            # 分散が小さいほど信頼度が高い
            confidence = max(0.0, min(1.0, 1.0 - variance))
        else:
            confidence = 0.5
        
        return confidence
    
    def _integrate_results(self, dictionary_result: Dict, ai_result: Optional[Dict], 
                         document_info: Dict) -> Dict[str, Any]:
        """辞書分析とAI分析の結果統合"""
        if not ai_result:
            # AI分析が利用できない場合は辞書分析のみ
            dictionary_result['integration_method'] = 'dictionary_only'
            return dictionary_result
        
        try:
            # 重み付き平均でスコア統合
            dict_score = dictionary_result.get('overall_score', 0.0)
            ai_score = ai_result.get('overall_score', 0.0)
            
            # AI信頼度による動的重み調整
            ai_confidence = ai_result.get('confidence', 0.5)
            adjusted_ai_weight = self.config.ai_weight_ratio * ai_confidence
            adjusted_dict_weight = 1.0 - adjusted_ai_weight
            
            integrated_score = (
                dict_score * adjusted_dict_weight + 
                ai_score * adjusted_ai_weight
            )
            
            # 統合結果の構築
            integrated_result = dictionary_result.copy()
            integrated_result.update({
                'overall_score': integrated_score,
                'integration_method': 'weighted_average',
                'component_scores': {
                    'dictionary_score': dict_score,
                    'ai_score': ai_score,
                    'dictionary_weight': adjusted_dict_weight,
                    'ai_weight': adjusted_ai_weight
                },
                'ai_analysis_details': ai_result,
                'integration_confidence': ai_confidence
            })
            
            return integrated_result
            
        except Exception as e:
            logger.error(f"結果統合エラー: {e}")
            return dictionary_result
    
    def _split_text_to_sentences(self, text: str) -> List[str]:
        """テキストを文章に分割"""
        sentences = re.split(r'[。！？\n]', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]
    
    def _filter_financial_sentences(self, sentences: List[str]) -> List[str]:
        """財務関連文章のフィルタリング"""
        financial_keywords = [
            '売上', '利益', '収益', '損失', '純益', '営業', '経常',
            '増収', '減収', '増益', '減益', '黒字', '赤字',
            '円', '%', '前年', '前期', '同期', '比較'
        ]
        
        financial_sentences = []
        for sentence in sentences:
            if any(keyword in sentence for keyword in financial_keywords):
                financial_sentences.append(sentence)
        
        return financial_sentences


# 使用例とサービス統合
class EnhancedSentimentAnalysisService:
    """AI強化感情分析サービス"""
    
    def __init__(self):
        self.analyzer = AIEnhancedSentimentAnalyzer()
    
    def analyze_document_enhanced(self, document_id: str, force: bool = False, 
                                user_ip: str = None) -> Dict[str, Any]:
        """AI強化感情分析実行"""
        try:
            # 既存のサービスロジックを流用
            from ..models import DocumentMetadata, SentimentAnalysisSession
            
            document = DocumentMetadata.objects.get(doc_id=document_id, legal_status='1')
            
            # セッション作成（既存ロジック）
            session = SentimentAnalysisSession.objects.create(
                document=document,
                processing_status='PENDING'
            )
            
            # AI強化分析実行
            document_info = {
                'company_name': document.company_name,
                'doc_description': document.doc_description,
                'doc_type_code': document.doc_type_code,
                'submit_date': document.submit_date_time.strftime('%Y-%m-%d'),
                'securities_code': document.securities_code or '',
            }
            
            # XBRLテキストまたはサンプルテキストを取得
            from .xbrl_extractor import EDINETXBRLService
            xbrl_service = EDINETXBRLService()
            
            try:
                text_sections = xbrl_service.get_xbrl_text_from_document(document)
                if text_sections:
                    combined_text = ' '.join(text_sections.values())
                else:
                    combined_text = self._generate_sample_text(document)
            except Exception:
                combined_text = self._generate_sample_text(document)
            
            # AI強化分析実行
            result = self.analyzer.analyze_text_enhanced(
                combined_text, str(session.session_id), document_info
            )
            
            # セッション更新
            session.overall_score = result['overall_score']
            session.sentiment_label = self._determine_sentiment_label(result['overall_score'])
            session.analysis_result = result
            session.processing_status = 'COMPLETED'
            session.save()
            
            return {
                'status': 'completed',
                'session_id': str(session.session_id),
                'result': result
            }
            
        except Exception as e:
            logger.error(f"AI強化感情分析エラー: {e}")
            raise
    
    def _determine_sentiment_label(self, score: float) -> str:
        """感情ラベル決定"""
        if score > 0.15:
            return 'positive'
        elif score < -0.15:
            return 'negative'
        else:
            return 'neutral'
    
    def _generate_sample_text(self, document) -> str:
        """サンプルテキスト生成"""
        return f"""
        企業名: {document.company_name}
        書類概要: {document.doc_description}
        提出日: {document.submit_date_time.strftime('%Y年%m月%d日')}
        
        当社の業績は前年同期と比較して順調に推移しており、
        売上高の増加と収益性の向上が実現されています。
        """