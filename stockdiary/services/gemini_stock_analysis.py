"""
Gemini APIを使った複数銘柄の投資比較分析サービス
"""
import google.generativeai as genai
import logging
import json
import re
from django.conf import settings
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class GeminiStockAnalyzer:
    """複数銘柄の財務比較データを分析するGeminiサービス"""

    def __init__(self):
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        self.api_available = bool(api_key)
        self.model = None
        self.initialization_error = None

        if not api_key:
            logger.warning("GEMINI_API_KEYが設定されていません")
            self.initialization_error = "API_KEY_MISSING"
            return

        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash-lite")
            logger.info("GeminiStockAnalyzer: API初期化完了")
        except Exception as e:
            logger.error(f"Gemini初期化エラー: {e}")
            self.api_available = False
            self.initialization_error = str(e)

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------
    def analyze_stocks(self, stocks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        複数銘柄を比較分析してJSON形式で返す
        stocks_data: フロントエンドから送られてくる各銘柄のデータ辞書のリスト
        """
        if not stocks_data:
            return self._error_result("銘柄データがありません")

        if not self.model:
            logger.warning("Gemini API未使用 - フォールバック分析を実行")
            result = self._fallback_analysis(stocks_data)
            result['api_success'] = False
            result['fallback_used'] = True
            result['error_message'] = self.initialization_error
            return result

        prompt = self._build_prompt(stocks_data)
        try:
            logger.info(f"Gemini API呼び出し開始: {len(stocks_data)}銘柄")
            response = self.model.generate_content(prompt)
            if response.text:
                parsed = self._parse_response(response.text, stocks_data)
                if parsed.get('api_success'):
                    logger.info("Gemini API分析完了")
                    return parsed
        except Exception as e:
            logger.error(f"Gemini API呼び出しエラー: {e}")

        result = self._fallback_analysis(stocks_data)
        result['api_success'] = False
        result['fallback_used'] = True
        return result

    # ----------------------------------------------------------------
    # Prompt building
    # ----------------------------------------------------------------
    def _build_prompt(self, stocks_data: List[Dict]) -> str:
        stocks_desc = ""
        for d in stocks_data:
            name = d.get('stock_name') or d.get('code', '不明')
            code = d.get('code', '')

            roe = self._latest(d.get('roe', []))
            rev = d.get('revenue', [])
            oi = d.get('operating_income', [])
            eq_ratio = self._latest(d.get('equity_ratio', []))
            per = d.get('per')
            pbr = d.get('pbr')
            div_yield = d.get('dividend_yield')

            rev_latest = self._latest(rev)
            oi_latest = self._latest(oi)
            opm = round(oi_latest / rev_latest * 100, 1) if rev_latest and oi_latest else None

            rev_cagr = self._calc_cagr(rev)
            oi_cagr = self._calc_cagr(oi)

            def fmt(v, suffix=''):
                return f"{v}{suffix}" if v is not None else "データなし"

            stocks_desc += f"""
■ {name}（{code}）
  ROE: {fmt(roe, '%')} | 営業利益率: {fmt(opm, '%')} | 自己資本比率: {fmt(eq_ratio, '%')}
  PER: {fmt(per, '倍')} | PBR: {fmt(pbr, '倍')} | 配当利回り: {fmt(div_yield, '%')}
  売上CAGR(4年): {fmt(rev_cagr, '%')} | 営業利益CAGR: {fmt(oi_cagr, '%')}
"""

        n = len(stocks_data)
        prompt = f"""あなたは日本株の投資プロアナリストです。以下の{n}銘柄の財務データを詳細に分析し、個人投資家向けの投資判断支援レポートを作成してください。

【分析銘柄】
{stocks_desc}
以下のJSON形式（日本語）で回答してください。コードブロック（```）や余分な説明テキストは不要です。JSONのみを返してください。

{{
  "overall_summary": "全銘柄を俯瞰した分析コメント（100〜150文字）",
  "top_pick": "最も投資推奨度が高い銘柄コード（例: 7203）",
  "top_pick_reason": "推奨理由（50〜80文字）",
  "stocks": [
    {{
      "code": "銘柄コード",
      "grade": "S/A/B/C/D（S:非常に優秀、A:優秀、B:標準、C:要注意、D:回避）",
      "investment_appeal": "投資魅力度の説明（50〜80文字）",
      "strengths": ["強み1（30文字程度）", "強み2"],
      "risks": ["リスク1（30文字程度）", "リスク2"],
      "recommendation": "積極買い/打診買い/様子見/回避"
    }}
  ],
  "comparison_insight": "銘柄間の相対的な優劣・特徴（80〜120文字）",
  "portfolio_note": "ポートフォリオ観点での組み入れ提案（50〜80文字）"
}}"""
        return prompt.strip()

    # ----------------------------------------------------------------
    # Response parsing
    # ----------------------------------------------------------------
    def _parse_response(self, text: str, stocks_data: List[Dict]) -> Dict:
        # コードブロックを除去
        text = re.sub(r'```(?:json)?', '', text).strip().rstrip('`')

        try:
            data = json.loads(text)
            data['api_success'] = True
            data['fallback_used'] = False
            # stocksの順序をstocks_dataに合わせて整列
            self._align_stocks_order(data, stocks_data)
            return data
        except json.JSONDecodeError:
            # JSONオブジェクトを抽出して再パース
            match = re.search(r'\{[\s\S]+\}', text)
            if match:
                try:
                    data = json.loads(match.group())
                    data['api_success'] = True
                    data['fallback_used'] = False
                    self._align_stocks_order(data, stocks_data)
                    return data
                except Exception:
                    pass

        logger.warning("Gemini応答のJSONパースに失敗 - フォールバックへ")
        return self._fallback_analysis(stocks_data)

    def _align_stocks_order(self, data: Dict, stocks_data: List[Dict]):
        """APIが返したstocksの順序をフロントエンドの銘柄順に整列"""
        if 'stocks' not in data:
            return
        code_map = {s.get('code', ''): s for s in data['stocks']}
        aligned = []
        for d in stocks_data:
            code = d.get('code', '')
            if code in code_map:
                aligned.append(code_map[code])
        if aligned:
            data['stocks'] = aligned

    # ----------------------------------------------------------------
    # Fallback analysis (API不使用時)
    # ----------------------------------------------------------------
    def _fallback_analysis(self, stocks_data: List[Dict]) -> Dict:
        stocks_analysis = []
        best_code = ''
        best_score = -1

        for d in stocks_data:
            code = d.get('code', '')
            roe = self._latest(d.get('roe', []))
            per = d.get('per')
            rev_cagr = self._calc_cagr(d.get('revenue', []))
            oi_cagr = self._calc_cagr(d.get('operating_income', []))
            eq_ratio = self._latest(d.get('equity_ratio', []))
            div_yield = d.get('dividend_yield')

            score = 0
            strengths = []
            risks = []

            if roe is not None:
                if roe >= 15:
                    score += 3
                    strengths.append(f'高ROE {roe}%: 資本効率に優れる')
                elif roe >= 10:
                    score += 2
                    strengths.append(f'ROE {roe}%: 良好な収益性')
                elif roe < 5:
                    risks.append(f'ROE {roe}%: 収益性の改善が必要')

            if per is not None:
                if per <= 12:
                    score += 3
                    strengths.append(f'PER {per}倍: 割安圏')
                elif per <= 20:
                    score += 2
                    strengths.append(f'PER {per}倍: 適正水準')
                elif per > 35:
                    risks.append(f'PER {per}倍: 割高圏')
                    score -= 1

            if rev_cagr is not None:
                if rev_cagr >= 10:
                    score += 3
                    strengths.append(f'売上CAGR +{rev_cagr}%: 高成長')
                elif rev_cagr >= 5:
                    score += 2
                    strengths.append(f'売上CAGR +{rev_cagr}%: 安定成長')
                elif rev_cagr < 0:
                    risks.append(f'売上CAGR {rev_cagr}%: 売上減少傾向')

            if eq_ratio is not None:
                if eq_ratio >= 60:
                    score += 2
                    strengths.append(f'自己資本比率 {eq_ratio}%: 財務健全')
                elif eq_ratio >= 40:
                    score += 1
                elif eq_ratio < 20:
                    risks.append(f'自己資本比率 {eq_ratio}%: 財務に注意')

            if div_yield is not None and div_yield >= 3:
                score += 1
                strengths.append(f'配当利回り {div_yield}%: 株主還元充実')

            grade = 'S' if score >= 9 else 'A' if score >= 7 else 'B' if score >= 4 else 'C' if score >= 2 else 'D'
            rec_map = {'S': '積極買い', 'A': '打診買い', 'B': '様子見', 'C': '様子見', 'D': '回避'}

            if score > best_score:
                best_score = score
                best_code = code

            stocks_analysis.append({
                'code': code,
                'grade': grade,
                'investment_appeal': f'財務スコア{score}点。{grade}評価の銘柄です。',
                'strengths': strengths[:3] if strengths else ['データ分析中'],
                'risks': risks[:2] if risks else ['特段のリスクなし'],
                'recommendation': rec_map.get(grade, '様子見'),
            })

        return {
            'overall_summary': (
                f'{len(stocks_data)}銘柄を財務スコアで自動評価しました。'
                'より詳細な見解はAI分析ボタンをご活用ください。'
            ),
            'top_pick': best_code,
            'top_pick_reason': '財務スコアが最も高い銘柄です（自動計算）',
            'stocks': stocks_analysis,
            'comparison_insight': '財務指標のスコアリングによる相対評価です。業種特性を考慮した判断をお勧めします。',
            'portfolio_note': 'リスク分散のため、異なる業種への投資も検討してください。',
            'api_success': False,
            'fallback_used': True,
        }

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------
    @staticmethod
    def _latest(arr: List) -> Optional[float]:
        if not arr:
            return None
        for v in reversed(arr):
            if v is not None:
                return v
        return None

    @staticmethod
    def _calc_cagr(arr: List) -> Optional[float]:
        valid = [v for v in (arr or []) if v is not None]
        if len(valid) < 2 or valid[0] <= 0:
            return None
        return round((pow(valid[-1] / valid[0], 1 / (len(valid) - 1)) - 1) * 100, 1)

    @staticmethod
    def _error_result(msg: str) -> Dict:
        return {
            'overall_summary': msg,
            'top_pick': '',
            'top_pick_reason': '',
            'stocks': [],
            'comparison_insight': '',
            'portfolio_note': '',
            'api_success': False,
            'fallback_used': True,
            'error_message': msg,
        }
