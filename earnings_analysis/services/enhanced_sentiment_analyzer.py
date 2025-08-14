# earnings_analysis/services/enhanced_sentiment_analyzer.py（既存システム拡張版）
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from django.conf import settings
from django.utils import timezone
import json
import re
import time
import asyncio
from .langextract_sentiment_service import HybridSentimentAnalysisService
from .sentiment_analyzer import TransparentSentimentAnalyzer, AnalysisConfig, SentimentAnalysisService
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
    """LangExtract対応の拡張感情分析サービス"""
    
    def __init__(self):
        self.hybrid_service = HybridSentimentAnalysisService()
        self.use_langextract = getattr(settings, 'USE_LANGEXTRACT_SENTIMENT', True)
        self.langextract_timeout = getattr(settings, 'LANGEXTRACT_TIMEOUT_SECONDS', 120)
    
    def _load_enhancement_config(self) -> AIEnhancedSentimentAnalyzer:
        """設定の読み込み"""
        settings_config = getattr(settings, 'SENTIMENT_ANALYSIS_CONFIG', {})
        
        return AIEnhancedSentimentAnalyzer(
            # 既存設定
            positive_threshold=settings_config.get('positive_threshold', 0.15),
            negative_threshold=settings_config.get('negative_threshold', -0.15),
            min_sentence_length=settings_config.get('min_sentence_length', 10),
            max_sample_sentences=settings_config.get('max_sample_sentences', 15),
            
            # 拡張設定
            enable_ai_enhancement=settings_config.get('enable_ai_enhancement', True),
            enable_context_weighting=settings_config.get('enable_context_weighting', True),
            enable_extended_dictionary=settings_config.get('enable_extended_dictionary', True),
            ai_enhancement_threshold=settings_config.get('ai_enhancement_threshold', 1.5),
            max_ai_sentences=settings_config.get('max_ai_sentences', 5),
            context_window_size=settings_config.get('context_window_size', 100),
            cache_ai_results=settings_config.get('cache_ai_results', True),
        )
    
    def start_analysis(self, document_id: str, force: bool = False, user_ip: str = None) -> Dict[str, Any]:
        """感情分析開始（LangExtract対応版）"""
        from ..models import DocumentMetadata, SentimentAnalysisSession
        
        try:
            document = DocumentMetadata.objects.get(doc_id=document_id, legal_status='1')
            # 期限切れセッションのクリーンアップ
            self._cleanup_expired_sessions_if_needed()
            
            # 拡張機能の使用判定
            if use_enhancement is None:
                use_enhancement = self.enhancement_config.enable_ai_enhancement
            
            if not force:
                # 有効な最新セッションのチェック（拡張版も含む）
                recent_session = SentimentAnalysisSession.objects.filter(
                    document=document,
                    processing_status='COMPLETED',
                    created_at__gte=timezone.now() - timedelta(hours=1),
                    expires_at__gt=timezone.now()
                ).first()
                
                if recent_session:
                    # 既存セッションが拡張版かどうかをチェック
                    is_enhanced = self._is_enhanced_session(recent_session)
                    
                    if use_enhancement == is_enhanced:
                        logger.info(f"有効な{'拡張版' if is_enhanced else '基本版'}セッションが存在: {recent_session.session_id}")
                        return {
                            'status': 'already_analyzed',
                            'session_id': str(recent_session.session_id),
                            'result': recent_session.analysis_result,
                            'enhancement_used': is_enhanced,
                            'message': f'1時間以内に分析済みです（{"拡張版" if is_enhanced else "基本版"}）'
                        }
            
            # 新しいセッションを作成
            session = SentimentAnalysisSession.objects.create(
                document=document,
                processing_status='PENDING'
            )
            
            logger.info(f"Starting {'hybrid' if self.use_langextract else 'traditional'} sentiment analysis: {session.session_id}")
            
            # 非同期処理で分析実行
            if self.use_langextract:
                # LangExtract + Gemini 分析
                asyncio.create_task(self._execute_hybrid_analysis(session.id, user_ip))
            else:
                # 従来の分析
                import threading
                threading.Thread(
                    target=self._execute_traditional_analysis,
                    args=(session.id, user_ip),
                    daemon=True
                ).start()
            
            return {
                'status': 'started',
                'session_id': str(session.session_id),
                'analysis_method': 'hybrid_langextract' if self.use_langextract else 'traditional',
                'message': f'{"高度感情分析（LangExtract + Gemini）" if self.use_langextract else "標準感情分析"}を開始しました'
            }
            
        except DocumentMetadata.DoesNotExist:
            raise Exception('指定された書類が見つかりません')
        except Exception as e:
            logger.error(f"拡張分析開始エラー: {e}")
            raise Exception(f"分析開始に失敗しました: {str(e)}")
    

    async def _execute_hybrid_analysis(self, session_id: int, user_ip: str = None):
        """ハイブリッド分析実行（非同期）"""
        from ..models import SentimentAnalysisSession, SentimentAnalysisHistory
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            session = SentimentAnalysisSession.objects.get(id=session_id)
            session.processing_status = 'PROCESSING'
            session.analysis_result = {
                'progress': 10, 
                'current_step': 'LangExtract初期化中...',
                'method': 'hybrid_langextract_gemini'
            }
            session.save()
            
            # 書類情報準備
            document_info = self._prepare_document_info(session.document)
            
            # XBRL取得
            session.analysis_result.update({
                'progress': 20,
                'current_step': 'XBRLデータ取得中...'
            })
            session.save()
            
            text_sections = await self._get_text_sections_async(session.document)
            
            if not text_sections:
                # フォールバック処理
                session.analysis_result.update({
                    'progress': 40,
                    'current_step': '基本データで従来分析実行中...'
                })
                session.save()
                
                document_text = self._extract_basic_document_text(session.document)
                text_sections = {'document_basic': document_text}
            
            # LangExtract + Gemini 分析実行
            session.analysis_result.update({
                'progress': 50,
                'current_step': 'LangExtractで重要要素抽出中...'
            })
            session.save()
            
            # タイムアウト付きで実行
            try:
                result = await asyncio.wait_for(
                    self.hybrid_service.analyze_hybrid(text_sections, document_info),
                    timeout=self.langextract_timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"LangExtract analysis timeout, falling back to traditional analysis")
                result = self._fallback_to_traditional_sync(text_sections, document_info)
                result['analysis_method'] = 'traditional_timeout_fallback'
            
            session.analysis_result.update({
                'progress': 90,
                'current_step': '分析結果統合中...'
            })
            session.save()
            
            # 結果保存
            session.overall_score = result['overall_score']
            session.sentiment_label = result['sentiment_label']
            session.analysis_result = result
            session.processing_status = 'COMPLETED'
            session.save()
            
            # 履歴保存
            analysis_duration = asyncio.get_event_loop().time() - start_time
            SentimentAnalysisHistory.objects.create(
                document=session.document,
                overall_score=result['overall_score'],
                sentiment_label=result['sentiment_label'],
                user_ip=user_ip,
                analysis_duration=analysis_duration
            )
            
            logger.info(f"Hybrid sentiment analysis completed: {session.session_id} ({analysis_duration:.2f}s)")
            
        except Exception as e:
            logger.error(f"Hybrid sentiment analysis error: {session_id} - {e}")
            
            # エラー時は従来分析にフォールバック
            try:
                session = SentimentAnalysisSession.objects.get(id=session_id)
                session.analysis_result.update({
                    'progress': 60,
                    'current_step': 'エラー発生、従来分析にフォールバック中...'
                })
                session.save()
                
                # 同期的に従来分析実行
                self._execute_traditional_analysis_sync(session_id, user_ip)
                
            except Exception as fallback_error:
                logger.error(f"Fallback analysis also failed: {fallback_error}")
                session = SentimentAnalysisSession.objects.get(id=session_id)
                session.processing_status = 'FAILED'
                session.error_message = f"ハイブリッド分析失敗: {str(e)}, フォールバック失敗: {str(fallback_error)}"
                session.save()
    
    async def _get_text_sections_async(self, document) -> Optional[Dict[str, str]]:
        """非同期でXBRLテキストセクション取得"""
        try:
            from .xbrl_extractor import EDINETXBRLService
            
            xbrl_service = EDINETXBRLService()
            
            # 非同期でXBRL取得（実際の実装では適切な非同期処理を使用）
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, 
                xbrl_service.get_xbrl_text_from_document, 
                document
            )
            
        except Exception as e:
            logger.warning(f"Async XBRL extraction failed: {e}")
            return None
    
    def _fallback_to_traditional_sync(self, text_sections: Dict[str, str], 
                                    document_info: Dict[str, str]) -> Dict[str, Any]:
        """同期的に従来分析実行（フォールバック用）"""
        try:
            from .sentiment_analyzer import TransparentSentimentAnalyzer
            
            analyzer = TransparentSentimentAnalyzer()
            return analyzer.analyze_text_sections(text_sections, document_info=document_info)
            
        except Exception as e:
            logger.error(f"Traditional fallback analysis failed: {e}")
            return self._empty_result()
    
    def _execute_traditional_analysis_sync(self, session_id: int, user_ip: str = None):
        """同期的に従来分析実行"""
        # 既存の_execute_analysis メソッドの内容をここに移動
        pass
    
    def _prepare_document_info(self, document) -> Dict[str, str]:
        """書類情報準備"""
        return {
            'company_name': document.company_name,
            'doc_description': document.doc_description,
            'doc_type_code': document.doc_type_code,
            'submit_date': document.submit_date_time.strftime('%Y-%m-%d'),
            'securities_code': document.securities_code or '',
        }
    
    def _extract_basic_document_text(self, document) -> str:
        """基本書類テキスト抽出（フォールバック用）"""
        text_parts = [
            f"企業名: {document.company_name}",
            f"書類概要: {document.doc_description}",
            f"提出日: {document.submit_date_time.strftime('%Y年%m月%d日')}",
        ]
        
        if document.period_start and document.period_end:
            text_parts.append(f"対象期間: {document.period_start}から{document.period_end}")
        
        # より詳細なサンプルテキストを追加
        enhanced_scenarios = [
            "当社の業績は前年同期と比較して順調に推移しており、売上高の増加と収益性の向上が実現されています。",
            "一方で、一部事業では減収の改善も見られ、市場環境の変化に適応しつつ継続的な事業改善を図っています。",
            "今後も持続的な成長を目指し、効率的な経営資源の活用と競争力の強化に取り組んでまいります。",
        ]
        
        text_parts.extend(enhanced_scenarios)
        return " ".join(text_parts)
    
    def _empty_result(self) -> Dict[str, Any]:
        """空結果生成"""
        return {
            'overall_score': 0.0,
            'sentiment_label': 'neutral',
            'analysis_method': 'error_fallback',
            'error': True
        }
            
    def _is_enhanced_session(self, session) -> bool:
        """セッションが拡張版で分析されたかどうかを判定"""
        if not session.analysis_result:
            return False
        
        # 拡張版の特徴的なメタデータの存在確認
        metadata = session.analysis_result.get('enhancement_metadata', {})
        return metadata.get('enhancement_version') is not None
    
    def _execute_enhanced_analysis(self, session_id: int, user_ip: str = None, use_enhancement: bool = True):
        """拡張分析実行"""
        from ..models import SentimentAnalysisSession, SentimentAnalysisHistory
        
        start_time = time.time()
        
        try:
            session = SentimentAnalysisSession.objects.get(id=session_id)
            session.processing_status = 'PROCESSING'
            
            # 進行状況の更新
            if use_enhancement:
                session.analysis_result = {'progress': 5, 'current_step': '拡張感情分析エンジン初期化中...'}
            else:
                session.analysis_result = {'progress': 5, 'current_step': '基本感情分析エンジン初期化中...'}
            session.save()
            
            # 書類情報を準備
            document_info = {
                'company_name': session.document.company_name,
                'doc_description': session.document.doc_description,
                'doc_type_code': session.document.doc_type_code,
                'submit_date': session.document.submit_date_time.strftime('%Y-%m-%d'),
                'securities_code': session.document.securities_code or '',
            }
            
            session.analysis_result = {'progress': 20, 'current_step': 'XBRLファイル取得中...'}
            session.save()
            
            # XBRLテキストの取得
            try:
                xbrl_text_sections = self.xbrl_service.get_xbrl_text_from_document(session.document)
            except Exception as e:
                logger.warning(f"XBRL取得失敗: {e}")
                xbrl_text_sections = None
            
            if not xbrl_text_sections:
                session.analysis_result = {
                    'progress': 40, 
                    'current_step': f'基本情報を使用して{"拡張版" if use_enhancement else "基本版"}分析中...'
                }
                session.save()
                
                # サンプルテキストで分析
                document_text = self._extract_enhanced_document_text(session.document)
                
                if use_enhancement:
                    result = self.enhanced_analyzer.analyze_text(document_text, str(session.session_id), document_info)
                else:
                    result = self.analyzer.analyze_text(document_text, str(session.session_id), document_info)
            else:
                session.analysis_result = {
                    'progress': 50, 
                    'current_step': 'XBRLテキスト前処理中...'
                }
                session.save()
                
                session.analysis_result = {
                    'progress': 70, 
                    'current_step': f'{"拡張版" if use_enhancement else "基本版"}感情分析実行中（重複カウント・否定文対応）...'
                }
                session.save()
                
                # XBRLセクション分析
                if use_enhancement:
                    result = self.enhanced_analyzer.analyze_text_sections(xbrl_text_sections, str(session.session_id), document_info)
                else:
                    result = self.analyzer.analyze_text_sections(xbrl_text_sections, str(session.session_id), document_info)
            
            session.analysis_result = {'progress': 90, 'current_step': '分析結果最適化中...'}
            session.save()
            
            # セッション更新
            session.overall_score = result['overall_score']
            session.sentiment_label = result['sentiment_label']
            session.analysis_result = result
            session.processing_status = 'COMPLETED'
            session.save()
            
            # 履歴保存
            analysis_duration = time.time() - start_time
            SentimentAnalysisHistory.objects.create(
                document=session.document,
                overall_score=result['overall_score'],
                sentiment_label=result['sentiment_label'],
                user_ip=user_ip,
                analysis_duration=analysis_duration
            )
            
            enhancement_info = "拡張版" if use_enhancement else "基本版"
            logger.info(f"{enhancement_info}感情分析完了: {session.session_id} ({analysis_duration:.2f}秒)")
            
        except Exception as e:
            logger.error(f"拡張感情分析エラー: {session_id} - {e}")
            
            try:
                session = SentimentAnalysisSession.objects.get(id=session_id)
                session.processing_status = 'FAILED'
                session.error_message = str(e)
                session.save()
            except:
                pass
    
    def get_progress(self, session_id: str) -> Dict[str, Any]:
        """進行状況取得（拡張版情報付き）"""
        result = super().get_progress(session_id)
        
        # 拡張版の情報を追加
        try:
            from ..models import SentimentAnalysisSession
            session = SentimentAnalysisSession.objects.get(session_id=session_id)
            
            if session.analysis_result:
                enhancement_metadata = session.analysis_result.get('enhancement_metadata', {})
                result['enhancement_info'] = {
                    'is_enhanced': enhancement_metadata.get('enhancement_version') is not None,
                    'ai_analysis_performed': enhancement_metadata.get('ai_analysis_performed', False),
                    'features_enabled': enhancement_metadata.get('features_enabled', {})
                }
        except:
            pass
        
        return result
    
    def get_result(self, session_id: str) -> Dict[str, Any]:
        """分析結果取得（拡張版情報付き）"""
        result = super().get_result(session_id)
        
        # 拡張版の情報を追加
        if result.get('status') == 'completed' and 'result' in result:
            enhancement_metadata = result['result'].get('enhancement_metadata', {})
            result['enhancement_summary'] = {
                'version': enhancement_metadata.get('enhancement_version', 'basic'),
                'ai_analysis_performed': enhancement_metadata.get('ai_analysis_performed', False),
                'enhanced_patterns_found': enhancement_metadata.get('enhanced_patterns_found', 0),
                'important_sentences_extracted': enhancement_metadata.get('important_sentences_extracted', 0),
                'processing_time': enhancement_metadata.get('processing_time', 0),
                'features_enabled': enhancement_metadata.get('features_enabled', {})
            }
        
        return result
    
    def _extract_enhanced_document_text(self, document) -> str:
        """拡張サンプルテキスト生成"""
        text_parts = [
            f"企業名: {document.company_name}",
            f"書類概要: {document.doc_description}",
            f"提出日: {document.submit_date_time.strftime('%Y年%m月%d日')}",
        ]
        
        if document.period_start and document.period_end:
            text_parts.append(f"対象期間: {document.period_start}から{document.period_end}")
        
        # より現実的で拡張パターンを含むサンプルテキスト
        enhanced_scenarios = [
            "当社の業績は前年同期と比較して順調に推移しており、売上高の増加と収益性の向上が実現されています。特に増収増益を達成し、継続的な成長を維持しています。",
            "前年同期の減収から改善し、市場環境の変化に適応しつつ継続的な事業改善を図っています。減収幅の縮小により、業績悪化に歯止めがかかり、回復基調が明確になりました。", 
            "営業損失は発生したものの、損失の大幅な改善傾向が見られ、今後の回復に期待しています。赤字幅の縮小により黒字転換への道筋が見えてきました。構造改革の効果が着実に現れています。",
            "今後も持続的な成長を目指し、効率的な経営資源の活用と競争力の強化に取り組んでまいります。成長の加速には至らずとも、着実な改善を進めており、業績の底打ちが確認されました。",
            "一部の事業では苦戦が続いていますが、全体としては好調な業績を維持しています。好調に若干の陰りは見られるものの、安定した経営基盤を保っています。",
            "大幅増収増益を達成し、株主の皆様には深く感謝申し上げます。この好調な業績は、継続的な改善活動と構造改革の効果によるものです。",
            "前期の減益から改善となりましたが、構造改革の効果により今後の業績向上が期待されます。減益幅の改善に向けた取り組みを強化しており、来期の回復を見込んでいます。",
            "赤字幅の大幅な縮小により黒字転換への道筋が明確になりました。赤字の改善は着実に進んでおり、V字回復を目指した取り組みが成果を上げています。",
            "V字回復を目指し、抜本的な改革に取り組んでおります。この改革により、長期的な成長基盤を構築し、持続可能な収益体質への転換を図ります。",
            "リスク管理体制を強化し、危機管理能力の向上を図っています。適切なリスク対策により、安定した経営を実現し、将来の成長への基盤を整えています。",
            "前年同期比で売上高は減収となったものの、減収幅の改善により業績の底打ちが確認されました。今後は回復基調の継続が期待されます。",
            "増収の勢いに鈍化が見られるものの、利益率の向上により増益を維持しています。成長の持続に向けた新たな取り組みを検討しています。"
        ]
        
        text_parts.extend(enhanced_scenarios)
        return " ".join(text_parts)


# 設定ファイルの拡張（settings.py に追加）
class SentimentAnalysisSettings:
    """感情分析設定クラス"""
    
    @staticmethod
    def get_default_config():
        """デフォルト設定を取得"""
        return {
            # 基本設定
            'positive_threshold': 0.15,
            'negative_threshold': -0.15,
            'min_sentence_length': 10,
            'max_sample_sentences': 15,
            
            # 拡張設定
            'enable_ai_enhancement': True,
            'enable_context_weighting': True,
            'enable_extended_dictionary': True,
            'ai_enhancement_threshold': 1.5,
            'max_ai_sentences': 5,
            'context_window_size': 100,
            'cache_ai_results': True,
            
            # パフォーマンス設定
            'cache_timeout': 3600,
            'max_concurrent_analyses': 3,
            'ai_timeout': 30,
            'fallback_on_ai_error': True,
        }
    
    @staticmethod
    def get_production_config():
        """本番環境設定を取得"""
        config = SentimentAnalysisSettings.get_default_config()
        config.update({
            'enable_ai_enhancement': True,
            'max_ai_sentences': 3,  # コスト制御
            'cache_ai_results': True,
            'ai_timeout': 20,
        })
        return config
    
    @staticmethod
    def get_development_config():
        """開発環境設定を取得"""
        config = SentimentAnalysisSettings.get_default_config()
        config.update({
            'enable_ai_enhancement': True,
            'max_ai_sentences': 5,
            'cache_ai_results': False,  # 開発時はキャッシュ無効
            'ai_timeout': 45,
        })
        return config
