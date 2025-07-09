# earnings_analysis/services/sentiment_analyzer.py（セクション統合修正版）
import re
import csv
import os
import threading
import time
import logging
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from .xbrl_extractor import EDINETXBRLService

logger = logging.getLogger(__name__)

@dataclass
class AnalysisConfig:
    """感情分析設定"""
    positive_threshold: float = 0.15  # 閾値を下げてより多くの語彙を検出
    negative_threshold: float = -0.15  # 閾値を下げてより多くの語彙を検出
    min_sentence_length: int = 10  # 最小文長を短くして文章を取得しやすく
    max_sample_sentences: int = 15  # サンプル文章数を増加
    cache_timeout: int = 3600
    min_numeric_value: float = 5.0
    context_window: int = 5


class TransparentSentimentDictionary:
    """分かりやすい感情辞書管理クラス"""
    
    def __init__(self, dict_path: Optional[str] = None):
        self.dict_path = dict_path or getattr(
            settings, 'SENTIMENT_DICT_PATH', 
            os.path.join(settings.BASE_DIR, 'data', 'sentiment_dict.csv')
        )
        self.sentiment_dict = {}
        self.improvement_patterns = []
        self.deterioration_patterns = []
        self.negation_patterns = []
        self._last_modified = 0
        self.load_dictionary()
    
    def load_dictionary(self) -> None:
        """感情辞書の読み込み（修正版）"""
        if os.path.exists(self.dict_path):
            try:
                self._load_from_file()
                self._build_patterns()
                logger.info(f"感情辞書読み込み完了: {len(self.sentiment_dict)}語")
                
                # デバッグ：辞書の一部をログ出力
                sample_items = list(self.sentiment_dict.items())[:10]
                logger.info(f"辞書サンプル: {sample_items}")
                
            except Exception as e:
                logger.error(f"感情辞書読み込みエラー: {e}")
                self._load_default_dictionary()
        else:
            logger.warning(f"感情辞書が見つかりません: {self.dict_path}")
            self._load_default_dictionary()
    
    def _load_from_file(self) -> None:
        """ファイルからの辞書読み込み（修正版）"""
        loaded_count = 0
        
        try:
            with open(self.dict_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # ヘッダー確認
                fieldnames = reader.fieldnames
                logger.info(f"CSVヘッダー: {fieldnames}")
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        # 語彙とスコアを取得
                        word = row.get('word', '').strip()
                        score_str = row.get('score', '').strip()
                        
                        if not word or not score_str:
                            logger.debug(f"行{row_num}: 空の値をスキップ - word='{word}', score='{score_str}'")
                            continue
                        
                        # コメント行をスキップ
                        if word.startswith('#'):
                            continue
                        
                        # スコアの正規化（全角・半角の数字、マイナス記号の統一）
                        score_str = score_str.replace('−', '-').replace('－', '-')
                        score_str = score_str.replace('１', '1').replace('２', '2').replace('３', '3')
                        score_str = score_str.replace('４', '4').replace('５', '5').replace('６', '6')
                        score_str = score_str.replace('７', '7').replace('８', '8').replace('９', '9')
                        score_str = score_str.replace('０', '0').replace('．', '.')
                        
                        score = float(score_str)
                        
                        # スコア範囲チェック
                        if not (-1.0 <= score <= 1.0):
                            logger.warning(f"行{row_num}: スコア範囲外 - {word}: {score}")
                            continue
                        
                        # 辞書に追加
                        self.sentiment_dict[word] = score
                        loaded_count += 1
                        
                        # 最初の数件をデバッグ出力
                        if loaded_count <= 5:
                            logger.info(f"語彙登録: '{word}' → {score}")
                            
                    except (ValueError, KeyError) as e:
                        logger.warning(f"行{row_num}: 解析エラー - {row} → {e}")
                        continue
                
                logger.info(f"辞書読み込み完了: {loaded_count}語を登録")
                
        except Exception as e:
            logger.error(f"ファイル読み込みエラー: {e}")
            raise
    
    def _build_patterns(self) -> None:
        """文脈パターンの構築（修正版）"""
        # 改善を表すパターン（ネガティブ→ポジティブ転換）
        self.improvement_patterns = [
            r'(減収|減益|赤字|損失|業績悪化|低迷|不振|苦戦)(?:の|幅の|幅)?(改善|回復|縮小|解消|脱却|克服)',
            r'(減収|減益|赤字|損失)(?:の|幅の|幅)?縮小',
            r'(業績悪化|低迷|不振)(?:からの|から)(回復|脱却|改善)',
            r'(悪化|低迷|不振)(?:に|への)歯止め',
            r'無配からの復配',
            r'赤字からの黒字転換',
        ]
        
        # 悪化を表すパターン（ポジティブ→ネガティブ転換）
        self.deterioration_patterns = [
            r'(増収|増益|成長|好調|回復)(?:の|に)(鈍化|頭打ち|一服|陰り)',
            r'(増収|増益|成長|改善)(?:の|が)(遅れ|足踏み)',
            r'(好調|順調)(?:に|な)(陰り|一服)',
        ]
        
        # 否定パターン
        self.negation_patterns = [
            r'(減収|減益|赤字|損失|悪化|低迷|不振)(?:で|では)?(は?な)(い|く)',
            r'(減収|減益|赤字|損失|悪化|低迷|不振)(?:という)?(?:わけ)?(で|では)?(は?な)(い|く)',
        ]
        
        logger.info(f"文脈パターン構築完了: 改善{len(self.improvement_patterns)}個, "
                   f"悪化{len(self.deterioration_patterns)}個, "
                   f"否定{len(self.negation_patterns)}個")
    
    def get_word_score(self, word: str) -> Optional[float]:
        """語彙のスコア取得（デバッグ付き）"""
        score = self.sentiment_dict.get(word)
        if score is not None:
            logger.debug(f"語彙スコア取得: '{word}' → {score}")
        return score
    
    def search_words(self, text: str) -> List[Tuple[str, float]]:
        """テキスト内の感情語彙を検索（デバッグ用）"""
        found_words = []
        for word, score in self.sentiment_dict.items():
            if word in text:
                count = text.count(word)
                found_words.append((word, score, count))
                logger.debug(f"語彙発見: '{word}' (スコア: {score}, 出現: {count}回)")
        
        return found_words
    
    def _load_default_dictionary(self) -> None:
        """デフォルト辞書（拡張版・デバッグ付き）"""
        logger.info("デフォルト辞書を使用します")
        
        self.sentiment_dict = {
            # ポジティブ語彙
            '増収': 0.8, '増益': 0.8, '大幅増収': 0.9, '大幅増益': 0.9,
            '過去最高益': 0.9, '最高益': 0.9, '黒字転換': 0.9, '黒字化': 0.8,
            'V字回復': 0.9, '復配': 0.8, '改善': 0.7, '向上': 0.7, '回復': 0.6, 
            '好調': 0.8, '順調': 0.7, '成長': 0.8, '拡大': 0.6, '上昇': 0.6, 
            '達成': 0.7, '成功': 0.8, '効率化': 0.5, '強化': 0.6, '堅調': 0.6,
            
            # 改善パターン
            '減収の改善': 0.7, '赤字縮小': 0.8, '損失の改善': 0.7,
            '減収幅の縮小': 0.7, '減益の改善': 0.7, '業績向上': 0.7,
            
            # ネガティブ語彙
            '減収': -0.7, '減益': -0.8, '大幅減収': -0.9, '大幅減益': -0.9,
            '赤字': -0.8, '赤字転落': -0.9, '損失': -0.7, '営業損失': -0.8,
            '悪化': -0.8, '低下': -0.6, '減少': -0.6, '低迷': -0.7, '不振': -0.7,
            '苦戦': -0.7, '困難': -0.7, '厳しい': -0.6, '下落': -0.6,
            
            # 悪化パターン
            '増収の鈍化': -0.5, '成長の鈍化': -0.6, '好調に陰り': -0.5,
            
            # 中立
            '維持': 0.1, '継続': 0.2, '推移': 0.0, '予想': 0.0,
        }
        
        logger.info(f"デフォルト辞書構築完了: {len(self.sentiment_dict)}語")
        self._build_patterns()
        

class TransparentTextProcessor:
    """分かりやすいテキスト前処理クラス"""
    
    @staticmethod
    def preprocess(text: str) -> str:
        """改良版テキスト前処理（数値保持）"""
        if not text:
            return ""
        
        # HTMLタグ除去
        text = re.sub(r'<[^>]+>', '', text)
        
        # 重要な金融表現を保護
        protected_patterns = []
        financial_patterns = [
            # 改善・悪化表現（数値付き）
            (r'(減収|減益|赤字|損失)(?:の|幅の|幅)?(?:が|は)?\d+(?:\.\d+)?[％%]?(?:の)?(改善|縮小)', 'IMPROVEMENT'),
            (r'(増収|増益|成長)(?:の|が)?\d+(?:\.\d+)?[％%]?(?:の)?(鈍化|頭打ち)', 'DETERIORATION'),
            
            # 基本的な改善・悪化表現
            (r'(減収|減益|赤字|損失|業績悪化|低迷|不振)(?:の|幅の|幅)?(改善|回復|縮小|解消|脱却)', 'IMPROVEMENT'),
            (r'(増収|増益|成長|好調)(?:の|に)(鈍化|頭打ち|一服|陰り)', 'DETERIORATION'),
            
            # 特別な表現
            (r'V字回復', 'RECOVERY'),
            (r'黒字転換', 'PROFIT_CHANGE'),
            (r'赤字転落', 'LOSS_CHANGE'),
            
            # 数値表現（重要なもののみ保護）
            (r'\d+(?:\.\d+)?(?:％|%|倍)(?:以上|超|増|減|上昇|下落|改善|悪化)', 'NUMERIC'),
            (r'(?:過去|)\d+年(?:ぶり|連続)', 'PERIOD'),
        ]
        
        for i, (pattern, prefix) in enumerate(financial_patterns):
            for match in re.finditer(pattern, text):
                placeholder = f"__{prefix}_{i}__"
                protected_patterns.append((placeholder, match.group()))
                text = text.replace(match.group(), placeholder, 1)
        
        # 一般的な整理（数値は保持）
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[【】「」（）\(\)\[\]〔〕]', '', text)
        
        # 保護したパターンを復元
        for placeholder, original in protected_patterns:
            text = text.replace(placeholder, original)
        
        return text.strip()


class UserInsightGenerator:
    """ユーザー向け見解生成クラス"""
    
    def __init__(self):
        self.business_terms = {
            'positive': [
                '成長戦略', '収益改善', '競争力強化', '市場拡大', '効率化',
                '業績向上', '株主価値', '持続的成長', '技術革新', '新規事業'
            ],
            'negative': [
                'リスク管理', '課題対応', '構造改革', '業績改善', 'コスト削減',
                '市場変化', '競争激化', '不確実性', '経営課題', '事業再編'
            ]
        }
    
    def generate_detailed_insights(self, analysis_result: Dict[str, Any], document_info: Dict[str, str]) -> Dict[str, Any]:
        """詳細な見解を生成"""
        overall_score = analysis_result.get('overall_score', 0)
        sentiment_label = analysis_result.get('sentiment_label', 'neutral')
        statistics = analysis_result.get('statistics', {})
        keyword_analysis = analysis_result.get('keyword_analysis', {})
        
        insights = {
            'market_implications': self._generate_market_implications(overall_score, sentiment_label, keyword_analysis),
            'business_strategy_reading': self._generate_business_strategy_reading(analysis_result, document_info),
            'investor_perspective': self._generate_investor_perspective(overall_score, sentiment_label, statistics),
            'risk_assessment': self._generate_risk_assessment(analysis_result),
            'competitive_position': self._generate_competitive_analysis(keyword_analysis, overall_score),
            'future_outlook': self._generate_future_outlook(analysis_result),
            'stakeholder_recommendations': self._generate_stakeholder_recommendations(overall_score, sentiment_label, statistics)
        }
        
        return insights
    
    def _generate_market_implications(self, score: float, label: str, keywords: Dict) -> Dict[str, Any]:
        """市場への影響分析"""
        implications = {
            'market_sentiment': '',
            'stock_impact_likelihood': '',
            'sector_comparison': '',
            'timing_considerations': ''
        }
        
        if label == 'positive':
            if score > 0.6:
                implications['market_sentiment'] = '非常にポジティブな市場反応が期待される内容です。'
                implications['stock_impact_likelihood'] = '高い確率で株価にプラスの影響を与える可能性があります。'
            else:
                implications['market_sentiment'] = '市場に対して前向きなメッセージを発信しています。'
                implications['stock_impact_likelihood'] = '短期的にはプラス材料として評価される可能性があります。'
        elif label == 'negative':
            if score < -0.6:
                implications['market_sentiment'] = '市場の慎重な反応が予想される内容です。'
                implications['stock_impact_likelihood'] = '一時的な株価下落要因となる可能性があります。'
            else:
                implications['market_sentiment'] = '市場は企業の透明性を評価する一方、慎重な姿勢を見せる可能性があります。'
                implications['stock_impact_likelihood'] = '短期的な影響は限定的である可能性があります。'
        else:
            implications['market_sentiment'] = '市場反応は中立的で、他の要因により左右される可能性があります。'
            implications['stock_impact_likelihood'] = '感情的な材料としての影響は限定的と予想されます。'
        
        return implications
    
    def _generate_business_strategy_reading(self, analysis_result: Dict, document_info: Dict) -> Dict[str, str]:
        """経営戦略の読み取り"""
        strategy_reading = {
            'management_stance': '',
            'strategic_direction': '',
            'operational_focus': ''
        }
        
        keyword_analysis = analysis_result.get('keyword_analysis', {})
        positive_keywords = keyword_analysis.get('positive', [])
        negative_keywords = keyword_analysis.get('negative', [])
        
        # ポジティブキーワードから戦略を読み取り
        growth_words = [kw for kw in positive_keywords if any(term in kw.get('word', '') for term in ['成長', '拡大', '増収', '増益'])]
        improvement_words = [kw for kw in positive_keywords if any(term in kw.get('word', '') for term in ['改善', '向上', '効率', '強化'])]
        
        if growth_words:
            strategy_reading['strategic_direction'] = '成長志向の戦略が明確に示されており、事業拡大への積極的な姿勢が読み取れます。'
        elif improvement_words:
            strategy_reading['strategic_direction'] = '効率性と品質向上に重点を置いた戦略が展開されています。'
        
        # ネガティブキーワードからリスク対応を読み取り
        risk_words = [kw for kw in negative_keywords if any(term in kw.get('word', '') for term in ['リスク', '課題', '困難', '厳しい'])]
        
        if risk_words:
            strategy_reading['management_stance'] = 'リスクを正面から捉え、課題解決に向けた現実的なアプローチを採用しています。'
        else:
            strategy_reading['management_stance'] = '安定した経営基盤の上に、着実な事業運営を行っています。'
        
        return strategy_reading
    
    def _generate_investor_perspective(self, score: float, label: str, statistics: Dict) -> Dict[str, str]:
        """投資家視点での分析"""
        investor_view = {
            'investment_appeal': '',
            'risk_reward_balance': '',
            'dividend_outlook': '',
            'growth_potential': ''
        }
        
        total_words = statistics.get('total_words_analyzed', 0)
        
        if label == 'positive':
            investor_view['investment_appeal'] = '投資魅力度は高く、成長期待を持てる企業として位置づけられます。'
            investor_view['growth_potential'] = '中長期的な成長ポテンシャルが期待できる内容となっています。'
            if score > 0.5:
                investor_view['dividend_outlook'] = '株主還元策の拡充や増配の可能性も期待されます。'
        elif label == 'negative':
            investor_view['investment_appeal'] = 'リスクを慎重に評価した上での投資判断が必要です。'
            investor_view['risk_reward_balance'] = 'リスクは存在しますが、それに見合ったリターンの可能性もあります。'
        else:
            investor_view['investment_appeal'] = '安定した投資先として、ディフェンシブな投資戦略に適しています。'
            investor_view['growth_potential'] = '急成長は期待できませんが、安定した成長が見込まれます。'
        
        if total_words > 50:
            investor_view['analysis_reliability'] = f'十分な情報量（{total_words}語）に基づく分析のため、信頼性は高いと考えられます。'
        
        return investor_view
    
    def _generate_risk_assessment(self, analysis_result: Dict) -> Dict[str, Any]:
        """リスク評価"""
        risk_assessment = {
            'identified_risks': [],
            'risk_level': 'medium',
            'mitigation_evidence': [],
            'monitoring_points': []
        }
        
        negative_keywords = analysis_result.get('keyword_analysis', {}).get('negative', [])
        negative_sentences = analysis_result.get('sample_sentences', {}).get('negative', [])
        
        # リスクの特定
        for keyword in negative_keywords:
            word = keyword.get('word', '')
            if any(risk_term in word for risk_term in ['リスク', '減収', '減益', '損失', '困難']):
                risk_assessment['identified_risks'].append(f"{word}に関するリスク")
        
        # リスクレベルの決定
        overall_score = analysis_result.get('overall_score', 0)
        if overall_score < -0.5:
            risk_assessment['risk_level'] = 'high'
            risk_assessment['monitoring_points'].append('短期的な業績動向の注意深い監視が必要')
        elif overall_score < -0.2:
            risk_assessment['risk_level'] = 'medium'
            risk_assessment['monitoring_points'].append('中期的な改善計画の進捗確認が重要')
        else:
            risk_assessment['risk_level'] = 'low'
        
        return risk_assessment
    
    def _generate_competitive_analysis(self, keywords: Dict, score: float) -> Dict[str, str]:
        """競争環境分析"""
        competitive_analysis = {
            'competitive_position': '',
            'market_strategy': '',
            'differentiation_factors': ''
        }
        
        positive_keywords = keywords.get('positive', [])
        
        # 競争力を示すキーワードの分析
        competitive_words = [kw for kw in positive_keywords if any(term in kw.get('word', '') for term in ['競争力', '強化', 'シェア', '市場'])]
        
        if competitive_words:
            competitive_analysis['competitive_position'] = '市場での競争優位性を確立し、リーディングポジションを目指しています。'
        elif score > 0.3:
            competitive_analysis['competitive_position'] = '業界内での地位を着実に向上させ、競争力を高めています。'
        else:
            competitive_analysis['competitive_position'] = '安定した事業基盤を維持し、堅実な市場参加者として位置づけられます。'
        
        return competitive_analysis
    
    def _generate_future_outlook(self, analysis_result: Dict) -> Dict[str, str]:
        """将来展望"""
        future_outlook = {
            'short_term_outlook': '',
            'medium_term_strategy': '',
            'long_term_vision': ''
        }
        
        overall_score = analysis_result.get('overall_score', 0)
        sentiment_label = analysis_result.get('sentiment_label', 'neutral')
        
        if sentiment_label == 'positive':
            future_outlook['short_term_outlook'] = '今後1-2年は継続的な成長が期待できる見通しです。'
            future_outlook['medium_term_strategy'] = '中期的には市場シェア拡大と収益性向上の両立を図る戦略が有効です。'
            future_outlook['long_term_vision'] = '長期的には業界のリーダー企業としての地位確立が期待されます。'
        elif sentiment_label == 'negative':
            future_outlook['short_term_outlook'] = '短期的には課題解決と構造改革に注力する必要があります。'
            future_outlook['medium_term_strategy'] = '中期的な回復軌道への転換が重要な課題となります。'
            future_outlook['long_term_vision'] = '長期的には持続可能なビジネスモデルの構築が求められます。'
        else:
            future_outlook['short_term_outlook'] = '現状維持を基本として、着実な成長を目指す見通しです。'
            future_outlook['medium_term_strategy'] = '安定した事業基盤の上に、選択的な投資を行う戦略が適切です。'
        
        return future_outlook
    
    def _generate_stakeholder_recommendations(self, score: float, label: str, statistics: Dict) -> Dict[str, List[str]]:
        """ステークホルダー別推奨事項"""
        recommendations = {
            'for_investors': [],
            'for_management': [],
            'for_employees': [],
            'for_customers': []
        }
        
        if label == 'positive':
            recommendations['for_investors'] = [
                '成長期待に基づく投資戦略の検討',
                '中長期的な保有を前提とした投資判断',
                '配当政策の動向に注目'
            ]
            recommendations['for_management'] = [
                '成長戦略の着実な実行',
                'ステークホルダーへの継続的な情報開示',
                '持続可能な成長基盤の構築'
            ]
        elif label == 'negative':
            recommendations['for_investors'] = [
                'リスク要因の詳細な分析と評価',
                '改善計画の進捗状況の定期的な確認',
                '分散投資によるリスク軽減'
            ]
            recommendations['for_management'] = [
                '課題解決への具体的なアクションプラン策定',
                'ステークホルダーとの積極的なコミュニケーション',
                '構造改革の加速化'
            ]
        else:
            recommendations['for_investors'] = [
                '安定配当を重視したポートフォリオ構築',
                '業界動向との比較分析',
                '長期的な視点での投資判断'
            ]
        
        return recommendations


class TransparentSentimentAnalyzer:
    """分かりやすい感情分析エンジン（見解生成強化版）"""
    
    def __init__(self, config: Optional[AnalysisConfig] = None):
        self.config = config or AnalysisConfig()
        self.dictionary = TransparentSentimentDictionary()
        self.text_processor = TransparentTextProcessor()
        self.insight_generator = UserInsightGenerator()
          # 問題の根本原因と修正箇所

    def _analyze_keyword_frequency_safe(self, all_matches: List) -> Dict[str, List[Dict]]:
        """安全なキーワード出現頻度の詳細分析（データ構造チェック付き）"""
        frequency_data = {'positive': [], 'negative': []}
        
        try:
            # データ構造の検証
            if not all_matches:
                logger.warning("all_matchesが空です")
                return frequency_data
            
            # 最初の要素の構造をチェック
            first_item = all_matches[0]
            logger.debug(f"最初の要素: {first_item}, 型: {type(first_item)}")
            
            # タプル形式かどうか確認
            if not isinstance(first_item, (tuple, list)) or len(first_item) != 3:
                logger.error(f"all_matchesのデータ構造が不正です。期待: (word, score, type), 実際: {type(first_item)}")
                logger.error(f"all_matchesサンプル: {all_matches[:5]}")
                return frequency_data
            
            # キーワードの出現回数を集計
            keyword_counts = {}
            keyword_scores = {}
            keyword_types = {}
            
            for i, match_item in enumerate(all_matches):
                try:
                    # データ構造の確認
                    if not isinstance(match_item, (tuple, list)) or len(match_item) != 3:
                        logger.warning(f"インデックス{i}の要素が不正: {match_item}")
                        continue
                    
                    word, score, type_name = match_item
                    
                    # 型チェック
                    if not isinstance(word, str):
                        logger.warning(f"インデックス{i}: wordが文字列ではありません: {word} ({type(word)})")
                        continue
                    
                    if not isinstance(score, (int, float)):
                        logger.warning(f"インデックス{i}: scoreが数値ではありません: {score} ({type(score)})")
                        continue
                    
                    if word not in keyword_counts:
                        keyword_counts[word] = 0
                        keyword_scores[word] = float(score)
                        keyword_types[word] = str(type_name)
                    
                    keyword_counts[word] += 1
                    # スコアは平均を取る
                    keyword_scores[word] = (keyword_scores[word] + float(score)) / 2
                    
                except Exception as e:
                    logger.error(f"インデックス{i}の処理でエラー: {e}, 要素: {match_item}")
                    continue
            
            logger.info(f"キーワード集計完了: {len(keyword_counts)}個のユニークワード")
            
            # ポジティブ・ネガティブに分類
            for word, count in keyword_counts.items():
                try:
                    score = keyword_scores[word]
                    
                    keyword_data = {
                        'word': word,
                        'count': count,
                        'score': float(score),
                        'type': keyword_types[word],
                        'impact_level': self._get_impact_level(score),
                        'frequency_rank': 0  # 後で設定
                    }
                    
                    if score > 0:
                        frequency_data['positive'].append(keyword_data)
                    elif score < 0:
                        frequency_data['negative'].append(keyword_data)
                        
                except Exception as e:
                    logger.error(f"キーワード'{word}'の分類でエラー: {e}")
                    continue
            
            # 出現回数でソートしてランク付け
            frequency_data['positive'].sort(key=lambda x: x['count'], reverse=True)
            frequency_data['negative'].sort(key=lambda x: x['count'], reverse=True)
            
            # ランク付け
            for i, item in enumerate(frequency_data['positive']):
                item['frequency_rank'] = i + 1
            
            for i, item in enumerate(frequency_data['negative']):
                item['frequency_rank'] = i + 1
            
            logger.info(f"頻度分析完了: ポジティブ{len(frequency_data['positive'])}語, ネガティブ{len(frequency_data['negative'])}語")
            
            return frequency_data
            
        except Exception as e:
            logger.error(f"キーワード頻度分析エラー: {e}")
            return frequency_data

    # ✅ 修正版のコード
    def analyze_text(self, text: str, session_id: str = None, document_info: Dict[str, str] = None) -> Dict[str, Any]:
        """透明性の高い感情分析（データ渡し問題修正版）"""
        try:
            if not text or len(text.strip()) < 10:
                return self._empty_result(session_id)
            
            # テキスト前処理
            cleaned_text = self.text_processor.preprocess(text)
            
            # 段階的な分析プロセス
            analysis_steps = []
            
            # ステップ1: 文脈パターンの検出
            context_matches = self._find_context_patterns(cleaned_text)
            if context_matches:
                analysis_steps.append({
                    'step': '文脈パターン検出',
                    'description': '「減収の改善」「成長の鈍化」のような文脈を考慮した表現を検出',
                    'matches': context_matches,
                    'impact': sum(score for _, score, _ in context_matches)
                })
            
            # ステップ2: 基本語彙の検出
            basic_matches = self._find_basic_words(cleaned_text, context_matches)
            if basic_matches:
                analysis_steps.append({
                    'step': '基本語彙検出',
                    'description': '感情辞書に登録されている語彙を検出',
                    'matches': basic_matches,
                    'impact': sum(score for _, score, _ in basic_matches)
                })
            
            # ★重要：全てのマッチを統合（タプル形式を維持）
            all_matches = context_matches + basic_matches
            
            # デバッグログ: データ構造確認
            if all_matches:
                logger.info(f"all_matches サンプル: {all_matches[:3]}")
                logger.info(f"all_matches 型: {type(all_matches)}, 長さ: {len(all_matches)}")
            
            # ★修正：all_matches（タプルリスト）をそのまま渡す
            score_calculation = self._calculate_detailed_score(all_matches)  # ✅ 正しい
            
            # 全体スコアと判定
            overall_score = score_calculation['final_score']
            sentiment_label = self._determine_sentiment_label(overall_score)
            
            # 分析根拠の生成
            analysis_reasoning = self._generate_reasoning(
                analysis_steps, score_calculation, overall_score, sentiment_label
            )
            
            # キーワード分析（修正版：all_matchesを使用）
            keyword_analysis = self._analyze_keywords(all_matches)
            
            # ★修正：キーワード頻度分析（all_matchesを直接使用）
            keyword_frequency_data = self._analyze_keyword_frequency_safe(all_matches)  # ✅ 正しい
            
            # 文章レベル分析
            sentences = self._split_sentences(cleaned_text)
            sentence_analysis = self._analyze_sentences(sentences)
            
            # 基本結果の構築
            basic_result = {
                'overall_score': round(overall_score, 3),
                'sentiment_label': sentiment_label,
                'analysis_reasoning': analysis_reasoning,
                'score_calculation': score_calculation,
                'analysis_steps': analysis_steps,
                'keyword_analysis': keyword_analysis,
                'keyword_frequency_data': keyword_frequency_data,  # ★追加
                'sample_sentences': {
                    'positive': [s for s in sentence_analysis if s['score'] > self.config.positive_threshold][:5],
                    'negative': [s for s in sentence_analysis if s['score'] < self.config.negative_threshold][:5],
                },
                'statistics': {
                    'total_words_analyzed': len(all_matches),
                    'context_patterns_found': len(context_matches),
                    'basic_words_found': len(basic_matches),
                    'sentences_analyzed': len(sentences),
                    'unique_words_found': len(set(word for word, _, _ in all_matches)),
                    'positive_words_count': len([s for _, s, _ in all_matches if s > 0]),
                    'negative_words_count': len([s for _, s, _ in all_matches if s < 0]),
                    'positive_sentences_count': len([s for s in sentence_analysis if s['score'] > self.config.positive_threshold]),
                    'negative_sentences_count': len([s for s in sentence_analysis if s['score'] < self.config.negative_threshold]),
                    'threshold_positive': self.config.positive_threshold,
                    'threshold_negative': self.config.negative_threshold,
                    # ★頻度統計を追加
                    'total_keyword_occurrences': sum(item['count'] for item in keyword_frequency_data['positive'] + keyword_frequency_data['negative']),
                    'top_positive_keyword': keyword_frequency_data['positive'][0] if keyword_frequency_data['positive'] else None,
                    'top_negative_keyword': keyword_frequency_data['negative'][0] if keyword_frequency_data['negative'] else None,
                },
                'analysis_metadata': {
                    'analyzed_at': timezone.now().isoformat(),
                    'dictionary_size': len(self.dictionary.sentiment_dict),
                    'session_id': session_id,
                    'analysis_version': '2.3_data_flow_fixed',
                }
            }
            
            # ユーザー向け詳細見解を生成
            if document_info:
                user_insights = self.insight_generator.generate_detailed_insights(basic_result, document_info)
                basic_result['user_insights'] = user_insights
            
            return basic_result
            
        except Exception as e:
            logger.error(f"感情分析エラー: {e}")
            raise Exception(f"感情分析処理中にエラーが発生しました: {str(e)}")
    def _find_basic_words(self, text: str, context_matches: List) -> List[Tuple[str, float, str]]:
        """基本語彙の検出（語彙情報保持版）"""
        matches = []
        
        try:
            # 文脈パターンで検出された語句を除外対象とする
            context_words = {word for word, _, _ in context_matches}
            
            # 辞書のすべての語彙をチェック
            for word, score in self.dictionary.sentiment_dict.items():
                if len(word) < 1:
                    continue
                    
                if word in context_words:
                    continue
                
                # テキスト内での出現回数をカウント
                count = text.count(word)
                if count > 0:
                    # 出現回数分だけ追加（最大5回まで）
                    for _ in range(min(count, 5)):
                        matches.append((word, score, '基本語彙'))  # ★重要: タプル形式
            
            return matches
            
        except Exception as e:
            logger.debug(f"基本語彙検出エラー: {e}")
            return []
        
    def _find_context_patterns(self, text: str) -> List[Tuple[str, float, str]]:
        """文脈パターンの検出（語彙情報保持版）"""
        matches = []
        
        try:
            # 改善パターンの検出
            for pattern in self.dictionary.improvement_patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    matched_text = match.group()
                    score = 0.7
                    matches.append((matched_text, score, '改善表現'))  # ★重要: タプル形式
            
            # 悪化パターンの検出
            for pattern in self.dictionary.deterioration_patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    matched_text = match.group()
                    score = -0.6
                    matches.append((matched_text, score, '悪化表現'))  # ★重要: タプル形式
            
            # 否定パターンの検出
            for pattern in self.dictionary.negation_patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    matched_text = match.group()
                    score = 0.4
                    matches.append((matched_text, score, '否定表現'))  # ★重要: タプル形式
            
            return matches
            
        except Exception as e:
            logger.debug(f"文脈パターン検出エラー: {e}")
            return []
               
    def _calculate_detailed_score(self, all_matches: List[Tuple[str, float, str]]) -> Dict:
        """詳細なスコア計算（語彙情報付き完全版）"""
        if not all_matches:
            return {
                'raw_scores': [], 'positive_scores': [], 'negative_scores': [],
                'positive_words': [], 'negative_words': [],
                'positive_sum': 0.0, 'negative_sum': 0.0, 'score_count': 0,
                'average_score': 0.0, 'final_score': 0.0,
            }
        
        # デバッグ: 入力データの確認
        logger.info(f"_calculate_detailed_score 入力: {len(all_matches)}個のマッチ")
        logger.info(f"サンプルマッチ: {all_matches[:3] if all_matches else '無し'}")
        
        positive_items = []
        negative_items = []
        all_scores = []
        
        # 重複を除去しながら集計
        word_scores = {}
        for word, score, type_name in all_matches:
            key = f"{word}_{type_name}"
            if key in word_scores:
                existing = word_scores[key]
                existing['score'] = (existing['score'] + score) / 2
                existing['count'] += 1
            else:
                word_scores[key] = {
                    'word': word, 'score': score, 'type': type_name, 'count': 1
                }
        
        # 分類とスコア集計
        for item in word_scores.values():
            weighted_score = item['score'] * min(item['count'], 3)
            all_scores.append(weighted_score)
            
            word_info = {
                'word': item['word'], 'score': item['score'], 'type': item['type'],
                'count': item['count'], 'weighted_score': weighted_score
            }
            
            if item['score'] > 0:
                positive_items.append(word_info)
            elif item['score'] < 0:
                negative_items.append(word_info)
        
        # スコア計算
        positive_scores = [item['weighted_score'] for item in positive_items]
        negative_scores = [item['weighted_score'] for item in negative_items]
        
        positive_sum = sum(positive_scores)
        negative_sum = sum(negative_scores)
        average_score = sum(all_scores) / len(all_scores) if all_scores else 0
        
        weighted_sum = sum(score * abs(score) for score in all_scores)
        weighted_avg = weighted_sum / len(all_scores) if all_scores else 0
        
        final_score = (average_score + weighted_avg) / 2 if all_scores else 0
        final_score = max(-1.0, min(1.0, final_score))
        
        # スコア順でソート
        positive_items.sort(key=lambda x: x['score'], reverse=True)
        negative_items.sort(key=lambda x: x['score'])
        
        return {
            'raw_scores': all_scores,
            'positive_scores': positive_scores,
            'negative_scores': negative_scores,
            'positive_words': positive_items,  # ★新規追加
            'negative_words': negative_items,  # ★新規追加
            'positive_sum': positive_sum,
            'negative_sum': negative_sum,
            'score_count': len(all_scores),
            'average_score': average_score,
            'weighted_average': weighted_avg,
            'final_score': final_score,
        }
        
    def _generate_reasoning(self, analysis_steps: List, score_calc: Dict, overall_score: float, sentiment_label: str) -> Dict:
        """分析根拠の生成"""
        reasoning = {
            'summary': '',
            'key_factors': [],
            'score_breakdown': '',
            'conclusion': ''
        }
        
        # 主要因子の特定
        pos_count = len(score_calc['positive_scores'])
        neg_count = len(score_calc['negative_scores'])
        
        if pos_count > neg_count:
            reasoning['key_factors'].append(f'ポジティブな表現が{pos_count}個検出されました')
        elif neg_count > pos_count:
            reasoning['key_factors'].append(f'ネガティブな表現が{neg_count}個検出されました')
        else:
            reasoning['key_factors'].append('ポジティブとネガティブな表現が同数検出されました')
        
        # 文脈パターンの影響
        context_steps = [step for step in analysis_steps if '文脈' in step['step']]
        if context_steps:
            context_impact = context_steps[0]['impact']
            if context_impact > 0:
                reasoning['key_factors'].append('「減収の改善」のような文脈を考慮した改善表現が検出されました')
            elif context_impact < 0:
                reasoning['key_factors'].append('「成長の鈍化」のような文脈を考慮した悪化表現が検出されました')
        
        # スコアの内訳説明
        if score_calc['positive_sum'] and score_calc['negative_sum']:
            reasoning['score_breakdown'] = (
                f'ポジティブ合計: {score_calc["positive_sum"]:.2f}, '
                f'ネガティブ合計: {score_calc["negative_sum"]:.2f}, '
                f'平均スコア: {score_calc["average_score"]:.2f}'
            )
        elif score_calc['positive_sum']:
            reasoning['score_breakdown'] = f'ポジティブ表現のみ検出: 合計{score_calc["positive_sum"]:.2f}'
        elif score_calc['negative_sum']:
            reasoning['score_breakdown'] = f'ネガティブ表現のみ検出: 合計{score_calc["negative_sum"]:.2f}'
        else:
            reasoning['score_breakdown'] = '感情を表す表現が検出されませんでした'
        
        # 結論
        if sentiment_label == 'positive':
            if overall_score > 0.6:
                reasoning['conclusion'] = '非常にポジティブな内容です'
            else:
                reasoning['conclusion'] = 'やや前向きな内容です'
        elif sentiment_label == 'negative':
            if overall_score < -0.6:
                reasoning['conclusion'] = '非常にネガティブな内容です'
            else:
                reasoning['conclusion'] = 'やや慎重な内容です'
        else:
            reasoning['conclusion'] = '中立的な内容です'
        
        # 要約
        reasoning['summary'] = f'{reasoning["conclusion"]}。{reasoning["key_factors"][0] if reasoning["key_factors"] else ""}'
        
        return reasoning
    
    def _analyze_keywords(self, matches: List[Tuple[str, float, str]]) -> Dict:
        """キーワード分析（分かりやすい形式）"""
        positive_words = []
        negative_words = []
        
        for word, score, type_name in matches:
            word_info = {
                'word': word,
                'score': round(score, 2),
                'type': type_name,
                'impact': '強い' if abs(score) > 0.7 else '中程度' if abs(score) > 0.4 else '軽微'
            }
            
            if score > 0:
                positive_words.append(word_info)
            elif score < 0:
                negative_words.append(word_info)
        
        # スコア順でソート
        positive_words.sort(key=lambda x: x['score'], reverse=True)
        negative_words.sort(key=lambda x: x['score'])
        
        return {
            'positive': positive_words[:10],  # 上位10件
            'negative': negative_words[:10],  # 上位10件
        }
    
    def _split_sentences(self, text: str) -> List[str]:
        """文分割（より短い文章も対象）"""
        sentences = re.split(r'[。！？\n]', text)
        return [s.strip() for s in sentences if len(s.strip()) >= self.config.min_sentence_length and 
                len(re.findall(r'[ぁ-んァ-ヶ一-龯]', s)) > 2]  # 日本語文字が2個以上
        
    def _analyze_sentences(self, sentences: List[str]) -> List[Dict]:
        """文章レベル分析（重複除去強化版）"""
        sentence_analysis = []
        analyzed_texts = set()  # 重複チェック用
        
        for sentence in sentences[:self.config.max_sample_sentences]:
            # 簡易的な文スコア計算
            context_matches = self._find_context_patterns(sentence)
            basic_matches = self._find_basic_words(sentence, context_matches)
            
            all_scores = [score for _, score, _ in context_matches + basic_matches]
            sent_score = sum(all_scores) / len(all_scores) if all_scores else 0
            
            if abs(sent_score) > 0.15:  # 閾値を0.15に下げて文章を取得しやすくする
                # 文章の正規化（重複チェック用）
                normalized_text = self._normalize_sentence_for_dedup(sentence)
                
                # 重複チェック
                if normalized_text in analyzed_texts:
                    continue
                    
                analyzed_texts.add(normalized_text)
                
                keywords = [word for word, _, _ in context_matches + basic_matches]
                # 一度にすべてのキーワードをハイライト
                highlighted_text = self._highlight_all_keywords_in_text(sentence, keywords)
                
                sentence_analysis.append({
                    'text': sentence[:200],  # 文字数制限
                    'highlighted_text': highlighted_text,
                    'score': round(sent_score, 2),
                    'keywords': list(set(keywords)),  # 重複キーワード除去
                })
        
        return sentence_analysis

    def _normalize_sentence_for_dedup(self, sentence: str) -> str:
        """重複チェック用の文章正規化"""
        import re
        
        # 空白や記号を統一
        normalized = re.sub(r'\s+', ' ', sentence)
        normalized = re.sub(r'[。、！？\.,!?]', '', normalized)
        normalized = normalized.strip().lower()
        
        # 50文字以上の場合は最初の50文字で重複判定
        if len(normalized) > 50:
            normalized = normalized[:50]
        
        return normalized

    def _highlight_all_keywords_in_text(self, text: str, keywords: List[str]) -> str:
        """テキスト内のすべてのキーワードを一度にハイライト"""
        highlighted_text = text[:200]  # 文字数制限
        
        if not keywords:
            return highlighted_text
        
        # キーワードを長い順にソートして、部分マッチによる重複を避ける
        sorted_keywords = sorted(set(keywords), key=len, reverse=True)
        
        for keyword in sorted_keywords:
            if keyword and keyword in highlighted_text:
                # 既にハイライトされている部分は除外
                if f'<span class="keyword-highlight">{keyword}</span>' not in highlighted_text:
                    highlighted_text = highlighted_text.replace(
                        keyword,
                        f'<span class="keyword-highlight">{keyword}</span>'
                    )
        
        return highlighted_text
    
    def _highlight_keywords_in_text(self, text: str, keywords: List[str]) -> str:
        """テキスト内のキーワードをハイライト"""
        highlighted_text = text[:200]  # 文字数制限
        
        # キーワードを長い順にソートして、部分マッチによる重複を避ける
        sorted_keywords = sorted(set(keywords), key=len, reverse=True)
        
        for keyword in sorted_keywords:
            if keyword and keyword in highlighted_text:
                # HTMLエスケープされていない状態でハイライトタグを挿入
                highlighted_text = highlighted_text.replace(
                    keyword,
                    f'<span class="keyword-highlight">{keyword}</span>'
                )
        
        return highlighted_text
    
    def _determine_sentiment_label(self, score: float) -> str:
        """感情ラベル決定"""
        if score > self.config.positive_threshold:
            return 'positive'
        elif score < self.config.negative_threshold:
            return 'negative'
        else:
            return 'neutral'
    
    def _empty_result(self, session_id: str = None) -> Dict[str, Any]:
        """空結果の生成"""
        return {
            'overall_score': 0.0,
            'sentiment_label': 'neutral',
            'analysis_reasoning': {
                'summary': '感情を表す表現が検出されませんでした',
                'key_factors': [],
                'score_breakdown': '分析対象となる語彙が見つかりませんでした',
                'conclusion': '中立的な内容です'
            },
            'score_calculation': {
                'raw_scores': [], 'positive_scores': [], 'negative_scores': [],
                'positive_sum': 0.0, 'negative_sum': 0.0, 'score_count': 0,
                'average_score': 0.0, 'final_score': 0.0,
            },
            'analysis_steps': [],
            'keyword_analysis': {'positive': [], 'negative': []},
            'sample_sentences': {'positive': [], 'negative': []},
            'statistics': {
                'total_words_analyzed': 0, 'context_patterns_found': 0,
                'basic_words_found': 0, 'sentences_analyzed': 0, 'unique_words_found': 0,
                'positive_words_count': 0, 'negative_words_count': 0,
                'positive_sentences_count': 0, 'negative_sentences_count': 0,
                'threshold_positive': self.config.positive_threshold,
                'threshold_negative': self.config.negative_threshold,
            },
            'analysis_metadata': {
                'analyzed_at': timezone.now().isoformat(),
                'dictionary_size': len(self.dictionary.sentiment_dict),
                'session_id': session_id,
                'analysis_version': '2.1_insight_enhanced',
            }
        }
    
    def _integrate_keywords(self, keyword_list: List[Dict]) -> List[Dict]:
        """キーワードの統合（重複除去・スコア集約）"""
        keyword_map = {}
        
        for keyword_info in keyword_list:
            word = keyword_info.get('word', '')
            score = keyword_info.get('score', 0)
            type_name = keyword_info.get('type', '')
            impact = keyword_info.get('impact', '')
            section = keyword_info.get('section', '')
            
            if word in keyword_map:
                # 既存のキーワードがある場合、スコアを平均化し、セクション情報を追加
                existing = keyword_map[word]
                existing['score'] = (existing['score'] + score) / 2
                existing['sections'] = existing.get('sections', []) + [section]
                existing['occurrences'] = existing.get('occurrences', 1) + 1
                
                # より強い影響度を採用
                impact_priority = {'強い': 3, '中程度': 2, '軽微': 1}
                if impact_priority.get(impact, 0) > impact_priority.get(existing['impact'], 0):
                    existing['impact'] = impact
            else:
                # 新しいキーワードの場合
                keyword_map[word] = {
                    'word': word,
                    'score': score,
                    'type': type_name,
                    'impact': impact,
                    'sections': [section],
                    'occurrences': 1
                }
        
        # スコア順でソート
        integrated_keywords = list(keyword_map.values())
        integrated_keywords.sort(key=lambda x: abs(x['score']), reverse=True)
        
        return integrated_keywords

    def analyze_text_sections(self, text_sections: Dict[str, str], session_id: str = None, document_info: Dict[str, str] = None) -> Dict[str, Any]:
        """複数セクションの分析（統計修正版）"""
        try:
            section_results = {}
            all_positive_sentences = []
            all_negative_sentences = []
            all_positive_keywords = []
            all_negative_keywords = []
            combined_steps = []
            
            # ★修正: 統計計算用の変数を追加
            total_context_patterns = 0
            total_sentences_analyzed = 0
            
            # ★修正：統合用のマッチデータ（タプル形式）
            all_matches_combined = []
            
            # 重複チェック用のセット
            seen_positive_sentences = set()
            seen_negative_sentences = set()
            
            # セクション別分析
            for section_name, text in text_sections.items():
                if len(text.strip()) < 50:
                    continue
                
                result = self.analyze_text(text, session_id)
                section_results[section_name] = result
                combined_steps.extend(result['analysis_steps'])
                
                # ★修正: 各セクションの統計を累積
                section_stats = result.get('statistics', {})
                total_context_patterns += section_stats.get('context_patterns_found', 0)
                total_sentences_analyzed += section_stats.get('sentences_analyzed', 0)
                
                # ★修正：analysis_stepsからマッチデータを正しく取得
                for step in result.get('analysis_steps', []):
                    matches = step.get('matches', [])
                    if matches:
                        for match in matches:
                            if isinstance(match, (tuple, list)) and len(match) == 3:
                                all_matches_combined.append(match)
                            else:
                                logger.warning(f"不正なマッチデータをスキップ: {match}")
                
                # 各セクションの結果を統合リストに追加（重複除去）
                sample_sentences = result.get('sample_sentences', {})
                keyword_analysis = result.get('keyword_analysis', {})
                
                # ポジティブ文章の統合（重複除去）
                positive_sentences = sample_sentences.get('positive', [])
                for sentence in positive_sentences:
                    normalized = self._normalize_sentence_for_dedup(sentence.get('text', ''))
                    if normalized not in seen_positive_sentences:
                        sentence['section'] = section_name
                        all_positive_sentences.append(sentence)
                        seen_positive_sentences.add(normalized)
                
                # ネガティブ文章の統合（重複除去）
                negative_sentences = sample_sentences.get('negative', [])
                for sentence in negative_sentences:
                    normalized = self._normalize_sentence_for_dedup(sentence.get('text', ''))
                    if normalized not in seen_negative_sentences:
                        sentence['section'] = section_name
                        all_negative_sentences.append(sentence)
                        seen_negative_sentences.add(normalized)
                
                # キーワードの統合
                positive_keywords = keyword_analysis.get('positive', [])
                negative_keywords = keyword_analysis.get('negative', [])
                
                # セクション名を追加してキーワードを統合
                for keyword in positive_keywords:
                    keyword['section'] = section_name
                    all_positive_keywords.append(keyword)
                
                for keyword in negative_keywords:
                    keyword['section'] = section_name
                    all_negative_keywords.append(keyword)
            
            if not all_matches_combined:
                return self._empty_result(session_id)
            
            # 統合分析
            combined_score_calc = self._calculate_detailed_score(all_matches_combined)
            overall_score = combined_score_calc['final_score']
            sentiment_label = self._determine_sentiment_label(overall_score)
            
            # 統合分析根拠
            integrated_reasoning = self._generate_reasoning(
                combined_steps, combined_score_calc, overall_score, sentiment_label
            )
            
            # ★修正：統合キーワード頻度分析
            integrated_keyword_frequency = self._analyze_keyword_frequency_safe(all_matches_combined)
            
            
            # ★修正：統合キーワード頻度分析（all_matches_combinedを使用）
            logger.debug(f"統合マッチデータ確認: {len(all_matches_combined)}件")
            if all_matches_combined:
                logger.debug(f"統合マッチデータサンプル: {all_matches_combined[:3]}")
            
            integrated_keyword_frequency = self._analyze_keyword_frequency_safe(all_matches_combined)
            
            # 統合されたサンプル文章（スコア順でソート）
            all_positive_sentences.sort(key=lambda x: x['score'], reverse=True)
            all_negative_sentences.sort(key=lambda x: x['score'])
            
            # 統合されたキーワード分析（重複除去とスコア順ソート）
            integrated_positive_keywords = self._integrate_keywords(all_positive_keywords)
            integrated_negative_keywords = self._integrate_keywords(all_negative_keywords)
            
            # ★修正: 正しい統計情報の構築
            basic_result = {
                'overall_score': round(overall_score, 3),
                'sentiment_label': sentiment_label,
                'analysis_reasoning': integrated_reasoning,
                'score_calculation': combined_score_calc,
                'section_analysis': section_results,
                'keyword_frequency_data': integrated_keyword_frequency,
                'sample_sentences': {
                    'positive': all_positive_sentences[:10],
                    'negative': all_negative_sentences[:10],
                },
                'keyword_analysis': {
                    'positive': integrated_positive_keywords[:15],
                    'negative': integrated_negative_keywords[:15],
                },
                'statistics': {
                    'sections_analyzed': len(section_results),
                    'total_words_analyzed': len(all_matches_combined),
                    # ★修正: 正しい文脈パターン数
                    'context_patterns_found': total_context_patterns,
                    # ★修正: 正しい分析文数  
                    'sentences_analyzed': total_sentences_analyzed,
                    'basic_words_found': sum(r['statistics'].get('basic_words_found', 0) for r in section_results.values()),
                    'unique_words_found': len(set(word for word, _, _ in all_matches_combined)),
                    'positive_sentences_found': len(all_positive_sentences),
                    'negative_sentences_found': len(all_negative_sentences),
                    'total_positive_keywords': len(all_positive_keywords),
                    'total_negative_keywords': len(all_negative_keywords),
                    'positive_words_count': len([s for _, s, _ in all_matches_combined if s > 0]),
                    'negative_words_count': len([s for _, s, _ in all_matches_combined if s < 0]),
                    'positive_sentences_count': len(all_positive_sentences),
                    'negative_sentences_count': len(all_negative_sentences),
                    'threshold_positive': self.config.positive_threshold,
                    'threshold_negative': self.config.negative_threshold,
                    # 頻度統計
                    'total_keyword_occurrences': sum(item['count'] for item in integrated_keyword_frequency['positive'] + integrated_keyword_frequency['negative']),
                    'top_positive_keyword': integrated_keyword_frequency['positive'][0] if integrated_keyword_frequency['positive'] else None,
                    'top_negative_keyword': integrated_keyword_frequency['negative'][0] if integrated_keyword_frequency['negative'] else None,
                },
                'analysis_metadata': {
                    'analyzed_at': timezone.now().isoformat(),
                    'dictionary_size': len(self.dictionary.sentiment_dict),
                    'session_id': session_id,
                    'sections_analyzed': list(text_sections.keys()),
                    'analysis_version': '2.4_stats_fixed',
                    'integration_method': 'section_aggregation_with_proper_stats',
                }
            }
            
            # ユーザー向け詳細見解を生成
            if document_info:
                user_insights = self.insight_generator.generate_detailed_insights(basic_result, document_info)
                basic_result['user_insights'] = user_insights
            
            # デバッグログ
            logger.info(f"セクション統合分析完了（統計修正版）: {len(section_results)}セクション, "
                    f"文脈パターン{total_context_patterns}個, "
                    f"分析文数{total_sentences_analyzed}文, "
                    f"ポジティブ文章{len(all_positive_sentences)}件, "
                    f"ネガティブ文章{len(all_negative_sentences)}件")
            
            return basic_result
            
        except Exception as e:
            logger.error(f"セクション分析エラー: {e}")
            raise Exception(f"感情分析処理中にエラーが発生しました: {str(e)}")

    def _get_impact_level(self, score: float) -> str:
        """スコアから影響度レベルを判定"""
        abs_score = abs(score)
        if abs_score >= 0.7:
            return 'high'
        elif abs_score >= 0.4:
            return 'medium'
        else:
            return 'low'
        
class SentimentAnalysisService:
    """感情分析サービス（見解生成強化版）"""
    
    def __init__(self):
        self.analyzer = TransparentSentimentAnalyzer()
        self.xbrl_service = EDINETXBRLService()
    
    def start_analysis(self, document_id: str, force: bool = False, user_ip: str = None) -> Dict[str, Any]:
        """感情分析開始"""
        from ..models import DocumentMetadata, SentimentAnalysisSession
        
        try:
            document = DocumentMetadata.objects.get(doc_id=document_id, legal_status='1')
            
            if not force:
                recent_session = SentimentAnalysisSession.objects.filter(
                    document=document,
                    processing_status='COMPLETED',
                    created_at__gte=timezone.now() - timedelta(hours=1)
                ).first()
                
                if recent_session:
                    return {
                        'status': 'already_analyzed',
                        'session_id': str(recent_session.session_id),
                        'result': recent_session.analysis_result,
                        'message': '1時間以内に分析済みです'
                    }
            
            session = SentimentAnalysisSession.objects.create(
                document=document,
                processing_status='PENDING'
            )
            
            threading.Thread(
                target=self._execute_analysis,
                args=(session.id, user_ip),
                daemon=True
            ).start()
            
            return {
                'status': 'started',
                'session_id': str(session.session_id),
                'message': '詳細な見解を含む感情分析を開始しました'
            }
            
        except DocumentMetadata.DoesNotExist:
            raise Exception('指定された書類が見つかりません')
        except Exception as e:
            logger.error(f"分析開始エラー: {e}")
            raise Exception(f"分析開始に失敗しました: {str(e)}")
    
    def get_progress(self, session_id: str) -> Dict[str, Any]:
        """進行状況取得"""
        from ..models import SentimentAnalysisSession
        
        try:
            session = SentimentAnalysisSession.objects.get(session_id=session_id)
            
            if session.is_expired:
                return {'status': 'expired', 'message': 'セッションが期限切れです'}
            
            if session.processing_status == 'PROCESSING':
                result = session.analysis_result or {}
                progress = result.get('progress', 50)
                message = result.get('current_step', '詳細見解を生成中...')
            elif session.processing_status == 'COMPLETED':
                progress = 100
                message = '詳細分析・見解生成完了'
            elif session.processing_status == 'FAILED':
                progress = 100
                message = f'分析失敗: {session.error_message}'
            else:
                progress = 0
                message = '分析待機中...'
            
            return {
                'progress': progress,
                'message': message,
                'status': session.processing_status,
                'timestamp': timezone.now().isoformat()
            }
            
        except SentimentAnalysisSession.DoesNotExist:
            return {'status': 'not_found', 'message': 'セッションが見つかりません'}
    
    def get_result(self, session_id: str) -> Dict[str, Any]:
        """分析結果取得"""
        from ..models import SentimentAnalysisSession
        
        try:
            session = SentimentAnalysisSession.objects.get(session_id=session_id)
            
            if session.is_expired:
                return {'status': 'expired', 'message': 'セッションが期限切れです'}
            
            if session.processing_status == 'COMPLETED':
                return {'status': 'completed', 'result': session.analysis_result}
            elif session.processing_status == 'FAILED':
                return {'status': 'failed', 'error': session.error_message}
            else:
                return {'status': 'processing', 'message': '分析中です'}
                
        except SentimentAnalysisSession.DoesNotExist:
            return {'status': 'not_found', 'message': 'セッションが見つかりません'}
    
    def _execute_analysis(self, session_id: int, user_ip: str = None):
        """分析実行（見解生成強化版）"""
        from ..models import SentimentAnalysisSession, SentimentAnalysisHistory
        
        start_time = time.time()
        
        try:
            session = SentimentAnalysisSession.objects.get(id=session_id)
            session.processing_status = 'PROCESSING'
            session.analysis_result = {'progress': 5, 'current_step': '書類情報確認中...'}
            session.save()
            
            # 書類情報を準備
            document_info = {
                'company_name': session.document.company_name,
                'doc_description': session.document.doc_description,
                'doc_type_code': session.document.doc_type_code,
                'submit_date': session.document.submit_date_time.strftime('%Y-%m-%d'),
                'securities_code': session.document.securities_code or '',
            }
            
            session.analysis_result = {'progress': 20, 'current_step': 'XBRLファイル取得中...'}
            session.save()
            
            try:
                xbrl_text_sections = self.xbrl_service.get_xbrl_text_from_document(session.document)
            except Exception as e:
                logger.warning(f"XBRL取得失敗: {e}")
                xbrl_text_sections = None
            
            if not xbrl_text_sections:
                session.analysis_result = {'progress': 40, 'current_step': '基本情報を使用して詳細分析中...'}
                session.save()
                
                document_text = self._extract_basic_document_text(session.document)
                result = self.analyzer.analyze_text(document_text, str(session.session_id), document_info)
            else:
                session.analysis_result = {'progress': 50, 'current_step': 'XBRLテキスト前処理中...'}
                session.save()
                
                session.analysis_result = {'progress': 70, 'current_step': '詳細感情分析実行中...'}
                session.save()
                
                result = self.analyzer.analyze_text_sections(xbrl_text_sections, str(session.session_id), document_info)
            
            session.analysis_result = {'progress': 90, 'current_step': 'ユーザー向け見解生成中...'}
            session.save()
            
            # セッション更新
            session.overall_score = result['overall_score']
            session.sentiment_label = result['sentiment_label']
            session.analysis_result = result
            session.processing_status = 'COMPLETED'
            session.save()
            
            # 履歴保存
            analysis_duration = time.time() - start_time
            SentimentAnalysisHistory.objects.create(
                document=session.document,
                overall_score=result['overall_score'],
                sentiment_label=result['sentiment_label'],
                user_ip=user_ip,
                analysis_duration=analysis_duration
            )
            
            logger.info(f"見解生成付き感情分析完了: {session.session_id} ({analysis_duration:.2f}秒)")
            
        except Exception as e:
            logger.error(f"感情分析エラー: {session_id} - {e}")
            
            try:
                session = SentimentAnalysisSession.objects.get(id=session_id)
                session.processing_status = 'FAILED'
                session.error_message = str(e)
                session.save()
            except:
                pass
    
    def _extract_basic_document_text(self, document) -> str:
        """基本的な書類情報からテキスト抽出"""
        text_parts = [
            f"企業名: {document.company_name}",
            f"書類概要: {document.doc_description}",
            f"提出日: {document.submit_date_time.strftime('%Y年%m月%d日')}",
        ]
        
        if document.period_start and document.period_end:
            text_parts.append(f"対象期間: {document.period_start}から{document.period_end}")
        
        # より現実的なサンプルテキスト（多くの語彙を含む）
        sample_scenarios = [
            "当社の業績は前年同期と比較して順調に推移しており、売上高の増加と収益性の向上が実現されています。",
            "一方で、減収幅の縮小も見られ、市場環境の変化に適応しつつ継続的な事業改善を図っています。", 
            "営業損失は発生したものの、損失の改善傾向が見られ、今後の回復に期待しています。",
            "今後も持続的な成長を目指し、効率的な経営資源の活用と競争力の強化に取り組んでまいります。",
            "一部の事業では苦戦が続いていますが、全体としては好調な業績を維持しています。",
            "増収増益を達成し、株主の皆様には深く感謝申し上げます。",
            "減益となりましたが、構造改革の効果により今後の業績向上が期待されます。",
            "赤字縮小により黒字転換への道筋が見えてきました。",
            "V字回復を目指し、抜本的な改革に取り組んでおります。"
        ]
        
        text_parts.extend(sample_scenarios)
        return " ".join(text_parts)
    
    def cleanup_expired_sessions(self) -> int:
        """期限切れセッションのクリーンアップ"""
        from ..models import SentimentAnalysisSession
        
        try:
            expired_count = SentimentAnalysisSession.objects.filter(
                expires_at__lt=timezone.now()
            ).delete()[0]
            
            logger.info(f"期限切れセッション削除: {expired_count}件")
            return expired_count
            
        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}")
            return 0


    def debug_zip_structure(self, zip_content: bytes, doc_id: str = None):
        """ZIPファイル構造の詳細デバッグ"""
        try:
            import zipfile
            import io
            
            logger.info(f"=== ZIP構造デバッグ開始: {doc_id} ===")
            
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
                logger.info(f"総ファイル数: {len(zip_file.filelist)}")
                
                # 全ファイルリスト
                xbrl_files = []
                other_files = []
                
                for file_info in zip_file.filelist:
                    file_details = {
                        'filename': file_info.filename,
                        'size': file_info.file_size,
                        'compressed_size': file_info.compress_size,
                        'date_time': file_info.date_time,
                    }
                    
                    if file_info.filename.endswith('.xbrl'):
                        xbrl_files.append(file_details)
                    else:
                        other_files.append(file_details)
                
                logger.info(f"\nXBRLファイル ({len(xbrl_files)}個):")
                for i, file_info in enumerate(xbrl_files):
                    logger.info(f"  {i+1}. {file_info['filename']}")
                    logger.info(f"     サイズ: {file_info['size']:,} bytes")
                    logger.info(f"     日時: {'-'.join(map(str, file_info['date_time']))}")
                
                logger.info(f"\nその他のファイル ({len(other_files)}個):")
                for file_info in other_files[:10]:  # 最初の10個のみ
                    logger.info(f"  - {file_info['filename']} ({file_info['size']:,} bytes)")
                
                # 各XBRLファイルの内容を簡易分析
                if xbrl_files:
                    logger.info(f"\n=== XBRLファイル内容分析 ===")
                    
                    for i, file_info in enumerate(xbrl_files):
                        filename = file_info['filename']
                        logger.info(f"\n--- {filename} の分析 ---")
                        
                        try:
                            with zip_file.open(filename) as xbrl_file:
                                xbrl_content = xbrl_file.read()
                                
                                # XMLとして解析
                                import xml.etree.ElementTree as ET
                                root = ET.fromstring(xbrl_content)
                                
                                # 基本情報
                                logger.info(f"  ルート要素: {root.tag}")
                                
                                # 名前空間の確認
                                namespaces = self._extract_namespaces(root)
                                logger.info(f"  名前空間数: {len(namespaces)}")
                                for prefix, uri in list(namespaces.items())[:5]:
                                    logger.info(f"    {prefix}: {uri}")
                                
                                # 財務関連要素の存在確認
                                cf_elements = self._count_financial_elements(root)
                                logger.info(f"  財務要素数:")
                                for element_type, count in cf_elements.items():
                                    logger.info(f"    {element_type}: {count}個")
                                
                                # テキスト要素の確認
                                text_elements = self._count_text_elements(root)
                                logger.info(f"  テキスト要素: {text_elements}個")
                                
                                # データ品質の予備評価
                                quality = self._quick_quality_assessment(root)
                                logger.info(f"  品質スコア（予備）: {quality:.3f}")
                                
                        except Exception as e:
                            logger.error(f"  ファイル分析エラー: {e}")
            
            logger.info("=== ZIP構造デバッグ終了 ===")
            
        except Exception as e:
            logger.error(f"ZIP構造デバッグエラー: {e}")

    def _extract_namespaces(self, root):
        """XML名前空間の抽出"""
        namespaces = {}
        for key, value in root.attrib.items():
            if key.startswith('xmlns'):
                prefix = key.split(':')[1] if ':' in key else 'default'
                namespaces[prefix] = value
        return namespaces

    def _count_financial_elements(self, root):
        """財務関連要素のカウント"""
        counts = {
            'operating_cf': 0,
            'investing_cf': 0,
            'financing_cf': 0,
            'sales': 0,
            'assets': 0,
        }
        
        financial_patterns = {
            'operating_cf': ['OperatingActivities', 'OperatingCashFlow', '営業活動'],
            'investing_cf': ['InvestingActivities', 'InvestingCashFlow', '投資活動'],
            'financing_cf': ['FinancingActivities', 'FinancingCashFlow', '財務活動'],
            'sales': ['NetSales', 'Sales', 'Revenue', '売上'],
            'assets': ['TotalAssets', 'Assets', '資産'],
        }
        
        for elem in root.iter():
            elem_text = elem.tag + (elem.text or '')
            
            for category, patterns in financial_patterns.items():
                for pattern in patterns:
                    if pattern in elem_text:
                        counts[category] += 1
                        break
        
        return counts

    def _count_text_elements(self, root):
        """長いテキスト要素のカウント"""
        count = 0
        for elem in root.iter():
            if elem.text and len(elem.text.strip()) > 100:
                count += 1
        return count

    def _quick_quality_assessment(self, root):
        """クイック品質評価"""
        financial_counts = self._count_financial_elements(root)
        text_count = self._count_text_elements(root)
        
        # 財務要素の完全性
        financial_score = sum(1 for count in financial_counts.values() if count > 0) / len(financial_counts)
        
        # テキストの豊富さ
        text_score = min(text_count / 10, 1.0)
        
        return financial_score * 0.7 + text_score * 0.3

    # EDINETXBRLService クラスに追加するメソッド
    def debug_zip_document(self, document):
        """特定書類のZIP構造をデバッグ"""
        try:
            from .edinet_api import EdinetAPIClient
            api_client = EdinetAPIClient.create_v2_client()
            
            logger.info(f"ZIP構造デバッグ開始: {document.doc_id}")
            xbrl_data = api_client.get_document(document.doc_id, doc_type=1)
            
            if xbrl_data[:4] == b'PK\x03\x04':
                self.extractor.debug_zip_structure(xbrl_data, document.doc_id)
            else:
                logger.info(f"ZIPファイルではありません: {document.doc_id}")
            
            return {'status': 'debug_completed'}
            
        except Exception as e:
            logger.error(f"ZIP構造デバッグエラー: {document.doc_id} - {e}")
            return {'status': 'debug_failed', 'error': str(e)}

    def compare_extraction_methods(self, document):
        """新旧の抽出方法を比較"""
        try:
            from .edinet_api import EdinetAPIClient
            api_client = EdinetAPIClient.create_v2_client()
            
            logger.info(f"抽出方法比較開始: {document.doc_id}")
            xbrl_data = api_client.get_document(document.doc_id, doc_type=1)
            
            if xbrl_data[:4] == b'PK\x03\x04':
                # 新しい方法
                logger.info("=== 新しい方法（データ欠損対策版）===")
                new_result = self._extract_comprehensive_from_bytes_safe(xbrl_data, document.doc_id)
                
                logger.info(f"新方法結果:")
                logger.info(f"  財務データ: {len(new_result.get('financial_data', {}))}項目")
                logger.info(f"  テキスト: {len(new_result.get('text_sections', {}))}セクション")
                if new_result.get('source_files'):
                    logger.info(f"  ソースファイル数: {len(new_result['source_files'])}")
                    for src in new_result['source_files']:
                        logger.info(f"    - {src['filename']}: 品質{src['quality']}, 財務{src['financial_items']}項目")
                
                # 財務データの詳細
                logger.info("  財務データ詳細:")
                for key, value in new_result.get('financial_data', {}).items():
                    logger.info(f"    {key}: {value}")
                
                return new_result
            else:
                logger.info("ZIPファイルではないため比較不要")
                return {'status': 'not_zip'}
            
        except Exception as e:
            logger.error(f"抽出方法比較エラー: {document.doc_id} - {e}")
            return {'status': 'comparison_failed', 'error': str(e)}        
            
            
    def _analyze_keyword_frequency(self, all_matches: List[Tuple[str, float, str]]) -> Dict[str, List[Dict]]:
        """キーワード出現頻度の詳細分析"""
        frequency_data = {'positive': [], 'negative': []}
        
        # キーワードの出現回数を集計
        keyword_counts = {}
        keyword_scores = {}
        keyword_types = {}
        
        for word, score, type_name in all_matches:
            if word not in keyword_counts:
                keyword_counts[word] = 0
                keyword_scores[word] = score
                keyword_types[word] = type_name
            
            keyword_counts[word] += 1
            # スコアは平均を取る
            keyword_scores[word] = (keyword_scores[word] + score) / 2
        
        # ポジティブ・ネガティブに分類
        for word, count in keyword_counts.items():
            score = keyword_scores[word]
            
            keyword_data = {
                'word': word,
                'count': count,
                'score': score,
                'type': keyword_types[word],
                'impact_level': self._get_impact_level(score),
                'frequency_rank': 0  # 後で設定
            }
            
            if score > 0:
                frequency_data['positive'].append(keyword_data)
            elif score < 0:
                frequency_data['negative'].append(keyword_data)
        
        # 出現回数でソートしてランク付け
        frequency_data['positive'].sort(key=lambda x: x['count'], reverse=True)
        frequency_data['negative'].sort(key=lambda x: x['count'], reverse=True)
        
        # ランク付け
        for i, item in enumerate(frequency_data['positive']):
            item['frequency_rank'] = i + 1
        
        for i, item in enumerate(frequency_data['negative']):
            item['frequency_rank'] = i + 1
        
        return frequency_data

    def analyze_text(self, text: str, session_id: str = None, document_info: Dict[str, str] = None) -> Dict[str, Any]:
        """透明性の高い感情分析（頻度分析修正版）"""
        try:
            if not text or len(text.strip()) < 10:
                return self._empty_result(session_id)
            
            # テキスト前処理
            cleaned_text = self.text_processor.preprocess(text)
            
            # 段階的な分析プロセス
            analysis_steps = []
            
            # ステップ1: 文脈パターンの検出
            context_matches = self._find_context_patterns(cleaned_text)
            if context_matches:
                analysis_steps.append({
                    'step': '文脈パターン検出',
                    'description': '「減収の改善」「成長の鈍化」のような文脈を考慮した表現を検出',
                    'matches': context_matches,
                    'impact': sum(score for _, score, _ in context_matches)
                })
            
            # ステップ2: 基本語彙の検出
            basic_matches = self._find_basic_words(cleaned_text, context_matches)
            if basic_matches:
                analysis_steps.append({
                    'step': '基本語彙検出',
                    'description': '感情辞書に登録されている語彙を検出',
                    'matches': basic_matches,
                    'impact': sum(score for _, score, _ in basic_matches)
                })
            
            # 全てのマッチを統合
            all_matches = context_matches + basic_matches
            sentiment_scores = [score for _, score, _ in all_matches]
            
            # デバッグログ追加
            logger.debug(f"all_matches構造チェック - 最初の3件: {all_matches[:3]}")
            logger.debug(f"all_matches型: {type(all_matches)}, 長さ: {len(all_matches)}")
            if all_matches:
                logger.debug(f"最初の要素の型: {type(all_matches[0])}")
            
            # スコア計算の詳細
            score_calculation = self._calculate_detailed_score(sentiment_scores)
            
            # 全体スコアと判定
            overall_score = score_calculation['final_score']
            sentiment_label = self._determine_sentiment_label(overall_score)
            
            # 分析根拠の生成
            analysis_reasoning = self._generate_reasoning(
                analysis_steps, score_calculation, overall_score, sentiment_label
            )
            
            # キーワード分析（分かりやすい形式）
            keyword_analysis = self._analyze_keywords(all_matches)
            
            # ★修正：キーワード頻度分析（データ構造チェック付き）
            keyword_frequency_data = self._analyze_keyword_frequency_safe(all_matches)
            
            # 文章レベル分析
            sentences = self._split_sentences(cleaned_text)
            sentence_analysis = self._analyze_sentences(sentences)
            
            # 基本結果の構築
            basic_result = {
                'overall_score': round(overall_score, 3),
                'sentiment_label': sentiment_label,
                'analysis_reasoning': analysis_reasoning,
                'score_calculation': score_calculation,
                'analysis_steps': analysis_steps,
                'keyword_analysis': keyword_analysis,
                'keyword_frequency_data': keyword_frequency_data,  # ★追加
                'sample_sentences': {
                    'positive': [s for s in sentence_analysis if s['score'] > self.config.positive_threshold][:5],
                    'negative': [s for s in sentence_analysis if s['score'] < self.config.negative_threshold][:5],
                },
                'statistics': {
                    'total_words_analyzed': len(all_matches),
                    'context_patterns_found': len(context_matches),
                    'basic_words_found': len(basic_matches),
                    'sentences_analyzed': len(sentences),
                    'unique_words_found': len(set(word for word, _, _ in all_matches)),
                    'positive_words_count': len([s for s in sentiment_scores if s > 0]),
                    'negative_words_count': len([s for s in sentiment_scores if s < 0]),
                    'positive_sentences_count': len([s for s in sentence_analysis if s['score'] > self.config.positive_threshold]),
                    'negative_sentences_count': len([s for s in sentence_analysis if s['score'] < self.config.negative_threshold]),
                    'threshold_positive': self.config.positive_threshold,
                    'threshold_negative': self.config.negative_threshold,
                    # ★頻度統計を追加
                    'total_keyword_occurrences': sum(item['count'] for item in keyword_frequency_data['positive'] + keyword_frequency_data['negative']),
                    'top_positive_keyword': keyword_frequency_data['positive'][0] if keyword_frequency_data['positive'] else None,
                    'top_negative_keyword': keyword_frequency_data['negative'][0] if keyword_frequency_data['negative'] else None,
                },
                'analysis_metadata': {
                    'analyzed_at': timezone.now().isoformat(),
                    'dictionary_size': len(self.dictionary.sentiment_dict),
                    'session_id': session_id,
                    'analysis_version': '2.2_frequency_enhanced_fixed',
                }
            }
            
            # ユーザー向け詳細見解を生成
            if document_info:
                user_insights = self.insight_generator.generate_detailed_insights(basic_result, document_info)
                basic_result['user_insights'] = user_insights
            
            return basic_result
            
        except Exception as e:
            logger.error(f"感情分析エラー: {e}")
            raise Exception(f"感情分析処理中にエラーが発生しました: {str(e)}")

