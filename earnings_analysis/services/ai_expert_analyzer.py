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
        """分析プロンプト構築（バランス調整版）"""
        
        max_text_length = 30000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "...(以下省略)"
        
        basic_summary = ""
        basic_score_info = ""
        if basic_analysis:
            basic_summary = f"""
    参考：ワードベース分析結果
    - 検出されたポジティブ語彙: {len(basic_analysis.get('keyword_analysis', {}).get('positive', []))}個
    - 検出されたネガティブ語彙: {len(basic_analysis.get('keyword_analysis', {}).get('negative', []))}個
    - 基本スコア: {basic_analysis.get('overall_score', 0):.3f}
    """
            # ワードベーススコアの換算（-1.0～1.0 → 0～100点）
            word_score = basic_analysis.get('overall_score', 0.0)
            converted_score = int((word_score + 1.0) * 50)
            basic_score_info = f"""
    【重要】ワードベース分析では既に語彙の出現頻度から{converted_score}点という評価が出ています。
    この点数は文書中のポジティブ/ネガティブ語彙の出現比率に基づいています。
    あなたは、この語彙分析結果を「参考値」として活用し、文脈・事業の質・数値の裏付けを総合的に判断してください。
    """
        
        company_name = doc_info.get('company_name', '不明')
        
        prompt = f"""
    あなたは30年以上の経験を持つ株式アナリストです。
    企業の開示資料を冷静に分析し、投資判断に必要な包括的評価を行ってください。

    【企業情報】
    企業名: {company_name}
    証券コード: {doc_info.get('securities_code', '不明')}
    書類種別: {doc_info.get('doc_description', '不明')}
    提出日: {doc_info.get('submit_date', '不明')}

    {basic_summary}

    {basic_score_info}

    【分析対象テキスト】
    {text}

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    【評価方針】企業開示資料の特性を理解した上での冷静な評価
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    企業が公表する資料には一定のポジティブバイアスが存在しますが、
    極端に厳しい評価ではなく、事業実態を反映したバランスの取れた評価を心がけてください。

    【スコアリング基準（現実的版）】

    ■ 35点未満 [D]: 深刻な業績悪化・重大な経営課題
    - 大幅な減収減益、赤字拡大
    - 事業継続性に疑問符
    - 財務危機の兆候

    ■ 35-49点 [C]: 課題が目立つ状況
    - 減収または減益
    - 前期目標の大幅未達
    - 構造的な問題が表面化

    ■ 50-64点 [B]: 標準的な企業開示（基準点55点）
    - 微増収微増益、または現状維持
    - 特筆すべき強みも弱みもない
    - 業界平均並みの成長

    ■ 65-74点 [B+]: 良好な状態
    - 堅調な増収増益（5-15%成長）
    - 利益率が維持または改善傾向
    - 明確な事業戦略がある

    ■ 75-84点 [A]: 優秀な業績
    - 二桁成長または大幅な利益率改善
    - 競争優位性が明確
    - 財務健全性が高い

    ■ 85点以上 [A+]: 極めて優秀（稀）
    - 業界トップクラスの実績
    - 持続的な競争優位性
    - イノベーションによる市場創造

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    【加点・減点の判断基準】
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    基準点55点を起点として、以下の要素を総合的に判断してください。
    ワードベース分析で既に語彙レベルの評価は行われているため、
    あなたは「文脈」「事業の質」「数値の裏付け」に注目してください。

    ▼【減点要素】実質的な問題がある場合のみ減点

    ■ 業績の質的問題（各-3～-8点）
    - 売上増でも利益率が大幅低下（価格競争に巻き込まれている）: -5～-7点
    - 営業CFが利益に比して著しく低い（利益の質に問題）: -5～-7点
    - 前期目標を大幅に未達（経営の実行力不足）: -6～-8点
    - 市場成長率を大きく下回る成長（シェア喪失）: -5～-7点
    - コスト削減だけに依存した増益（本業の競争力低下）: -4～-6点

    ■ 事業基盤の問題（各-3～-7点）
    - 主力事業の成長鈍化が明確: -4～-6点
    - 競合他社に明らかに劣後している（具体的データがある場合）: -5～-7点
    - 顧客基盤の縮小傾向: -4～-6点
    - 技術的優位性の喪失: -5～-7点

    ■ 財務上のリスク（各-3～-6点）
    - 有利子負債が総資産の60%超: -5～-6点
    - 自己資本比率が20%未満: -5～-6点
    - 流動比率が80%未満: -4～-5点
    - 営業CFが2期連続マイナス: -6～-7点

    ■ 情報開示の問題（各-2～-5点）
    ※ただし、これはあくまで「情報の透明性」の評価であり、事業実態の評価ではない
    - 重要な数値目標が一切示されていない: -3～-4点
    - リスク情報が極めて形式的（2項目以下、各30文字以下）: -3～-5点
    - 前期の失敗や課題に全く触れていない（異常に楽観的）: -2～-4点
    - 競合比較を意図的に回避している様子: -2～-3点

    ▲【加点要素】明確な強みがある場合に加点

    ■ 業績の質的優位性（各+3～+8点）
    - 営業利益率が前年比2%ポイント以上改善: +5～+7点
    - ROEが15%以上かつ改善傾向: +5～+7点
    - 営業CFが当期純利益の120%以上: +4～+6点
    - 市場成長率を5%以上上回る成長: +5～+7点
    - 売上と利益がともに二桁成長: +6～+8点

    ■ 競争優位性の証拠（各+3～+7点）
    - 市場シェアがトップ3かつ拡大中（具体的数値あり）: +5～+7点
    - 独自技術や特許による差別化が明確: +4～+6点
    - 顧客満足度やリピート率の具体的データ: +3～+5点
    - ブランド力の客観的評価（外部評価）: +3～+5点

    ■ 成長性・将来性（各+3～+6点）
    - 新製品・新サービスの売上寄与が具体的に示されている: +4～+6点
    - 成長市場での明確なポジション確立: +4～+6点
    - M&Aや提携による相乗効果が数値で示されている: +3～+5点

    ■ 経営の質（各+2～+5点）
    - 過去の失敗を認め、具体的改善策を提示: +3～+5点
    - 株主還元方針が明確で実績もある: +2～+4点
    - ESGへの取り組みが業界トップ水準（外部評価あり）: +2～+4点

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    【重要な判断ポイント】
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    1. **表面的な増収増益だけで高評価しない**
    → 成長の「質」を見る：利益率は？市場比では？持続性は？

    2. **ネガティブ語彙が多い ≠ 必ずしも悪い企業**
    → 「課題」「リスク」に言及する誠実な企業もある
    → 文脈を読んで判断（課題を認識→改善中 なら評価できる）

    3. **ポジティブ語彙が多い ≠ 必ずしも良い企業**
    → 抽象的な美辞麗句だけで具体性がない場合は割り引く

    4. **数値の裏付けを重視**
    → 「順調」「好調」という言葉より、具体的な％や金額

    5. **相対評価を意識**
    → 業界の成長率、競合の動向と比較（情報があれば）

    6. **情報開示の不足は大きな減点にしない**
    → 事業実態の評価を優先。開示不足は-2～-4点程度に留める

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    【スコア計算の進め方】
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ステップ1: 基準点55点からスタート

    ステップ2: 業績実態の評価（最重要）
    - 増収増益の質を見る
    - 利益率・効率性指標の変化
    - 市場環境との比較
    → この段階で±10～15点程度の変動

    ステップ3: 競争力・持続性の評価
    - 競合優位性の有無
    - 事業基盤の強さ
    - 成長戦略の具体性
    → この段階で±5～10点程度の変動

    ステップ4: 財務健全性・リスク評価
    - 財務指標のチェック
    - 事業リスクの大きさ
    → この段階で±3～5点程度の変動

    ステップ5: 情報開示の透明性
    - あくまで補足的評価
    → この段階で±2～3点程度の変動

    最終スコア = 55点 + 上記の合計

    ※減点・加点の合計が±30点を超える場合は、評価が極端すぎないか再確認してください

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    【専門家考察の記述方針】
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    expert_commentaryセクションでは、バランスの取れた分析を提供してください：

    ■ summary（総括）
    - 企業の現状を客観的に総括（2-3文）
    - ポジティブ・ネガティブ両面を簡潔に

    ■ business_assessment（事業評価）
    - 事業の競争力を実態ベースで評価
    - 成長の持続可能性について
    - 競合比較（情報があれば）

    ■ financial_health（財務健全性）
    - 主要な財務指標の評価
    - 利益の質とキャッシュフロー
    - 財務リスクの程度

    ■ management_evaluation（経営評価）
    - 経営戦略の具体性と実現可能性
    - 過去の実績との整合性
    - 株主還元姿勢

    ■ market_positioning（市場ポジション）
    - 業界内での位置づけ
    - 競争優位性の源泉
    - 市場環境への適応力

    ■ key_concerns（懸念事項）
    - 2-4つの具体的な懸念材料
    - 過度に悲観的にならず、現実的なリスク評価

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    【出力形式】以下のJSON形式のみを出力（マークダウン記号不要）
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    {{
    "overall_score": 65,
    "sentiment_label": "positive",
    "investment_grade": "B+",
    "expert_commentary": {{
        "summary": "売上高は前年比8%増、営業利益は12%増と堅調な増収増益を達成。主力事業の収益性も改善しており、事業基盤は安定している。一方で市場成長率15%と比較するとやや成長ペースが鈍く、競争力強化が今後の課題となる。",
        "business_assessment": "主力の○○事業は市場シェア20%を維持し、新製品投入により客単価も向上している。△△セグメントでは競合との差別化に成功し、利益率が前年比1.5%ポイント改善した。ただし、□□市場での競争激化により販売数量の伸びは鈍化傾向にある。",
        "financial_health": "自己資本比率48%、流動比率135%と財務基盤は健全。営業キャッシュフローは当期純利益の110%を確保しており、利益の質も良好。有利子負債比率は適正水準であり、成長投資と配当の両立が可能な状況。",
        "management_evaluation": "中期経営計画の進捗は概ね順調で、営業利益率目標8%に対し7.8%まで改善。経営陣は市場環境の変化を認識し、デジタル化投資を加速させている。配当性向35%を維持し、株主還元への意識も高い。",
        "market_positioning": "業界4位の地位を維持しているが、上位3社とのギャップは縮小傾向。特定の製品カテゴリーでは技術的優位性を持ち、一定の差別化に成功している。今後は新規顧客の獲得がシェア拡大の鍵となる。",
        "key_concerns": "第一に、市場全体の成長率15%に対し当社8%と相対的なシェア低下が懸念される。第二に、原材料価格の上昇圧力が続いており、価格転嫁の遅れは利益率を圧迫する可能性。第三に、新規事業の収益化には2-3年かかる見込みで、短期的な収益貢献は限定的。"
    }},
    "score_breakdown": {{
        "base_score": 55,
        "positive_factors": [
        {{"factor": "増収増益の達成", "impact": 5, "description": "売上8%増、営業利益12%増"}},
        {{"factor": "営業利益率の改善", "impact": 4, "description": "7.3%→7.8%に改善"}},
        {{"factor": "営業CFが堅調", "impact": 3, "description": "利益の110%を確保"}},
        {{"factor": "財務基盤が健全", "impact": 3, "description": "自己資本比率48%"}}
        ],
        "negative_factors": [
        {{"factor": "市場成長率を下回る", "impact": -5, "description": "当社8% vs 市場15%"}},
        {{"factor": "競合情報が限定的", "impact": -3, "description": "相対的評価が困難"}},
        {{"factor": "新規事業の不確実性", "impact": -2, "description": "収益化に時間要する"}}
        ],
        "final_calculation": "基準点55点 + ポジティブ要因15点 - ネガティブ要因10点 = 60点 → 業績の質を考慮して65点"
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
        "description": "売上・利益ともに成長を維持しており、事業基盤は安定。",
        "importance": "high",
        "impact": "positive"
        }},
        {{
        "title": "財務健全性が高い",
        "description": "自己資本比率48%、営業CFも堅調で財務リスクは低い。",
        "importance": "medium",
        "impact": "positive"
        }},
        {{
        "title": "市場成長率との乖離",
        "description": "業界平均を下回る成長率は相対的なシェア低下を意味する。",
        "importance": "medium",
        "impact": "negative"
        }}
    ],
    "investor_insights": [
        {{
        "title": "堅実な経営姿勢",
        "description": "大きな成長は見込めないが、着実に利益を積み上げるディフェンシブな投資先として評価できる。",
        "source": "ai_generated"
        }}
    ],
    "risk_analysis": {{
        "major_risks": ["市場成長率を下回る成長", "原材料価格上昇", "新規事業の不確実性"],
        "risk_severity": "medium",
        "mitigation_evidence": "コスト削減努力と価格改定を進めており、一定の対応力はある。"
    }},
    "future_outlook": {{
        "short_term": "現状の増収増益基調は継続する見込み。",
        "medium_term": "利益率改善の余地があり、営業利益率8-9%への到達が期待される。",
        "long_term": "新規事業の育成と既存事業の効率化により、持続的成長は可能と判断。"
    }},
    "confidence": 0.78,
    "analysis_reasoning": [
        "overall_score 65点の根拠: 基準点55点に対し、堅調な増収増益と利益率改善で+15点、一方で市場成長率を下回る点や情報開示の限定性で-10点、最終的に業績の質を総合評価して65点とした。",
        "標準を上回る良好な企業だが、業界トップクラスというほどではない。安定志向の投資家に適した銘柄。"
    ]
    }}

    【最終確認】
    ✓ overall_scoreは実態を反映しているか？（極端に低すぎないか？）
    ✓ 語彙の頻度だけでなく、文脈・数値・事業の質を評価したか？
    ✓ ポジティブ・ネガティブ両面をバランスよく記述したか？
    ✓ score_breakdownの計算は論理的か？
    ✓ 50-70点のレンジに多くの企業が収まるような評価になっているか？
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