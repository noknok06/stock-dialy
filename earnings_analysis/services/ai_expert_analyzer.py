# earnings_analysis/services/ai_expert_analyzer.py (0-100点スケール版)
import google.generativeai as genai
import logging
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any
import json

logger = logging.getLogger(__name__)

class AIExpertAnalyzer:
    """AI専門家による統合感情分析サービス (0-100点スケール)"""
    
    def __init__(self):
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        self.api_available = api_key is not None
        self.model = None
        self.initialization_error = None
        
        logger.info(f"AIExpertAnalyzer初期化開始")
        logger.info(f"APIキー設定状況: {'設定あり' if api_key else '設定なし'}")
        
        if not api_key:
            self.initialization_error = "GEMINI_API_KEYが設定されていません"
            logger.warning(self.initialization_error)
            logger.warning("settings.pyまたは環境変数でGEMINI_API_KEYを設定してください")
            self.api_available = False
            return
        
        try:
            import google.generativeai as genai
            logger.info("google.generativeai モジュールのインポート成功")
            
            genai.configure(api_key=api_key)
            logger.info("Gemini API設定完了")
            
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            logger.info("Geminiモデル初期化成功: gemini-2.5-flash")
            
            self.api_available = True
            logger.info("AI Expert Analyzer初期化成功")
            
        except ImportError as e:
            self.initialization_error = f"google-generativeaiモジュールがインストールされていません: {e}"
            logger.error(self.initialization_error)
            logger.error("pip install google-generativeai を実行してください")
            self.model = None
            self.api_available = False
        except Exception as e:
            self.initialization_error = f"初期化エラー: {str(e)}"
            logger.error(f"AI Expert Analyzer初期化エラー: {e}")
            self.model = None
            self.api_available = False
    
    def get_status(self) -> Dict[str, Any]:
        """現在の状態を取得（デバッグ用）"""
        return {
            'api_available': self.api_available,
            'model_initialized': self.model is not None,
            'initialization_error': self.initialization_error,
            'api_key_configured': getattr(settings, 'GEMINI_API_KEY', None) is not None
        }
    
    def _validate_score_consistency(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """スコアとグレードの整合性をチェックし、必要に応じて修正 (0-100点版 + 計算検証)"""
        
        score = result.get('overall_score', 60)
        grade = result.get('investment_grade', 'B')
        
        # ========== 計算の検証を追加 ==========
        score_breakdown = result.get('score_breakdown', {})
        if score_breakdown:
            base_score = score_breakdown.get('base_score', 60)
            
            # ポジティブ要因の合計を計算
            positive_total = 0
            if 'positive_factors' in score_breakdown:
                for factor in score_breakdown['positive_factors']:
                    positive_total += factor.get('impact', 0)
            
            # ネガティブ要因の合計を計算
            negative_total = 0
            if 'negative_factors' in score_breakdown:
                for factor in score_breakdown['negative_factors']:
                    negative_total += factor.get('impact', 0)
            
            # 正しいスコアを計算
            calculated_score = base_score + positive_total + negative_total
            
            # 範囲チェック（0-100点）
            calculated_score = max(0, min(100, calculated_score))
            
            logger.info(f"スコア検証: 基準{base_score} + プラス{positive_total} + マイナス{negative_total} = 計算値{calculated_score}, AI出力{score}")
            
            # 5点以上の差がある場合は修正
            if abs(calculated_score - score) > 5:
                logger.warning(f"スコア計算エラーを検出: AI出力{score}点 vs 正しい計算{calculated_score}点")
                result['overall_score'] = calculated_score
                result['score_calculation_corrected'] = True
                result['original_score'] = score
                
                # adjustmentsも修正
                score_breakdown['adjustments'] = [
                    {"item": "基準点", "value": base_score},
                    {"item": "ポジティブ要因合計", "value": positive_total},
                    {"item": "ネガティブ要因合計", "value": negative_total},
                    {"item": "純増減", "value": positive_total + negative_total},
                    {"item": "計算結果", "value": calculated_score}
                ]
                
                # 最終計算式も更新
                score_breakdown['final_calculation'] = (
                    f"基準点{base_score}点 + プラス要因{positive_total}点 + マイナス要因{negative_total}点 = {calculated_score}点。"
                    f"（注: AI出力{score}点は計算エラーのため{calculated_score}点に修正）"
                )
                
                # 理由にも追加
                if 'analysis_reasoning' in result and isinstance(result['analysis_reasoning'], list):
                    result['analysis_reasoning'].insert(0,
                        f"注意: AI出力スコア{score}点は計算が正しくないため、正しい計算値{calculated_score}点に自動修正しました"
                    )
                
                # スコアを修正後の値で再設定
                score = calculated_score
        
        # ========== グレードの整合性チェック ==========
        # スコアから期待されるグレードを計算
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
        
        # 不整合を検出
        inconsistency_detected = False
        
        grade_order = {'A+': 5, 'A': 4, 'B+': 3, 'B': 2, 'C': 1, 'D': 0}
        
        if abs(grade_order.get(grade, 2) - grade_order.get(expected_grade, 2)) > 1:
            inconsistency_detected = True
            logger.warning(f"スコアとグレードの不整合を検出: score={score}, grade={grade}, expected={expected_grade}")
            
            # 修正: スコアを優先してグレードを調整
            result['investment_grade'] = expected_grade
            result['grade_adjusted'] = True
            result['original_grade'] = grade
            
            # 理由に追加
            if 'analysis_reasoning' in result and isinstance(result['analysis_reasoning'], list):
                result['analysis_reasoning'].append(
                    f"注意: 当初のグレード'{grade}'はスコア{score}点と整合性が低いため、'{expected_grade}'に調整しました"
                )
        
        result['consistency_check'] = {
            'passed': not inconsistency_detected,
            'expected_grade': expected_grade,
            'score_range': self._get_score_range_description(score),
            'calculation_verified': True
        }
        
        return result

    def _get_score_range_description(self, score: float) -> str:
        """スコア範囲の説明を返す (0-100点版)"""
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

    def analyze_document_comprehensive(
        self, 
        document_text: str, 
        document_info: Dict[str, str],
        basic_analysis: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        文書の包括的AI分析（1回のAPIコールで全て実行）
        
        Args:
            document_text: 分析対象テキスト
            document_info: 企業・書類情報
            basic_analysis: 既存のワードベース分析結果（参考用）
        
        Returns:
            統合分析結果
        """
        if not self.model:
            return self._fallback_analysis(basic_analysis)
        
        try:
            prompt = self._build_expert_analysis_prompt(
                document_text, 
                document_info, 
                basic_analysis
            )
            
            # JSON形式での応答を要求
            response = self.model.generate_content(prompt)
            
            if not response.text:
                return self._fallback_analysis(basic_analysis)
            
            # JSON応答をパース
            result = self._parse_ai_response(response.text)
            logger.info("AI応答パース完了")
            
            # 整合性チェックを追加
            result = self._validate_score_consistency(result)
            logger.info("整合性チェック完了")
            
            # メタデータ追加
            result['analysis_metadata'] = {
                'method': 'ai_expert_comprehensive',
                'model': 'gemini-2.5-flash',
                'timestamp': timezone.now().isoformat(),
                'api_available': True,
                'confidence': result.get('confidence', 0.8),
                'consistency_validated': True,
                'score_scale': '0-100'
            }
            
            return result
        except Exception as e:
            logger.error(f"AI Expert分析エラー: {e}")
            return self._fallback_analysis(basic_analysis)
    
    def _build_expert_analysis_prompt(
        self, 
        text: str, 
        doc_info: Dict[str, str],
        basic_analysis: Dict[str, Any] = None
    ) -> str:
        """株式専門家としての統合分析プロンプト構築 (0-100点版)"""
        
        # テキストを適切な長さに制限（Geminiのコンテキスト制限対策）
        max_text_length = 30000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "...(以下省略)"
        
        # 基本分析の要約（参考情報として）
        basic_summary = ""
        if basic_analysis:
            basic_summary = f"""
参考：ワードベース分析結果
- 検出されたポジティブ語彙: {len(basic_analysis.get('keyword_analysis', {}).get('positive', []))}個
- 検出されたネガティブ語彙: {len(basic_analysis.get('keyword_analysis', {}).get('negative', []))}個
- 基本スコア: {basic_analysis.get('overall_score', 0):.3f}
"""
        
        prompt = f"""
あなたは30年以上の経験を持つ株式アナライストで、政治経済に精通し、企業の将来性を見抜く洞察力を持っています。
以下の決算書類を分析し、投資判断に必要な包括的評価を行ってください。

【企業情報】
企業名: {doc_info.get('company_name', '不明')}
証券コード: {doc_info.get('securities_code', '不明')}
書類種別: {doc_info.get('doc_description', '不明')}
提出日: {doc_info.get('submit_date', '不明')}

{basic_summary}

【分析対象テキスト】
{text}

【重要: 出力形式】
**以下のJSON形式のみを出力してください。前置きの説明や追加のコメントは一切不要です。**
**マークダウンのコードブロック記号（```）も不要です。純粋なJSON形式のみを出力してください。**

【重要: 計算の正確性】
**overall_scoreは必ず以下の計算式で算出してください:**
overall_score = base_score + (全てのpositive_factorsのimpact合計) + (全てのnegative_factorsのimpact合計)

例: base_score=60, positive合計=+18, negative合計=-6 の場合
→ overall_score = 60 + 18 + (-6) = 72

**計算が正しいか必ず検算してください。間違った数値を出力すると自動修正されます。**

【重要: 評価基準と採点方針】

**0-100点スケールでの厳格な評価**

1. **総合評価スコア (overall_score)** - 0～100点
   - **60点を標準点**として設定
   - 60点: 標準的な業績、目立った特徴なし
   - 70点: 明確なポジティブ要素が複数ある
   - 80点: 非常に優れた業績、強い成長期待
   - 90点以上: 例外的に優れた内容（滅多に該当しない）
   - 50点: やや課題あり
   - 40点以下: 深刻な問題あり

**採点の厳格な基準:**
- 単なる「増収増益」だけでは65点程度
- 「大幅な増収増益」で70～75点
- 「過去最高益+市場シェア拡大+新規事業成功」で80点以上
- 減収減益は40～55点の範囲
- 赤字は30～45点の範囲

**加点・減点の目安:**
- 売上高20%以上増加: +5～10点
- 営業利益率改善: +3～7点
- 市場シェア拡大: +3～5点
- 新規事業の成功: +3～7点
- 為替リスク大: -3～5点
- 競争激化: -2～4点
- 重大なリスク要因: -5～10点

2. **投資推奨度 (investment_grade)** とスコアの対応
   - 'A+': 強気買い推奨（85点以上）
   - 'A': 買い推奨（75～84点）
   - 'B+': やや買い推奨（65～74点）
   - 'B': 中立・保有（50～64点）
   - 'C': 慎重・売り検討（35～49点）
   - 'D': 強気売り推奨（34点以下）

【出力するJSON形式】
{{
  "overall_score": 72,
  "sentiment_label": "positive",
  "investment_grade": "B+",
  "score_breakdown": {{
    "base_score": 60,
    "positive_factors": [
      {{"factor": "売上高15%増加", "impact": 8, "description": "主力製品の販売好調により大幅増収"}},
      {{"factor": "営業利益率3%改善", "impact": 5, "description": "コスト削減効果が顕在化"}},
      {{"factor": "新規事業が黒字化", "impact": 5, "description": "投資が実を結び今後の成長ドライバーに"}}
    ],
    "negative_factors": [
      {{"factor": "為替リスク", "impact": -4, "description": "海外売上比率60%で円高リスクあり"}},
      {{"factor": "競争激化", "impact": -2, "description": "主力市場で新規参入が増加"}}
    ],
    "adjustments": [
      {{"item": "ポジティブ要因合計", "value": 18}},
      {{"item": "ネガティブ要因合計", "value": -6}},
      {{"item": "純増減", "value": 12}}
    ],
    "final_calculation": "基準点60点 + 純増減12点 = 72点。明確な成長が見られるため75点ではなく72点と評価。"
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
      "description": "売上高15%増、営業利益20%増と好調な業績が継続。市場シェアも拡大傾向。",
      "importance": "high",
      "impact": "positive"
    }}
  ],
  "risk_analysis": {{
    "major_risks": [
      "為替変動リスク（海外売上比率60%）",
      "競争激化による価格下落圧力"
    ],
    "risk_severity": "medium",
    "mitigation_evidence": "為替ヘッジ戦略を強化中。差別化製品により価格維持力あり。"
  }},
  "future_outlook": {{
    "short_term": "堅調な業績継続。四半期ごとの増収増益トレンド維持が見込まれる。",
    "medium_term": "新規事業の収益化により、営業利益率が2-3%改善する可能性。",
    "long_term": "持続的成長基盤が構築される見込み。市場地位の向上が期待される。"
  }},
  "confidence": 0.85,
  "analysis_reasoning": [
    "overall_score 72点の算出根拠: 基準点60点 + (売上増+8点 + 利益率改善+5点 + 新規事業+5点) - (為替リスク-4点 + 競争-2点) = 72点",
    "investment_grade B+の根拠: スコア72点は65～74点の範囲に該当し、明確なポジティブ要素があるためB+と評価",
    "厳格な採点により、単なる増収増益では高得点にならない基準を適用",
    "成長性は認められるが、リスク要因も存在するため80点台には届かず",
    "今後の継続的な改善が確認できれば、次回はより高い評価も可能"
  ]
}}

**繰り返しますが、上記のJSON形式のみを出力し、それ以外の説明文やコメントは一切含めないでください。**
"""
        return prompt.strip()
    
    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """AI応答のパース（強化版：前置き説明文対応）"""
        try:
            import re
            
            # ステップ1: JSON部分を抽出
            json_text = None
            
            # パターン1: ```json ... ``` の形式
            json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
                logger.info("パターン1でJSON抽出成功 (```json```)")
            
            # パターン2: ``` ... ``` の形式（jsonなし）
            if not json_text:
                json_match = re.search(r'```\s*\n(.*?)\n```', response_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(1)
                    logger.info("パターン2でJSON抽出成功 (```のみ)")
            
            # パターン3: { ... } の形式（コードブロックなし）
            if not json_text:
                # 最初の { から最後の } までを抽出
                start_idx = response_text.find('{')
                if start_idx != -1:
                    # 対応する閉じ括弧を探す（ネストを考慮）
                    bracket_count = 0
                    end_idx = -1
                    for i in range(start_idx, len(response_text)):
                        if response_text[i] == '{':
                            bracket_count += 1
                        elif response_text[i] == '}':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end_idx = i + 1
                                break
                    
                    if end_idx != -1:
                        json_text = response_text[start_idx:end_idx]
                        logger.info("パターン3でJSON抽出成功 ({}のみ)")
            
            if not json_text:
                logger.error("JSON部分が見つかりませんでした")
                logger.error(f"応答の最初の500文字: {response_text[:500]}")
                raise ValueError("応答からJSON部分を抽出できませんでした")
            
            # ステップ2: JSON文字列のクリーニング
            json_text = json_text.strip()
            
            # 念のため、前後の不要な文字を除去
            if not json_text.startswith('{'):
                # { が見つかるまでスキップ
                start = json_text.find('{')
                if start != -1:
                    json_text = json_text[start:]
            
            if not json_text.endswith('}'):
                # 最後の } までを取得
                end = json_text.rfind('}')
                if end != -1:
                    json_text = json_text[:end+1]
            
            logger.info(f"クリーニング後のJSON長: {len(json_text)} 文字")
            logger.info(f"JSON開始: {json_text[:100]}")
            
            # ステップ3: JSONパース
            result = json.loads(json_text)
            logger.info("JSONパース成功")
            
            # ステップ4: 必須フィールドの検証
            required_fields = ['overall_score', 'sentiment_label', 'investment_grade']
            for field in required_fields:
                if field not in result:
                    logger.error(f"必須フィールド '{field}' が見つかりません")
                    logger.error(f"結果キー: {list(result.keys())}")
                    raise ValueError(f"必須フィールド '{field}' が見つかりません")
            
            # ステップ5: スコアの範囲チェック (0-100点)
            if not 0 <= result['overall_score'] <= 100:
                logger.warning(f"スコアが範囲外: {result['overall_score']}")
                result['overall_score'] = max(0, min(100, result['overall_score']))
            
            logger.info(f"最終スコア: {result['overall_score']}点, グレード: {result['investment_grade']}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}")
            logger.error(f"問題のJSON (最初の500文字): {json_text[:500] if json_text else 'N/A'}")
            logger.error(f"元の応答 (最初の500文字): {response_text[:500]}")
            raise
        except Exception as e:
            logger.error(f"応答パースエラー: {e}")
            logger.error(f"エラー詳細: {str(e)}")
            import traceback
            logger.error(f"スタックトレース: {traceback.format_exc()}")
            raise
    
    def _fallback_analysis(self, basic_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """AIが利用できない場合のフォールバック (0-100点版)"""
        if basic_analysis:
            # -1.0~1.0 を 0~100 に変換
            old_score = basic_analysis.get('overall_score', 0.0)
            # 変換式: (score + 1) * 50 で 0-100 に変換
            score = int((old_score + 1.0) * 50)
            score = max(0, min(100, score))
            
            sentiment = basic_analysis.get('sentiment_label', 'neutral')
        else:
            score = 60
            sentiment = 'neutral'
        
        # スコアからグレード推定
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
            'analysis_reasoning': ['基本的な語彙分析のみ実施'],
            'analysis_metadata': {
                'method': 'fallback_basic',
                'api_available': False,
                'timestamp': timezone.now().isoformat(),
                'score_scale': '0-100'
            }
        }