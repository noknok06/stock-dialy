# earnings_analysis/views/tdnet_ui.py

from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404
from ..models import TDNETReport, TDNETDisclosure
import logging

logger = logging.getLogger('earnings_analysis.tdnet')


class TDNETReportListView(ListView):
    """
    レポート一覧（ユーザー向け）
    
    公開されているレポートのみ表示
    """
    model = TDNETReport
    template_name = 'earnings_analysis/tdnet/user/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20
    
    def get_queryset(self):
        """公開されているレポートのみ取得"""
        queryset = TDNETReport.objects.filter(
            status='published'
        ).select_related('disclosure').order_by('-published_at')
        
        # レポート種別フィルタ
        report_type = self.request.GET.get('type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        # 企業名検索
        company_name = self.request.GET.get('company')
        if company_name:
            queryset = queryset.filter(
                disclosure__company_name__icontains=company_name
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'TDNETレポート一覧'
        context['report_types'] = TDNETReport.REPORT_TYPE_CHOICES
        return context


class TDNETReportDetailView(DetailView):
    """
    レポート詳細（ユーザー向け）
    
    公開されているレポートのみ表示、閲覧数をカウント
    """
    model = TDNETReport
    template_name = 'earnings_analysis/tdnet/user/report_detail.html'
    context_object_name = 'report'
    slug_field = 'report_id'
    slug_url_kwarg = 'report_id'
    
    def get_queryset(self):
        """公開されているレポートのみ取得"""
        return TDNETReport.objects.filter(
            status='published'
        ).select_related('disclosure', 'disclosure__company_master')
    
    def get_object(self, queryset=None):
        """閲覧数をインクリメント"""
        obj = super().get_object(queryset)
        obj.increment_view_count()
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.object.title
        context['sections'] = self.object.sections.order_by('order')
        
        # 関連レポート（同じ企業の他のレポート）
        related_reports = TDNETReport.objects.filter(
            status='published',
            disclosure__company_code=self.object.disclosure.company_code
        ).exclude(
            id=self.object.id
        ).order_by('-published_at')[:5]
        
        context['related_reports'] = related_reports
        
        return context


class CompanyTDNETReportListView(ListView):
    """
    企業別レポート一覧
    
    特定企業の公開レポートを表示
    """
    model = TDNETReport
    template_name = 'earnings_analysis/tdnet/user/company_reports.html'
    context_object_name = 'reports'
    paginate_by = 20
    
    def get_queryset(self):
        """企業コードでフィルタ"""
        self.company_code = self.kwargs['company_code']
        
        return TDNETReport.objects.filter(
            status='published',
            disclosure__company_code=self.company_code
        ).select_related('disclosure').order_by('-published_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 企業情報取得
        disclosure = TDNETDisclosure.objects.filter(
            company_code=self.company_code
        ).first()
        
        if disclosure:
            context['company_name'] = disclosure.company_name
            context['company_code'] = self.company_code
            context['company_master'] = disclosure.company_master
        else:
            context['company_name'] = self.company_code
            context['company_code'] = self.company_code
        
        context['page_title'] = f'{context["company_name"]}のレポート一覧'
        
        return context