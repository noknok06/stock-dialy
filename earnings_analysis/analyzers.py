# earnings_analysis/analyzers.py
import re
from typing import Dict, List, Tuple, Optional
from decimal import Decimal, InvalidOperation
import logging
from collections import Counter

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """感情分析・経営陣自信度分析クラス"""
    
    def __init__(self):
        # ポジティブ表現キーワード
        self.positive_keywords = [
            '好調', '堅調', '順調', '成長', '拡大', '改善', '向上', '増加', '回復', '安定',
            '強い', '高い', '良好', '優秀', '優位', '競争力', 'トップ', 'リーダー',
            '期待', '見込み', '予想上回る', '上振れ', '好転', '明るい', '確信',
            '自信', '積極的', '前向き', 'ポジティブ', '楽観', '期待以上'
        ]
        
        # ネガティブ表現キーワード
        self.negative_keywords = [
            '低迷', '悪化', '減少', '下落', '困難', '厳しい', '苦戦', '不振', '低下',
            '弱い', '低い', '不調', '不安', '懸念', '心配', '課題', '問題', '困難',
            '予想下回る', '下振れ', '悪影響', 'リスク', '不透明', '不確実',
            '慎重', '警戒', 'ネガティブ', '悲観', '失望'
        ]
        
        # 自信表現キーワード
        self.confidence_keywords = [
            '確信', '自信', '間違いない', '必ず', 'きっと', '確実', '断言',
            '約束', '保証', '確約', '達成できる', '成功する', '実現する',
            '強く信じる', '確信している', '期待している', '見込んでいる'
        ]
        
        # 不確実性表現キーワード
        self.uncertainty_keywords = [
            '不明', '不透明', '不確実', '未定', '検討中', '予測困難', '見通せない',
            '分からない', 'わからない', '判断が難しい', '見極めが必要',
            '様子を見る', '慎重に', '状況次第', '場合によっては', 'かもしれない',
            '可能性がある', '恐れがある', '懸念される'
        ]
        
        # リスク言及キーワード
        self.risk_keywords = [
            'リスク', '危険', '脅威', '不安要因', 'リスク要因', '懸念事項',
            '不確実性', '変動', 'ボラティリティ', '市場リスク', '信用リスク',
            '流動性リスク', '為替リスク', '金利リスク', '競合リスク',
            '規制リスク', '技術リスク', 'システムリスク'
        ]
    
    def analyze_sentiment(self, text_sections: Dict[str, str]) -> Dict:
        """
        テキストの感情分析を実行
        
        Args:
            text_sections: セクション別テキスト辞書
            
        Returns:
            分析結果辞書
        """
        all_text = ' '.join(text_sections.values())
        
        # キーワードカウント
        positive_count = self._count_keywords(all_text, self.positive_keywords)
        negative_count = self._count_keywords(all_text, self.negative_keywords)
        confidence_count = self._count_keywords(all_text, self.confidence_keywords)
        uncertainty_count = self._count_keywords(all_text, self.uncertainty_keywords)
        risk_count = self._count_keywords(all_text, self.risk_keywords)
        
        # 感情スコア計算（-100 〜 +100）
        total_emotional = positive_count + negative_count
        if total_emotional > 0:
            sentiment_score = ((positive_count - negative_count) / total_emotional) * 100
        else:
            sentiment_score = 0
        
        # 経営陣自信度判定
        confidence_level = self._determine_confidence_level(
            confidence_count, uncertainty_count, positive_count, negative_count
        )
        
        # 抽出されたキーワードの詳細
        extracted_keywords = {
            'positive': self._extract_matched_keywords(all_text, self.positive_keywords),
            'negative': self._extract_matched_keywords(all_text, self.negative_keywords),
            'confidence': self._extract_matched_keywords(all_text, self.confidence_keywords),
            'uncertainty': self._extract_matched_keywords(all_text, self.uncertainty_keywords),
            'risk': self._extract_matched_keywords(all_text, self.risk_keywords)
        }
        
        # 分析要約を生成
        analysis_summary = self._generate_sentiment_summary(
            sentiment_score, confidence_level, positive_count, negative_count,
            confidence_count, uncertainty_count, risk_count
        )
        
        return {
            'positive_expressions': positive_count,
            'negative_expressions': negative_count,
            'confidence_keywords': confidence_count,
            'uncertainty_keywords': uncertainty_count,
            'risk_mentions': risk_count,
            'sentiment_score': round(sentiment_score, 2),
            'confidence_level': confidence_level,
            'extracted_keywords': extracted_keywords,
            'analysis_summary': analysis_summary
        }
    
    def _count_keywords(self, text: str, keywords: List[str]) -> int:
        """テキスト内のキーワード出現回数をカウント"""
        count = 0
        text_lower = text.lower()
        
        for keyword in keywords:
            # 部分一致でカウント
            count += len(re.findall(re.escape(keyword), text_lower))
        
        return count
    
    def _extract_matched_keywords(self, text: str, keywords: List[str]) -> List[Dict]:
        """マッチしたキーワードとその文脈を抽出"""
        matches = []
        text_lower = text.lower()
        
        for keyword in keywords:
            positions = [m.start() for m in re.finditer(re.escape(keyword), text_lower)]
            
            for pos in positions[:3]:  # 最大3つまで
                # 前後30文字の文脈を取得
                start = max(0, pos - 30)
                end = min(len(text), pos + len(keyword) + 30)
                context = text[start:end].strip()
                
                matches.append({
                    'keyword': keyword,
                    'context': context,
                    'position': pos
                })
        
        return matches[:10]  # 最大10件まで
    
    def _determine_confidence_level(self, confidence_count: int, uncertainty_count: int,
                                   positive_count: int, negative_count: int) -> str:
        """経営陣の自信度を判定"""
        
        # 自信表現と不確実性表現の比率
        confidence_ratio = confidence_count / max(1, confidence_count + uncertainty_count)
        
        # ポジティブ・ネガティブ表現の比率
        positive_ratio = positive_count / max(1, positive_count + negative_count)
        
        # 総合判定
        overall_score = (confidence_ratio * 0.6) + (positive_ratio * 0.4)
        
        if overall_score >= 0.8:
            return 'very_high'
        elif overall_score >= 0.6:
            return 'high'
        elif overall_score >= 0.4:
            return 'moderate'
        elif overall_score >= 0.2:
            return 'low'
        else:
            return 'very_low'
    
    def _generate_sentiment_summary(self, sentiment_score: float, confidence_level: str,
                                   positive: int, negative: int, confidence: int,
                                   uncertainty: int, risk: int) -> str:
        """感情分析の要約を生成"""
        
        # 感情傾向
        if sentiment_score > 20:
            sentiment_trend = "ポジティブな表現が多く"
        elif sentiment_score < -20:
            sentiment_trend = "ネガティブな表現が多く"
        else:
            sentiment_trend = "中立的な表現で"
        
        # 自信度説明
        confidence_descriptions = {
            'very_high': '経営陣の自信度は非常に高い',
            'high': '経営陣の自信度は高い',
            'moderate': '経営陣の自信度は普通',
            'low': '経営陣の自信度は低い',
            'very_low': '経営陣の自信度は非常に低い'
        }
        
        confidence_desc = confidence_descriptions.get(confidence_level, '判定困難')
        
        # リスク言及状況
        if risk > 10:
            risk_desc = "リスクへの言及が多い"
        elif risk > 5:
            risk_desc = "適度にリスクに言及"
        else:
            risk_desc = "リスクへの言及は少ない"
        
        return f"{sentiment_trend}、{confidence_desc}。{risk_desc}状況です。"


class CashFlowAnalyzer:
    """キャッシュフロー分析クラス"""
    
    def __init__(self):
        # CFパターンの判定基準（百万円単位）
        self.cf_threshold = 1000  # 1億円
    
    def analyze_cashflow_pattern(self, operating_cf: float, investing_cf: float,
                                financing_cf: float) -> Dict:
        """
        キャッシュフローパターンを分析
        
        Args:
            operating_cf: 営業CF（百万円）
            investing_cf: 投資CF（百万円）
            financing_cf: 財務CF（百万円）
            
        Returns:
            分析結果辞書
        """
        
        # CFの符号を判定
        op_positive = operating_cf > self.cf_threshold
        inv_negative = investing_cf < -self.cf_threshold
        fin_negative = financing_cf < -self.cf_threshold
        
        op_negative = operating_cf < -self.cf_threshold
        inv_positive = investing_cf > self.cf_threshold
        fin_positive = financing_cf > self.cf_threshold
        
        # パターン判定
        cf_pattern = self._determine_cf_pattern(
            op_positive, op_negative, inv_negative, inv_positive,
            fin_negative, fin_positive
        )
        
        # 健全性スコア計算
        health_score = self._calculate_health_score(
            operating_cf, investing_cf, financing_cf, cf_pattern
        )
        
        # フリーキャッシュフロー計算
        free_cf = operating_cf + investing_cf
        
        # 分析要約生成
        analysis_summary = self._generate_cf_summary(
            cf_pattern, health_score, operating_cf, investing_cf, financing_cf, free_cf
        )
        
        # リスク要因の特定
        risk_factors = self._identify_risk_factors(
            operating_cf, investing_cf, financing_cf, cf_pattern
        )
        
        return {
            'cf_pattern': cf_pattern,
            'health_score': health_score,
            'free_cf': free_cf,
            'analysis_summary': analysis_summary,
            'risk_factors': risk_factors
        }
    
    def _determine_cf_pattern(self, op_pos: bool, op_neg: bool, inv_neg: bool,
                             inv_pos: bool, fin_neg: bool, fin_pos: bool) -> str:
        """CFパターンを判定"""
        
        # 理想型: +営業CF, -投資CF, -財務CF
        if op_pos and inv_neg and fin_neg:
            return 'ideal'
        
        # 成長型: +営業CF, -投資CF, +財務CF
        elif op_pos and inv_neg and fin_pos:
            return 'growth'
        
        # 危険型: -営業CF, +投資CF, +財務CF
        elif op_neg and inv_pos and fin_pos:
            return 'danger'
        
        # 回復型: +営業CF, +投資CF, -財務CF
        elif op_pos and inv_pos and fin_neg:
            return 'recovery'
        
        # リストラ型: -営業CF, +投資CF, -財務CF
        elif op_neg and inv_pos and fin_neg:
            return 'restructuring'
        
        # その他
        else:
            return 'unknown'
    
    def _calculate_health_score(self, operating_cf: float, investing_cf: float,
                               financing_cf: float, cf_pattern: str) -> str:
        """健全性スコアを算出"""
        
        score = 0
        
        # 営業CFの評価
        if operating_cf > 10000:  # 100億円以上
            score += 40
        elif operating_cf > 1000:  # 10億円以上
            score += 30
        elif operating_cf > 0:
            score += 20
        elif operating_cf > -1000:
            score += 10
        else:
            score += 0
        
        # パターンボーナス
        pattern_bonus = {
            'ideal': 30,
            'growth': 20,
            'recovery': 10,
            'restructuring': 5,
            'unknown': 0,
            'danger': -20
        }
        score += pattern_bonus.get(cf_pattern, 0)
        
        # フリーCFの評価
        free_cf = operating_cf + investing_cf
        if free_cf > 5000:
            score += 20
        elif free_cf > 0:
            score += 10
        elif free_cf > -5000:
            score += 0
        else:
            score -= 10
        
        # スコアを5段階に変換
        if score >= 80:
            return 'excellent'
        elif score >= 60:
            return 'good'
        elif score >= 40:
            return 'fair'
        elif score >= 20:
            return 'poor'
        else:
            return 'critical'
    
    def _generate_cf_summary(self, pattern: str, health: str, op_cf: float,
                            inv_cf: float, fin_cf: float, free_cf: float) -> str:
        """CF分析要約を生成"""
        
        pattern_descriptions = {
            'ideal': 'トヨタ型の理想的なキャッシュフローパターン',
            'growth': 'テスラ型の成長投資パターン',
            'danger': '破綻企業型の危険なパターン',
            'recovery': '回復段階のパターン',
            'restructuring': '事業再構築パターン',
            'unknown': '特殊なパターン'
        }
        
        health_descriptions = {
            'excellent': '非常に健全',
            'good': '健全',
            'fair': '普通',
            'poor': '要注意',
            'critical': '危険'
        }
        
        pattern_desc = pattern_descriptions.get(pattern, '不明')
        health_desc = health_descriptions.get(health, '不明')
        
        # 営業CFの状況
        if op_cf > 0:
            op_desc = f"営業CFは{op_cf:,.0f}百万円のプラス"
        else:
            op_desc = f"営業CFは{abs(op_cf):,.0f}百万円のマイナス"
        
        # フリーCFの状況
        if free_cf > 0:
            free_desc = f"フリーCFは{free_cf:,.0f}百万円のプラス"
        else:
            free_desc = f"フリーCFは{abs(free_cf):,.0f}百万円のマイナス"
        
        return f"{pattern_desc}を示しており、財務健全性は{health_desc}です。{op_desc}、{free_desc}となっています。"
    
    def _identify_risk_factors(self, op_cf: float, inv_cf: float,
                              fin_cf: float, pattern: str) -> str:
        """リスク要因を特定"""
        
        risks = []
        
        # 営業CFのリスク
        if op_cf < 0:
            risks.append("本業でキャッシュを生み出せていない")
        elif op_cf < 1000:
            risks.append("営業CFが小規模で事業の安定性に懸念")
        
        # パターン別リスク
        if pattern == 'danger':
            risks.append("営業赤字を投資の売却と借入で補っている危険な状態")
        elif pattern == 'growth':
            risks.append("成長投資が過度で財務負担が増加する可能性")
        elif pattern == 'restructuring':
            risks.append("事業再構築中で業績が不安定")
        
        # フリーCFのリスク
        free_cf = op_cf + inv_cf
        if free_cf < -5000:
            risks.append("大幅なフリーCFマイナスで資金繰りが厳しい")
        
        # 財務CFのリスク
        if fin_cf > 10000:
            risks.append("大規模な資金調達で借入負担が増加")
        
        return "、".join(risks) if risks else "特筆すべきリスク要因は見当たりません"
    
    def compare_with_previous(self, current_cf: Dict, previous_cf: Dict) -> Dict:
        """前期との比較分析"""
        
        changes = {}
        
        cf_items = ['operating_cf', 'investing_cf', 'financing_cf', 'free_cf']
        
        for item in cf_items:
            current_val = current_cf.get(item, 0)
            previous_val = previous_cf.get(item, 0)
            
            if previous_val != 0:
                change_rate = ((current_val - previous_val) / abs(previous_val)) * 100
            else:
                change_rate = 0 if current_val == 0 else 100
            
            changes[f'{item}_change_rate'] = round(change_rate, 2)
        
        # 変化の総合評価
        op_change = changes.get('operating_cf_change_rate', 0)
        free_change = changes.get('free_cf_change_rate', 0)
        
        if op_change > 10 and free_change > 10:
            trend = "大幅改善"
        elif op_change > 0 and free_change > 0:
            trend = "改善傾向"
        elif op_change < -10 or free_change < -10:
            trend = "悪化傾向"
        else:
            trend = "横ばい"
        
        changes['overall_trend'] = trend
        
        return changes