from django.db.models import Avg, Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from stockdiary.models import StockDiary
from decimal import Decimal
import numpy as np
from scipy import stats

def calculate_template_performance(user):
    """
    分析テンプレートごとの投資パフォーマンスを分析
    
    Returns:
        List of template performance dictionaries
    """
    templates = AnalysisTemplate.objects.filter(user=user)
    template_performance = []

    for template in templates:
        # このテンプレートを使用した日記を取得
        diaries = StockDiary.objects.filter(
            user=user, 
            analysis_values__analysis_item__template=template
        ).distinct()

        # パフォーマンス計算
        total_investment = 0
        total_return = 0
        profitable_trades = 0
        total_trades = 0

        for diary in diaries:
            total_trades += 1
            investment = diary.purchase_price * diary.purchase_quantity
            total_investment += investment

            # 売却済みの場合は実際の収益
            if diary.sell_date:
                trade_return = (diary.sell_price - diary.purchase_price) * diary.purchase_quantity
            else:
                # 売却前の場合は現在の理論上の評価額（仮想的な現在株価を使用）
                trade_return = 0  # TODO: 現在株価APIから取得する必要あり

            total_return += trade_return

            if trade_return > 0:
                profitable_trades += 1

        # テンプレートの数値項目を分析
        significant_items = analyze_template_items(template, diaries)

        template_performance.append({
            'template_id': template.id,
            'template_name': template.name,
            'total_trades': total_trades,
            'total_investment': total_investment,
            'total_return': total_return,
            'return_rate': (total_return / total_investment * 100) if total_investment > 0 else 0,
            'profitable_trade_ratio': (profitable_trades / total_trades * 100) if total_trades > 0 else 0,
            'significant_items': significant_items
        })

    return template_performance

def analyze_template_items(template, diaries):
    """
    テンプレートの各数値項目と投資パフォーマンスの相関を分析
    
    Args:
        template (AnalysisTemplate): 分析するテンプレート
        diaries (QuerySet): 対象の日記
    
    Returns:
        List of item correlation details
    """
    numeric_items = template.items.filter(item_type='number')
    item_correlations = []

    for item in numeric_items:
        # 項目の値と収益率を収集
        values = []
        returns = []

        for diary in diaries:
            try:
                # この項目の分析値を取得
                analysis_value = DiaryAnalysisValue.objects.get(
                    diary=diary, 
                    analysis_item=item
                )
                
                # 収益率計算
                if diary.sell_date:
                    return_rate = (diary.sell_price - diary.purchase_price) / diary.purchase_price * 100
                else:
                    # 売却前の場合は0と仮定
                    return_rate = 0

                values.append(float(analysis_value.number_value))
                returns.append(return_rate)
            except DiaryAnalysisValue.DoesNotExist:
                continue

        # 相関係数を計算
        if len(values) > 1:
            correlation, p_value = stats.pearsonr(values, returns)
        else:
            correlation, p_value = 0, 1

        item_correlations.append({
            'item_id': item.id,
            'item_name': item.name,
            'correlation': correlation,
            'p_value': p_value,
            'is_significant': p_value < 0.05  # 統計的に有意かどうか
        })

    return item_correlations

def get_template_keyword_insights(user):
    """
    分析テンプレートから得られる投資キーワードの洞察
    
    Args:
        user: 対象ユーザー
    
    Returns:
        List of keyword insights
    """
    templates = AnalysisTemplate.objects.filter(user=user)
    keyword_insights = []

    for template in templates:
        # テキスト項目を取得
        text_items = template.items.filter(item_type='text')
        
        for item in text_items:
            # この項目の値を収集
            values = DiaryAnalysisValue.objects.filter(
                analysis_item=item
            ).values_list('text_value', flat=True)

            # キーワード抽出（簡易的な実装）
            keywords = {}
            for value in values:
                if value:
                    # スペース区切りでキーワードを抽出
                    for word in value.split():
                        if len(word) > 1:  # 2文字以上のワードのみ
                            keywords[word] = keywords.get(word, 0) + 1

            # 上位キーワードを抽出
            top_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:5]

            keyword_insights.append({
                'template_name': template.name,
                'item_name': item.name,
                'top_keywords': [{'word': word, 'count': count} for word, count in top_keywords]
            })

    return keyword_insights