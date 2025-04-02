# stockdiary/templatetags/sector_analysis_tags.py
from django import template
from django.db.models import Avg, Count, Sum, F, ExpressionWrapper, FloatField, Q, StdDev
from django.db.models.functions import Length, Coalesce
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from analysis_template.models import DiaryAnalysisValue, AnalysisItem
from tags.models import Tag

import math
import json
from collections import defaultdict, Counter

register = template.Library()

@register.filter
def sector_allocation(sector_diaries, total_investment):
    """セクター内の投資額合計の割合を計算"""
    if not sector_diaries or total_investment == 0:
        return 0.0
    
    sector_investment = sum([
        diary.purchase_price * diary.purchase_quantity 
        for diary in sector_diaries 
        if diary.purchase_price and diary.purchase_quantity
    ])
    
    return (sector_investment / total_investment) * 100 if total_investment else 0

@register.filter
def sector_avg_return(sector_diaries):
    """セクター内の日記の平均リターンを計算"""
    if not sector_diaries:
        return 0.0
    
    total_return = 0.0
    valid_diaries = 0
    
    for diary in sector_diaries:
        if diary.sell_date and diary.purchase_price and diary.sell_price:
            # 売却済みの場合は実際のリターン
            # Decimal型をfloatに変換
            purchase_price = float(diary.purchase_price)
            sell_price = float(diary.sell_price)
            return_rate = ((sell_price - purchase_price) / purchase_price) * 100
            total_return += return_rate
            valid_diaries += 1
    
    return total_return / valid_diaries if valid_diaries > 0 else 0.0

@register.filter
def sector_success_rate(sector_diaries):
    """セクター内の投資成功率を計算"""
    if not sector_diaries:
        return 0.0
    
    sold_diaries = [d for d in sector_diaries if d.sell_date and d.purchase_price and d.sell_price]
    if not sold_diaries:
        return 0.0
    
    successful = sum(1 for d in sold_diaries if d.sell_price >= d.purchase_price)
    return (successful / len(sold_diaries)) * 100

@register.filter
def sector_avg_investment(sector_diaries):
    """セクター内の平均投資額を計算"""
    if not sector_diaries:
        return 0
    
    total_investment = 0
    valid_diaries = 0
    
    for diary in sector_diaries:
        if diary.purchase_price and diary.purchase_quantity:
            # Decimalをfloatに変換
            price = float(diary.purchase_price)
            quantity = diary.purchase_quantity
            investment = price * quantity
            total_investment += investment
            valid_diaries += 1
    
    return total_investment / valid_diaries if valid_diaries > 0 else 0
    
@register.filter
def sector_avg_holding_days(sector_diaries):
    """セクター内の平均保有日数を計算"""
    if not sector_diaries:
        return 0
    
    total_days = 0
    sold_count = 0
    
    for diary in sector_diaries:
        if diary.sell_date and diary.purchase_date:
            days = (diary.sell_date - diary.purchase_date).days
            total_days += days
            sold_count += 1
    
    # 売却されていないものは現在までの日数を計算
    unsold_count = 0
    for diary in sector_diaries:
        if not diary.sell_date and diary.purchase_date:
            days = (timezone.now().date() - diary.purchase_date).days
            total_days += days
            unsold_count += 1
    
    total_count = sold_count + unsold_count
    return total_days / total_count if total_count > 0 else 0

@register.filter
def sector_metrics(sector_diaries):
    """セクター内の注目指標とタグを抽出"""
    if not sector_diaries:
        return {'indicators': [], 'tags': []}
    
    # 注目指標の抽出（分析項目から）
    indicators = Counter()
    for diary in sector_diaries:
        # 分析値を取得
        analysis_values = DiaryAnalysisValue.objects.filter(diary=diary).select_related('analysis_item')
        for value in analysis_values:
            # アイテム名をカウント
            indicators[value.analysis_item.name] += 1
    
    # 頻出タグの抽出
    tags = Counter()
    for diary in sector_diaries:
        for tag in diary.tags.all():
            tags[tag.name] += 1
    
    # 上位3つの指標とタグを返す
    return {
        'indicators': [{'name': name, 'count': count} for name, count in indicators.most_common(3)],
        'tags': [{'name': name, 'count': count} for name, count in tags.most_common(4)]
    }

@register.filter
def sector_per_roe_matrix(sector_diaries):
    """セクターのPERとROEに基づく成功率マトリックスを生成"""
    if not sector_diaries:
        return None
    
    # 十分なデータがない場合はNoneを返す
    sold_diaries = [d for d in sector_diaries if d.sell_date]
    if len(sold_diaries) < 5:  # 最低5件のデータが必要
        return None
    
    # PERとROEのデータを集計
    # この例では既存データが存在すると仮定
    # 実際の実装では、分析値からPERとROEを取得する必要がある
    
    # サンプルデータ構造
    # PER（縦軸）：10, 15, 20, 25, 30倍
    # ROE（横軸）：5, 10, 15, 20, 25%
    per_values = [10, 15, 20, 25, 30]
    roe_values = [5, 10, 15, 20, 25]
    
    # 成功率マトリックスを生成（サンプル値）
    matrix = []
    for per in per_values:
        row = {'per': per, 'values': []}
        for roe in roe_values:
            # CSSクラスを決定
            success_rate = get_sample_success_rate(per, roe)
            css_class = get_success_rate_css_class(success_rate)
            
            # セルデータを追加
            row['values'].append({
                'value': success_rate,
                'css_class': css_class
            })
        matrix.append(row)
    
    return {
        'per_values': per_values,
        'roe_values': roe_values,
        'matrix': matrix
    }

def get_sample_success_rate(per, roe):
    """サンプルの成功率を返す関数"""
    # 実際の実装ではデータベースからの集計値を使用
    success_rates = {
        (10, 5): 48, (10, 10): 51, (10, 15): 77, (10, 20): 86, (10, 25): 87,
        (15, 5): 45, (15, 10): 57, (15, 15): 94, (15, 20): 91, (15, 25): 87,
        (20, 5): 49, (20, 10): 54, (20, 15): 95, (20, 20): 91, (20, 25): 79,
        (25, 5): 39, (25, 10): 51, (25, 15): 55, (25, 20): 69, (25, 25): 62,
        (30, 5): 36, (30, 10): 37, (30, 15): 44, (30, 20): 36, (30, 25): 45
    }
    return success_rates.get((per, roe), 0)

def get_success_rate_css_class(rate):
    """成功率に応じたCSSクラスを返す"""
    if rate >= 90:
        return 'bg-success bg-opacity-75'
    elif rate >= 80:
        return 'bg-success bg-opacity-50'
    elif rate >= 60:
        return 'bg-success bg-opacity-25'
    elif rate >= 40:
        return 'bg-warning bg-opacity-25'
    else:
        return 'bg-danger bg-opacity-25'

@register.filter
def sector_insights(sector_diaries, all_diaries):
    """セクター分析のインサイトを生成"""
    if not sector_diaries or len(sector_diaries) < 3:
        return []
    
    insights = []
    
    # 1. リターンの分析
    avg_return = sector_avg_return(sector_diaries)
    all_avg_return = sector_avg_return(all_diaries)
    if avg_return > all_avg_return + 3:
        insights.append(f"このセクターは全体平均より<strong>{(avg_return - all_avg_return):.1f}%高いリターン</strong>を示しています")
    elif avg_return < all_avg_return - 3:
        insights.append(f"このセクターは全体平均より<strong>{(all_avg_return - avg_return):.1f}%低いリターン</strong>となっています")
    
    # 2. 保有期間の分析
    holding_days = sector_avg_holding_days(sector_diaries)
    all_holding_days = sector_avg_holding_days(all_diaries)
    if holding_days > all_holding_days * 1.2:
        insights.append(f"平均保有期間が他セクターより<strong>{(holding_days - all_holding_days):.0f}日長く</strong>、長期投資の傾向があります")
    elif holding_days < all_holding_days * 0.8:
        insights.append(f"平均保有期間が他セクターより<strong>{(all_holding_days - holding_days):.0f}日短く</strong>、短期売買の傾向があります")
    
    # 3. 投資規模の分析
    avg_investment = sector_avg_investment(sector_diaries)
    all_avg_investment = sector_avg_investment(all_diaries)
    if avg_investment > all_avg_investment * 1.2:
        insights.append(f"平均投資額が全体平均より<strong>{((avg_investment / all_avg_investment) - 1) * 100:.0f}%大きく</strong>、重点的に投資しているセクターです")
    
    # 4. 成功率の分析
    success_rate = sector_success_rate(sector_diaries)
    all_success_rate = sector_success_rate(all_diaries)
    if success_rate > 75:
        insights.append(f"<strong>{success_rate:.1f}%の高い成功率</strong>を示しており、投資判断の精度が高いセクターです")
    elif success_rate < all_success_rate - 10:
        insights.append(f"成功率が全体平均より<strong>{(all_success_rate - success_rate):.1f}%低く</strong>、より慎重な分析が必要です")
    
    # 5. タグとの関連性
    metrics = sector_metrics(sector_diaries)
    if metrics['tags']:
        tag_names = [tag['name'] for tag in metrics['tags'][:2]]
        insights.append(f"<strong>{', '.join(tag_names)}</strong>のタグが付けられた銘柄が多く、これらの特性を持つ企業に注目すると良いでしょう")
    
    # 生成したインサイトを返す（最大5つ）
    return insights[:5]

# この関数はビューからの直接呼び出し用で、テンプレートでは使用しない
def get_sector_correlation_data(diaries):
    """セクター間の相関行列データを生成"""
    # セクターごとにリターンデータを集計
    sector_returns = defaultdict(list)
    
    for diary in diaries:
        sector = diary.sector or "未分類"
        if diary.sell_date and diary.purchase_price and diary.sell_price:
            return_rate = ((diary.sell_price - diary.purchase_price) / diary.purchase_price) * 100
            sector_returns[sector].append(return_rate)
    
    # 有効なセクター（十分なデータがあるもの）を抽出
    valid_sectors = [sector for sector, returns in sector_returns.items() if len(returns) >= 3]
    
    if len(valid_sectors) < 2:
        return [] # 相関を計算するには少なくとも2つのセクターが必要
    
    # 相関行列を計算
    correlation_matrix = []
    
    for sector1 in valid_sectors:
        row = {"sector": sector1, "correlations": []}
        for sector2 in valid_sectors:
            if sector1 == sector2:
                # 自己相関は常に1.0
                row["correlations"].append({
                    "value": "1.00",
                    "css_class": "bg-light"
                })
            else:
                # 2つのセクター間の相関係数を計算
                corr = calculate_correlation(sector_returns[sector1], sector_returns[sector2])
                css_class = get_correlation_css_class(corr)
                
                row["correlations"].append({
                    "value": f"{corr:.2f}",
                    "css_class": css_class
                })
        
        correlation_matrix.append(row)
    
    return correlation_matrix

def calculate_correlation(x, y):
    """2つの数値リストの相関係数を計算"""
    if len(x) != len(y) or len(x) < 3:
        return 0  # 十分なデータがない場合は相関なし
    
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi ** 2 for xi in x)
    sum_y2 = sum(yi ** 2 for yi in y)
    
    numerator = n * sum_xy - sum_x * sum_y
    denominator = math.sqrt((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2))
    
    if denominator == 0:
        return 0
    
    return numerator / denominator

def get_correlation_css_class(corr):
    """相関係数に基づいたCSSクラスを返す"""
    if corr > 0.5:
        return "bg-success bg-opacity-25"  # 強い正の相関
    elif corr > 0.1:
        return "bg-success bg-opacity-10"  # 弱い正の相関
    elif corr < -0.5:
        return "bg-danger bg-opacity-25"   # 強い負の相関
    elif corr < -0.1:
        return "bg-danger bg-opacity-10"   # 弱い負の相関
    else:
        return "bg-light"                  # ほぼ無相関