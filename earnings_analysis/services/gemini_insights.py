# earnings_analysis/services/gemini_insights.py（Langextract統合版）
import google.generativeai as genai
import logging
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any, Optional, List
import json
import re

logger = logging.getLogger(__name__)

class GeminiInsightsGenerator:
    """Google Gemini APIを使った感情分析見解生成サービス（Langextract統合版）"""
    
    def __init__(self):
        # 環境変数からAPIキーを取得
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        self.api_available = api_key is not None
        self.model = None
        self.langextract_enabled = getattr(settings, 'LANGEXTRACT_ENABLED', True)
        self.initialization_error = None
        
        if not api_key:
            logger.warning("GEMINI_API_KEYが設定されていません")
            self.initialization_error = "API_KEY_MISSING"
            return
        
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            logger.info("Gemini APIが正常に初期化されました")
            
            # Langextractが利用可能かチェック
            if self.langextract_enabled:
                try:
                    import langextract
                    self.langextract = langextract
                    logger.info("Langextract統合が有効化されました")
                except ImportError:
                    logger.warning("Langextractがインストールされていません。従来機能のみ使用します。")
                    self.langextract_enabled = False
                    self.langextract = None
            
        except Exception as e:
            logger.error(f"Gemini API初期化エラー: {e}")
            self.model = None
            self.api_available = False
            self.initialization_error = str(e)
    
    def generate_enhanced_sentiment_analysis(self, text_content: str, document_info: Dict[str, str]) -> Dict[str, Any]:
        """Langextractを使った強化感情分析"""
        start_time = timezone.now()
        
        if not self.model:
            logger.warning("Gemini APIが利用できません - フォールバック分析を使用")
            return self._generate_fallback_sentiment_analysis(text_content, document_info)
        
        # Langextractが有効な場合の処理
        if self.langextract_enabled:
            try:
                return self._perform_langextract_analysis(text_content, document_info, start_time)
            except Exception as e:
                logger.error(f"Langextract分析エラー: {e}")
                # フォールバック：従来のGemini分析
                return self._perform_traditional_gemini_analysis(text_content, document_info, start_time)
        else:
            # 従来のGemini分析
            return self._perform_traditional_gemini_analysis(text_content, document_info, start_time)
    
    def _perform_langextract_analysis(self, text_content: str, document_info: Dict[str, str], start_time) -> Dict[str, Any]:
        """Langextractを使った高精度分析"""
        logger.info("Langextract感情分析開始")
        
        # Langextractスキーマ定義（感情分析用）
        sentiment_schema = {
            "type": "object",
            "properties": {
                "overall_sentiment": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": -1.0, "maximum": 1.0},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "label": {"type": "string", "enum": ["very_positive", "positive", "neutral", "negative", "very_negative"]},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["score", "confidence", "label", "reasoning"]
                },
                "contextual_sentiments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text_segment": {"type": "string"},
                            "sentiment_score": {"type": "number", "minimum": -1.0, "maximum": 1.0},
                            "context": {"type": "string"},
                            "key_phrases": {"type": "array", "items": {"type": "string"}},
                            "business_impact": {"type": "string", "enum": ["high", "medium", "low"]}
                        },
                        "required": ["text_segment", "sentiment_score", "context", "key_phrases"]
                    }
                },
                "key_themes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "theme": {"type": "string"},
                            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                            "importance": {"type": "string", "enum": ["high", "medium", "low"]},
                            "evidence": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["theme", "sentiment", "importance", "evidence"]
                    }
                },
                "investment_insights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "enum": ["performance", "strategy", "risk", "opportunity", "governance"]},
                            "insight": {"type": "string"},
                            "impact_level": {"type": "string", "enum": ["high", "medium", "low"]},
                            "time_horizon": {"type": "string", "enum": ["short_term", "medium_term", "long_term"]}
                        },
                        "required": ["category", "insight", "impact_level"]
                    }
                }
            },
            "required": ["overall_sentiment", "contextual_sentiments", "key_themes", "investment_insights"]
        }
        
        # Langextractプロンプト構築
        langextract_prompt = self._build_langextract_prompt(text_content, document_info)
        
        try:
            # Langextract実行
            extractor = self.langextract.LangExtractor(model_name="gemini-2.5-flash")
            
            result = extractor.extract(
                text=langextract_prompt,
                schema=sentiment_schema,
                instruction="この決算書類の内容から、投資家向けの詳細な感情分析を実行してください。文脈を重視し、表面的な語彙だけでなく、経営陣の意図や市場への影響を読み取ってください。"
            )
            
            logger.info("Langextract分析完了")
            
            # 結果の変換と検証
            processed_result = self._process_langextract_result(result, start_time)
            processed_result.update({
                'analysis_method': 'langextract',
                'api_available': True,
                'api_success': True,
                'generation_timestamp': start_time.isoformat(),
                'langextract_enabled': True
            })
            
            return processed_result
            
        except Exception as e:
            logger.error(f"Langextract実行エラー: {e}")
            # フォールバック
            return self._perform_traditional_gemini_analysis(text_content, document_info, start_time)
    
    def _build_langextract_prompt(self, text_content: str, document_info: Dict[str, str]) -> str:
        """Langextract用プロンプト構築"""
        
        # テキストを適切な長さに制限（トークン制限対応）
        max_chars = 10000  # 約2000-3000トークン相当
        truncated_text = text_content[:max_chars]
        if len(text_content) > max_chars:
            truncated_text += "...[以下省略]"
        
        prompt = f"""
以下は{document_info.get('company_name', '企業')}の決算書類「{document_info.get('doc_description', '書類')}」からの抜粋です。

【企業情報】
企業名: {document_info.get('company_name', '不明')}
書類種別: {document_info.get('doc_description', '不明')}
提出日: {document_info.get('submit_date', '不明')}
証券コード: {document_info.get('securities_code', '不明')}

【分析対象テキスト】
{truncated_text}

この文書の内容を分析し、以下の観点から詳細な感情分析を実行してください：

1. 全体的な感情スコア（-1.0から1.0）と信頼度
2. 文脈別の感情分析（各セクションごとの詳細分析）
3. 主要テーマの抽出（業績、戦略、リスク等）
4. 投資家向けの具体的な示唆

特に重要なのは：
- 表面的な語彙だけでなく、文脈や隠れた意味の読み取り
- 経営陣のトーンや姿勢の分析
- 将来見通しに関する表現の解釈
- リスクや課題に関する言及の評価
"""
        return prompt
    
    def _process_langextract_result(self, langextract_result: Dict, start_time) -> Dict[str, Any]:
        """Langextract結果の処理と変換"""
        try:
            processed = {
                'overall_score': langextract_result.get('overall_sentiment', {}).get('score', 0.0),
                'sentiment_label': self._convert_sentiment_label(langextract_result.get('overall_sentiment', {}).get('label', 'neutral')),
                'confidence_score': langextract_result.get('overall_sentiment', {}).get('confidence', 0.5),
                'reasoning': langextract_result.get('overall_sentiment', {}).get('reasoning', ''),
                
                # 文脈別分析
                'contextual_analysis': self._process_contextual_sentiments(
                    langextract_result.get('contextual_sentiments', [])
                ),
                
                # 主要テーマ
                'key_themes': self._process_key_themes(
                    langextract_result.get('key_themes', [])
                ),
                
                # 投資家向けポイント
                'investment_points': self._process_investment_insights(
                    langextract_result.get('investment_insights', [])
                ),
                
                # メタデータ
                'analysis_quality': 'high',
                'processing_time': (timezone.now() - start_time).total_seconds(),
                'segments_analyzed': len(langextract_result.get('contextual_sentiments', [])),
                'themes_identified': len(langextract_result.get('key_themes', [])),
            }
            
            return processed
            
        except Exception as e:
            logger.error(f"Langextract結果処理エラー: {e}")
            return self._generate_fallback_sentiment_analysis("", {})
    
    def _convert_sentiment_label(self, langextract_label: str) -> str:
        """Langextractラベルを既存システム用に変換"""
        label_map = {
            'very_positive': 'positive',
            'positive': 'positive',
            'neutral': 'neutral',
            'negative': 'negative',
            'very_negative': 'negative'
        }
        return label_map.get(langextract_label, 'neutral')
    
    def _process_contextual_sentiments(self, contextual_data: List[Dict]) -> List[Dict]:
        """文脈別感情分析の処理"""
        processed = []
        
        for context in contextual_data[:10]:  # 上位10件まで
            processed.append({
                'text': context.get('text_segment', ''),
                'score': context.get('sentiment_score', 0.0),
                'context': context.get('context', ''),
                'key_phrases': context.get('key_phrases', []),
                'business_impact': context.get('business_impact', 'medium'),
                'highlighted_text': self._highlight_key_phrases(
                    context.get('text_segment', ''),
                    context.get('key_phrases', [])
                )
            })
        
        return processed
    
    def _process_key_themes(self, themes_data: List[Dict]) -> List[Dict]:
        """主要テーマの処理"""
        processed = []
        
        for theme in themes_data:
            processed.append({
                'theme': theme.get('theme', ''),
                'sentiment': theme.get('sentiment', 'neutral'),
                'importance': theme.get('importance', 'medium'),
                'evidence': theme.get('evidence', []),
                'icon': self._get_theme_icon(theme.get('theme', ''))
            })
        
        return processed
    
    def _process_investment_insights(self, insights_data: List[Dict]) -> List[Dict]:
        """投資分析ポイントの処理"""
        processed = []
        
        for insight in insights_data:
            processed.append({
                'title': f"{insight.get('category', '分析').replace('_', ' ').title()}分析",
                'description': insight.get('insight', ''),
                'impact_level': insight.get('impact_level', 'medium'),
                'time_horizon': insight.get('time_horizon', 'medium_term'),
                'category_icon': self._get_category_icon(insight.get('category', 'performance')),
                'source': 'langextract_analysis'
            })
        
        return processed
    
    def _highlight_key_phrases(self, text: str, key_phrases: List[str]) -> str:
        """重要フレーズのハイライト"""
        highlighted_text = text
        
        for phrase in key_phrases:
            if phrase in highlighted_text:
                highlighted_text = highlighted_text.replace(
                    phrase,
                    f'<span class="keyword-highlight">{phrase}</span>'
                )
        
        return highlighted_text
    
    def _get_theme_icon(self, theme: str) -> str:
        """テーマに応じたアイコン"""
        theme_lower = theme.lower()
        
        if any(word in theme_lower for word in ['業績', '売上', '利益', 'performance']):
            return 'fas fa-chart-line'
        elif any(word in theme_lower for word in ['戦略', '方針', 'strategy']):
            return 'fas fa-chess'
        elif any(word in theme_lower for word in ['リスク', 'risk', '課題']):
            return 'fas fa-shield-alt'
        elif any(word in theme_lower for word in ['成長', '拡大', 'growth']):
            return 'fas fa-trending-up'
        else:
            return 'fas fa-file-text'
    
    def _get_category_icon(self, category: str) -> str:
        """カテゴリに応じたアイコン"""
        icon_map = {
            'performance': 'fas fa-chart-line',
            'strategy': 'fas fa-chess',
            'risk': 'fas fa-shield-alt',
            'opportunity': 'fas fa-lightbulb',
            'governance': 'fas fa-gavel'
        }
        return icon_map.get(category, 'fas fa-file-text')
    
    def _perform_traditional_gemini_analysis(self, text_content: str, document_info: Dict[str, str], start_time) -> Dict[str, Any]:
        """従来のGemini分析（フォールバック用）"""
        logger.info("従来のGemini分析を実行")
        
        try:
            prompt = self._build_traditional_gemini_prompt(text_content, document_info)
            response = self.model.generate_content(prompt)
            
            if hasattr(response, "text") and response.text:
                parsed_result = self._parse_traditional_gemini_response(response.text)
                parsed_result.update({
                    'analysis_method': 'traditional_gemini',
                    'api_available': True,
                    'api_success': True,
                    'generation_timestamp': start_time.isoformat(),
                    'langextract_enabled': False
                })
                return parsed_result
            else:
                raise Exception("Gemini APIから有効な応答を取得できませんでした")
                
        except Exception as e:
            logger.error(f"従来のGemini分析エラー: {e}")
            return self._generate_fallback_sentiment_analysis(text_content, document_info)
    
    def _build_traditional_gemini_prompt(self, text_content: str, document_info: Dict[str, str]) -> str:
        """従来のGeminiプロンプト構築"""
        return f"""
以下の決算書類の内容を分析し、感情分析スコア（-1.0から1.0）と投資判断ポイントを提供してください。

【企業情報】
企業名: {document_info.get('company_name', '不明')}
書類種別: {document_info.get('doc_description', '不明')}

【分析対象テキスト】
{text_content[:5000]}

以下の形式で回答してください：
スコア: [数値]
判定: [ポジティブ/ネガティブ/中立]
理由: [詳細説明]
投資ポイント1: [ポイント説明]
投資ポイント2: [ポイント説明]
投資ポイント3: [ポイント説明]
"""
    
    def _parse_traditional_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """従来のGemini応答解析"""
        # 既存のparse_gemini_responseメソッドを使用
        return self._parse_gemini_response(response_text, {})
    
    def generate_investment_insights(self, analysis_result: Dict[str, Any], document_info: Dict[str, str]) -> Dict[str, Any]:
        """既存の投資家向け見解生成（互換性維持）"""
        # Langextract結果がある場合はそれを使用
        if 'investment_points' in analysis_result and analysis_result.get('analysis_method') == 'langextract':
            return {
                'investment_points': analysis_result['investment_points'],
                'generated_by': 'langextract_analysis',
                'response_quality': 'high',
                'api_available': True,
                'api_success': True,
                'fallback_used': False,
                'generation_timestamp': timezone.now().isoformat(),
                'points_count': len(analysis_result['investment_points'])
            }
        
        # 既存の処理を継続
        return self._generate_traditional_investment_insights(analysis_result, document_info)
    
    def _generate_traditional_investment_insights(self, analysis_result: Dict[str, Any], document_info: Dict[str, str]) -> Dict[str, Any]:
        """既存の投資見解生成処理"""
        start_time = timezone.now()
        api_call_success = False
        api_error_message = None
        points_generated = 0
        
        if not self.model:
            logger.warning("Gemini APIが利用できません - フォールバック見解を使用")
            fallback_result = self._generate_fallback_insights(analysis_result, document_info)
            fallback_result.update({
                'api_available': self.api_available,
                'api_success': False,
                'fallback_used': True,
                'error_message': self.initialization_error,
                'generation_timestamp': start_time.isoformat(),
                'points_count': len(fallback_result.get('investment_points', []))
            })
            return fallback_result
        
        try:
            logger.info("Gemini API投資家向け見解生成開始")
            prompt = self._build_investment_prompt(analysis_result, document_info)
            
            logger.debug("Gemini APIにリクエスト送信中...")
            response = self.model.generate_content(prompt)
            
            if hasattr(response, "text") and response.text:
                logger.info("Gemini APIから有効な応答を受信")
                parsed_result = self._parse_gemini_response(response.text, analysis_result)
                api_call_success = True
                points_generated = len(parsed_result.get('investment_points', []))
                
                # 成功時のメタデータを追加
                parsed_result.update({
                    'api_available': True,
                    'api_success': True,
                    'fallback_used': False,
                    'generation_timestamp': start_time.isoformat(),
                    'points_count': points_generated,
                    'model_used': 'gemini-2.5-flash',
                    'response_length': len(response.text)
                })
                
                logger.info(f"Gemini API見解生成完了: {points_generated}個のポイント")
                return parsed_result
            else:
                logger.warning("Gemini APIから有効な応答を取得できませんでした")
                api_error_message = "EMPTY_RESPONSE"
                
        except Exception as e:
            logger.error(f"Gemini API呼び出しエラー: {e}")
            api_error_message = str(e)
        
        # API呼び出し失敗時のフォールバック処理
        logger.info("Gemini API失敗のため、フォールバック見解を生成")
        fallback_result = self._generate_fallback_insights(analysis_result, document_info)
        fallback_result.update({
            'api_available': self.api_available,
            'api_success': api_call_success,
            'fallback_used': True,
            'error_message': api_error_message,
            'generation_timestamp': start_time.isoformat(),
            'points_count': len(fallback_result.get('investment_points', []))
        })
        
        return fallback_result
    
    def _generate_fallback_sentiment_analysis(self, text_content: str, document_info: Dict[str, str]) -> Dict[str, Any]:
        """Langextract/Gemini API利用不可時のフォールバック感情分析"""
        return {
            'overall_score': 0.0,
            'sentiment_label': 'neutral',
            'confidence_score': 0.3,
            'reasoning': 'AIモデルが利用できないため、基本的な分析のみ実行されました。',
            'contextual_analysis': [],
            'key_themes': [],
            'investment_points': self._generate_basic_fallback_points(),
            'analysis_method': 'fallback',
            'analysis_quality': 'basic',
            'api_available': False,
            'api_success': False,
            'langextract_enabled': False
        }
    
    def _generate_basic_fallback_points(self) -> List[Dict]:
        """基本的なフォールバックポイント"""
        return [
            {
                'title': '分析制限',
                'description': 'AIによる高度な分析が利用できないため、基本的な辞書ベース分析のみ実行されています。',
                'impact_level': 'low',
                'source': 'fallback_basic'
            },
            {
                'title': '推奨事項',
                'description': '詳細な分析のため、時間をおいて再度実行するか、他の分析手法も併用してください。',
                'impact_level': 'medium',
                'source': 'fallback_basic'
            }
        ]
    
    # 既存メソッドを継承
    def _build_investment_prompt(self, analysis_result: Dict[str, Any], document_info: Dict[str, str]) -> str:
        """既存の投資家向けプロンプト構築メソッド"""
        overall_score = analysis_result.get('overall_score', 0)
        sentiment_label = analysis_result.get('sentiment_label', 'neutral')
        statistics = analysis_result.get('statistics', {})
        
        keyword_analysis = analysis_result.get('keyword_analysis', {})
        positive_keywords = [kw.get('word', '') for kw in keyword_analysis.get('positive', [])[:5]]
        negative_keywords = [kw.get('word', '') for kw in keyword_analysis.get('negative', [])[:5]]

        sample_sentences = analysis_result.get('sample_sentences', {})
        positive_sentences = [s.get('text', '')[:100] for s in sample_sentences.get('positive', [])[:3]]
        negative_sentences = [s.get('text', '')[:100] for s in sample_sentences.get('negative', [])[:3]]

        prompt = f"""
あなたは金融アナリストとして、企業の決算書類の感情分析結果を基に、投資家向けの見解を作成してください。

【企業情報】
企業名: {document_info.get('company_name', '不明')}
書類種別: {document_info.get('doc_description', '不明')}
提出日: {document_info.get('submit_date', '不明')}
証券コード: {document_info.get('securities_code', '不明')}

【感情分析結果】
総合スコア: {overall_score:.3f} ({sentiment_label})
分析語彙数: {statistics.get('total_words_analyzed', 0)}語
検出パターン数: {statistics.get('context_patterns_found', 0)}個
文章数: {statistics.get('sentences_analyzed', 0)}文

【検出されたキーワード】
ポジティブ語彙: {', '.join(positive_keywords) or 'なし'}
ネガティブ語彙: {', '.join(negative_keywords) or 'なし'}

【サンプル文章】
ポジティブ文章例:
{chr(10).join(positive_sentences) or 'なし'}

ネガティブ文章例:
{chr(10).join(negative_sentences) or 'なし'}

以下の観点から、3〜5個の実用的な投資判断ポイントを日本語で作成してください：

1. 経営姿勢の読み取り（経営陣の方針・戦略）
2. 業績トレンド（現在の動向と将来性）
3. リスク要因（注意すべき課題）
4. 投資機会（注目すべき分野や動き）
5. 市場反応（株価・市場インパクト）

各ポイントは以下の形式で出力してください：
- 見出しタイトル: 説明（50〜80文字程度）

Markdownなどの記号（**など）は使用せず、自然な文章で記述してください。
"""
        return prompt.strip()

    def _parse_gemini_response(self, response_text: str, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """既存のGemini応答解析メソッド"""
        try:
            points = []
            lines = response_text.strip().split('\n')
            successful_parses = 0

            # タイトル:説明 形式をマッチする正規表現（記号なし）
            pattern = re.compile(r'^\s*(\d+\.?|・|\-)?\s*(.+?)[:：]\s*(.+)$')

            for line in lines:
                line = line.strip()
                if not line or len(line) < 10:
                    continue

                match = pattern.match(line)
                if match:
                    title = match.group(2).strip()
                    description = match.group(3).strip()
                    if title and description:
                        points.append({
                            'title': title,
                            'description': description,
                            'source': 'gemini_generated'
                        })
                        successful_parses += 1
                    continue

                # フォーマットに合わないが十分長い行も一応拾う
                if len(line) > 20:
                    points.append({
                        'title': 'AI分析ポイント',
                        'description': line,
                        'source': 'gemini_generated'
                    })
                    successful_parses += 1

            # 生成されたポイントが少ない場合、フォールバックポイントで補完
            if len(points) < 3:
                logger.warning(f"Gemini APIで生成されたポイントが少ない: {len(points)}個")
                fallback_points = self._generate_fallback_points(analysis_result)
                needed_points = 3 - len(points)
                points.extend(fallback_points[:needed_points])

            quality = 'high' if successful_parses >= 3 else 'medium' if successful_parses >= 2 else 'low'

            return {
                'investment_points': points[:5],
                'generated_by': 'gemini_api',
                'response_quality': quality,
                'original_response_length': len(response_text),
                'successful_parses': successful_parses,
                'total_points_generated': len(points)
            }

        except Exception as e:
            logger.error(f"Gemini応答解析エラー: {e}")
            # 解析エラー時もフォールバックを返す
            fallback_points = self._generate_fallback_points(analysis_result)
            return {
                'investment_points': fallback_points,
                'generated_by': 'parsing_error',
                'response_quality': 'failed',
                'error_message': str(e)
            }

    def _generate_fallback_insights(self, analysis_result: Dict[str, Any], document_info: Dict[str, str]) -> Dict[str, Any]:
        """既存のフォールバック見解生成メソッド"""
        overall_score = analysis_result.get('overall_score', 0)
        sentiment_label = analysis_result.get('sentiment_label', 'neutral')
        
        points = self._generate_fallback_points(analysis_result)
        
        return {
            'investment_points': points,
            'generated_by': 'fallback_logic',
            'response_quality': 'basic',
            'fallback_reason': 'api_unavailable'
        }
    
    def _generate_fallback_points(self, analysis_result: Dict[str, Any]) -> list:
        """既存のフォールバックポイント生成メソッド"""
        overall_score = analysis_result.get('overall_score', 0)
        sentiment_label = analysis_result.get('sentiment_label', 'neutral')
        statistics = analysis_result.get('statistics', {})
        
        points = []
        
        if sentiment_label == 'positive':
            if overall_score > 0.6:
                points.extend([
                    {
                        'title': '強い成長意欲',
                        'description': f'感情分析スコア{overall_score:.2f}は経営陣の積極的な姿勢を示しており、将来の成長への期待が持てます',
                        'source': 'fallback_generated'
                    },
                    {
                        'title': '投資魅力度向上',
                        'description': 'ポジティブな表現が多用されており、投資家にとって魅力的な投資機会を示唆しています',
                        'source': 'fallback_generated'
                    },
                    {
                        'title': '市場評価の向上期待',
                        'description': '前向きなメッセージが一貫しており、市場での評価向上が期待される内容となっています',
                        'source': 'fallback_generated'
                    }
                ])
            else:
                points.extend([
                    {
                        'title': '安定的な経営姿勢',
                        'description': '堅実で建設的な表現が使われており、持続可能な経営戦略を示しています',
                        'source': 'fallback_generated'
                    },
                    {
                        'title': '段階的改善期待',
                        'description': '着実な取り組みを重視する姿勢が読み取れ、中長期的な改善が期待できます',
                        'source': 'fallback_generated'
                    }
                ])
        elif sentiment_label == 'negative':
            if overall_score < -0.6:
                points.extend([
                    {
                        'title': '透明性の高い情報開示',
                        'description': f'感情分析スコア{overall_score:.2f}は困難な状況への率直な言及を示し、誠実な経営姿勢が評価できます',
                        'source': 'fallback_generated'
                    },
                    {
                        'title': 'リスク管理への注力',
                        'description': '課題を正面から捉える姿勢が表れており、適切なリスク管理体制の構築が期待されます',
                        'source': 'fallback_generated'
                    },
                    {
                        'title': '構造改革の契機',
                        'description': '現在の困難は将来の構造改革と競争力向上への重要な転換点となる可能性があります',
                        'source': 'fallback_generated'
                    }
                ])
            else:
                points.extend([
                    {
                        'title': '慎重な経営判断',
                        'description': 'リスクを適切に評価し、慎重なアプローチを採用している姿勢が読み取れます',
                        'source': 'fallback_generated'
                    },
                    {
                        'title': '改善への取り組み',
                        'description': '課題に対する具体的な対応策への言及があり、改善に向けた努力が期待できます',
                        'source': 'fallback_generated'
                    }
                ])
        else:  # neutral
            points.extend([
                {
                    'title': 'バランスの取れた報告',
                    'description': '客観的で事実ベースの記述が中心となっており、冷静な経営判断が期待できます',
                    'source': 'fallback_generated'
                },
                {
                    'title': '安定した事業基盤',
                    'description': '感情的な表現を避けた報告は、安定した事業基盤を示唆している可能性があります',
                    'source': 'fallback_generated'
                },
                {
                    'title': 'ディフェンシブ投資適性',
                    'description': '大きな変動要因が少なく、安定志向の投資戦略に適した企業特性を示しています',
                    'source': 'fallback_generated'
                }
            ])
        
        # 統計情報に基づく追加ポイント
        total_words = statistics.get('total_words_analyzed', 0)
        if total_words > 50:
            points.append({
                'title': '充実した分析基盤',
                'description': f'{total_words}語の豊富な情報に基づく分析結果で、信頼性の高い評価となっています',
                'source': 'fallback_generated'
            })
        
        context_patterns = statistics.get('context_patterns_found', 0)
        if context_patterns > 3:
            points.append({
                'title': '多角的な表現分析',
                'description': f'{context_patterns}個の文脈パターンが検出され、多面的な経営状況の把握が可能です',
                'source': 'fallback_generated'
            })
        
        return points[:5]  # 最大5個