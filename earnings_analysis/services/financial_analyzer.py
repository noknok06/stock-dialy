# earnings_analysis/services/financial_analyzer.py（新規作成）
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from dataclasses import dataclass
from django.utils import timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

@dataclass
class CashFlowPattern:
    """キャッシュフローパターンの定義"""
    name: str
    description: str
    operating_cf: str  # '+', '-', '0'
    investing_cf: str  # '+', '-', '0'
    financing_cf: str  # '+', '-', '0'
    risk_level: str    # 'low', 'medium', 'high'
    interpretation: str
    examples: List[str]

@dataclass
class FinancialHealth:
    """財務健全性評価"""
    overall_score: float  # 0-100
    risk_level: str
    pattern: CashFlowPattern
    strengths: List[str]
    concerns: List[str]
    recommendations: List[str]

@dataclass
class ManagementConfidence:
    """経営陣の自信度評価"""
    confidence_score: float  # 0-100
    confidence_level: str
    positive_indicators: List[str]
    negative_indicators: List[str]
    key_phrases: List[str]

class FinancialAnalyzer:
    """財務分析エンジン"""
    
    def __init__(self):
        # キャッシュフローパターンの定義
        self.cf_patterns = {
            'ideal': CashFlowPattern(
                name='理想型',
                description='トヨタ型：稼いで→投資して→借金返済',
                operating_cf='+',
                investing_cf='-',
                financing_cf='-',
                risk_level='low',
                interpretation='本業で稼いだ資金で投資を行い、借金も返済している理想的な状態',
                examples=['トヨタ自動車', 'ソフトバンクグループ（一部期間）']
            ),
            'growth': CashFlowPattern(
                name='成長型',
                description='テスラ型：稼いで→投資して→更に資金調達',
                operating_cf='+',
                investing_cf='-',
                financing_cf='+',
                risk_level='medium',
                interpretation='本業で利益を出しながら、積極的な投資のために追加資金調達を行う成長企業パターン',
                examples=['Tesla', 'Amazon（成長期）', 'スタートアップ企業']
            ),
            'restructuring': CashFlowPattern(
                name='再建型',
                description='立て直し中：本業改善→資産売却→借金返済',
                operating_cf='+',
                investing_cf='+',
                financing_cf='-',
                risk_level='medium',
                interpretation='本業の回復と資産売却により資金を確保し、借金返済を進める再建パターン',
                examples=['JAL（再建期）', 'シャープ（再建期）']
            ),
            'mature_defensive': CashFlowPattern(
                name='成熟型',
                description='安定重視：本業で稼ぐ→投資控えめ→株主還元',
                operating_cf='+',
                investing_cf='0',
                financing_cf='-',
                risk_level='low',
                interpretation='成熟企業で安定した営業利益があり、大型投資は控えて株主還元重視',
                examples=['花王', 'KDDI', '成熟期の大手企業']
            ),
            'danger': CashFlowPattern(
                name='危険型',
                description='破綻企業型：赤字で→資産売却→借金増',
                operating_cf='-',
                investing_cf='+',
                financing_cf='+',
                risk_level='high',
                interpretation='本業の赤字を資産売却と借入で補っている危険な状態',
                examples=['破綻企業の典型例', 'リーマンショック後の企業']
            ),
            'declining': CashFlowPattern(
                name='衰退型',
                description='事業縮小：赤字→投資減らす→資金調達',
                operating_cf='-',
                investing_cf='-',
                financing_cf='+',
                risk_level='high',
                interpretation='本業の悪化により投資を削減し、運転資金のために借入を増やしている状態',
                examples=['斜陽産業企業', '業績不振企業']
            ),
        }
        
        # 経営陣の自信度を測るキーワード
        self.confidence_indicators = {
            'high_confidence': {
                'keywords': [
                    '確信', '自信', '強固', '堅実', '安定', '順調', '着実',
                    '期待を上回る', '計画通り', '順調に推移', '確実に実行',
                    '競争優位', '市場リーダー', '業界トップ', '圧倒的',
                    '積極的', '攻めの経営', '前向き', '楽観的'
                ],
                'score_impact': 1.5
            },
            'medium_confidence': {
                'keywords': [
                    '継続', '維持', '安定化', '改善傾向', '回復基調',
                    '計画的', '段階的', '着実な成長', '持続的'
                ],
                'score_impact': 1.0
            },
            'low_confidence': {
                'keywords': [
                    '課題', '困難', '厳しい', '不透明', '不確実', '懸念',
                    '慎重', '様子見', '検討中', '模索', '試行錯誤',
                    '予断を許さない', '注意深く', '慎重に検討'
                ],
                'score_impact': 0.5
            },
            'very_low_confidence': {
                'keywords': [
                    '危機', '深刻', '重大な問題', '抜本的見直し', '緊急',
                    'リストラ', '事業撤退', '大幅な方針転換', '非常事態'
                ],
                'score_impact': 0.2
            }
        }
    
    def analyze_cashflow_pattern(self, financial_data: Dict[str, Decimal]) -> Dict[str, Any]:
        """キャッシュフローパターン分析"""
        try:
            # キャッシュフローデータの取得
            operating_cf = financial_data.get('operating_cf', Decimal('0'))
            investing_cf = financial_data.get('investing_cf', Decimal('0'))
            financing_cf = financial_data.get('financing_cf', Decimal('0'))
            
            # パターン判定
            cf_pattern = self._determine_cf_pattern(operating_cf, investing_cf, financing_cf)
            
            # 数値分析
            total_cf = operating_cf + investing_cf + financing_cf
            
            # 前年同期比分析（データがあれば）
            trends = self._analyze_cf_trends(financial_data)
            
            return {
                'pattern': {
                    'name': cf_pattern.name,
                    'description': cf_pattern.description,
                    'risk_level': cf_pattern.risk_level,
                    'interpretation': cf_pattern.interpretation,
                },
                'amounts': {
                    'operating_cf': float(operating_cf),
                    'investing_cf': float(investing_cf),
                    'financing_cf': float(financing_cf),
                    'total_cf': float(total_cf),
                },
                'analysis': {
                    'strengths': self._identify_cf_strengths(cf_pattern, operating_cf, investing_cf, financing_cf),
                    'concerns': self._identify_cf_concerns(cf_pattern, operating_cf, investing_cf, financing_cf),
                    'key_insights': self._generate_cf_insights(cf_pattern, operating_cf, investing_cf, financing_cf),
                },
                'trends': trends,
            }
            
        except Exception as e:
            logger.error(f"キャッシュフロー分析エラー: {e}")
            return {'error': f'キャッシュフロー分析中にエラーが発生しました: {str(e)}'}
    
    def _determine_cf_pattern(self, operating_cf: Decimal, investing_cf: Decimal, financing_cf: Decimal) -> CashFlowPattern:
        """キャッシュフローパターンの判定"""
        # 符号によるパターン分類
        op_sign = '+' if operating_cf > 0 else '-' if operating_cf < 0 else '0'
        inv_sign = '+' if investing_cf > 0 else '-' if investing_cf < 0 else '0'
        fin_sign = '+' if financing_cf > 0 else '-' if financing_cf < 0 else '0'
        
        # パターンマッチング
        for pattern in self.cf_patterns.values():
            if (pattern.operating_cf == op_sign and 
                pattern.investing_cf == inv_sign and 
                pattern.financing_cf == fin_sign):
                return pattern
        
        # デフォルトパターン（その他）
        return CashFlowPattern(
            name='その他',
            description='特殊なキャッシュフローパターン',
            operating_cf=op_sign,
            investing_cf=inv_sign,
            financing_cf=fin_sign,
            risk_level='medium',
            interpretation='標準的なパターンに当てはまらない特殊な状況',
            examples=[]
        )
    
    def _identify_cf_strengths(self, pattern: CashFlowPattern, op_cf: Decimal, inv_cf: Decimal, fin_cf: Decimal) -> List[str]:
        """キャッシュフローの強み特定"""
        strengths = []
        
        if op_cf > 0:
            if op_cf > abs(inv_cf) + abs(fin_cf):
                strengths.append('営業活動で十分なキャッシュを創出')
            else:
                strengths.append('営業活動から安定したキャッシュフロー')
        
        if pattern.name == '理想型':
            strengths.extend([
                '自立した資金繰り',
                '健全な投資活動',
                '借入金の着実な返済'
            ])
        elif pattern.name == '成長型':
            strengths.extend([
                '成長のための積極的投資',
                '外部資金の効果的活用'
            ])
        
        return strengths
    
    def _identify_cf_concerns(self, pattern: CashFlowPattern, op_cf: Decimal, inv_cf: Decimal, fin_cf: Decimal) -> List[str]:
        """キャッシュフローの懸念点特定"""
        concerns = []
        
        if op_cf < 0:
            concerns.append('営業活動からのキャッシュフロー不足')
        
        if pattern.risk_level == 'high':
            concerns.extend([
                '財務状況の不安定性',
                '持続可能性への懸念'
            ])
        
        if pattern.name == '危険型':
            concerns.extend([
                '本業での資金創出力の不足',
                '資産売却への依存',
                '借入金の増加傾向'
            ])
        
        # 投資が極端に少ない場合
        if abs(inv_cf) < abs(op_cf) * Decimal('0.1'):
            concerns.append('将来への投資不足の可能性')
        
        return concerns
    
    def _generate_cf_insights(self, pattern: CashFlowPattern, op_cf: Decimal, inv_cf: Decimal, fin_cf: Decimal) -> List[str]:
        """キャッシュフロー洞察の生成"""
        insights = []
        
        # 基本パターンの解説
        insights.append(f"【{pattern.name}】{pattern.interpretation}")
        
        # 数値に基づく具体的な洞察
        if op_cf > 0:
            op_ratio = abs(inv_cf) / op_cf if op_cf != 0 else 0
            if op_ratio > 1:
                insights.append('営業CF以上の投資を行っており、成長への強い意欲が見られる')
            elif op_ratio > 0.5:
                insights.append('営業CFの半分以上を投資に充当し、バランス良い資金配分')
            else:
                insights.append('営業CFに対して投資は控えめで、資金の余裕がある状況')
        
        # リスクレベルに基づく洞察
        if pattern.risk_level == 'low':
            insights.append('財務リスクは低く、安定した経営基盤')
        elif pattern.risk_level == 'high':
            insights.append('財務リスクが高く、慎重な投資判断が必要')
        
        return insights
    
    def analyze_management_confidence(self, text_sections: Dict[str, str]) -> Dict[str, Any]:
        """経営陣の自信度分析"""
        try:
            # 全テキストを結合
            combined_text = ' '.join(text_sections.values())
            
            confidence_scores = []
            detected_phrases = []
            category_counts = {category: 0 for category in self.confidence_indicators.keys()}
            
            # カテゴリ別キーワード検出
            for category, info in self.confidence_indicators.items():
                for keyword in info['keywords']:
                    count = combined_text.count(keyword)
                    if count > 0:
                        category_counts[category] += count
                        confidence_scores.extend([info['score_impact']] * count)
                        detected_phrases.append(f"{keyword}({count}回)")
            
            # 総合自信度スコア算出
            if confidence_scores:
                avg_confidence = sum(confidence_scores) / len(confidence_scores)
                confidence_score = min(100, max(0, avg_confidence * 100))
            else:
                confidence_score = 50  # デフォルト
            
            # 自信度レベル判定
            if confidence_score >= 80:
                confidence_level = '非常に高い'
            elif confidence_score >= 60:
                confidence_level = '高い'
            elif confidence_score >= 40:
                confidence_level = '普通'
            elif confidence_score >= 20:
                confidence_level = '低い'
            else:
                confidence_level = '非常に低い'
            
            return {
                'confidence_score': confidence_score,
                'confidence_level': confidence_level,
                'category_breakdown': category_counts,
                'detected_phrases': detected_phrases[:20],  # 上位20個
                'analysis': {
                    'positive_indicators': self._extract_positive_confidence_indicators(text_sections),
                    'negative_indicators': self._extract_negative_confidence_indicators(text_sections),
                    'key_insights': self._generate_confidence_insights(confidence_score, category_counts),
                }
            }
            
        except Exception as e:
            logger.error(f"経営陣自信度分析エラー: {e}")
            return {'error': f'自信度分析中にエラーが発生しました: {str(e)}'}
    
    def _extract_positive_confidence_indicators(self, text_sections: Dict[str, str]) -> List[str]:
        """ポジティブな自信指標の抽出"""
        indicators = []
        
        positive_patterns = [
            r'業績.*?向上',
            r'売上.*?増加',
            r'利益.*?改善',
            r'市場.*?拡大',
            r'競争力.*?強化',
            r'順調.*?推移',
        ]
        
        combined_text = ' '.join(text_sections.values())
        
        for pattern in positive_patterns:
            import re
            matches = re.findall(pattern, combined_text)
            indicators.extend(matches[:3])  # 各パターンから最大3個
        
        return indicators[:10]  # 最大10個
    
    def _extract_negative_confidence_indicators(self, text_sections: Dict[str, str]) -> List[str]:
        """ネガティブな自信指標の抽出"""
        indicators = []
        
        negative_patterns = [
            r'課題.*?深刻',
            r'業績.*?悪化',
            r'売上.*?減少',
            r'市場.*?縮小',
            r'競争.*?激化',
            r'不透明.*?状況',
        ]
        
        combined_text = ' '.join(text_sections.values())
        
        for pattern in negative_patterns:
            import re
            matches = re.findall(pattern, combined_text)
            indicators.extend(matches[:3])
        
        return indicators[:10]
    
    def _generate_confidence_insights(self, confidence_score: float, category_counts: Dict[str, int]) -> List[str]:
        """自信度に関する洞察生成"""
        insights = []
        
        # スコアベースの洞察
        if confidence_score >= 80:
            insights.append('経営陣は事業戦略に非常に強い自信を示している')
        elif confidence_score >= 60:
            insights.append('経営陣は前向きで自信のある姿勢を示している')
        elif confidence_score <= 30:
            insights.append('経営陣は慎重で控えめなトーンで業績を説明している')
        
        # カテゴリ別の洞察
        total_mentions = sum(category_counts.values())
        if total_mentions > 0:
            high_conf_ratio = category_counts.get('high_confidence', 0) / total_mentions
            if high_conf_ratio > 0.5:
                insights.append('強気な表現が多く、業績への自信が感じられる')
            
            low_conf_ratio = (category_counts.get('low_confidence', 0) + 
                            category_counts.get('very_low_confidence', 0)) / total_mentions
            if low_conf_ratio > 0.4:
                insights.append('課題や不透明性への言及が多く、慎重な姿勢')
        
        return insights
    
    def calculate_financial_ratios(self, financial_data: Dict[str, Decimal]) -> Dict[str, Any]:
        """財務指標の計算"""
        try:
            ratios = {}
            
            # 基本的な財務指標
            net_sales = financial_data.get('net_sales', Decimal('0'))
            operating_income = financial_data.get('operating_income', Decimal('0'))
            net_income = financial_data.get('net_income', Decimal('0'))
            total_assets = financial_data.get('total_assets', Decimal('0'))
            net_assets = financial_data.get('net_assets', Decimal('0'))
            
            # 収益性指標
            if net_sales > 0:
                ratios['operating_margin'] = float(operating_income / net_sales * 100)
                ratios['net_margin'] = float(net_income / net_sales * 100)
            
            # 効率性指標
            if total_assets > 0:
                ratios['roa'] = float(net_income / total_assets * 100)
            
            # 安全性指標
            if total_assets > 0:
                ratios['equity_ratio'] = float(net_assets / total_assets * 100)
            
            return {
                'ratios': ratios,
                'interpretation': self._interpret_financial_ratios(ratios),
                'benchmarks': self._get_ratio_benchmarks(),
            }
            
        except Exception as e:
            logger.error(f"財務指標計算エラー: {e}")
            return {'error': f'財務指標計算中にエラーが発生しました: {str(e)}'}
    
# earnings_analysis/services/financial_analyzer.py の修正箇所

    def calculate_overall_health_score(self, cf_analysis: Dict, financial_ratios: Dict, confidence_analysis: Dict) -> Dict[str, Any]:
        """総合健全性スコアの算出（辞書形式で返す）"""
        try:
            # 各要素のスコア化
            cf_score = self._score_cashflow_health(cf_analysis)
            ratio_score = self._score_financial_ratios(financial_ratios)
            confidence_score = confidence_analysis.get('confidence_score', 50)
            
            # 重み付き平均
            overall_score = (cf_score * 0.4 + ratio_score * 0.4 + confidence_score * 0.2)
            
            # リスクレベル判定
            cf_risk = cf_analysis.get('pattern', {}).get('risk_level', 'medium')
            if overall_score >= 80 and cf_risk == 'low':
                risk_level = 'low'
            elif overall_score >= 60 and cf_risk != 'high':
                risk_level = 'medium'
            else:
                risk_level = 'high'
            
            # パターン情報（辞書として確実に取得）
            pattern_info = cf_analysis.get('pattern', {})
            if not isinstance(pattern_info, dict):
                pattern_info = {}
            
            return {
                'overall_score': round(overall_score, 1),
                'risk_level': risk_level,
                'pattern': pattern_info,
                'strengths': self._compile_overall_strengths(cf_analysis, financial_ratios, confidence_analysis),
                'concerns': self._compile_overall_concerns(cf_analysis, financial_ratios, confidence_analysis),
                'recommendations': self._generate_overall_recommendations(overall_score, risk_level),
                'component_scores': {
                    'cashflow_score': cf_score,
                    'ratio_score': ratio_score,
                    'confidence_score': confidence_score,
                }
            }
            
        except Exception as e:
            logger.error(f"総合健全性スコア算出エラー: {e}")
            return {
                'overall_score': 50.0,
                'risk_level': 'medium',
                'pattern': {},
                'strengths': [],
                'concerns': [f'分析中にエラーが発生しました: {str(e)}'],
                'recommendations': [],
                'component_scores': {
                    'cashflow_score': 0,
                    'ratio_score': 0,
                    'confidence_score': 0,
                }
            }

    def analyze_comprehensive_financial_health(self, 
                                             financial_data: Dict[str, Decimal],
                                             text_sections: Dict[str, str],
                                             document_info: Dict[str, str] = None) -> Dict[str, Any]:
        """包括的な財務健全性分析"""
        try:
            # 1. キャッシュフロー分析
            cf_analysis = self.analyze_cashflow_pattern(financial_data)
            
            # 2. 財務指標分析
            financial_ratios = self.calculate_financial_ratios(financial_data)
            
            # 3. 経営陣の自信度分析
            confidence_analysis = self.analyze_management_confidence(text_sections)
            
            # 4. 総合健全性スコア算出（必ず辞書を返す）
            overall_health = self.calculate_overall_health_score(
                cf_analysis, financial_ratios, confidence_analysis
            )
            
            # 5. 投資家向け提案生成
            investment_recommendations = self.generate_investment_recommendations(
                overall_health, cf_analysis, confidence_analysis
            )
            
            # 6. リスク評価
            risk_assessment = self.assess_investment_risks(
                cf_analysis, financial_ratios, confidence_analysis
            )
            
            result = {
                'analysis_timestamp': timezone.now().isoformat(),
                'document_info': document_info or {},
                
                # 主要分析結果（すべて辞書形式で統一）
                'overall_health': overall_health,  # 必ず辞書
                'cashflow_analysis': cf_analysis,
                'financial_ratios': financial_ratios,
                'management_confidence': confidence_analysis,
                
                # 投資判断支援
                'investment_recommendations': investment_recommendations,
                'risk_assessment': risk_assessment,
                
                # メタデータ
                'analysis_metadata': {
                    'analyzer_version': '1.0',
                    'data_quality': self._assess_data_quality(financial_data, text_sections),
                    'confidence_in_analysis': self._calculate_analysis_confidence(financial_data, text_sections),
                }
            }
            
            logger.info(f"包括財務分析完了: 健全性スコア{overall_health['overall_score']:.1f}, パターン: {cf_analysis.get('pattern', {}).get('name', '不明')}")
            return result
            
        except Exception as e:
            logger.error(f"包括財務分析エラー: {e}")
            return self._generate_error_result(str(e))
        
    def generate_investment_recommendations(self, overall_health: Dict, 
                                          cf_analysis: Dict, confidence_analysis: Dict) -> Dict[str, Any]:
        """投資推奨の生成（辞書形式の overall_health を受け取る）"""
        recommendations = {
            'investment_stance': '',
            'key_points': [],
            'risk_considerations': [],
            'monitoring_items': []
        }
        
        # overall_health が辞書であることを確認
        if not isinstance(overall_health, dict):
            logger.warning("overall_health is not a dict, converting...")
            overall_health = {'overall_score': 50.0, 'risk_level': 'medium'}
        
        overall_score = overall_health.get('overall_score', 50.0)
        risk_level = overall_health.get('risk_level', 'medium')
        
        # 投資スタンス決定
        if overall_score >= 80 and risk_level == 'low':
            recommendations['investment_stance'] = '積極的投資推奨'
            recommendations['key_points'] = [
                '健全な財務基盤と安定したキャッシュフロー',
                '経営陣の前向きな姿勢',
                '持続的な成長が期待できる'
            ]
        elif overall_score >= 60:
            recommendations['investment_stance'] = '条件付き投資推奨'
            recommendations['key_points'] = [
                '概ね良好な財務状況',
                '一部注意すべき点があるが投資価値あり'
            ]
        else:
            recommendations['investment_stance'] = '慎重な検討が必要'
            recommendations['key_points'] = [
                '財務状況に課題あり',
                '詳細な分析と継続的な監視が必要'
            ]
        
        return recommendations
    
    def assess_investment_risks(self, cf_analysis: Dict, financial_ratios: Dict, 
                              confidence_analysis: Dict) -> Dict[str, Any]:
        """投資リスク評価（辞書パラメータ前提）"""
        risks = {
            'overall_risk_level': '',
            'primary_risks': [],
            'mitigation_strategies': []
        }
        
        # リスク要因の特定
        risk_factors = []
        
        cf_pattern = cf_analysis.get('pattern', {})
        if isinstance(cf_pattern, dict) and cf_pattern.get('risk_level') == 'high':
            risk_factors.append('キャッシュフロー構造リスク')
        
        confidence_score = confidence_analysis.get('confidence_score', 50)
        if confidence_score < 40:
            risk_factors.append('経営陣の消極的姿勢')
        
        risks['primary_risks'] = risk_factors
        
        # 総合リスクレベル
        if len(risk_factors) >= 3:
            risks['overall_risk_level'] = 'high'
        elif len(risk_factors) >= 1:
            risks['overall_risk_level'] = 'medium'
        else:
            risks['overall_risk_level'] = 'low'
        
        return risks
    
    def _score_cashflow_health(self, cf_analysis: Dict) -> float:
        """キャッシュフロー健全性スコア"""
        pattern_scores = {
            '理想型': 90,
            '成長型': 75,
            '再建型': 60,
            '成熟型': 80,
            '危険型': 20,
            '衰退型': 30,
        }
        
        pattern_name = cf_analysis.get('pattern', {}).get('name', 'その他')
        base_score = pattern_scores.get(pattern_name, 50)
        
        # 営業CFの規模による調整
        amounts = cf_analysis.get('amounts', {})
        operating_cf = amounts.get('operating_cf', 0)
        
        if operating_cf > 0:
            base_score += 10
        elif operating_cf < 0:
            base_score -= 15
        
        return max(0, min(100, base_score))
    
    def _score_financial_ratios(self, financial_ratios: Dict) -> float:
        """財務指標スコア"""
        ratios = financial_ratios.get('ratios', {})
        
        score = 50  # ベーススコア
        
        # 営業利益率
        operating_margin = ratios.get('operating_margin', 0)
        if operating_margin > 10:
            score += 15
        elif operating_margin > 5:
            score += 10
        elif operating_margin < 0:
            score -= 20
        
        # ROA
        roa = ratios.get('roa', 0)
        if roa > 5:
            score += 15
        elif roa > 2:
            score += 10
        elif roa < 0:
            score -= 15
        
        # 自己資本比率
        equity_ratio = ratios.get('equity_ratio', 0)
        if equity_ratio > 50:
            score += 10
        elif equity_ratio < 20:
            score -= 15
        
        return max(0, min(100, score))
    
    def _assess_data_quality(self, financial_data: Dict, text_sections: Dict) -> str:
        """データ品質評価"""
        financial_completeness = len([v for v in financial_data.values() if v != 0]) / len(financial_data) if financial_data else 0
        text_completeness = len([t for t in text_sections.values() if len(t) > 100]) / len(text_sections) if text_sections else 0
        
        avg_completeness = (financial_completeness + text_completeness) / 2
        
        if avg_completeness >= 0.8:
            return 'high'
        elif avg_completeness >= 0.5:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_analysis_confidence(self, financial_data: Dict, text_sections: Dict) -> float:
        """分析信頼性の算出"""
        data_quality = self._assess_data_quality(financial_data, text_sections)
        
        base_confidence = {'high': 90, 'medium': 70, 'low': 40}.get(data_quality, 50)
        
        # 主要データの存在チェック
        key_financial_items = ['operating_cf', 'investing_cf', 'financing_cf']
        available_items = sum(1 for item in key_financial_items if financial_data.get(item, 0) != 0)
        
        confidence_adjustment = (available_items / len(key_financial_items)) * 20
        
        return min(100, base_confidence + confidence_adjustment)
    
    def _generate_error_result(self, error_message: str) -> Dict[str, Any]:
        """エラー時の結果生成"""
        return {
            'error': error_message,
            'analysis_timestamp': timezone.now().isoformat(),
            'overall_health': FinancialHealth(
                overall_score=0.0,
                risk_level='unknown',
                pattern=None,
                strengths=[],
                concerns=[f'分析中にエラーが発生しました: {error_message}'],
                recommendations=['データを確認して再度分析を実行してください']
            )
        }
    
    
    # 以下、補助メソッド（簡略化）
    def _analyze_cf_trends(self, financial_data: Dict) -> Dict[str, Any]:
        """キャッシュフロートレンド分析（簡略版）"""
        return {'note': '前年同期比データが利用可能な場合に詳細分析を実行'}
    
    def _interpret_financial_ratios(self, ratios: Dict) -> List[str]:
        """財務指標の解釈"""
        interpretations = []
        
        operating_margin = ratios.get('operating_margin', 0)
        if operating_margin > 10:
            interpretations.append('優秀な営業利益率')
        elif operating_margin < 0:
            interpretations.append('営業赤字状態')
        
        return interpretations
    
    def _get_ratio_benchmarks(self) -> Dict[str, Dict]:
        """財務指標ベンチマーク"""
        return {
            'operating_margin': {'excellent': 15, 'good': 10, 'average': 5},
            'roa': {'excellent': 10, 'good': 5, 'average': 2},
            'equity_ratio': {'excellent': 60, 'good': 40, 'average': 30}
        }
    
    def _compile_overall_strengths(self, cf_analysis: Dict, financial_ratios: Dict, confidence_analysis: Dict) -> List[str]:
        """総合的な強みの整理"""
        strengths = []
        strengths.extend(cf_analysis.get('analysis', {}).get('strengths', []))
        if confidence_analysis.get('confidence_score', 0) > 60:
            strengths.append('経営陣の前向きな姿勢')
        return strengths[:5]
    
    def _compile_overall_concerns(self, cf_analysis: Dict, financial_ratios: Dict, confidence_analysis: Dict) -> List[str]:
        """総合的な懸念点の整理"""
        concerns = []
        concerns.extend(cf_analysis.get('analysis', {}).get('concerns', []))
        if confidence_analysis.get('confidence_score', 0) < 40:
            concerns.append('経営陣の慎重すぎる姿勢')
        return concerns[:5]
    
    def _generate_overall_recommendations(self, overall_score: float, risk_level: str) -> List[str]:
        """総合的な推奨事項の生成"""
        recommendations = []
        
        if overall_score >= 80:
            recommendations.append('安心して投資できる財務状況')
        elif overall_score >= 60:
            recommendations.append('投資価値はあるが定期的な監視が必要')
        else:
            recommendations.append('投資前に詳細な検討が必要')
        
        return recommendations