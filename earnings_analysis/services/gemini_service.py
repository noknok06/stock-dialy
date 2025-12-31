# earnings_analysis/services/gemini_service.py

import google.generativeai as genai
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any, Optional
import json
import re
import logging

logger = logging.getLogger('earnings_analysis.tdnet')


class GeminiReportGenerator:
    """
    GEMINI APIを使用したレポート生成
    スマホ画面に最適化された簡潔なレポートを生成
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'GEMINI_API_KEY', None)
        self.api_available = self.api_key is not None
        self.model = None
        self.initialization_error = None
        
        tdnet_settings = getattr(settings, 'TDNET_REPORT_SETTINGS', {})
        self.model_name = tdnet_settings.get('GEMINI_MODEL', 'gemini-2.5-flash-lite')
        self.max_tokens = tdnet_settings.get('MAX_TOKENS', 4000)
        self.temperature = tdnet_settings.get('TEMPERATURE', 0.7)
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEYが設定されていません")
            self.initialization_error = "API_KEY_MISSING"
            return
        
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"GEMINI API初期化完了: {self.model_name}")
        except Exception as e:
            logger.error(f"GEMINI API初期化エラー: {e}")
            self.model = None
            self.api_available = False
            self.initialization_error = str(e)
    
    def generate_report(self, disclosure_dict: Dict[str, Any], report_type: str) -> Dict[str, Any]:
        """レポート生成（スマホ最適化版）"""
        start_time = timezone.now()
        
        if not self.model:
            logger.warning("GEMINI APIが利用できません - フォールバックレポートを使用")
            fallback_result = self._generate_fallback_report(disclosure_dict, report_type)
            fallback_result.update({
                'api_available': self.api_available,
                'api_success': False,
                'fallback_used': True,
                'error': self.initialization_error or 'API not initialized',
                'generation_timestamp': start_time.isoformat(),
                'model_used': None
            })
            return fallback_result
        
        try:
            prompt = self._create_prompt(disclosure_dict, report_type)
            logger.info(f"レポート生成開始: {report_type}, model={self.model_name}")
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
            )
            
            if not hasattr(response, "text") or not response.text:
                raise Exception("Empty response from GEMINI API")
            
            result = self._parse_response(response.text)
            
            if result['success']:
                token_count = len(prompt) + len(response.text)
                logger.info(f"レポート生成成功: {report_type}")
                
                return {
                    'success': True,
                    'data': result['data'],
                    'prompt': prompt,
                    'token_count': token_count,
                    'api_available': True,
                    'api_success': True,
                    'fallback_used': False,
                    'model_used': self.model_name,
                    'generation_timestamp': start_time.isoformat(),
                    'error': None
                }
            else:
                raise Exception(f"Response parsing failed: {result['error']}")
            
        except Exception as e:
            logger.error(f"GEMINI API呼び出しエラー: {e}")
        
        fallback_result = self._generate_fallback_report(disclosure_dict, report_type)
        fallback_result.update({
            'api_available': self.api_available,
            'api_success': False,
            'fallback_used': True,
            'error': str(e) if 'e' in dir() else 'Unknown error',
            'generation_timestamp': start_time.isoformat(),
            'model_used': self.model_name
        })
        return fallback_result
    
    def _create_prompt(self, disclosure: Dict[str, Any], report_type: str) -> str:
        """スマホ最適化プロンプト生成"""
        company_name = disclosure.get('company_name', '不明')
        company_code = disclosure.get('company_code', '')
        disclosure_date = disclosure.get('disclosure_date', '')
        title = disclosure.get('title', '')
        content = disclosure.get('content', disclosure.get('summary', ''))
        
        return f"""# 役割
あなたは機関投資家向けの証券アナリストです。
TDNET開示情報を分析し、**スマホ画面で一目で把握できる**簡潔なレポートを作成してください。

# 入力データ
- 企業名: {company_name}
- 証券コード: {company_code}
- 開示日時: {disclosure_date}
- タイトル: {title}
- 開示種別: {report_type}

## 開示内容
{content[:20000]}

# 出力形式（JSON）
以下のJSON形式で出力してください。**簡潔さが最重要**です。

{{
  "overall_score": 0-100の整数（投資魅力度。50が中立、80以上が非常に良い、20以下が非常に悪い）,
  "signal": "strong_positive" | "positive" | "neutral" | "negative" | "strong_negative",
  "one_line_summary": "15文字以内の一言評価（例：「増収増益で好調」「減益だが想定内」）",
  "summary": "3文以内の要約。数値を含めて具体的に。",
  "key_points": [
    "📈 ポイント1（20文字以内、絵文字で始める）",
    "💰 ポイント2（20文字以内）",
    "⚠️ ポイント3（20文字以内、リスクや注意点）"
  ],
  "score_details": {{
    "growth": {{"score": 0-100, "label": "成長性", "comment": "10文字以内"}},
    "profitability": {{"score": 0-100, "label": "収益性", "comment": "10文字以内"}},
    "stability": {{"score": 0-100, "label": "安定性", "comment": "10文字以内"}},
    "outlook": {{"score": 0-100, "label": "見通し", "comment": "10文字以内"}}
  }},
  "sections": [
    {{
      "section_type": "overview",
      "title": "ポイント",
      "content": "最も重要な情報を3行以内で。数値があれば含める。"
    }},
    {{
      "section_type": "analysis", 
      "title": "注目点",
      "content": "投資家が注目すべき点を2-3行で。"
    }},
    {{
      "section_type": "risk",
      "title": "リスク・注意",
      "content": "リスクや懸念点を2行以内で。なければ「特になし」"
    }}
  ]
}}

# 採点基準
- **overall_score**: 
  - 80-100: 非常にポジティブ（大幅増益、上方修正、増配など）
  - 60-79: ややポジティブ（小幅増益、計画通り進捗）
  - 40-59: 中立（横ばい、特筆事項なし）
  - 20-39: ややネガティブ（小幅減益、下方修正）
  - 0-19: 非常にネガティブ（大幅減益、無配など）

- **signal**:
  - strong_positive: 買い推奨レベル
  - positive: やや強気
  - neutral: 様子見
  - negative: やや弱気
  - strong_negative: 警戒レベル

# 重要な指示
1. **スマホ画面で読める長さ**を最優先。各フィールドの文字数制限を厳守。
2. 数値は必ず含める（売上〇億円、前年比+〇%など）
3. 専門用語は避け、一般投資家にわかる表現で
4. 開示内容に財務数値がない場合は、内容の重要度で採点
5. 絵文字を効果的に使用（key_pointsの先頭など）
6. **必ずJSON形式のみで出力**（余計な説明文は不要）
"""
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """GEMINIレスポンスを解析"""
        try:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response_text.strip()
                json_str = re.sub(r'^[^{]*', '', json_str)
                json_str = re.sub(r'[^}]*$', '', json_str)
            
            parsed_data = json.loads(json_str)
            
            if not self._validate_report_structure(parsed_data):
                return {'success': False, 'data': None, 'error': 'レポート構造が不正です'}
            
            return {'success': True, 'data': parsed_data, 'error': None}
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}")
            return {'success': False, 'data': None, 'error': f"JSON解析エラー: {str(e)}"}
        except Exception as e:
            logger.error(f"レスポンス解析エラー: {e}")
            return {'success': False, 'data': None, 'error': f"解析エラー: {str(e)}"}
    
    def _validate_report_structure(self, data: Dict) -> bool:
        """レポート構造の妥当性チェック"""
        try:
            required_fields = ['overall_score', 'signal', 'summary', 'key_points']
            for field in required_fields:
                if field not in data:
                    logger.error(f"{field}フィールドがありません")
                    return False
            
            if not isinstance(data.get('key_points'), list) or len(data['key_points']) < 2:
                logger.error("key_pointsが不正です")
                return False
            
            score = data.get('overall_score', 0)
            if not isinstance(score, (int, float)) or score < 0 or score > 100:
                data['overall_score'] = 50
            
            valid_signals = ['strong_positive', 'positive', 'neutral', 'negative', 'strong_negative']
            if data.get('signal') not in valid_signals:
                data['signal'] = 'neutral'
            
            return True
        except Exception as e:
            logger.error(f"構造検証エラー: {e}")
            return False
    
    def _generate_fallback_report(self, disclosure_dict: Dict[str, Any], report_type: str) -> Dict[str, Any]:
        """フォールバックレポート生成"""
        company_name = disclosure_dict.get('company_name', '不明')
        title = disclosure_dict.get('title', '')
        summary_text = disclosure_dict.get('summary', '')[:200]
        
        return {
            'success': True,
            'data': {
                'overall_score': 50,
                'signal': 'neutral',
                'one_line_summary': '詳細は原文参照',
                'summary': f'{company_name}より「{title}」が開示されました。詳細は原文PDFをご確認ください。',
                'key_points': [
                    '📄 開示情報を確認してください',
                    '🔍 詳細は原文PDFを参照',
                    '⏳ AI分析は現在利用できません'
                ],
                'score_details': {
                    'growth': {'score': 50, 'label': '成長性', 'comment': '—'},
                    'profitability': {'score': 50, 'label': '収益性', 'comment': '—'},
                    'stability': {'score': 50, 'label': '安定性', 'comment': '—'},
                    'outlook': {'score': 50, 'label': '見通し', 'comment': '—'}
                },
                'sections': [
                    {
                        'section_type': 'overview',
                        'title': '概要',
                        'content': summary_text or '開示情報の詳細は原文をご確認ください。'
                    }
                ]
            },
            'prompt': 'N/A (fallback)',
            'token_count': 0,
            'response_quality': 'fallback'
        }