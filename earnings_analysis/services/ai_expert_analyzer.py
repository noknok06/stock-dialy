# earnings_analysis/services/ai_expert_analyzer.py
import google.generativeai as genai
import logging
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any
import json

logger = logging.getLogger(__name__)

class AIExpertAnalyzer:
    """AI専門家による統合感情分析サービス"""
    
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
            logger.error(f"エラー詳細: {traceback.format_exc()}")
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
        """スコアとグレードの整合性をチェックし、必要に応じて修正"""
        
        score = result.get('overall_score', 0.0)
        grade = result.get('investment_grade', 'B')
        
        # スコアから期待されるグレードを計算
        if score > 0.7:
            expected_grade = 'A+'
        elif score > 0.6:
            expected_grade = 'A'
        elif score > 0.4:
            expected_grade = 'B+'
        elif score > 0.3:
            expected_grade = 'B'
        elif score > -0.3:
            expected_grade = 'B'
        elif score > -0.6:
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
                    f"注意: 当初のグレード'{grade}'はスコア{score:.2f}と整合性が低いため、'{expected_grade}'に調整しました"
                )
        
        result['consistency_check'] = {
            'passed': not inconsistency_detected,
            'expected_grade': expected_grade,
            'score_range': self._get_score_range_description(score)
        }
        
        return result

    def _get_score_range_description(self, score: float) -> str:
        """スコア範囲の説明を返す"""
        if score > 0.7:
            return "非常にポジティブ（+0.7以上）"
        elif score > 0.6:
            return "ポジティブ（+0.6～+0.7）"
        elif score > 0.3:
            return "やや前向き（+0.3～+0.6）"
        elif score > -0.3:
            return "中立的（-0.3～+0.3）"
        elif score > -0.6:
            return "やや慎重（-0.6～-0.3）"
        else:
            return "ネガティブ（-0.6以下）"

    
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
            
            # 整合性チェックを追加
            result = self._validate_score_consistency(result)
            
            # メタデータ追加
            result['analysis_metadata'] = {
                'method': 'ai_expert_comprehensive',
                'model': 'gemini-2.0-flash-exp',
                'timestamp': timezone.now().isoformat(),
                'api_available': True,
                'confidence': result.get('confidence', 0.8),
                'consistency_validated': True
            }
            
            return result
        except Exception as e:
            logger.error(f"AI Expert分析エラー: {e}")
            return self._fallback_analysis(basic_analysis)
            
        except Exception as e:
            logger.error(f"AI Expert分析エラー: {e}")
            return self._fallback_analysis(basic_analysis)
    
    def _build_expert_analysis_prompt(
        self, 
        text: str, 
        doc_info: Dict[str, str],
        basic_analysis: Dict[str, Any] = None
    ) -> str:
        """株式専門家としての統合分析プロンプト構築"""
        
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
    あなたは30年以上の経験を持つ株式アナリストで、政治経済に精通し、企業の将来性を見抜く洞察力を持っています。
    以下の決算書類を分析し、投資判断に必要な包括的評価を行ってください。

    【企業情報】
    企業名: {doc_info.get('company_name', '不明')}
    証券コード: {doc_info.get('securities_code', '不明')}
    書類種別: {doc_info.get('doc_description', '不明')}
    提出日: {doc_info.get('submit_date', '不明')}

    {basic_summary}

    【分析対象テキスト】
    {text}

    【重要: スコアとグレードの整合性】
    以下の評価では、overall_scoreとinvestment_gradeは**必ず整合性を保つこと**:

    スコアとグレードの対応表:
    - overall_score > +0.6  → investment_grade: A+ または A
    - overall_score +0.3 ~ +0.6 → investment_grade: B+ または B
    - overall_score -0.3 ~ +0.3 → investment_grade: B
    - overall_score -0.6 ~ -0.3 → investment_grade: C
    - overall_score < -0.6 → investment_grade: D

    【分析指示】
    以下の観点から専門家として分析し、**必ずJSON形式のみ**で回答してください。

    1. **総合感情スコア (overall_score)**
    - -1.0（非常にネガティブ）〜 +1.0（非常にポジティブ）の範囲
    - 経営陣の自信度、業績トレンド、将来見通しを総合評価
    - **このスコアとinvestment_gradeは上記対応表に従うこと**

    2. **投資推奨度 (investment_grade)**
    - 'A+'〜'D'の5段階評価
    - **overall_scoreから上記対応表に基づいて決定すること**
    - 'A+': 強気買い推奨（スコア +0.7以上が目安）
    - 'A': 買い推奨（スコア +0.6〜+0.7が目安）
    - 'B+': やや買い推奨（スコア +0.4〜+0.6が目安）
    - 'B': 中立・保有（スコア -0.3〜+0.3が目安）
    - 'C': 慎重・売り検討（スコア -0.6〜-0.3が目安）
    - 'D': 強気売り推奨（スコア -0.6以下が目安）

    3. **詳細評価項目 (detailed_scores)**
    各項目を0-10点で評価：
    - growth_potential: 成長性（将来の売上・利益拡大期待）
    - profitability_outlook: 収益性見通し（利益率改善の可能性）
    - management_quality: 経営の質（戦略・実行力・透明性）
    - risk_level: リスク度（事業リスク・財務リスク）※低いほど良い
    - market_position: 市場地位（競争優位性・シェア）
    - innovation_capability: イノベーション力（技術力・新規事業）

    4. **投資判断ポイント (investment_points)**
    プロの視点から3-5個の具体的ポイント：
    - title: 簡潔な見出し（30文字以内）
    - description: 詳細説明（100文字程度）
    - importance: 重要度（'high', 'medium', 'low'）
    - impact: 株価へのインパクト（'positive', 'negative', 'neutral'）

    5. **リスク分析 (risk_analysis)**
    - major_risks: 主要リスク要因（3個まで）
    - risk_severity: リスクの深刻度（'low', 'medium', 'high', 'critical'）
    - mitigation_evidence: リスク軽減策の有無と評価

    6. **将来見通し (future_outlook)**
    - short_term: 短期見通し（3-6ヶ月）
    - medium_term: 中期見通し（1-2年）
    - long_term: 長期見通し（3-5年）
    
    7. **確信度 (confidence)**
    - 0.0〜1.0の範囲で、この分析の確信度を評価
    - 情報の充実度、矛盾の有無、業界知識との整合性から判断

    8. **分析根拠 (analysis_reasoning)**
    - **必須**: overall_scoreとinvestment_gradeを決定した主要な理由（5個以上）
    - **必須**: なぜそのスコアになったのか具体的な根拠を示すこと
    - 例: 「売上高が前年比20%増加し、営業利益率も改善しているため+0.7と評価」
    - 例: 「重大なリスク要因が3つ特定され、短期的な業績悪化が予想されるため-0.5と評価」

    9. **評価の内訳 (score_breakdown)** ※新規追加
    - positive_factors: ポジティブ要因とその影響度（配列）
    - negative_factors: ネガティブ要因とその影響度（配列）
    - score_calculation_logic: スコア計算のロジック説明

    出力形式（このJSON構造のみを出力）:
    {{
    "overall_score": 0.65,
    "sentiment_label": "positive",
    "investment_grade": "A",
    "score_breakdown": {{
        "positive_factors": [
        {{"factor": "大幅な増収増益達成", "impact": 0.3, "description": "売上高20%増、営業利益30%増"}},
        {{"factor": "市場シェア拡大", "impact": 0.2, "description": "主力製品のシェアが15%→20%に向上"}},
        {{"factor": "新規事業の成長", "impact": 0.15, "description": "新規事業が黒字化し今後の成長ドライバーに"}}
        ],
        "negative_factors": [
        {{"factor": "為替リスク", "impact": -0.1, "description": "海外売上比率60%で円高リスクあり"}},
        {{"factor": "原材料高騰", "impact": -0.05, "description": "主要原材料価格が上昇傾向"}}
        ],
        "score_calculation_logic": "ポジティブ要因の合計(+0.65)からネガティブ要因(-0.15)を差し引き、最終スコア+0.5とした。さらに経営の質の高さを評価し+0.15を加算して+0.65とした。"
    }},
    "detailed_scores": {{
        "growth_potential": 8,
        "profitability_outlook": 7,
        "management_quality": 9,
        "risk_level": 3,
        "market_position": 8,
        "innovation_capability": 7
    }},
    "investment_points": [
        {{
        "title": "積極的な成長戦略",
        "description": "新規市場への投資拡大と技術開発により、今後2-3年で売上高30%増が期待される。",
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
        "long_term": "市場リーダーとしての地位確立。持続的成長基盤が構築される見込み。"
    }},
    "confidence": 0.85,
    "analysis_reasoning": [
        "overall_score +0.65 の根拠: 大幅な増収増益(+0.3)、市場シェア拡大(+0.2)、新規事業成長(+0.15)により合計+0.65",
        "investment_grade A の根拠: スコア+0.65は対応表により'A'に該当。強い成長性と経営の質の高さから買い推奨",
        "経営陣の発言が具体的で実現可能性が高く、信頼性がある",
        "過去の計画達成率が90%以上と高く、今回の計画も達成見込みが高い",
        "業界トレンドと整合した戦略が明確で、競争優位性が確立されている",
        "リスク要因は存在するが、適切な対策が講じられており、管理可能な範囲内"
    ]
    }}

    **重要**: 
    - overall_scoreとinvestment_gradeは必ず整合性を保つこと
    - analysis_reasoningには必ずスコア決定の具体的根拠を含めること
    - score_breakdownで計算ロジックを明示すること
    - マークダウン記号は使用しないこと
    """
        return prompt.strip()
    
    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """AI応答のパース"""
        try:
            # マークダウンコードブロックを除去
            cleaned = response_text.strip()
            if cleaned.startswith('```'):
                # ```json と ``` を除去
                lines = cleaned.split('\n')
                lines = [l for l in lines if not l.strip().startswith('```')]
                cleaned = '\n'.join(lines)
            
            # JSONパース
            result = json.loads(cleaned)
            
            # 必須フィールドの検証
            required_fields = ['overall_score', 'sentiment_label', 'investment_grade']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"必須フィールド '{field}' が見つかりません")
            
            # スコアの範囲チェック
            if not -1.0 <= result['overall_score'] <= 1.0:
                logger.warning(f"スコアが範囲外: {result['overall_score']}")
                result['overall_score'] = max(-1.0, min(1.0, result['overall_score']))
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}")
            logger.error(f"応答テキスト: {response_text[:500]}")
            raise
        except Exception as e:
            logger.error(f"応答パースエラー: {e}")
            raise
    
    def _fallback_analysis(self, basic_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """AIが利用できない場合のフォールバック"""
        if basic_analysis:
            score = basic_analysis.get('overall_score', 0.0)
            sentiment = basic_analysis.get('sentiment_label', 'neutral')
        else:
            score = 0.0
            sentiment = 'neutral'
        
        # 基本分析からグレード推定
        if score > 0.6:
            grade = 'A'
        elif score > 0.3:
            grade = 'B+'
        elif score > -0.3:
            grade = 'B'
        elif score > -0.6:
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
                'timestamp': timezone.now().isoformat()
            }
        }