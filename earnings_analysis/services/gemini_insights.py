# earnings_analysis/services/gemini_insights.py
import google.generativeai as genai
import logging
from django.conf import settings
from typing import Dict, Any, Optional
import json
import re

logger = logging.getLogger(__name__)

class GeminiInsightsGenerator:
    """Google Gemini APIを使った感情分析見解生成サービス"""
    
    def __init__(self):
        # 環境変数からAPIキーを取得
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            logger.warning("GEMINI_API_KEYが設定されていません")
            self.model = None
            return
        
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            logger.info("Gemini APIが正常に初期化されました")
        except Exception as e:
            logger.error(f"Gemini API初期化エラー: {e}")
            self.model = None
    
    def generate_investment_insights(self, analysis_result: Dict[str, Any], document_info: Dict[str, str]) -> Dict[str, Any]:
        """投資家向け見解を生成"""
        if not self.model:
            logger.warning("Gemini APIが利用できません - フォールバック見解を使用")
            return self._generate_fallback_insights(analysis_result, document_info)
        
        try:
            prompt = self._build_investment_prompt(analysis_result, document_info)
            response = self.model.generate_content(prompt)
            
            if hasattr(response, "text") and response.text:
                return self._parse_gemini_response(response.text, analysis_result)
            else:
                logger.warning("Gemini APIから有効な応答を取得できませんでした")
                return self._generate_fallback_insights(analysis_result, document_info)
                
        except Exception as e:
            logger.error(f"Gemini API呼び出しエラー: {e}")
            return self._generate_fallback_insights(analysis_result, document_info)
        
    def _build_investment_prompt(self, analysis_result: Dict[str, Any], document_info: Dict[str, str]) -> str:
        """投資家向けプロンプトを構築"""
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
        """Gemini APIの応答を解析してポイントリストに変換"""
        try:
            points = []
            lines = response_text.strip().split('\n')

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
                    continue

                # フォーマットに合わないが十分長い行も一応拾う
                if len(line) > 20:
                    points.append({
                        'title': 'AI分析ポイント',
                        'description': line,
                        'source': 'gemini_generated'
                    })

            if len(points) < 3:
                fallback_points = self._generate_fallback_points(analysis_result)
                points.extend(fallback_points[len(points):])

            return {
                'investment_points': points[:5],
                'generated_by': 'gemini_api',
                'response_quality': 'high' if len(points) >= 3 else 'medium'
            }

        except Exception as e:
            logger.error(f"Gemini応答解析エラー: {e}")
            return self._generate_fallback_insights(analysis_result, {})

    
    def _generate_fallback_insights(self, analysis_result: Dict[str, Any], document_info: Dict[str, str]) -> Dict[str, Any]:
        """Gemini APIが利用できない場合のフォールバック見解"""
        overall_score = analysis_result.get('overall_score', 0)
        sentiment_label = analysis_result.get('sentiment_label', 'neutral')
        
        points = self._generate_fallback_points(analysis_result)
        
        return {
            'investment_points': points,
            'generated_by': 'fallback_logic',
            'response_quality': 'basic'
        }
    
    def _generate_fallback_points(self, analysis_result: Dict[str, Any]) -> list:
        """フォールバック用の固定ポイント生成"""
        overall_score = analysis_result.get('overall_score', 0)
        sentiment_label = analysis_result.get('sentiment_label', 'neutral')
        statistics = analysis_result.get('statistics', {})
        
        points = []
        
        if sentiment_label == 'positive':
            if overall_score > 0.6:
                points.extend([
                    {
                        'title': '強い成長意欲',
                        'description': '経営陣の積極的な姿勢が文章に強く表れており、将来の成長への期待が持てます',
                        'source': 'fallback_logic'
                    },
                    {
                        'title': '投資魅力度向上',
                        'description': 'ポジティブな表現が多用されており、投資家にとって魅力的な投資機会を示唆しています',
                        'source': 'fallback_logic'
                    }
                ])
            else:
                points.extend([
                    {
                        'title': '安定的な経営姿勢',
                        'description': '堅実で建設的な表現が使われており、持続可能な経営戦略を示しています',
                        'source': 'fallback_logic'
                    },
                    {
                        'title': '段階的改善期待',
                        'description': '着実な取り組みを重視する姿勢が読み取れ、中長期的な改善が期待できます',
                        'source': 'fallback_logic'
                    }
                ])
        elif sentiment_label == 'negative':
            if overall_score < -0.6:
                points.extend([
                    {
                        'title': '透明性の高い情報開示',
                        'description': '困難な状況についても率直に言及しており、誠実な経営姿勢が評価できます',
                        'source': 'fallback_logic'
                    },
                    {
                        'title': 'リスク管理への注力',
                        'description': '課題を正面から捉える姿勢が表れており、適切なリスク管理が期待されます',
                        'source': 'fallback_logic'
                    }
                ])
            else:
                points.extend([
                    {
                        'title': '慎重な経営判断',
                        'description': 'リスクを適切に評価し、慎重なアプローチを採用している姿勢が読み取れます',
                        'source': 'fallback_logic'
                    },
                    {
                        'title': '改善への取り組み',
                        'description': '課題に対する具体的な対応策への言及があり、改善に向けた努力が期待できます',
                        'source': 'fallback_logic'
                    }
                ])
        else:
            points.extend([
                {
                    'title': 'バランスの取れた報告',
                    'description': '客観的で事実ベースの記述が中心となっており、冷静な経営判断が期待できます',
                    'source': 'fallback_logic'
                },
                {
                    'title': '安定した事業基盤',
                    'description': '感情的な表現を避けた報告は、安定した事業基盤を示唆している可能性があります',
                    'source': 'fallback_logic'
                }
            ])
        
        # 統計情報に基づく追加ポイント
        total_words = statistics.get('total_words_analyzed', 0)
        if total_words > 50:
            points.append({
                'title': '充実した情報量',
                'description': f'{total_words}語の豊富な情報に基づく分析結果で、信頼性の高い評価となっています',
                'source': 'fallback_logic'
            })
        
        return points[:5]  # 最大5個