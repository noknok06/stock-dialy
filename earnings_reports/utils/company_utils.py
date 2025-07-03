"""
earnings_reports/utils/company_utils.py
企業データ処理ユーティリティ
"""

import logging
from typing import Optional
from datetime import datetime
from django.utils import timezone

from ..models import Company
from ..services.edinet_service import EDINETService

logger = logging.getLogger('earnings_analysis')


def get_or_create_company_from_edinet(stock_code: str, edinet_service: EDINETService) -> Optional[Company]:
    """
    EDINETから企業情報を取得してDBに保存
    
    Args:
        stock_code: 証券コード
        edinet_service: EDINETサービスインスタンス
        
    Returns:
        Company: 企業オブジェクト（失敗時はNone）
    """
    
    try:
        logger.info(f"EDINET企業検索開始: {stock_code}")
        
        # EDINETから企業の書類を検索
        company_docs = edinet_service.search_company_documents_optimized(
            stock_code, 
            days_back=30,
            max_results=1
        )
        
        if not company_docs:
            logger.warning(f"企業{stock_code}の書類が見つかりません")
            return None
        
        # 最初の書類から企業情報を取得
        doc_info = company_docs[0]
        company_name = doc_info[1]  # 企業名
        
        # 企業オブジェクトを作成
        company = Company.objects.create(
            stock_code=stock_code,
            name=company_name,
            last_sync=timezone.now()
        )
        
        logger.info(f"企業作成完了: {company.name}")
        return company
        
    except Exception as e:
        logger.error(f"EDINET企業作成エラー: {str(e)}")
        return None


def update_company_from_market_data(company: Company, market_data: dict) -> bool:
    """
    市場データから企業情報を更新
    
    Args:
        company: 企業オブジェクト
        market_data: 市場データ辞書
        
    Returns:
        bool: 更新成功の場合True
    """
    
    try:
        # 市場データから情報を更新
        if 'name_kana' in market_data and market_data['name_kana']:
            company.name_kana = market_data['name_kana']
        
        if 'market' in market_data and market_data['market']:
            company.market = market_data['market']
        
        if 'sector' in market_data and market_data['sector']:
            company.sector = market_data['sector']
        
        company.save()
        logger.info(f"企業情報更新完了: {company.name}")
        return True
        
    except Exception as e:
        logger.error(f"企業情報更新エラー: {str(e)}")
        return False


def search_similar_companies(query: str, limit: int = 10) -> list:
    """
    類似企業を検索
    
    Args:
        query: 検索クエリ
        limit: 最大検索件数
        
    Returns:
        list: 企業リスト
    """
    
    from django.db.models import Q
    
    companies = Company.objects.filter(
        Q(stock_code__icontains=query) |
        Q(name__icontains=query) |
        Q(name_kana__icontains=query)
    ).order_by('stock_code')[:limit]
    
    return list(companies)


def get_company_analysis_stats(company: Company, user) -> dict:
    """
    企業の分析統計を取得
    
    Args:
        company: 企業オブジェクト
        user: ユーザー
        
    Returns:
        dict: 統計情報
    """
    
    from ..models import Analysis, Document
    from django.db.models import Count, Avg, Max
    
    # 基本統計
    total_documents = Document.objects.filter(company=company).count()
    total_analyses = Analysis.objects.filter(
        document__company=company,
        user=user
    ).count()
    
    # 完了した分析の統計
    completed_analyses = Analysis.objects.filter(
        document__company=company,
        user=user,
        status='completed'
    )
    
    avg_score = completed_analyses.aggregate(
        avg_score=Avg('overall_score')
    )['avg_score']
    
    latest_analysis = completed_analyses.order_by('-analysis_date').first()
    
    # 書類種別ごとの統計
    doc_type_stats = Document.objects.filter(company=company).values(
        'doc_type'
    ).annotate(
        count=Count('id'),
        analyzed_count=Count('analysis', filter=Q(analysis__user=user, analysis__status='completed'))
    )
    
    return {
        'total_documents': total_documents,
        'total_analyses': total_analyses,
        'completed_analyses': completed_analyses.count(),
        'avg_score': round(avg_score, 2) if avg_score else None,
        'latest_analysis': latest_analysis,
        'doc_type_stats': list(doc_type_stats),
        'last_sync': company.last_sync,
    }


def calculate_industry_benchmark(sector: str, metric: str) -> Optional[float]:
    """
    業界ベンチマークを計算
    
    Args:
        sector: 業種
        metric: メトリクス名
        
    Returns:
        float: ベンチマーク値（データ不足の場合はNone）
    """
    
    from ..models import Analysis, SentimentAnalysis, CashFlowAnalysis
    from django.db.models import Avg
    
    if not sector:
        return None
    
    try:
        # 同業種の企業を取得
        companies_in_sector = Company.objects.filter(sector=sector)
        
        if companies_in_sector.count() < 3:  # 最低3社以上のデータが必要
            return None
        
        # メトリクスに応じた計算
        if metric == 'overall_score':
            benchmark = Analysis.objects.filter(
                document__company__in=companies_in_sector,
                status='completed'
            ).aggregate(avg=Avg('overall_score'))['avg']
            
        elif metric == 'sentiment_score':
            benchmark = SentimentAnalysis.objects.filter(
                analysis__document__company__in=companies_in_sector,
                analysis__status='completed'
            ).aggregate(avg=Avg('positive_score'))['avg']
            
        elif metric == 'cf_quality':
            benchmark = CashFlowAnalysis.objects.filter(
                analysis__document__company__in=companies_in_sector,
                analysis__status='completed'
            ).aggregate(avg=Avg('cf_quality_score'))['avg']
            
        else:
            return None
        
        return round(benchmark, 2) if benchmark else None
        
    except Exception as e:
        logger.error(f"業界ベンチマーク計算エラー: {str(e)}")
        return None


def get_earnings_schedule(company: Company, days_ahead: int = 30) -> list:
    """
    決算発表予定を取得
    
    Args:
        company: 企業オブジェクト
        days_ahead: 何日先まで取得するか
        
    Returns:
        list: 決算発表予定リスト
    """
    
    from datetime import datetime, timedelta
    from ..models import Document
    
    # 過去の決算発表パターンから予測
    recent_earnings = Document.objects.filter(
        company=company,
        doc_type__in=['120', '130', '350']  # 有価証券報告書、四半期報告書、決算短信
    ).order_by('-submit_date')[:8]  # 過去2年分
    
    if not recent_earnings:
        return []
    
    schedule = []
    
    # 四半期ごとの発表パターンを分析
    quarterly_patterns = {}
    for doc in recent_earnings:
        quarter = f"{doc.submit_date.month:02d}"  # 月をキーにする
        if quarter not in quarterly_patterns:
            quarterly_patterns[quarter] = []
        quarterly_patterns[quarter].append(doc.submit_date.day)
    
    # 今後の予定日を推定
    today = datetime.now().date()
    end_date = today + timedelta(days=days_ahead)
    
    current_date = today
    while current_date <= end_date:
        month_key = f"{current_date.month:02d}"
        
        if month_key in quarterly_patterns:
            # 過去の平均発表日を計算
            avg_day = sum(quarterly_patterns[month_key]) // len(quarterly_patterns[month_key])
            
            estimated_date = current_date.replace(day=min(avg_day, 28))  # 28日を上限
            
            if estimated_date >= today:
                schedule.append({
                    'date': estimated_date,
                    'type': 'estimated',
                    'description': f'{current_date.year}年{current_date.month}月期 決算発表予定'
                })
        
        # 次の月へ
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
    
    return schedule


def export_company_analysis_data(company: Company, user, format: str = 'json') -> str:
    """
    企業分析データをエクスポート
    
    Args:
        company: 企業オブジェクト
        user: ユーザー
        format: エクスポート形式 ('json', 'csv')
        
    Returns:
        str: エクスポートされたデータ
    """
    
    import json
    import csv
    import io
    from ..models import Analysis
    
    # 分析データを取得
    analyses = Analysis.objects.filter(
        document__company=company,
        user=user,
        status='completed'
    ).select_related(
        'document', 'sentiment', 'cashflow'
    ).order_by('-analysis_date')
    
    if format == 'json':
        data = []
        for analysis in analyses:
            item = {
                'analysis_date': analysis.analysis_date.isoformat(),
                'document_type': analysis.document.get_doc_type_display(),
                'submit_date': analysis.document.submit_date.isoformat(),
                'overall_score': analysis.overall_score,
                'confidence_level': analysis.confidence_level,
            }
            
            if hasattr(analysis, 'sentiment'):
                sentiment = analysis.sentiment
                item['sentiment'] = {
                    'positive_score': sentiment.positive_score,
                    'negative_score': sentiment.negative_score,
                    'confidence_keywords_count': sentiment.confidence_keywords_count,
                    'risk_keywords_count': sentiment.risk_keywords_count,
                }
            
            if hasattr(analysis, 'cashflow'):
                cashflow = analysis.cashflow
                item['cashflow'] = {
                    'pattern': cashflow.pattern,
                    'pattern_score': cashflow.pattern_score,
                    'operating_cf': cashflow.operating_cf,
                    'investing_cf': cashflow.investing_cf,
                    'financing_cf': cashflow.financing_cf,
                }
            
            data.append(item)
        
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    elif format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        
        # ヘッダー
        writer.writerow([
            '分析日時', '書類種別', '提出日', '総合スコア', '信頼性',
            'ポジティブ度', 'ネガティブ度', '自信度', 'リスク言及',
            'CFパターン', 'CFスコア', '営業CF', '投資CF', '財務CF'
        ])
        
        # データ行
        for analysis in analyses:
            sentiment = getattr(analysis, 'sentiment', None)
            cashflow = getattr(analysis, 'cashflow', None)
            
            writer.writerow([
                analysis.analysis_date.strftime('%Y-%m-%d %H:%M'),
                analysis.document.get_doc_type_display(),
                analysis.document.submit_date.strftime('%Y-%m-%d'),
                analysis.overall_score,
                analysis.confidence_level,
                sentiment.positive_score if sentiment else '',
                sentiment.negative_score if sentiment else '',
                sentiment.confidence_keywords_count if sentiment else '',
                sentiment.risk_keywords_count if sentiment else '',
                cashflow.get_pattern_display() if cashflow else '',
                cashflow.pattern_score if cashflow else '',
                cashflow.operating_cf if cashflow else '',
                cashflow.investing_cf if cashflow else '',
                cashflow.financing_cf if cashflow else '',
            ])
        
        return output.getvalue()
    
    else:
        raise ValueError(f"サポートされていない形式: {format}")