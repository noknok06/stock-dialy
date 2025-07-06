# earnings_analysis/views/financial_ui.py（新規作成）
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.generic import TemplateView
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import logging

from ..models import DocumentMetadata, FinancialAnalysisSession, FinancialAnalysisHistory, CompanyFinancialData

logger = logging.getLogger(__name__)

class FinancialAnalysisView(TemplateView):
    """財務分析専用ページ"""
    template_name = 'earnings_analysis/financial/analysis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc_id = kwargs.get('doc_id')
        
        # 書類情報取得
        document = get_object_or_404(
            DocumentMetadata,
            doc_id=doc_id,
            legal_status='1'
        )
        
        # 最新の分析結果確認
        latest_session = FinancialAnalysisSession.objects.filter(
            document=document,
            processing_status='COMPLETED'
        ).order_by('-created_at').first()
        
        # 過去の分析履歴
        analysis_history = FinancialAnalysisHistory.objects.filter(
            document=document
        ).order_by('-analysis_date')[:5]
        
        # 既存の財務データ確認
        existing_financial_data = CompanyFinancialData.objects.filter(
            document=document
        ).first()
        
        context.update({
            'document': document,
            'latest_session': latest_session,
            'analysis_history': analysis_history,
            'existing_financial_data': existing_financial_data,
            'has_recent_analysis': latest_session and latest_session.created_at >= timezone.now() - timedelta(hours=2),
            'xbrl_available': document.xbrl_flag,
        })
        
        return context


class FinancialResultView(TemplateView):
    """財務分析結果表示ページ"""
    template_name = 'earnings_analysis/financial/result.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session_id = kwargs.get('session_id')
        
        # セッション情報取得
        session = get_object_or_404(
            FinancialAnalysisSession,
            session_id=session_id
        )
        
        if session.is_expired:
            messages.error(self.request, 'セッションが期限切れです。')
            return redirect('earnings_analysis:document-detail-ui', doc_id=session.document.doc_id)
        
        # 関連データの取得
        related_analyses = FinancialAnalysisHistory.objects.filter(
            document__edinet_code=session.document.edinet_code
        ).exclude(
            document=session.document
        ).order_by('-analysis_date')[:5]
                
        # 財務データの時系列
        historical_financial_data = CompanyFinancialData.objects.filter(
            document__edinet_code=session.document.edinet_code
        ).order_by('-period_end')[:8]  # 過去8期分
        
        context.update({
            'session': session,
            'document': session.document,
            'related_analyses': related_analyses,
            'historical_financial_data': historical_financial_data,
        })
        
        return context


class FinancialDataView(TemplateView):
    """企業財務データ一覧ページ"""
    template_name = 'earnings_analysis/financial/data_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # クエリパラメータ取得
        company_query = self.request.GET.get('company', '').strip()
        period_type = self.request.GET.get('period_type', '')
        fiscal_year = self.request.GET.get('fiscal_year', '')
        
        # 財務データクエリセット
        financial_data = CompanyFinancialData.objects.select_related('document', 'company')
        
        # フィルタリング
        if company_query:
            from django.db.models import Q
            financial_data = financial_data.filter(
                Q(company__company_name__icontains=company_query) |
                Q(document__company_name__icontains=company_query) |
                Q(company__securities_code__icontains=company_query) |
                Q(document__securities_code__icontains=company_query)
            )
        
        if period_type:
            financial_data = financial_data.filter(period_type=period_type)
        
        if fiscal_year:
            try:
                financial_data = financial_data.filter(fiscal_year=int(fiscal_year))
            except ValueError:
                pass
        
        # ページネーション
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
        
        financial_data = financial_data.order_by('-period_end', '-created_at')
        paginator = Paginator(financial_data, 20)
        
        page = self.request.GET.get('page', 1)
        try:
            financial_data_page = paginator.page(page)
        except PageNotAnInteger:
            financial_data_page = paginator.page(1)
        except EmptyPage:
            financial_data_page = paginator.page(paginator.num_pages)
        
        # 選択肢データ
        period_types = CompanyFinancialData.objects.values_list('period_type', flat=True).distinct()
        fiscal_years = CompanyFinancialData.objects.exclude(
            fiscal_year__isnull=True
        ).values_list('fiscal_year', flat=True).distinct().order_by('-fiscal_year')
        
        context.update({
            'financial_data': financial_data_page,
            'search_params': {
                'company': company_query,
                'period_type': period_type,
                'fiscal_year': fiscal_year,
            },
            'period_types': period_types,
            'fiscal_years': fiscal_years,
            'total_count': paginator.count,
        })
        
        return context


class FinancialStatsView(TemplateView):
    """財務分析統計ページ"""
    template_name = 'earnings_analysis/financial/stats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 基本統計
        from django.db.models import Count, Avg, Q
        from datetime import datetime, timedelta
        
        total_analyses = FinancialAnalysisHistory.objects.count()
        total_financial_records = CompanyFinancialData.objects.count()
        
        # 最近30日の分析数
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_analyses = FinancialAnalysisHistory.objects.filter(
            analysis_date__gte=thirty_days_ago
        ).count()
        
        # リスクレベル別統計
        risk_stats = FinancialAnalysisHistory.objects.values('risk_level').annotate(
            count=Count('id')
        ).order_by('risk_level')
        
        # キャッシュフローパターン別統計
        cf_pattern_stats = FinancialAnalysisHistory.objects.exclude(
            cashflow_pattern__isnull=True
        ).exclude(
            cashflow_pattern=''
        ).values('cashflow_pattern').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # 健全性スコア分布
        score_ranges = [
            ('80-100', FinancialAnalysisHistory.objects.filter(overall_health_score__gte=80).count()),
            ('60-79', FinancialAnalysisHistory.objects.filter(overall_health_score__gte=60, overall_health_score__lt=80).count()),
            ('40-59', FinancialAnalysisHistory.objects.filter(overall_health_score__gte=40, overall_health_score__lt=60).count()),
            ('0-39', FinancialAnalysisHistory.objects.filter(overall_health_score__lt=40).count()),
        ]
        
        # 月別分析数（過去12ヶ月）
        from django.db.models.functions import TruncMonth
        monthly_stats = FinancialAnalysisHistory.objects.filter(
            analysis_date__gte=datetime.now() - timedelta(days=365)
        ).annotate(
            month=TruncMonth('analysis_date')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        # 平均値
        avg_health_score = FinancialAnalysisHistory.objects.aggregate(
            avg=Avg('overall_health_score')
        )['avg'] or 0
        
        avg_confidence_score = FinancialAnalysisHistory.objects.aggregate(
            avg=Avg('management_confidence_score')
        )['avg'] or 0
        
        context.update({
            'basic_stats': {
                'total_analyses': total_analyses,
                'total_financial_records': total_financial_records,
                'recent_analyses': recent_analyses,
                'avg_health_score': round(avg_health_score, 1),
                'avg_confidence_score': round(avg_confidence_score, 1),
            },
            'risk_stats': list(risk_stats),
            'cf_pattern_stats': list(cf_pattern_stats),
            'score_distribution': score_ranges,
            'monthly_stats': list(monthly_stats),
        })
        
        return context


class CompanyFinancialComparisonView(TemplateView):
    """企業間財務比較ページ"""
    template_name = 'earnings_analysis/financial/comparison.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 比較対象企業のリスト取得
        companies = self.request.GET.getlist('companies')  # 複数の企業コード
        
        if companies:
            # 各企業の最新財務データを取得
            comparison_data = []
            
            for company_code in companies[:5]:  # 最大5社まで
                # EDINETコードまたは証券コードで検索
                financial_records = CompanyFinancialData.objects.filter(
                    Q(document__edinet_code=company_code) |
                    Q(document__securities_code=company_code) |
                    Q(company__edinet_code=company_code) |
                    Q(company__securities_code=company_code)
                ).select_related('document', 'company').order_by('-period_end')
                
                latest_record = financial_records.first()
                if latest_record:
                    company_name = latest_record.company.company_name if latest_record.company else latest_record.document.company_name
                    securities_code = latest_record.company.securities_code if latest_record.company else latest_record.document.securities_code
                    
                    comparison_data.append({
                        'company_name': company_name,
                        'securities_code': securities_code,
                        'latest_data': latest_record,
                        'historical_data': list(financial_records[:4]),  # 過去4期分
                    })
            
            context['comparison_data'] = comparison_data
        
        # 検索用の企業候補
        from ..models import Company
        popular_companies = Company.objects.filter(
            is_active=True,
            securities_code__isnull=False
        ).order_by('company_name')[:20]
        
        context.update({
            'selected_companies': companies,
            'popular_companies': popular_companies,
        })
        
        return context