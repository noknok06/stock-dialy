# earnings_analysis/services/gemini_insights.py（メタデータ強化版）
import google.generativeai as genai
import logging
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any, Optional
import json
import re

logger = logging.getLogger(__name__)

class GeminiInsightsGenerator:
    """Google Gemini APIを使った感情分析見解生成サービス（メタデータ強化版）"""
    
    def __init__(self):
        # 環境変数からAPIキーを取得
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        self.api_available = api_key is not None
        self.model = None
        self.initialization_error = None
        
        if not api_key:
            logger.warning("GEMINI_API_KEYが設定されていません")
            self.initialization_error = "API_KEY_MISSING"
            return
        
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            logger.info("Gemini APIが正常に初期化されました")
        except Exception as e:
            logger.error(f"Gemini API初期化エラー: {e}")
            self.model = None
            self.api_available = False
            self.initialization_error = str(e)
    
    def generate_investment_insights(self, analysis_result: Dict[str, Any], document_info: Dict[str, str]) -> Dict[str, Any]:
        """投資家向け見解を生成（メタデータ強化版）"""
        start_time = timezone.now()
        api_call_success = False
        api_error_message = None
        points_generated = 0
        
        if not self.model:
            logger.warning("Gemini APIが利用できません - フォールバック見解を使用")
            fallback_result = self._generate_fallback_insights(analysis_result, document_info)
            fallback_result['api_available'] = self.api_available
            fallback_result['api_success'] = False
            fallback_result['fallback_used'] = True
            fallback_result['error_message'] = self.initialization_error
            fallback_result['generation_timestamp'] = start_time.isoformat()
            fallback_result['points_count'] = len(fallback_result.get('investment_points', []))
            return fallback_result
        
        try:
            logger.info("Gemini API投資家向け見解生成開始")
            prompt = self._build_investment_prompt(analysis_result, document_info)
            
            logger.debug("Gemini APIにリクエスト送信中...")
            response = self.model.generate_content(prompt)
            
            if hasattr(response, "text") and response.text:
                logger.info("Gemini APIから有効な応答を受信")
                parsed_result = self._parse_gemini_response(response.text, analysis_result)
                api_call_success = True
                points_generated = len(parsed_result.get('investment_points', []))
                
                # 成功時のメタデータを追加
                parsed_result.update({
                    'api_available': True,
                    'api_success': True,
                    'fallback_used': False,
                    'generation_timestamp': start_time.isoformat(),
                    'points_count': points_generated,
                    'model_used': 'gemini-2.5-flash',
                    'response_length': len(response.text)
                })
                
                logger.info(f"Gemini API見解生成完了: {points_generated}個のポイント")
                return parsed_result
            else:
                logger.warning("Gemini APIから有効な応答を取得できませんでした")
                api_error_message = "EMPTY_RESPONSE"
                
        except Exception as e:
            logger.error(f"Gemini API呼び出しエラー: {e}")
            api_error_message = str(e)
        
        # API呼び出し失敗時のフォールバック処理
        logger.info("Gemini API失敗のため、フォールバック見解を生成")
        fallback_result = self._generate_fallback_insights(analysis_result, document_info)
        fallback_result.update({
            'api_available': self.api_available,
            'api_success': api_call_success,
            'fallback_used': True,
            'error_message': api_error_message,
            'generation_timestamp': start_time.isoformat(),
            'points_count': len(fallback_result.get('investment_points', []))
        })
        
        return fallback_result
        
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
        """Gemini APIの応答を解析してポイントリストに変換（メタデータ強化版）"""
        try:
            points = []
            lines = response_text.strip().split('\n')
            successful_parses = 0

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
                        successful_parses += 1
                    continue

                # フォーマットに合わないが十分長い行も一応拾う
                if len(line) > 20:
                    points.append({
                        'title': 'AI分析ポイント',
                        'description': line,
                        'source': 'gemini_generated'
                    })
                    successful_parses += 1

            # 生成されたポイントが少ない場合、フォールバックポイントで補完
            if len(points) < 3:
                logger.warning(f"Gemini APIで生成されたポイントが少ない: {len(points)}個")
                fallback_points = self._generate_fallback_points(analysis_result)
                needed_points = 3 - len(points)
                points.extend(fallback_points[:needed_points])

            quality = 'high' if successful_parses >= 3 else 'medium' if successful_parses >= 2 else 'low'

            return {
                'investment_points': points[:5],
                'generated_by': 'gemini_api',
                'response_quality': quality,
                'original_response_length': len(response_text),
                'successful_parses': successful_parses,
                'total_points_generated': len(points)
            }

        except Exception as e:
            logger.error(f"Gemini応答解析エラー: {e}")
            # 解析エラー時もフォールバックを返す
            fallback_points = self._generate_fallback_points(analysis_result)
            return {
                'investment_points': fallback_points,
                'generated_by': 'parsing_error',
                'response_quality': 'failed',
                'error_message': str(e)
            }

    def _generate_fallback_insights(self, analysis_result: Dict[str, Any], document_info: Dict[str, str]) -> Dict[str, Any]:
        """Gemini APIが利用できない場合のフォールバック見解（メタデータ強化版）"""
        overall_score = analysis_result.get('overall_score', 0)
        sentiment_label = analysis_result.get('sentiment_label', 'neutral')
        
        points = self._generate_fallback_points(analysis_result)
        
        return {
            'investment_points': points,
            'generated_by': 'fallback_logic',
            'response_quality': 'basic',
            'fallback_reason': 'api_unavailable'
        }
    
    def _generate_fallback_points(self, analysis_result: Dict[str, Any]) -> list:
        """フォールバック用の固定ポイント生成（強化版）"""
        overall_score = analysis_result.get('overall_score', 0)
        sentiment_label = analysis_result.get('sentiment_label', 'neutral')
        statistics = analysis_result.get('statistics', {})
        
        points = []
        
        if sentiment_label == 'positive':
            if overall_score > 0.6:
                points.extend([
                    {
                        'title': '強い成長意欲',
                        'description': f'感情分析スコア{overall_score:.2f}は経営陣の積極的な姿勢を示しており、将来の成長への期待が持てます',
                        'source': 'fallback_generated'
                    },
                    {
                        'title': '投資魅力度向上',
                        'description': 'ポジティブな表現が多用されており、投資家にとって魅力的な投資機会を示唆しています',
                        'source': 'fallback_generated'
                    },
                    {
                        'title': '市場評価の向上期待',
                        'description': '前向きなメッセージが一貫しており、市場での評価向上が期待される内容となっています',
                        'source': 'fallback_generated'
                    }
                ])
            else:
                points.extend([
                    {
                        'title': '安定的な経営姿勢',
                        'description': '堅実で建設的な表現が使われており、持続可能な経営戦略を示しています',
                        'source': 'fallback_generated'
                    },
                    {
                        'title': '段階的改善期待',
                        'description': '着実な取り組みを重視する姿勢が読み取れ、中長期的な改善が期待できます',
                        'source': 'fallback_generated'
                    }
                ])
        elif sentiment_label == 'negative':
            if overall_score < -0.6:
                points.extend([
                    {
                        'title': '透明性の高い情報開示',
                        'description': f'感情分析スコア{overall_score:.2f}は困難な状況への率直な言及を示し、誠実な経営姿勢が評価できます',
                        'source': 'fallback_generated'
                    },
                    {
                        'title': 'リスク管理への注力',
                        'description': '課題を正面から捉える姿勢が表れており、適切なリスク管理体制の構築が期待されます',
                        'source': 'fallback_generated'
                    },
                    {
                        'title': '構造改革の契機',
                        'description': '現在の困難は将来の構造改革と競争力向上への重要な転換点となる可能性があります',
                        'source': 'fallback_generated'
                    }
                ])
            else:
                points.extend([
                    {
                        'title': '慎重な経営判断',
                        'description': 'リスクを適切に評価し、慎重なアプローチを採用している姿勢が読み取れます',
                        'source': 'fallback_generated'
                    },
                    {
                        'title': '改善への取り組み',
                        'description': '課題に対する具体的な対応策への言及があり、改善に向けた努力が期待できます',
                        'source': 'fallback_generated'
                    }
                ])
        else:  # neutral
            points.extend([
                {
                    'title': 'バランスの取れた報告',
                    'description': '客観的で事実ベースの記述が中心となっており、冷静な経営判断が期待できます',
                    'source': 'fallback_generated'
                },
                {
                    'title': '安定した事業基盤',
                    'description': '感情的な表現を避けた報告は、安定した事業基盤を示唆している可能性があります',
                    'source': 'fallback_generated'
                },
                {
                    'title': 'ディフェンシブ投資適性',
                    'description': '大きな変動要因が少なく、安定志向の投資戦略に適した企業特性を示しています',
                    'source': 'fallback_generated'
                }
            ])
        
        # 統計情報に基づく追加ポイント
        total_words = statistics.get('total_words_analyzed', 0)
        if total_words > 50:
            points.append({
                'title': '充実した分析基盤',
                'description': f'{total_words}語の豊富な情報に基づく分析結果で、信頼性の高い評価となっています',
                'source': 'fallback_generated'
            })
        
        context_patterns = statistics.get('context_patterns_found', 0)
        if context_patterns > 3:
            points.append({
                'title': '多角的な表現分析',
                'description': f'{context_patterns}個の文脈パターンが検出され、多面的な経営状況の把握が可能です',
                'source': 'fallback_generated'
            })
        
        return points[:5]  # 最大5個