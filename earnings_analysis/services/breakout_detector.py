# earnings_analysis/services/breakout_detector.py
# 株価突破ポテンシャル検出サービス
# AI分析結果から「稀有な高収益パターン」を検出し、現在株価を突き抜ける可能性を評価する

import logging
import json
import re
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ========== 突破パターン定義 ==========

BREAKOUT_PATTERNS = {
    "perfect_alignment": {
        "name": "完全アライメント",
        "description": "利益成長・CF品質・競争力が同時に理想的な状態",
        "icon": "⚡",
        "weight": 40,
    },
    "quality_earnings": {
        "name": "利益の質プレミアム",
        "description": "報告利益を大幅に上回るキャッシュ創出力（市場が見落としがち）",
        "icon": "💎",
        "weight": 30,
    },
    "growth_acceleration": {
        "name": "成長加速",
        "description": "売上・利益の二桁成長とシェア拡大・マージン改善が同時進行",
        "icon": "🚀",
        "weight": 35,
    },
    "hidden_value": {
        "name": "隠れた価値",
        "description": "市場未評価の技術的・競争的優位性と健全なキャッシュフロー",
        "icon": "🔍",
        "weight": 25,
    },
    "exceptional_score": {
        "name": "例外的な高評価",
        "description": "AI総合評価が例外的レベル（85点以上）の稀有な評価水準",
        "icon": "🌟",
        "weight": 45,
    },
}

# 高収益を示す positive_factors のキーワード
POSITIVE_FACTOR_KEYWORDS = {
    "double_digit_growth": ["二桁成長", "増収増益", "大幅増収", "大幅増益", "二桁増"],
    "high_roe": ["ROE", "自己資本利益率"],
    "strong_cashflow": ["営業CF", "キャッシュフロー", "フリーキャッシュ", "CF"],
    "market_leadership": ["市場シェア", "トップ3", "シェア拡大", "業界首位", "市場首位"],
    "tech_patents": ["技術", "特許", "差別化", "独自", "イノベーション"],
    "margin_improvement": ["利益率", "マージン", "収益性改善", "利益率改善"],
}


class BreakoutDetector:
    """
    株価突破ポテンシャル検出サービス

    AI Expert分析結果から「稀有な高収益パターン」を検出し、
    現在の株価水準を大きく超える可能性があるかを評価する。
    """

    def __init__(self):
        self._init_gemini()

    def _init_gemini(self):
        """Gemini API初期化（失敗してもデグレードしない）"""
        self.model = None
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash-lite")
        except Exception as e:
            logger.warning(f"BreakoutDetector Gemini初期化失敗（ルールベース分析のみ実行）: {e}")

    # ------------------------------------------------------------------
    # メインエントリポイント
    # ------------------------------------------------------------------

    def detect_and_analyze(
        self,
        ai_expert_result: Dict[str, Any],
        document_info: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        突破ポテンシャルを検出・分析する。

        Args:
            ai_expert_result: ai_expert_analysis の辞書
            document_info: 企業・書類情報（Gemini分析用）

        Returns:
            {
                detected: bool,
                level: "HIGH" | "MEDIUM" | "LOW" | "NONE",
                score: int (0-100),
                patterns: list[{key, name, description, icon}],
                key_signals: list[str],
                gemini_analysis: list[{title, description}] | None,
            }
        """
        if not ai_expert_result:
            return self._empty_result()

        # ルールベースのパターン検出
        detected_pattern_keys = self._detect_patterns(ai_expert_result)
        score = self._calculate_score(detected_pattern_keys, ai_expert_result)
        level = self._get_level(score)
        patterns = [
            {
                "key": k,
                "name": BREAKOUT_PATTERNS[k]["name"],
                "description": BREAKOUT_PATTERNS[k]["description"],
                "icon": BREAKOUT_PATTERNS[k]["icon"],
            }
            for k in detected_pattern_keys
        ]
        key_signals = self._extract_key_signals(ai_expert_result, detected_pattern_keys)

        # Gemini による追加分析（HIGH/MEDIUM かつ API 利用可能な場合のみ）
        gemini_analysis = None
        if level in ("HIGH", "MEDIUM") and self.model:
            gemini_analysis = self._get_gemini_analysis(
                ai_expert_result, detected_pattern_keys, document_info
            )

        return {
            "detected": level != "NONE",
            "level": level,
            "score": score,
            "patterns": patterns,
            "key_signals": key_signals,
            "gemini_analysis": gemini_analysis,
            "generated_at": timezone.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # パターン検出ロジック
    # ------------------------------------------------------------------

    def _detect_patterns(self, ai: Dict[str, Any]) -> List[str]:
        """AI分析結果から突破パターンを検出する"""
        detected = []
        overall_score = ai.get("overall_score", 0) or 0
        grade = ai.get("investment_grade", "") or ""
        positive_factors = ai.get("score_breakdown", {}).get("positive_factors", []) or []
        detailed_scores = ai.get("detailed_scores", {}) or {}
        risk_severity = (ai.get("risk_analysis", {}) or {}).get("risk_severity", "medium")

        # 各 positive_factor の factor 文字列を集約
        factor_texts = " ".join(f.get("factor", "") + " " + f.get("description", "") for f in positive_factors)

        # ---------- exceptional_score ----------
        if overall_score >= 85:
            detected.append("exceptional_score")

        # ---------- perfect_alignment ----------
        # 条件: A/A+ グレード + 高スコア + CF関連ポジティブ + リスク低
        has_high_grade = grade in ("A", "A+")
        has_cf_positive = self._has_keywords(factor_texts, POSITIVE_FACTOR_KEYWORDS["strong_cashflow"])
        has_low_risk = risk_severity == "low"
        if has_high_grade and overall_score >= 75 and has_cf_positive and has_low_risk:
            detected.append("perfect_alignment")

        # ---------- quality_earnings ----------
        # 条件: CF強調 + 総合スコア高め(70+) + grade B+以上
        high_grade_set = {"A+", "A", "B+"}
        has_quality_cf = self._has_keywords(factor_texts, POSITIVE_FACTOR_KEYWORDS["strong_cashflow"])
        if has_quality_cf and overall_score >= 70 and grade in high_grade_set:
            # さらに詳細スコアで profitability_outlook が高い場合を優先
            prof_score = detailed_scores.get("profitability_outlook", 0) or 0
            if prof_score >= 7:
                detected.append("quality_earnings")

        # ---------- growth_acceleration ----------
        # 条件: 二桁成長 + マージン改善 + マーケットリーダーシップ のうち2つ以上
        growth_signals = [
            self._has_keywords(factor_texts, POSITIVE_FACTOR_KEYWORDS["double_digit_growth"]),
            self._has_keywords(factor_texts, POSITIVE_FACTOR_KEYWORDS["margin_improvement"]),
            self._has_keywords(factor_texts, POSITIVE_FACTOR_KEYWORDS["market_leadership"]),
        ]
        growth_count = sum(growth_signals)
        if growth_count >= 2 and overall_score >= 65:
            detected.append("growth_acceleration")

        # ---------- hidden_value ----------
        # 条件: 技術・特許 + CF健全 + B+以上
        has_tech = self._has_keywords(factor_texts, POSITIVE_FACTOR_KEYWORDS["tech_patents"])
        has_cf_ok = self._has_keywords(factor_texts, POSITIVE_FACTOR_KEYWORDS["strong_cashflow"])
        innov_score = detailed_scores.get("innovation_capability", 0) or 0
        if (has_tech or innov_score >= 7) and overall_score >= 70 and grade in high_grade_set:
            detected.append("hidden_value")

        return detected

    def _has_keywords(self, text: str, keywords: List[str]) -> bool:
        return any(kw in text for kw in keywords)

    # ------------------------------------------------------------------
    # スコア・レベル計算
    # ------------------------------------------------------------------

    def _calculate_score(self, pattern_keys: List[str], ai: Dict[str, Any]) -> int:
        """検出パターンと AI スコアから突破スコアを計算する（0-100）"""
        if not pattern_keys:
            return 0

        # パターンウェイト合計
        pattern_score = sum(BREAKOUT_PATTERNS[k]["weight"] for k in pattern_keys)
        # 上限は60点（残り40点はAIスコアで補正）
        pattern_score = min(pattern_score, 60)

        # AIスコア補正（overall_score 85 → +40, 75 → +25, 65 → +10）
        overall_score = ai.get("overall_score", 0) or 0
        if overall_score >= 85:
            ai_bonus = 40
        elif overall_score >= 75:
            ai_bonus = 25
        elif overall_score >= 65:
            ai_bonus = 10
        else:
            ai_bonus = 0

        # 複数パターン検出時のボーナス
        multi_bonus = (len(pattern_keys) - 1) * 5 if len(pattern_keys) > 1 else 0

        total = pattern_score + ai_bonus + multi_bonus
        return min(100, max(0, total))

    def _get_level(self, score: int) -> str:
        if score >= 70:
            return "HIGH"
        elif score >= 45:
            return "MEDIUM"
        elif score >= 20:
            return "LOW"
        return "NONE"

    # ------------------------------------------------------------------
    # キーシグナル抽出
    # ------------------------------------------------------------------

    def _extract_key_signals(
        self, ai: Dict[str, Any], pattern_keys: List[str]
    ) -> List[str]:
        """投資家向けのキーシグナル文言を生成する"""
        signals = []
        overall_score = ai.get("overall_score", 0) or 0
        grade = ai.get("investment_grade", "") or ""
        positive_factors = ai.get("score_breakdown", {}).get("positive_factors", []) or []

        if overall_score >= 85:
            signals.append(f"AI総合評価スコア {overall_score}点（例外的水準）")
        elif overall_score >= 75:
            signals.append(f"AI総合評価スコア {overall_score}点（高水準）")

        if grade in ("A+", "A"):
            signals.append(f"投資グレード {grade}（最上位評価）")

        # ポジティブ要因の上位2件をシグナルとして採用
        for f in positive_factors[:2]:
            factor = f.get("factor", "")
            desc = f.get("description", "")
            impact = f.get("impact", 0)
            if factor and impact and int(impact) >= 5:
                signals.append(f"{factor}: {desc}" if desc else factor)

        # パターン別の補足メッセージ
        if "quality_earnings" in pattern_keys:
            signals.append("キャッシュ創出力が報告利益を大幅に上回る可能性（利益の質が高い）")
        if "growth_acceleration" in pattern_keys:
            signals.append("売上・利益の二桁成長とシェア拡大が同時進行中")
        if "hidden_value" in pattern_keys:
            signals.append("技術・競争優位性が株価に十分織り込まれていない可能性")
        if "perfect_alignment" in pattern_keys:
            signals.append("財務健全性・成長性・競争力が高水準で揃っている")

        return signals[:6]  # 最大6件

    # ------------------------------------------------------------------
    # Gemini による追加分析
    # ------------------------------------------------------------------

    def _get_gemini_analysis(
        self,
        ai: Dict[str, Any],
        pattern_keys: List[str],
        document_info: Optional[Dict[str, str]],
    ) -> Optional[List[Dict[str, str]]]:
        """
        突破ポテンシャルについて Gemini に特化した分析を依頼する。
        失敗した場合は None を返す（分析全体はブロックしない）。
        """
        try:
            prompt = self._build_gemini_prompt(ai, pattern_keys, document_info)
            response = self.model.generate_content(prompt)
            if not response or not response.text:
                return None
            return self._parse_gemini_response(response.text)
        except Exception as e:
            logger.warning(f"BreakoutDetector Gemini分析失敗（スキップ）: {e}")
            return None

    def _build_gemini_prompt(
        self,
        ai: Dict[str, Any],
        pattern_keys: List[str],
        document_info: Optional[Dict[str, str]],
    ) -> str:
        company_name = (document_info or {}).get("company_name", "対象企業")
        grade = ai.get("investment_grade", "")
        score = ai.get("overall_score", 0)
        summary = (ai.get("expert_commentary") or {}).get("summary", "")
        pattern_names = "、".join(BREAKOUT_PATTERNS[k]["name"] for k in pattern_keys)

        # ポジティブ要因を文字列化
        positive_factors = ai.get("score_breakdown", {}).get("positive_factors", []) or []
        pos_text = "\n".join(
            f"- {f.get('factor','')}: {f.get('description','')}"
            for f in positive_factors[:5]
        )

        prompt = f"""
あなたは株式投資の専門アナリストです。
以下の企業分析結果について「現在の株価水準を大きく上回る可能性」の観点から分析してください。

【企業名】{company_name}
【AI評価グレード】{grade}（総合スコア: {score}/100点）
【検出された稀有パターン】{pattern_names}
【AI専門家評価サマリー】{summary}
【主なポジティブ要因】
{pos_text}

【分析依頼】
この企業の分析結果は「{pattern_names}」という稀有な高収益パターンを示しています。

次の観点で3〜4点を具体的に日本語で教えてください:
1. 現在の株価水準にまだ反映されていない可能性がある要因
2. 投資家が見落としがちな財務的・事業的強み
3. 今後の株価上昇の具体的なカタリスト候補

【出力形式】JSONのみ（マークダウン不要）
[
  {{"title": "要因タイトル（15字以内）", "description": "具体的な説明（50〜80字）"}},
  ...
]

【注意】
- 投機的・断定的な表現は避け「可能性がある」「考えられる」等の表現を使用
- 3〜4点を出力。それ以上は不要
- 根拠のない楽観的表現は使わない
"""
        return prompt.strip()

    def _parse_gemini_response(self, text: str) -> Optional[List[Dict[str, str]]]:
        """Gemini の JSON レスポンスをパースする"""
        try:
            cleaned = text.strip()

            # JSON配列を直接パース
            if cleaned.startswith('['):
                return json.loads(cleaned)

            # Markdownコードブロックから抽出
            match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', cleaned)
            if match:
                return json.loads(match.group(1))

            # 配列部分を抽出
            start = cleaned.find('[')
            end = cleaned.rfind(']')
            if start != -1 and end != -1 and end > start:
                return json.loads(cleaned[start:end + 1])

            logger.warning("BreakoutDetector: Gemini応答からJSON配列を抽出できませんでした")
            return None

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"BreakoutDetector: Gemini応答のパースエラー: {e}")
            return None

    # ------------------------------------------------------------------
    # ユーティリティ
    # ------------------------------------------------------------------

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "detected": False,
            "level": "NONE",
            "score": 0,
            "patterns": [],
            "key_signals": [],
            "gemini_analysis": None,
            "generated_at": timezone.now().isoformat(),
        }
