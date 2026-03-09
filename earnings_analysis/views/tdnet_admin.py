# earnings_analysis/views/tdnet_admin.py

from django.views import View
from django.views.generic import FormView, ListView, DetailView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from ..forms import PDFUploadForm
from ..models import TDNETDisclosure, TDNETReport
from ..models.tdnet import TDNETPDFJob
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
        """フォーム送信時の処理（バックグラウンドタスクとして非同期実行）"""
        from django_q.tasks import async_task
        from ..tasks import generate_report_from_pdf_url_task

        pdf_url = form.cleaned_data['pdf_url']
        company_code = form.cleaned_data['company_code']
        company_name = form.cleaned_data['company_name']
        disclosure_type = form.cleaned_data['disclosure_type']
        title = form.cleaned_data['title']
        max_pdf_pages = form.cleaned_data['max_pdf_pages']

        # ジョブレコードを作成してすぐにステータスページへリダイレクト
        try:
            job = TDNETPDFJob.objects.create(
                pdf_url=pdf_url,
                company_code=company_code,
                company_name=company_name,
                disclosure_type=disclosure_type,
                title=title,
                max_pdf_pages=max_pdf_pages,
                created_by=self.request.user,
                status=TDNETPDFJob.STATUS_PENDING,
            )

            async_task(
                generate_report_from_pdf_url_task,
                str(job.job_id),
                pdf_url,
                company_code,
                company_name,
                disclosure_type,
                title,
                self.request.user.pk,
                max_pdf_pages,
            )

            messages.info(
                self.request,
                'PDF処理をバックグラウンドで開始しました。完了までしばらくお待ちください。'
            )
            return redirect('copomo:tdnet-admin-job-status', job_id=job.job_id)

        except Exception as e:
            logger.error(f"PDFジョブ作成エラー: {e}")
            messages.error(self.request, f'予期しないエラー: {str(e)}')
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'PDF URLから開示情報を作成'
        return context


class TDNETJobStatusView(AdminRequiredMixin, View):
    """PDFジョブステータス確認ページ"""

    def get(self, request, job_id):
        job = get_object_or_404(TDNETPDFJob, job_id=job_id)
        context = {
            'page_title': 'PDF処理状況',
            'job': job,
        }
        return render(request, 'earnings_analysis/tdnet/admin/job_status.html', context)


class TDNETJobStatusAPIView(AdminRequiredMixin, View):
    """PDFジョブステータスAPI（AJAXポーリング用）"""

    def get(self, request, job_id):
        job = get_object_or_404(TDNETPDFJob, job_id=job_id)

        data = {
            'status': job.status,
            'status_display': job.get_status_display(),
            'is_done': job.is_done,
            'is_error': job.is_error,
            'error_message': job.error_message,
            'report_admin_url': None,
            'disclosure_id': None,
        }

        if job.is_done and job.report:
            data['report_admin_url'] = reverse(
                'admin:earnings_analysis_tdnetreport_change', args=[job.report.pk]
            )
        if job.is_done and job.disclosure:
            data['disclosure_id'] = job.disclosure.disclosure_id

        return JsonResponse(data)


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