# earnings_analysis/services/forecast_reliability_service.py
"""
予想信頼性スコア算出サービス

各企業の業績予想と実績を比較し、
複数年にわたる「予想信頼性」を数値化して投資判断に活用する。

【設計思想】
- 単発の予想値は信頼できない
- 3年以上継続して予想を達成している企業は信頼できる
- 保守的な予想（常に超過達成）は安定性の証拠として加点
- 楽観的な予想（常に未達）は警告シグナル
- 予想の安定性（標準偏差の小ささ）も信頼性を高める
"""

import logging
import math
from decimal import Decimal
from typing import List, Optional, Dict, Any

from django.db.models import Avg, StdDev, Min, Max, Count
from django.utils import timezone

logger = logging.getLogger('earnings_analysis.forecast')


class ForecastReliabilityService:
    """予想信頼性スコア算出サービス"""

    # グレード判定閾値
    GRADE_THRESHOLDS = {
        'S': 85,
        'A': 70,
        'B': 55,
        'C': 40,
        'D': 0,
    }

    # 信頼性スコア計算パラメータ
    MIN_YEARS_FOR_GRADING = 2   # グレード付与に必要な最低年数
    MIN_YEARS_FOR_TRUST = 3     # 「信頼できる」判定に必要な最低年数

    def calculate_reliability(self, company_code: str) -> Optional[Dict[str, Any]]:
        """
        指定企業の予想信頼性スコアを計算してDBに保存する。

        Returns:
            計算結果のdict（DBに保存済み）、データ不足時はNone
        """
        from ..models.forecast import EarningsForecast, ForecastReliabilityScore

        # 実績が確定しているレコードのみ集計
        records = EarningsForecast.objects.filter(
            company_code=company_code,
            has_actual=True,
            period_type='annual',  # 通期のみで信頼性を判断
        ).order_by('fiscal_year')

        if not records.exists():
            return None

        # 達成率リスト（composite_achievement_rate を使用）
        rates = []
        for rec in records:
            rate = rec.composite_achievement_rate
            if rate is not None:
                rates.append((rec.fiscal_year, rate))

        if len(rates) < 1:
            return None

        years_tracked = len(rates)
        rate_values = [r for _, r in rates]

        # 統計量
        avg_rate = sum(rate_values) / len(rate_values)
        if len(rate_values) >= 2:
            variance = sum((r - avg_rate) ** 2 for r in rate_values) / (len(rate_values) - 1)
            std_rate = math.sqrt(variance)
        else:
            std_rate = 0.0

        min_rate = min(rate_values)
        max_rate = max(rate_values)

        # 達成カウント
        beat_count = sum(1 for r in rate_values if r >= 105)
        met_count = sum(1 for r in rate_values if 95 <= r < 105)
        miss_count = sum(1 for r in rate_values if r < 95)

        # 予想傾向の分類
        tendency = self._classify_tendency(avg_rate, std_rate, beat_count, miss_count, years_tracked)

        # 信頼性スコア計算（0-100）
        score = self._calculate_score(
            avg_rate=avg_rate,
            std_rate=std_rate,
            years_tracked=years_tracked,
            beat_count=beat_count,
            miss_count=miss_count,
            recent_rates=[r for _, r in rates[-3:]],  # 直近3年
        )

        # グレード
        grade = self._score_to_grade(score, years_tracked)

        # 直近傾向（直近2年 vs それ以前）
        recent_trend = self._calc_recent_trend(rates)

        # 投資シグナル
        signal, reason = self._build_investment_signal(
            tendency=tendency,
            score=score,
            grade=grade,
            years_tracked=years_tracked,
            avg_rate=avg_rate,
            miss_count=miss_count,
            beat_count=beat_count,
        )

        # 企業名取得
        company_name = records.first().company_name or company_code

        # DB保存
        obj, _ = ForecastReliabilityScore.objects.update_or_create(
            company_code=company_code,
            defaults=dict(
                company_name=company_name,
                years_tracked=years_tracked,
                earliest_fiscal_year=rates[0][0],
                latest_fiscal_year=rates[-1][0],
                avg_achievement_rate=Decimal(str(round(avg_rate, 2))),
                std_achievement_rate=Decimal(str(round(std_rate, 2))),
                min_achievement_rate=Decimal(str(round(min_rate, 2))),
                max_achievement_rate=Decimal(str(round(max_rate, 2))),
                beat_count=beat_count,
                met_count=met_count,
                miss_count=miss_count,
                forecast_tendency=tendency,
                reliability_score=score,
                grade=grade,
                investment_signal=signal,
                investment_signal_reason=reason,
                recent_trend=recent_trend,
            )
        )

        return {
            'company_code': company_code,
            'company_name': company_name,
            'years_tracked': years_tracked,
            'avg_achievement_rate': round(avg_rate, 2),
            'std_achievement_rate': round(std_rate, 2),
            'min_achievement_rate': round(min_rate, 2),
            'max_achievement_rate': round(max_rate, 2),
            'beat_count': beat_count,
            'met_count': met_count,
            'miss_count': miss_count,
            'forecast_tendency': tendency,
            'reliability_score': score,
            'grade': grade,
            'investment_signal': signal,
            'investment_signal_reason': reason,
            'recent_trend': recent_trend,
            'yearly_rates': [{'year': y, 'rate': r} for y, r in rates],
        }

    def _classify_tendency(
        self,
        avg_rate: float,
        std_rate: float,
        beat_count: int,
        miss_count: int,
        years_tracked: int,
    ) -> str:
        """
        予想傾向を分類する。

        - avg > 115% かつ miss < 10%: very_conservative
        - avg > 105%: conservative
        - avg 95-105%: accurate
        - avg 85-95%: optimistic
        - avg < 85%: very_optimistic
        """
        total = beat_count + years_tracked - beat_count  # = years_tracked

        if avg_rate >= 115 and (miss_count / max(years_tracked, 1)) < 0.15:
            return 'very_conservative'
        elif avg_rate >= 108:
            return 'conservative'
        elif avg_rate >= 93:
            return 'accurate'
        elif avg_rate >= 82:
            return 'optimistic'
        elif avg_rate >= 0:
            return 'very_optimistic'
        return 'unknown'

    def _calculate_score(
        self,
        avg_rate: float,
        std_rate: float,
        years_tracked: int,
        beat_count: int,
        miss_count: int,
        recent_rates: List[float],
    ) -> int:
        """
        信頼性スコア（0-100）を計算する。

        構成要素:
        1. 達成率ベーススコア (40点): avg_rate をもとに基礎点
        2. 安定性ボーナス (20点): std_rate が低いほど高い
        3. 年数ボーナス (20点): 追跡年数が多いほど高い
        4. 傾向ボーナス/ペナルティ (20点): 保守的 → 加点、楽観的 → 減点
        """

        # 1. 達成率ベーススコア（40点満点）
        # 100%達成 = 28点、110%超過 = 35点、120%超過 = 40点、80%以下 = 0点
        if avg_rate >= 120:
            base_score = 40
        elif avg_rate >= 110:
            base_score = 35 + (avg_rate - 110) / 10 * 5
        elif avg_rate >= 100:
            base_score = 28 + (avg_rate - 100) / 10 * 7
        elif avg_rate >= 90:
            base_score = 14 + (avg_rate - 90) / 10 * 14
        elif avg_rate >= 80:
            base_score = 4 + (avg_rate - 80) / 10 * 10
        else:
            base_score = max(0, avg_rate / 80 * 4)
        base_score = min(40, base_score)

        # 2. 安定性ボーナス（20点満点）
        # std < 5%: 20点, std < 10%: 15点, std < 20%: 8点, std >= 30%: 0点
        if std_rate < 5:
            stability_score = 20
        elif std_rate < 10:
            stability_score = 15 + (10 - std_rate) / 5 * 5
        elif std_rate < 20:
            stability_score = 8 + (20 - std_rate) / 10 * 7
        elif std_rate < 30:
            stability_score = (30 - std_rate) / 10 * 8
        else:
            stability_score = 0
        stability_score = min(20, max(0, stability_score))

        # 3. 年数ボーナス（20点満点）
        # データが多いほど信頼性が高い
        # 1年: 5点, 2年: 10点, 3年: 15点, 5年以上: 20点
        if years_tracked >= 5:
            years_score = 20
        elif years_tracked >= 3:
            years_score = 15 + (years_tracked - 3) / 2 * 5
        elif years_tracked >= 2:
            years_score = 10
        else:
            years_score = 5
        years_score = min(20, years_score)

        # 4. 傾向ボーナス/ペナルティ（20点満点 / 最大 -10点ペナルティ）
        # miss_rate が高いほどペナルティ
        total = beat_count + years_tracked - beat_count
        miss_rate = miss_count / max(years_tracked, 1)

        if miss_rate <= 0:
            # 一度も未達がない: ボーナス
            tendency_score = 20
        elif miss_rate <= 0.1:
            tendency_score = 16
        elif miss_rate <= 0.2:
            tendency_score = 10
        elif miss_rate <= 0.3:
            tendency_score = 5
        elif miss_rate <= 0.5:
            tendency_score = 0
        else:
            # 50%以上が未達: ペナルティ
            tendency_score = max(-10, -((miss_rate - 0.5) * 20))
        tendency_score = min(20, tendency_score)

        total_score = base_score + stability_score + years_score + tendency_score
        return max(0, min(100, round(total_score)))

    def _score_to_grade(self, score: int, years_tracked: int) -> str:
        """スコアをグレードに変換"""
        if years_tracked < self.MIN_YEARS_FOR_GRADING:
            return 'N'
        for grade, threshold in self.GRADE_THRESHOLDS.items():
            if score >= threshold:
                return grade
        return 'D'

    def _calc_recent_trend(self, rates: List[tuple]) -> str:
        """直近3年のトレンドを計算"""
        if len(rates) < 3:
            return 'unknown'

        recent = [r for _, r in rates[-3:]]
        # 単純線形トレンド（終点 - 始点）
        slope = recent[-1] - recent[0]
        if slope >= 5:
            return 'improving'
        elif slope <= -5:
            return 'declining'
        return 'stable'

    def _build_investment_signal(
        self,
        tendency: str,
        score: int,
        grade: str,
        years_tracked: int,
        avg_rate: float,
        miss_count: int,
        beat_count: int,
    ) -> tuple:
        """投資シグナルと判断理由を生成"""

        if years_tracked < self.MIN_YEARS_FOR_GRADING:
            return 'insufficient_data', f'データ年数が{years_tracked}年と不足しています（最低{self.MIN_YEARS_FOR_GRADING}年必要）'

        if grade in ('D',) or (miss_count / max(years_tracked, 1) > 0.5):
            reason = (
                f'過去{years_tracked}年中{miss_count}年で業績予想を未達。'
                f'平均達成率{avg_rate:.1f}%と予想の信頼性が低い。'
            )
            return 'warning', reason

        if tendency == 'very_conservative' and score >= 75:
            reason = (
                f'過去{years_tracked}年間、継続的に業績予想を大幅超過（平均{avg_rate:.1f}%達成）。'
                '経営陣が意図的に保守的な予想を出す傾向があり、実績は予想を常に上回る。'
                '予想値が低くても実際のパフォーマンスは高い可能性が高い。'
            )
            return 'strong_positive', reason

        if tendency == 'conservative' and score >= 60:
            reason = (
                f'過去{years_tracked}年間、業績予想を安定的に超過（平均{avg_rate:.1f}%達成）。'
                '予想の信頼性が高く、下振れリスクが低い。'
            )
            return 'positive', reason

        if tendency == 'accurate' and score >= 55:
            reason = (
                f'過去{years_tracked}年間の平均達成率{avg_rate:.1f}%と予想精度が高い。'
                '予想値をほぼそのまま期待値として活用できる。'
            )
            return 'positive', reason

        if tendency == 'optimistic':
            reason = (
                f'過去{years_tracked}年の平均達成率が{avg_rate:.1f}%と予想を下回る傾向がある。'
                '予想値に対して割り引いて評価することを推奨。'
            )
            return 'caution', reason

        if tendency == 'very_optimistic':
            reason = (
                f'過去{years_tracked}年の平均達成率が{avg_rate:.1f}%と大幅に予想を下回る。'
                '経営陣の予想が過度に楽観的である可能性があり、実績への期待は慎重に。'
            )
            return 'warning', reason

        # デフォルト
        reason = f'過去{years_tracked}年の平均達成率{avg_rate:.1f}%（グレード{grade}）'
        return 'neutral', reason

    def get_or_calculate(self, company_code: str) -> Optional[Dict[str, Any]]:
        """
        DBにキャッシュがあればそれを返し、なければ計算する。
        24時間以内のキャッシュは再計算しない。
        """
        from ..models.forecast import ForecastReliabilityScore
        from datetime import timedelta

        try:
            cached = ForecastReliabilityScore.objects.get(company_code=company_code)
            age = timezone.now() - cached.last_calculated
            if age.total_seconds() < 86400:  # 24時間
                return self._score_to_dict(cached)
        except ForecastReliabilityScore.DoesNotExist:
            pass

        return self.calculate_reliability(company_code)

    def _score_to_dict(self, score_obj) -> Dict[str, Any]:
        """ForecastReliabilityScore モデルを dict に変換"""
        from ..models.forecast import EarningsForecast

        records = EarningsForecast.objects.filter(
            company_code=score_obj.company_code,
            has_actual=True,
            period_type='annual',
        ).order_by('fiscal_year')

        yearly_rates = []
        for rec in records:
            rate = rec.composite_achievement_rate
            if rate is not None:
                yearly_rates.append({'year': rec.fiscal_year, 'rate': round(rate, 2)})

        return {
            'company_code': score_obj.company_code,
            'company_name': score_obj.company_name,
            'years_tracked': score_obj.years_tracked,
            'avg_achievement_rate': float(score_obj.avg_achievement_rate or 0),
            'std_achievement_rate': float(score_obj.std_achievement_rate or 0),
            'min_achievement_rate': float(score_obj.min_achievement_rate or 0),
            'max_achievement_rate': float(score_obj.max_achievement_rate or 0),
            'beat_count': score_obj.beat_count,
            'met_count': score_obj.met_count,
            'miss_count': score_obj.miss_count,
            'forecast_tendency': score_obj.forecast_tendency,
            'reliability_score': score_obj.reliability_score,
            'grade': score_obj.grade,
            'investment_signal': score_obj.investment_signal,
            'investment_signal_reason': score_obj.investment_signal_reason,
            'recent_trend': score_obj.recent_trend,
            'beat_rate': score_obj.beat_rate,
            'miss_rate': score_obj.miss_rate,
            'signal_color': score_obj.signal_color,
            'grade_color': score_obj.grade_color,
            'yearly_rates': yearly_rates,
        }

    def bulk_recalculate(self, company_codes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        複数企業の信頼性スコアを一括再計算する。
        company_codes が None の場合は全企業を対象とする。
        """
        from ..models.forecast import EarningsForecast

        if company_codes is None:
            company_codes = list(
                EarningsForecast.objects.filter(has_actual=True)
                .values_list('company_code', flat=True)
                .distinct()
            )

        results = {'success': [], 'skipped': [], 'error': []}
        for code in company_codes:
            try:
                result = self.calculate_reliability(code)
                if result:
                    results['success'].append(code)
                else:
                    results['skipped'].append(code)
            except Exception as e:
                logger.error(f"信頼性スコア計算エラー {code}: {e}")
                results['error'].append(code)

        logger.info(
            f"一括再計算完了: 成功={len(results['success'])} "
            f"スキップ={len(results['skipped'])} "
            f"エラー={len(results['error'])}"
        )
        return results
