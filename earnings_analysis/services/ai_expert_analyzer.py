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
            self.model = genai.GenerativeModel("gemini-2.5-flash-lite")
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
                'model': 'gemini-2.5-flash-lite',
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
        
        # 計算チェック（既存のロジック）
        score_breakdown = result.get('score_breakdown', {})
        if score_breakdown:
            base_score = score_breakdown.get('base_score', 55)  # 55に変更
            
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
        
        # グレードの整合性チェック（更新版）
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
        """スコア範囲の説明（更新版）"""
        if score >= 85:
            return "極めて優れている（85点以上・A+）"
        elif score >= 75:
            return "優れている（75～84点・A）"
        elif score >= 65:
            return "良好（65～74点・B+）"
        elif score >= 50:
            return "標準的（50～64点・B）"
        elif score >= 35:
            return "やや課題あり（35～49点・C）"
        else:
            return "大きな課題あり（34点以下・D）"


    def _build_expert_analysis_prompt(self, text: str, doc_info: Dict[str, str], basic_analysis: Dict[str, Any] = None) -> str:
        """最適化版分析プロンプト（トークン削減）"""
        
        max_text_length = 30000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "...(以下省略)"
        
        # ワードベース分析情報（簡潔版）
        basic_info = ""
        if basic_analysis:
            word_score = basic_analysis.get('overall_score', 0.0)
            converted_score = int((word_score + 1.0) * 50)
            pos_count = len(basic_analysis.get('keyword_analysis', {}).get('positive', []))
            neg_count = len(basic_analysis.get('keyword_analysis', {}).get('negative', []))
            basic_info = f"""
    参考：語彙分析結果
    - スコア: {converted_score}点 (ポジティブ{pos_count}語、ネガティブ{neg_count}語)
    - この結果を参考に、文脈・事業の質・数値を総合評価してください
    """
        
        company_name = doc_info.get('company_name', '不明')
        
        prompt = f"""あなたは経験豊富な株式アナリストです。企業開示資料を分析し、0-100点スケールで評価してください。

    【企業情報】
    企業名: {company_name}
    証券コード: {doc_info.get('securities_code', '不明')}
    書類種別: {doc_info.get('doc_description', '不明')}
    提出日: {doc_info.get('submit_date', '不明')}

    {basic_info}

    【分析対象テキスト】
    {text}

    【評価基準】基準点55点から加減点

    スコア範囲：
    - 85+点(A+): 極めて優秀（業界トップ級、二桁成長、高ROE）
    - 75-84点(A): 優秀（二桁成長または大幅利益改善、明確な競争優位性）
    - 65-74点(B+): 良好（堅調な増収増益5-15%、利益率改善）
    - 50-64点(B): 標準的（微増または現状維持、特筆すべき強み・弱みなし）
    - 35-49点(C): 課題あり（減収減益、目標未達、構造的問題）
    - 34点以下(D): 深刻（大幅業績悪化、赤字拡大、事業継続性に疑問）

    加点要素（各+3～+8点）：
    - 営業利益率2%以上改善: +5～+7
    - ROE15%以上かつ改善: +5～+7
    - 営業CF/純利益120%以上: +4～+6
    - 市場成長率+5%以上上回る: +5～+7
    - 売上・利益とも二桁成長: +6～+8
    - 市場シェアトップ3かつ拡大: +5～+7
    - 独自技術・特許による差別化: +4～+6
    - 新製品の具体的貢献明示: +4～+6

    減点要素（各-3～-8点）：
    - 売上増でも利益率大幅低下: -5～-7
    - 営業CF/純利益が著しく低い: -5～-7
    - 前期目標大幅未達: -6～-8
    - 市場成長率を大きく下回る: -5～-7
    - コスト削減のみの増益: -4～-6
    - 主力事業成長鈍化: -4～-6
    - 競合に明確に劣後: -5～-7
    - 有利子負債/総資産60%超: -5～-6
    - 自己資本比率20%未満: -5～-6
    - 営業CF2期連続マイナス: -6～-7
    - 重要数値目標なし: -3～-4
    - リスク情報が極めて形式的: -3～-5

    【評価方針】
    1. 基準点55点から開始
    2. 業績の質を最重視（利益率、効率性、市場比較）
    3. 語彙の頻度だけでなく文脈・数値・事業の質を評価
    4. ネガティブ語彙多=悪い企業とは限らない（誠実な開示の可能性）
    5. ポジティブ語彙多=良い企業とは限らない（具体性が重要）
    6. 情報開示不足は大きく減点しない（事業実態を優先）

    【専門家考察】各項目を記述：
    - summary: 企業の現状を客観的に総括（2-3文、両面記載）
    - business_assessment: 事業競争力、成長持続性、競合比較
    - financial_health: 主要財務指標、利益の質、CF、財務リスク
    - management_evaluation: 経営戦略の具体性・実現性、過去実績整合性、株主還元
    - market_positioning: 業界内位置、競争優位性源泉、市場適応力
    - key_concerns: 2-4つの具体的懸念材料（過度に悲観的にならない）

    【出力形式】以下のJSON形式のみ（マークダウン不要）

    {{
    "overall_score": 65,
    "sentiment_label": "positive",
    "investment_grade": "B+",
    "expert_commentary": {{
        "summary": "...",
        "business_assessment": "...",
        "financial_health": "...",
        "management_evaluation": "...",
        "market_positioning": "...",
        "key_concerns": "..."
    }},
    "score_breakdown": {{
        "base_score": 55,
        "positive_factors": [
        {{"factor": "増収増益達成", "impact": 5, "description": "売上8%増、営業利益12%増"}},
        {{"factor": "営業利益率改善", "impact": 4, "description": "7.3%→7.8%"}}
        ],
        "negative_factors": [
        {{"factor": "市場成長率下回る", "impact": -5, "description": "当社8% vs 市場15%"}}
        ],
        "final_calculation": "55 + 9 - 5 = 59点 → 業績質考慮で65点"
    }},
    "detailed_scores": {{
        "growth_potential": 6,
        "profitability_outlook": 7,
        "management_quality": 6,
        "risk_level": 5,
        "market_position": 6,
        "innovation_capability": 6
    }},
    "investment_points": [
        {{
        "title": "安定的な増収増益基調",
        "description": "売上・利益とも成長維持、事業基盤安定",
        "importance": "high",
        "impact": "positive"
        }}
    ],
    "investor_insights": [
        {{
        "title": "堅実な経営姿勢",
        "description": "大きな成長は見込めないが着実に利益を積み上げるディフェンシブな投資先",
        "source": "ai_generated"
        }}
    ],
    "risk_analysis": {{
        "major_risks": ["市場成長率下回る", "原材料価格上昇"],
        "risk_severity": "medium",
        "mitigation_evidence": "コスト削減努力と価格改定を推進"
    }},
    "future_outlook": {{
        "short_term": "現状の増収増益基調継続見込み",
        "medium_term": "利益率改善余地あり、8-9%到達期待",
        "long_term": "新規事業育成と既存効率化で持続成長可能"
    }},
    "confidence": 0.78,
    "analysis_reasoning": [
        "65点根拠: 基準55点+堅調増収増益+利益率改善15点-市場成長下回る等10点→業績質総合65点",
        "標準上回る良好企業だが業界トップ級ではない。安定志向投資家に適す"
    ]
    }}

    【確認】
    ✓ スコアは実態反映か（極端に低すぎないか）
    ✓ 語彙頻度だけでなく文脈・数値・事業質を評価したか
    ✓ ポジティブ・ネガティブ両面記述したか
    ✓ 計算は論理的か
    ✓ 50-70点レンジに多くの企業が収まる評価か
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
        """フォールバック分析結果（グレード基準更新版）"""
        if basic_analysis:
            old_score = basic_analysis.get('overall_score', 0.0)
            score = int((old_score + 1.0) * 50)
            score = max(0, min(100, score))
            sentiment = basic_analysis.get('sentiment_label', 'neutral')
        else:
            score = 55  # デフォルトを60→55に変更
            sentiment = 'neutral'
        
        # グレード判定（更新版）
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