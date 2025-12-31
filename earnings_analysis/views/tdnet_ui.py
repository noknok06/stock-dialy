# earnings_analysis/views/tdnet_ui.py

from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404
from ..models import TDNETReport, TDNETDisclosure
import logging

logger = logging.getLogger('earnings_analysis.tdnet')


class TDNETReportListView(ListView):
    """
    レポート一覧（ユーザー向け・スマホ最適化）
    公開されているレポートのみ表示
    """
    model = TDNETReport
    template_name = 'earnings_analysis/tdnet/user/report_list.html'
    context_object_name = 'reports'
    paginate_by = 15
    
    def get_queryset(self):
        queryset = TDNETReport.objects.filter(
            status='published'
        ).select_related('disclosure').order_by('-published_at')
        
        report_type = self.request.GET.get('type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        company_name = self.request.GET.get('company')
        if company_name:
            queryset = queryset.filter(
                disclosure__company_name__icontains=company_name
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = '開示レポート'
        context['report_types'] = TDNETReport.REPORT_TYPE_CHOICES
        return context


class TDNETReportDetailView(DetailView):
    """
    レポート詳細（ユーザー向け・スマホ最適化）
    公開されているレポートのみ表示、閲覧数をカウント
    """
    model = TDNETReport
    template_name = 'earnings_analysis/tdnet/user/report_detail.html'
    context_object_name = 'report'
    slug_field = 'report_id'
    slug_url_kwarg = 'report_id'
    
    def get_queryset(self):
        return TDNETReport.objects.filter(
            status='published'
        ).select_related('disclosure', 'disclosure__company_master')
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # 閲覧数インクリメント
        TDNETReport.objects.filter(pk=obj.pk).update(
            view_count=obj.view_count + 1
        )
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.object.one_line_summary or self.object.title
        context['sections'] = self.object.sections.order_by('order')
        return context


class CompanyTDNETReportListView(ListView):
    """
    企業別レポート一覧（スマホ最適化）
    特定企業の公開レポートを表示
    """
    model = TDNETReport
    template_name = 'earnings_analysis/tdnet/user/company_reports.html'
    context_object_name = 'reports'
    paginate_by = 15
    
    def get_queryset(self):
        self.company_code = self.kwargs['company_code']
        
        return TDNETReport.objects.filter(
            status='published',
            disclosure__company_code=self.company_code
        ).select_related('disclosure').order_by('-published_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
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
        
        context['page_title'] = f'{context["company_name"]}のレポート'
        
        return context