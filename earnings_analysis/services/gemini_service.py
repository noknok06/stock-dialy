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
    GEMINI APIを使用したレポート生成（エラーハンドリング・フォールバック強化版）
    
    TDNETの開示情報からわかりやすいレポートを自動生成
    """
    
    def __init__(self):
        # 環境変数からAPIキーを取得
        self.api_key = getattr(settings, 'GEMINI_API_KEY', None)
        self.api_available = self.api_key is not None
        self.model = None
        self.initialization_error = None
        
        tdnet_settings = getattr(settings, 'TDNET_REPORT_SETTINGS', {})
        
        # gemini-2.5-flash-liteを使用（高速・低コスト）
        self.model_name = tdnet_settings.get('GEMINI_MODEL', 'gemini-2.5-flash-lite')
        self.max_tokens = tdnet_settings.get('MAX_TOKENS', 8000)
        self.temperature = tdnet_settings.get('TEMPERATURE', 0.7)
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEYが設定されていません")
            self.initialization_error = "API_KEY_MISSING"
            return
        
        # GEMINI API設定
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"GEMINI API初期化完了: {self.model_name}")
        except Exception as e:
            logger.error(f"GEMINI API初期化エラー: {e}")
            self.model = None
            self.api_available = False
            self.initialization_error = str(e)
    
    def generate_report(self, 
                       disclosure_dict: Dict[str, Any],
                       report_type: str) -> Dict[str, Any]:
        """
        レポート生成（エラーハンドリング・メタデータ強化版）
        
        Args:
            disclosure_dict: 開示情報辞書
                - company_name: 企業名
                - company_code: 証券コード
                - disclosure_date: 開示日時
                - title: タイトル
                - summary: 概要
                - content: 詳細内容（PDFテキスト等）
            report_type: レポート種別
        
        Returns:
            {
                'success': True/False,
                'data': {
                    'summary': '要約',
                    'key_points': ['ポイント1', ...],
                    'sections': [...]
                },
                'prompt': '使用したプロンプト',
                'token_count': トークン数,
                'api_available': APIが利用可能か,
                'api_success': API呼び出しが成功したか,
                'fallback_used': フォールバックを使用したか,
                'model_used': 使用したモデル,
                'generation_timestamp': 生成日時,
                'error': エラーメッセージ（失敗時）
            }
        """
        start_time = timezone.now()
        api_call_success = False
        api_error_message = None
        
        # APIが利用できない場合
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
            # プロンプト生成
            prompt = self._create_prompt(disclosure_dict, report_type)
            logger.info(f"レポート生成開始: {report_type}, model={self.model_name}")
            
            # GEMINI API呼び出し
            logger.debug("GEMINI APIにリクエスト送信中...")
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
            )
            
            # レスポンスチェック
            if not hasattr(response, "text") or not response.text:
                logger.warning("GEMINI APIから有効な応答を取得できませんでした")
                api_error_message = "EMPTY_RESPONSE"
                raise Exception("Empty response from GEMINI API")
            
            logger.info("GEMINI APIから有効な応答を受信")
            
            # レスポンス解析
            result = self._parse_response(response.text)
            api_call_success = result['success']
            
            if result['success']:
                token_count = len(prompt) + len(response.text)  # 概算
                logger.info(f"レポート生成成功: {report_type}, sections={len(result['data']['sections'])}")
                
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
                    'response_length': len(response.text),
                    'error': None
                }
            else:
                logger.error(f"レスポンス解析失敗: {result['error']}")
                api_error_message = result['error']
                raise Exception(f"Response parsing failed: {result['error']}")
            
        except Exception as e:
            logger.error(f"GEMINI API呼び出しエラー: {e}")
            api_error_message = str(e)
        
        # API失敗時のフォールバック
        logger.info("GEMINI API失敗のため、フォールバックレポートを生成")
        fallback_result = self._generate_fallback_report(disclosure_dict, report_type)
        fallback_result.update({
            'api_available': self.api_available,
            'api_success': api_call_success,
            'fallback_used': True,
            'error': api_error_message,
            'generation_timestamp': start_time.isoformat(),
            'model_used': self.model_name
        })
        
        return fallback_result
    
    def _create_prompt(self, disclosure: Dict[str, Any], report_type: str) -> str:
        """プロンプト生成"""
        
        # 基本情報の抽出
        company_name = disclosure.get('company_name', '不明')
        company_code = disclosure.get('company_code', '')
        disclosure_date = disclosure.get('disclosure_date', '')
        title = disclosure.get('title', '')
        summary = disclosure.get('summary', '')
        content = disclosure.get('content', summary)
        
        # レポート種別ごとのプロンプト
        if report_type == 'earnings':
            return self._create_earnings_prompt(
                company_name, company_code, disclosure_date, title, content
            )
        elif report_type == 'forecast':
            return self._create_forecast_prompt(
                company_name, company_code, disclosure_date, title, content
            )
        elif report_type == 'dividend':
            return self._create_dividend_prompt(
                company_name, company_code, disclosure_date, title, content
            )
        else:
            return self._create_general_prompt(
                company_name, company_code, disclosure_date, title, content
            )
    
    def _create_earnings_prompt(self, company_name, company_code, disclosure_date, title, content) -> str:
        """決算短信用プロンプト（改善版 - 詳細分析）"""
        return f"""# 役割
あなたは経験豊富な金融アナリスト・証券アナリストです。
機関投資家レベルの深い分析と洞察を含む、投資判断に役立つ詳細なレポートを作成してください。

# 入力データ
## 企業情報
- 企業名: {company_name}
- 証券コード: {company_code}
- 開示日時: {disclosure_date}
- タイトル: {title}

## 開示内容（決算短信全文）
{content[:15000]}

# 出力形式（JSON）
以下のJSON形式で**必ず詳細な分析**を含めて出力してください：

{{
  "summary": "決算の要点を5-8文で詳細に記載。売上・利益の具体的な数値、前年比率、主要な増減要因を含める。",
  "key_points": [
    "業績サマリー: 売上高XXX億円（前年比+X.X%）、営業利益XXX億円（前年比+X.X%）など具体的数値",
    "利益率分析: 営業利益率X.X%（前年X.X%）、ROE X.X%など収益性指標の変化",
    "セグメント別動向: 主力事業の詳細な業績と成長ドライバー",
    "通期予想: 売上XXX億円、営業利益XXX億円の見通しと達成可能性",
    "配当方針: 配当金XX円（前年XX円）、配当性向XX%、株主還元の姿勢",
    "財務健全性: 自己資本比率XX%、現金及び現金同等物XXX億円など",
    "事業トピックス: 新製品、M&A、提携など重要な事業展開",
    "リスク・課題: 原材料価格、為替、競争環境などの懸念材料"
  ],
  "sections": [
    {{
      "section_type": "overview",
      "title": "決算概要",
      "content": "今回の決算の全体像を3-4段落で詳述。売上高・各段階利益の実績値と前年比を記載し、業績が好調/不調だった理由を具体的に説明。市場予想との比較があれば言及。",
      "data": {{}}
    }},
    {{
      "section_type": "financial",
      "title": "財務ハイライト - 詳細分析",
      "content": "【連結業績】\\n売上高: XXX億円（前年比+X.X%、前年XXX億円）\\n営業利益: XXX億円（前年比+X.X%、前年XXX億円）\\n経常利益: XXX億円（前年比+X.X%）\\n当期純利益: XXX億円（前年比+X.X%）\\n\\n【収益性指標】\\n営業利益率: X.X%（前年X.X%）\\nROE: X.X%（前年X.X%）\\nROA: X.X%\\n\\n【1株当たり指標】\\nEPS: XX.XX円（前年XX.XX円）\\nBPS: XXX.XX円\\n\\n各指標の変化要因を具体的に分析。売上が伸びた理由（価格転嫁、数量増、新製品貢献など）、利益率が改善/悪化した理由（コスト削減効果、原材料高騰影響など）を詳述。",
      "data": {{
        "revenue": "売上高の数値",
        "operating_profit": "営業利益の数値",
        "net_income": "当期純利益の数値",
        "operating_margin": "営業利益率",
        "roe": "ROE",
        "eps": "EPS"
      }}
    }},
    {{
      "section_type": "analysis",
      "title": "セグメント別・事業別分析",
      "content": "主要な事業セグメント（または製品カテゴリー）ごとに業績を分析。\\n\\n【セグメントA】\\n売上: XXX億円（前年比+X.X%）\\n営業利益: XXX億円（前年比+X.X%）\\n主な要因: 〇〇製品の販売好調、△△市場での拡大など\\n\\n【セグメントB】\\n売上: XXX億円（前年比-X.X%）\\n営業利益: XXX億円（前年比-X.X%）\\n主な要因: ××の影響で減収、コスト増など\\n\\nどのセグメントが全社業績を牽引しているか、または足を引っ張っているかを明確に。",
      "data": {{}}
    }},
    {{
      "section_type": "forecast",
      "title": "通期業績予想と進捗率",
      "content": "【通期予想】\\n売上高: XXX億円（前年比+X.X%）\\n営業利益: XXX億円（前年比+X.X%）\\n当期純利益: XXX億円（前年比+X.X%）\\n\\n【進捗率】\\n今回の実績は通期予想の約XX%を達成。\\n過去の季節性を考慮すると、この進捗率は【順調/やや遅れ/前倒し】と評価。\\n\\n【前回予想からの変更】\\n前回発表時から【上方修正/下方修正/据え置き】。\\n変更理由: 〇〇の影響で売上/利益が想定を上回る/下回る見込み。\\n\\n【達成可能性】\\n残りの期間で必要な売上・利益を考慮すると、通期予想の達成は【確度が高い/やや不透明/困難】と予想。理由を具体的に記載。",
      "data": {{}}
    }},
    {{
      "section_type": "opportunity",
      "title": "ポジティブ要因・成長機会",
      "content": "【好材料】\\n1. 〇〇事業の急成長: 具体的な成長率と要因\\n2. 新製品の市場投入: 期待される貢献度\\n3. コスト削減効果: 具体的な施策と効果額\\n4. 市場環境の追い風: 業界全体の成長など\\n5. 戦略的投資: M&A、設備投資などの効果\\n\\n各要因が今後の業績にどの程度プラスに寄与するかを数値や期間とともに説明。",
      "data": {{}}
    }},
    {{
      "section_type": "risk",
      "title": "リスク要因・懸念材料",
      "content": "【リスク・課題】\\n1. 原材料価格の高騰: 影響額と対策\\n2. 為替変動リスク: 感応度分析（1円の変動で利益への影響XX億円など）\\n3. 競争環境の激化: 価格競争や市場シェア変動\\n4. 地政学リスク: 特定地域への依存度と影響\\n5. 法規制・制度変更: コンプライアンスコストなど\\n\\n各リスクの顕在化可能性と、顕在化した場合の業績へのインパクトを評価。会社の対応策があれば言及。",
      "data": {{}}
    }},
    {{
      "section_type": "conclusion",
      "title": "投資家への示唆・総合評価",
      "content": "【株価への影響予想】\\n今回の決算は市場予想と比較して【サプライズ/インライン/ディスアポイント】。\\n短期的には〇〇の好材料で株価は【上昇/横ばい/下落】圧力。\\n\\n【中長期的評価】\\nPER: 現在XX倍（業界平均XX倍と比較して【割安/割高/妥当】）\\nPBR: XX倍\\n配当利回り: X.X%\\n\\n【投資判断の観点】\\n1. 成長性: 売上・利益成長率の持続可能性\\n2. 収益性: 利益率の改善余地\\n3. 株主還元: 配当性向XX%、自社株買いの可能性\\n4. バリュエーション: 同業他社との比較\\n\\n【総合判断】\\n現在の株価水準や業績トレンドを踏まえた投資妙味を評価。【買い推奨/中立/慎重姿勢】とその理由を明確に。",
      "data": {{}}
    }}
  ]
}}

# 重要な指示
1. **具体的な数値を必ず記載**: 「増加した」ではなく「前年比+15.3%増の120億円」のように記載
2. **前年比・前期比を明示**: すべての主要指標で比較データを提供
3. **要因分析を深掘り**: 「〇〇の影響で」だけでなく、その背景や数値的インパクトまで
4. **セクション間の重複を避ける**: 各セクションは異なる観点から分析
5. **投資判断に直結する情報**: 株価、PER、配当などの投資指標を含める
6. **客観性と公平性**: ポジティブ・ネガティブ両面をバランス良く
7. **必ずJSON形式のみで出力**: 余計な説明文やマークダウンは含めない

この指示に従い、機関投資家レベルの深い分析を提供してください。
"""
    
    def _create_forecast_prompt(self, company_name, company_code, disclosure_date, title, content) -> str:
        """業績予想修正用プロンプト"""
        return f"""# 役割
あなたは金融アナリストです。
業績予想修正の影響を投資家にわかりやすく伝えるレポートを作成してください。

# 入力データ
## 企業情報
- 企業名: {company_name}
- 証券コード: {company_code}
- 開示日時: {disclosure_date}
- タイトル: {title}

## 予想修正内容
{content[:5000]}

# 出力形式（JSON）
{{
  "summary": "予想修正の要約を3-5文で記載",
  "key_points": [
    "修正の主なポイント1: 上方修正or下方修正",
    "修正の主なポイント2: 修正幅（金額・比率）",
    "修正の主なポイント3: 修正の理由",
    "修正の主なポイント4: 今後の見通し",
    "修正の主なポイント5: 株価への影響予想"
  ],
  "sections": [
    {{
      "section_type": "overview",
      "title": "予想修正の概要",
      "content": "どの指標がどのくらい修正されたかを明確に記載。",
      "data": {{
        "previous_forecast": "前回予想",
        "new_forecast": "今回予想",
        "change_amount": "修正額",
        "change_rate": "修正率(%)"
      }}
    }},
    {{
      "section_type": "analysis",
      "title": "修正の主な要因",
      "content": "なぜ修正が必要になったのか、要因を分析。"
    }},
    {{
      "section_type": "opportunity",
      "title": "投資機会の評価",
      "content": "上方修正の場合は投資機会、下方修正の場合はリスクを評価。"
    }},
    {{
      "section_type": "conclusion",
      "title": "今後の注目点",
      "content": "今後注目すべきポイントや次回決算の見通し。"
    }}
  ]
}}

# 要件
1. 上方/下方修正の理由を明確に
2. 前回予想との比較を数値で示す
3. 業界トレンドとの関連性を分析
4. 投資判断への影響を考察
5. **必ずJSON形式で出力**
"""
    
    def _create_dividend_prompt(self, company_name, company_code, disclosure_date, title, content) -> str:
        """配当関連用プロンプト"""
        return f"""# 役割
配当政策の変更を投資家に分かりやすく説明するレポートを作成してください。

# 入力データ
## 企業情報
- 企業名: {company_name}
- 証券コード: {company_code}
- 開示日時: {disclosure_date}

## 内容
{content[:5000]}

# 出力形式（JSON）
{{
  "summary": "配当変更の要約",
  "key_points": ["ポイント1", "ポイント2", "ポイント3", "ポイント4", "ポイント5"],
  "sections": [
    {{
      "section_type": "overview",
      "title": "配当変更の概要",
      "content": "...",
      "data": {{
        "previous_dividend": "前回配当",
        "new_dividend": "今回配当",
        "yield": "配当利回り(%)"
      }}
    }},
    {{
      "section_type": "analysis",
      "title": "変更の背景",
      "content": "配当変更の理由を分析"
    }},
    {{
      "section_type": "conclusion",
      "title": "株主への影響",
      "content": "株主にとってのメリット・デメリット"
    }}
  ]
}}

# 要件
1. 配当金額・利回りを明確に
2. 変更理由を説明
3. 株主還元方針を考察
4. **必ずJSON形式で出力**
"""
    
    def _create_general_prompt(self, company_name, company_code, disclosure_date, title, content) -> str:
        """一般的な開示用プロンプト"""
        return f"""# 役割
適時開示情報を投資家向けにわかりやすく解説してください。

# 入力データ
- 企業名: {company_name}
- 証券コード: {company_code}
- タイトル: {title}

## 内容
{content[:5000]}

# 出力形式（JSON）
{{
  "summary": "開示内容の要約（3-5文）",
  "key_points": ["ポイント1", "ポイント2", "ポイント3", "ポイント4", "ポイント5"],
  "sections": [
    {{
      "section_type": "overview",
      "title": "概要",
      "content": "開示内容の概要"
    }},
    {{
      "section_type": "analysis",
      "title": "分析",
      "content": "開示内容の分析"
    }},
    {{
      "section_type": "conclusion",
      "title": "まとめ",
      "content": "投資家への影響"
    }}
  ]
}}

# 要件
- わかりやすく説明
- 投資判断に役立つ情報を強調
- **必ずJSON形式で出力**
"""
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        GEMINIレスポンスを解析
        
        Args:
            response_text: GEMINIからのレスポンステキスト
        
        Returns:
            {
                'success': True/False,
                'data': 解析済みデータ or None,
                'error': エラーメッセージ or None
            }
        """
        try:
            # JSONブロックを抽出
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # JSONブロックがない場合、全体をJSONとして試行
                json_str = response_text.strip()
                # 先頭・末尾の不要な文字を削除
                json_str = re.sub(r'^[^{]*', '', json_str)
                json_str = re.sub(r'[^}]*$', '', json_str)
            
            # JSONパース
            parsed_data = json.loads(json_str)
            
            # 必須フィールドの検証
            if not self._validate_report_structure(parsed_data):
                return {
                    'success': False,
                    'data': None,
                    'error': 'レポート構造が不正です'
                }
            
            return {
                'success': True,
                'data': parsed_data,
                'error': None
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}")
            logger.error(f"レスポンステキスト: {response_text[:500]}")
            return {
                'success': False,
                'data': None,
                'error': f"JSON解析エラー: {str(e)}"
            }
        except Exception as e:
            logger.error(f"レスポンス解析エラー: {e}")
            return {
                'success': False,
                'data': None,
                'error': f"解析エラー: {str(e)}"
            }
    
    def _validate_report_structure(self, data: Dict) -> bool:
        """レポート構造の妥当性チェック"""
        try:
            # 必須フィールドチェック
            if 'summary' not in data:
                logger.error("summaryフィールドがありません")
                return False
            
            if 'key_points' not in data or not isinstance(data['key_points'], list):
                logger.error("key_pointsフィールドが不正です")
                return False
            
            if len(data['key_points']) < 3:
                logger.error("key_pointsが少なすぎます")
                return False
            
            if 'sections' not in data or not isinstance(data['sections'], list):
                logger.error("sectionsフィールドが不正です")
                return False
            
            if len(data['sections']) < 2:
                logger.error("sectionsが少なすぎます")
                return False
            
            # セクションの構造チェック
            for section in data['sections']:
                required_keys = ['section_type', 'title', 'content']
                if not all(k in section for k in required_keys):
                    logger.error(f"セクションに必須フィールドがありません: {section}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"構造検証エラー: {e}")
            return False
    
    def _generate_fallback_report(self, 
                                  disclosure_dict: Dict[str, Any],
                                  report_type: str) -> Dict[str, Any]:
        """
        フォールバックレポート生成（GEMINI API失敗時）
        
        Args:
            disclosure_dict: 開示情報辞書
            report_type: レポート種別
        
        Returns:
            基本的なレポート構造
        """
        company_name = disclosure_dict.get('company_name', '不明')
        company_code = disclosure_dict.get('company_code', '')
        title = disclosure_dict.get('title', '')
        summary_text = disclosure_dict.get('summary', '')
        content = disclosure_dict.get('content', '')
        
        logger.info(f"フォールバックレポート生成: {company_name}, type={report_type}")
        
        # 基本的な要約
        if len(summary_text) > 200:
            summary = summary_text[:200] + '...'
        else:
            summary = summary_text or f'{company_name}の{title}に関する開示情報です。'
        
        # 重要ポイント生成
        key_points = self._generate_fallback_key_points(
            disclosure_dict, report_type
        )
        
        # セクション生成
        sections = self._generate_fallback_sections(
            disclosure_dict, report_type
        )
        
        return {
            'success': True,
            'data': {
                'summary': summary,
                'key_points': key_points,
                'sections': sections
            },
            'prompt': 'N/A (fallback)',
            'token_count': 0,
            'response_quality': 'fallback'
        }
    
    def _generate_fallback_key_points(self,
                                      disclosure_dict: Dict[str, Any],
                                      report_type: str) -> list:
        """フォールバック用の重要ポイント生成"""
        company_name = disclosure_dict.get('company_name', '不明')
        title = disclosure_dict.get('title', '')
        
        points = []
        
        if report_type == 'earnings':
            points = [
                f'{company_name}の決算情報が開示されました',
                '詳細な財務データの確認が推奨されます',
                '前期比較や業界トレンドとの照合が重要です',
                '今後の業績予想にも注目が必要です',
                '適時開示された情報の精査をお勧めします'
            ]
        elif report_type == 'forecast':
            points = [
                f'{company_name}の業績予想が修正されました',
                '修正の背景と要因の確認が重要です',
                '通期予想への影響を精査する必要があります',
                '市場予想との比較検討が推奨されます',
                '今後の動向に注意が必要です'
            ]
        elif report_type == 'dividend':
            points = [
                f'{company_name}の配当方針が発表されました',
                '配当利回りの確認が推奨されます',
                '株主還元方針の変更点に注目が必要です',
                '業績との整合性を確認することが重要です',
                '今後の配当政策の動向に注意が必要です'
            ]
        else:
            points = [
                f'{company_name}の重要情報が開示されました',
                '開示内容の詳細確認が推奨されます',
                '投資判断への影響を慎重に検討する必要があります',
                '関連する他の開示情報も併せて確認が重要です',
                '今後の動向に注意を払う必要があります'
            ]
        
        return points[:5]
    
    def _generate_fallback_sections(self,
                                    disclosure_dict: Dict[str, Any],
                                    report_type: str) -> list:
        """フォールバック用のセクション生成"""
        company_name = disclosure_dict.get('company_name', '不明')
        title = disclosure_dict.get('title', '')
        summary_text = disclosure_dict.get('summary', '')
        content = disclosure_dict.get('content', '')
        
        # コンテンツの最初の部分を抽出
        content_preview = content[:500] if content else summary_text[:500]
        
        sections = [
            {
                'section_type': 'overview',
                'title': '開示情報の概要',
                'content': f'{company_name}より「{title}」が適時開示されました。本レポートは開示情報の要点をまとめたものです。詳細は原文をご確認ください。',
                'data': {}
            },
            {
                'section_type': 'analysis',
                'title': '主な内容',
                'content': content_preview if content_preview else '開示情報の詳細は原文PDFをご参照ください。',
                'data': {}
            },
            {
                'section_type': 'conclusion',
                'title': '投資家への情報',
                'content': '本開示情報は投資判断の重要な材料となります。詳細な分析は原文および関連資料をご確認いただくことを推奨します。',
                'data': {}
            }
        ]
        
        if report_type == 'earnings':
            sections.insert(1, {
                'section_type': 'financial',
                'title': '財務情報',
                'content': '決算に関する詳細な財務データは原文PDFをご確認ください。売上高、営業利益、経常利益、当期純利益などの主要指標を確認することが重要です。',
                'data': {}
            })
        
        return sections