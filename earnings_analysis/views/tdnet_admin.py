# earnings_analysis/views/tdnet_admin.py

from django.views import View
from django.views.generic import FormView, ListView, DetailView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse
from ..forms import PDFUploadForm
from ..models import TDNETDisclosure, TDNETReport
from ..services.tdnet_report_generator import TDNETReportGeneratorService
import logging

logger = logging.getLogger('earnings_analysis.tdnet')


class AdminRequiredMixin(UserPassesTestMixin):
    """管理者権限が必要"""
    
    def test_func(self):
        return self.request.user.is_staff


class TDNETPDFUploadView(AdminRequiredMixin, FormView):
    """
    PDF URL入力画面
    
    PDF URLと基本情報を入力して、開示情報＋レポートを生成
    """
    template_name = 'earnings_analysis/tdnet/admin/pdf_upload.html'
    form_class = PDFUploadForm
    
    def form_valid(self, form):
        """フォーム送信時の処理"""
        pdf_url = form.cleaned_data['pdf_url']
        company_code = form.cleaned_data['company_code']
        company_name = form.cleaned_data['company_name']
        disclosure_type = form.cleaned_data['disclosure_type']
        title = form.cleaned_data['title']
        max_pdf_pages = form.cleaned_data['max_pdf_pages']
        auto_generate = form.cleaned_data['auto_generate_report']
        
        try:
            generator_service = TDNETReportGeneratorService()
            
            # PDF URL→開示情報＋レポート生成
            result = generator_service.generate_report_from_pdf_url(
                pdf_url=pdf_url,
                company_code=company_code,
                company_name=company_name,
                disclosure_type=disclosure_type,
                title=title,
                user=self.request.user,
                max_pdf_pages=max_pdf_pages
            )
            
            if result['success']:
                disclosure = result['disclosure']
                report = result['report']
                
                messages.success(
                    self.request,
                    f'開示情報とレポートを生成しました: {disclosure.disclosure_id}'
                )
                
                # レポート詳細画面へリダイレクト
                return redirect('admin:earnings_analysis_tdnetreport_change', report.id)
            else:
                messages.error(
                    self.request,
                    f'エラー: {result["error"]}'
                )
                return self.form_invalid(form)
            
        except Exception as e:
            logger.error(f"PDF処理エラー: {e}")
            messages.error(self.request, f'予期しないエラー: {str(e)}')
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'PDF URLから開示情報を作成'
        return context


class TDNETDisclosureListView(AdminRequiredMixin, ListView):
    """開示情報一覧"""
    model = TDNETDisclosure
    template_name = 'earnings_analysis/tdnet/admin/disclosure_list.html'
    context_object_name = 'disclosures'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = TDNETDisclosure.objects.select_related('company_master').order_by('-disclosure_date')
        
        # フィルタ
        disclosure_type = self.request.GET.get('type')
        if disclosure_type:
            queryset = queryset.filter(disclosure_type=disclosure_type)
        
        company_code = self.request.GET.get('company_code')
        if company_code:
            queryset = queryset.filter(company_code=company_code)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'TDNET開示情報一覧'
        context['disclosure_types'] = TDNETDisclosure.DISCLOSURE_TYPE_CHOICES
        return context


class TDNETDisclosureDetailView(AdminRequiredMixin, DetailView):
    """開示情報詳細"""
    model = TDNETDisclosure
    template_name = 'earnings_analysis/tdnet/admin/disclosure_detail.html'
    context_object_name = 'disclosure'
    slug_field = 'disclosure_id'
    slug_url_kwarg = 'disclosure_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'開示情報詳細: {self.object.disclosure_id}'
        context['reports'] = self.object.reports.all()
        return context


class TDNETReportGenerateView(AdminRequiredMixin, View):
    """レポート生成"""
    
    def post(self, request, disclosure_id):
        """レポート生成実行"""
        report_type = request.POST.get('report_type', 'earnings')
        
        try:
            generator_service = TDNETReportGeneratorService()
            
            result = generator_service.generate_report_from_disclosure(
                disclosure_id=disclosure_id,
                report_type=report_type,
                user=request.user
            )
            
            if result['success']:
                report = result['report']
                messages.success(request, f'レポートを生成しました: {report.report_id}')
                return redirect('admin:earnings_analysis_tdnetreport_change', report.id)
            else:
                messages.error(request, f'エラー: {result["error"]}')
                return redirect('admin:earnings_analysis_tdnetdisclosure_change', 
                              result['disclosure'].id if result['disclosure'] else None)
        
        except Exception as e:
            logger.error(f"レポート生成エラー: {e}")
            messages.error(request, f'予期しないエラー: {str(e)}')
            return redirect('copomo:tdnet-admin-disclosure-list')


class TDNETReportListView(AdminRequiredMixin, ListView):
    """レポート一覧（管理者用）"""
    model = TDNETReport
    template_name = 'earnings_analysis/tdnet/admin/report_list.html'
    context_object_name = 'reports'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = TDNETReport.objects.select_related('disclosure').order_by('-created_at')
        
        # フィルタ
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        report_type = self.request.GET.get('type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'TDNETレポート一覧'
        context['status_choices'] = TDNETReport.STATUS_CHOICES
        context['report_types'] = TDNETReport.REPORT_TYPE_CHOICES
        return context


class TDNETReportPublishView(AdminRequiredMixin, View):
    """レポート公開/非公開"""
    
    def post(self, request, report_id):
        """公開状態変更"""
        action = request.POST.get('action')
        
        try:
            generator_service = TDNETReportGeneratorService()
            
            if action == 'publish':
                result = generator_service.publish_report(report_id)
            elif action == 'unpublish':
                result = generator_service.unpublish_report(report_id)
            else:
                messages.error(request, '不正なアクション')
                return redirect('copomo:tdnet-admin-report-list')
            
            if result['success']:
                messages.success(request, result['message'])
            else:
                messages.error(request, result['message'])
            
            return redirect('admin:earnings_analysis_tdnetreport_change', result['report'].id)
        
        except Exception as e:
            logger.error(f"公開状態変更エラー: {e}")
            messages.error(request, f'エラー: {str(e)}')
            return redirect('copomo:tdnet-admin-report-list')