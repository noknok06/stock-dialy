# earnings_analysis/services/ai_expert_analyzer.py (API容量制限対応・専門家考察追加版)
import google.generativeai as genai
import logging
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any
import json
import re

logger = logging.getLogger(__name__)


class AIExpertAnalyzer:
    """AI専門家による統合感情分析サービス (0-100点スケール + 容量制限対応 + 専門家考察)"""
    
    # 容量制限関連のエラーメッセージパターン
    RATE_LIMIT_PATTERNS = [
        'rate limit',
        'rate_limit',
        'too many requests',
        '429',
        'quota exceeded',
        'quota_exceeded',
        'resource exhausted',
        'resource_exhausted',
        'requests per minute',
        'requests per day',
        'daily limit',
        'minute limit',
    ]
    
    def __init__(self):
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        self.api_available = api_key is not None
        self.model = None
        self.initialization_error = None
        self.last_api_error = None
        
        logger.info(f"AIExpertAnalyzer初期化開始")
        logger.info(f"APIキー設定状況: {'設定あり' if api_key else '設定なし'}")
        
        if not api_key:
            self.initialization_error = "GEMINI_API_KEYが設定されていません"
            logger.warning(self.initialization_error)
            self.api_available = False
            return
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            self.api_available = True
            logger.info("AI Expert Analyzer初期化成功")
            
        except ImportError as e:
            self.initialization_error = f"google-generativeaiモジュールがインストールされていません: {e}"
            logger.error(self.initialization_error)
            self.model = None
            self.api_available = False
        except Exception as e:
            self.initialization_error = f"初期化エラー: {str(e)}"
            logger.error(f"AI Expert Analyzer初期化エラー: {e}")
            self.model = None
            self.api_available = False
    
    def get_status(self) -> Dict[str, Any]:
        """現在の状態を取得"""
        return {
            'api_available': self.api_available,
            'model_initialized': self.model is not None,
            'initialization_error': self.initialization_error,
            'api_key_configured': getattr(settings, 'GEMINI_API_KEY', None) is not None,
            'last_api_error': self.last_api_error
        }
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """エラーがレート制限/クォータ超過かどうかを判定"""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        for pattern in self.RATE_LIMIT_PATTERNS:
            if pattern in error_str or pattern in error_type:
                return True
        
        try:
            from google.api_core import exceptions as google_exceptions
            if isinstance(error, (google_exceptions.ResourceExhausted, 
                                  google_exceptions.TooManyRequests)):
                return True
        except ImportError:
            pass
        
        return False
    
    def _check_response_for_errors(self, response) -> Dict[str, Any]:
        """レスポンスにエラーが含まれているかチェック"""
        error_info = {
            'has_error': False,
            'error_type': None,
            'error_message': None,
            'is_retryable': False
        }
        
        if response is None:
            error_info['has_error'] = True
            error_info['error_type'] = 'empty_response'
            error_info['error_message'] = 'APIからの応答がありません'
            error_info['is_retryable'] = True
            return error_info
        
        if not response.text:
            error_info['has_error'] = True
            error_info['error_type'] = 'empty_text'
            error_info['error_message'] = 'APIからのテキスト応答が空です'
            error_info['is_retryable'] = True
            return error_info
        
        response_lower = response.text.lower()
        for pattern in self.RATE_LIMIT_PATTERNS:
            if pattern in response_lower:
                error_info['has_error'] = True
                error_info['error_type'] = 'rate_limit_in_response'
                error_info['error_message'] = f'API容量制限: {pattern}'
                error_info['is_retryable'] = True
                return error_info
        
        if hasattr(response, 'prompt_feedback'):
            feedback = response.prompt_feedback
            if feedback and hasattr(feedback, 'block_reason') and feedback.block_reason:
                error_info['has_error'] = True
                error_info['error_type'] = 'blocked'
                error_info['error_message'] = f'リクエストがブロックされました: {feedback.block_reason}'
                error_info['is_retryable'] = False
                return error_info
        
        return error_info

    def analyze_document_comprehensive(
        self, 
        document_text: str, 
        document_info: Dict[str, str],
        basic_analysis: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        文書の包括的AI分析
        
        Returns:
            成功時: AI分析結果 + ai_analysis_status: {success: True, ...}
            失敗時: フォールバック結果 + ai_analysis_status: {success: False, error_type: ..., ...}
        """
        self.last_api_error = None
        
        # モデルが初期化されていない場合
        if not self.model:
            logger.warning("モデルが初期化されていないためフォールバック")
            return self._create_fallback_result(
                basic_analysis,
                error_type='model_not_initialized',
                error_message=self.initialization_error or 'モデルが初期化されていません',
                is_retryable=False
            )
        
        try:
            prompt = self._build_expert_analysis_prompt(document_text, document_info, basic_analysis)
            
            logger.info("Gemini API呼び出し開始...")
            response = self.model.generate_content(prompt)
            logger.info("Gemini API呼び出し完了")
            
            # レスポンスのエラーチェック
            error_check = self._check_response_for_errors(response)
            if error_check['has_error']:
                logger.warning(f"APIレスポンスにエラー検出: {error_check}")
                self.last_api_error = error_check
                return self._create_fallback_result(
                    basic_analysis,
                    error_type=error_check['error_type'],
                    error_message=error_check['error_message'],
                    is_retryable=error_check['is_retryable']
                )
            
            # JSON応答をパース
            result = self._parse_ai_response(response.text)
            logger.info("AI応答パース完了")
            
            # 整合性チェック
            result = self._validate_score_consistency(result)
            
            # メタデータと成功ステータスを追加
            result['analysis_metadata'] = {
                'method': 'ai_expert_comprehensive_unified',
                'model': 'gemini-2.5-flash',
                'timestamp': timezone.now().isoformat(),
                'api_available': True,
                'confidence': result.get('confidence', 0.8),
                'score_scale': '0-100',
                'api_calls': 1
            }
            
            # ★重要: 成功ステータスを追加
            result['ai_analysis_status'] = {
                'success': True,
                'error_type': None,
                'error_message': None,
                'is_retryable': False
            }
            
            return result
            
        except Exception as e:
            logger.error(f"AI Expert分析エラー: {e}")
            
            is_rate_limit = self._is_rate_limit_error(e)
            
            if is_rate_limit:
                error_type = 'rate_limit'
                error_message = 'API利用制限に達しました。しばらく時間をおいて再度お試しください。'
            else:
                error_type = 'api_error'
                error_message = f'AI分析中にエラーが発生しました: {str(e)}'
            
            self.last_api_error = {
                'error_type': error_type,
                'error_message': error_message,
                'original_error': str(e)
            }
            
            return self._create_fallback_result(
                basic_analysis,
                error_type=error_type,
                error_message=error_message,
                is_retryable=True,
                original_error=str(e)
            )
    
    def _create_fallback_result(
        self, 
        basic_analysis: Dict[str, Any],
        error_type: str,
        error_message: str,
        is_retryable: bool,
        original_error: str = None
    ) -> Dict[str, Any]:
        """フォールバック結果を生成（エラー情報付き）"""
        
        result = self._fallback_analysis(basic_analysis)
        
        # ★重要: 失敗ステータスを追加
        result['ai_analysis_status'] = {
            'success': False,
            'error_type': error_type,
            'error_message': error_message,
            'is_retryable': is_retryable,
            'original_error': original_error
        }
        
        return result
    
    def _validate_score_consistency(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """スコアとグレードの整合性をチェック"""
        
        score = result.get('overall_score', 60)
        grade = result.get('investment_grade', 'B')
        
        score_breakdown = result.get('score_breakdown', {})
        if score_breakdown:
            base_score = score_breakdown.get('base_score', 60)
            
            positive_total = 0
            if 'positive_factors' in score_breakdown:
                for factor in score_breakdown['positive_factors']:
                    positive_total += factor.get('impact', 0)
            
            negative_total = 0
            if 'negative_factors' in score_breakdown:
                for factor in score_breakdown['negative_factors']:
                    negative_total += factor.get('impact', 0)
            
            calculated_score = base_score + positive_total + negative_total
            calculated_score = max(0, min(100, calculated_score))
            
            if abs(calculated_score - score) > 5:
                logger.warning(f"スコア計算エラー検出: AI出力{score}点 vs 計算{calculated_score}点")
                result['overall_score'] = calculated_score
                result['score_calculation_corrected'] = True
                result['original_score'] = score
                score = calculated_score
        
        # グレードの整合性チェック
        if score >= 85:
            expected_grade = 'A+'
        elif score >= 75:
            expected_grade = 'A'
        elif score >= 65:
            expected_grade = 'B+'
        elif score >= 50:
            expected_grade = 'B'
        elif score >= 35:
            expected_grade = 'C'
        else:
            expected_grade = 'D'
        
        grade_order = {'A+': 5, 'A': 4, 'B+': 3, 'B': 2, 'C': 1, 'D': 0}
        
        if abs(grade_order.get(grade, 2) - grade_order.get(expected_grade, 2)) > 1:
            result['investment_grade'] = expected_grade
            result['grade_adjusted'] = True
            result['original_grade'] = grade
        
        result['consistency_check'] = {
            'passed': grade == expected_grade or result.get('grade_adjusted', False) == False,
            'expected_grade': expected_grade,
            'score_range': self._get_score_range_description(score)
        }
        
        return result

    def _get_score_range_description(self, score: float) -> str:
        """スコア範囲の説明"""
        if score >= 85:
            return "非常に優れている（85点以上）"
        elif score >= 75:
            return "優れている（75～84点）"
        elif score >= 65:
            return "良好（65～74点）"
        elif score >= 50:
            return "標準的（50～64点）"
        elif score >= 35:
            return "やや課題あり（35～49点）"
        else:
            return "大きな課題あり（34点以下）"
    
    def _build_expert_analysis_prompt(self, text: str, doc_info: Dict[str, str], basic_analysis: Dict[str, Any] = None) -> str:
        """分析プロンプト構築（専門家考察追加版）"""
        
        max_text_length = 30000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "...(以下省略)"
        
        basic_summary = ""
        if basic_analysis:
            basic_summary = f"""
参考：ワードベース分析結果
- 検出されたポジティブ語彙: {len(basic_analysis.get('keyword_analysis', {}).get('positive', []))}個
- 検出されたネガティブ語彙: {len(basic_analysis.get('keyword_analysis', {}).get('negative', []))}個
- 基本スコア: {basic_analysis.get('overall_score', 0):.3f}
"""
        
        company_name = doc_info.get('company_name', '不明')
        
        prompt = f"""
あなたは30年以上の経験を持つ株式アナライストです。
以下の決算書類を分析し、投資判断に必要な包括的評価を行ってください。

【企業情報】
企業名: {company_name}
証券コード: {doc_info.get('securities_code', '不明')}
書類種別: {doc_info.get('doc_description', '不明')}
提出日: {doc_info.get('submit_date', '不明')}

{basic_summary}

【分析対象テキスト】
{text}

【重要: 出力形式】
以下のJSON形式のみを出力してください。マークダウンのコードブロック記号も不要です。

【評価基準】
- 60点を標準点として設定
- 単なる増収増益では65点程度、大幅な増収増益で70～75点
- 80点以上は非常に優れた内容

【専門家考察について】
expert_commentaryセクションでは、30年以上の経験を持つアナリストとして、以下の観点から専門的な考察を記述してください：
- summary: 文書全体を通しての総括的な評価（2-3文）
- business_assessment: 事業の実態と競争力についての分析
- financial_health: 財務健全性と資金繰りの評価
- management_evaluation: 経営陣の姿勢と能力に対する評価
- market_positioning: 市場でのポジショニングと業界内での立ち位置
- key_concerns: 注意すべき点や今後の懸念材料

【出力するJSON形式】
{{
  "overall_score": 72,
  "sentiment_label": "positive",
  "investment_grade": "B+",
  "expert_commentary": {{
    "summary": "本決算書類を精査した結果、当社は○○という強みを持ち、△△の分野で着実な成長を遂げていると評価できます。全体として投資妙味のある銘柄と判断します。",
    "business_assessment": "主力事業である○○は市場シェアXX%を維持し、収益性も安定しています。特に△△セグメントでの成長が顕著であり、今後の収益ドライバーとして期待できます。一方で、□□事業については構造改革の途上にあり、改善の余地があります。",
    "financial_health": "自己資本比率XX%、流動比率XX%と財務基盤は堅固です。有利子負債の水準も適正であり、金利上昇局面でも十分に対応可能な体制と評価します。営業キャッシュフローは安定的に創出されており、設備投資と株主還元の両立が可能な状況です。",
    "management_evaluation": "経営陣は課題を率直に認識し、具体的な改善策を提示しています。中期経営計画の達成に向けた施策は現実的であり、実行力にも一定の信頼が置けます。株主還元への意識も高く、配当性向の向上姿勢は評価できます。",
    "market_positioning": "業界内では上位XX社に位置し、特に○○分野では競合他社に対して優位性を持っています。技術力・ブランド力を活かした差別化戦略が奏功しており、価格競争に巻き込まれにくい事業構造を構築しています。",
    "key_concerns": "一方で、原材料価格の高騰や為替変動など外部環境リスクへの対応が課題となります。また、○○市場の成熟化に伴い、新たな成長領域の開拓が中長期的な課題として認識されます。人材確保・育成も継続的な取り組みが必要です。"
  }},
  "score_breakdown": {{
    "base_score": 60,
    "positive_factors": [
      {{"factor": "売上高15%増加", "impact": 8, "description": "主力製品の販売好調"}}
    ],
    "negative_factors": [
      {{"factor": "為替リスク", "impact": -4, "description": "海外売上比率が高い"}}
    ],
    "final_calculation": "基準点60点 + プラス要因 - マイナス要因 = XX点"
  }},
  "detailed_scores": {{
    "growth_potential": 8,
    "profitability_outlook": 7,
    "management_quality": 7,
    "risk_level": 4,
    "market_position": 7,
    "innovation_capability": 6
  }},
  "investment_points": [
    {{
      "title": "堅調な増収増益基調",
      "description": "売上高15%増、営業利益20%増と好調。",
      "importance": "high",
      "impact": "positive"
    }}
  ],
  "investor_insights": [
    {{
      "title": "経営陣の積極的な成長戦略",
      "description": "新規事業への投資と既存事業の効率化を両立。",
      "source": "ai_generated"
    }}
  ],
  "risk_analysis": {{
    "major_risks": ["為替変動リスク"],
    "risk_severity": "medium",
    "mitigation_evidence": "為替ヘッジ戦略を強化中。"
  }},
  "future_outlook": {{
    "short_term": "堅調な業績継続が見込まれる。",
    "medium_term": "営業利益率の改善可能性。",
    "long_term": "持続的成長基盤の構築。"
  }},
  "confidence": 0.85,
  "analysis_reasoning": [
    "overall_score XX点の算出根拠: ..."
  ]
}}
"""
        return prompt.strip()
    
    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """AI応答をパース"""
        try:
            cleaned_text = response_text.strip()
            
            # 直接JSON
            if cleaned_text.startswith('{') and cleaned_text.endswith('}'):
                try:
                    return json.loads(cleaned_text)
                except json.JSONDecodeError:
                    pass
            
            # Markdownコードブロック
            json_pattern = r'```json\s*([\s\S]*?)\s*```'
            match = re.search(json_pattern, cleaned_text)
            if match:
                return json.loads(match.group(1).strip())
            
            # 言語指定なしコードブロック
            code_pattern = r'```\s*([\s\S]*?)\s*```'
            match = re.search(code_pattern, cleaned_text)
            if match and match.group(1).strip().startswith('{'):
                return json.loads(match.group(1).strip())
            
            # JSON部分抽出
            start_idx = cleaned_text.find('{')
            end_idx = cleaned_text.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                return json.loads(cleaned_text[start_idx:end_idx + 1])
            
            raise ValueError("応答からJSON部分を抽出できませんでした")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSONパースエラー: {e}")
            raise ValueError(f"JSON解析エラー: {e}")
    
    def _fallback_analysis(self, basic_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """フォールバック分析結果"""
        if basic_analysis:
            old_score = basic_analysis.get('overall_score', 0.0)
            score = int((old_score + 1.0) * 50)
            score = max(0, min(100, score))
            sentiment = basic_analysis.get('sentiment_label', 'neutral')
        else:
            score = 60
            sentiment = 'neutral'
        
        if score >= 85:
            grade = 'A+'
        elif score >= 75:
            grade = 'A'
        elif score >= 65:
            grade = 'B+'
        elif score >= 50:
            grade = 'B'
        elif score >= 35:
            grade = 'C'
        else:
            grade = 'D'
        
        return {
            'overall_score': score,
            'sentiment_label': sentiment,
            'investment_grade': grade,
            'expert_commentary': {
                'summary': 'AI分析が利用できないため、詳細な考察は提供できません。ワードベース分析に基づく基本的な評価をご参照ください。',
                'business_assessment': '詳細分析が必要です。',
                'financial_health': '詳細分析が必要です。',
                'management_evaluation': '詳細分析が必要です。',
                'market_positioning': '詳細分析が必要です。',
                'key_concerns': '詳細分析が必要です。'
            },
            'detailed_scores': {
                'growth_potential': 5,
                'profitability_outlook': 5,
                'management_quality': 5,
                'risk_level': 5,
                'market_position': 5,
                'innovation_capability': 5
            },
            'investment_points': [
                {
                    'title': '基本分析結果',
                    'description': 'AI分析が利用できないため、ワードベース分析のみの結果です。',
                    'importance': 'medium',
                    'impact': 'neutral'
                }
            ],
            'investor_insights': [
                {
                    'title': '基本分析による評価',
                    'description': f'感情スコア{score}点に基づく基本的な評価です。詳細なAI分析を実行するには再分析してください。',
                    'source': 'fallback_generated'
                }
            ],
            'risk_analysis': {
                'major_risks': ['詳細分析が実施されていません'],
                'risk_severity': 'unknown',
                'mitigation_evidence': 'N/A'
            },
            'future_outlook': {
                'short_term': '詳細分析が必要です',
                'medium_term': '詳細分析が必要です',
                'long_term': '詳細分析が必要です'
            },
            'confidence': 0.3,
            'analysis_reasoning': ['基本的な語彙分析のみ実施（AI分析は実行されていません）'],
            'score_breakdown': {
                'base_score': 60,
                'positive_factors': [],
                'negative_factors': [],
                'final_calculation': 'AI分析が実行されなかったため、基本スコアを使用'
            },
            'consistency_check': {
                'passed': True,
                'expected_grade': grade,
                'score_range': self._get_score_range_description(score)
            },
            'analysis_metadata': {
                'method': 'fallback_basic',
                'api_available': False,
                'timestamp': timezone.now().isoformat(),
                'score_scale': '0-100',
                'api_calls': 0
            }
        }