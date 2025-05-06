# financial_reports/views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.contrib import messages

from .models import Company, FinancialReport, ReportView
from .forms import CompanyForm, FinancialReportForm

# ユーティリティ関数
def is_admin(user):
    return user.is_authenticated and user.is_staff

# 管理者権限確認ミックスイン
class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)


class ReportListView(ListView):
    model = FinancialReport
    template_name = 'financial_reports/public/report_list.html'
    context_object_name = 'reports'
    paginate_by = 9  # 1ページあたり9件表示
    
    def get_queryset(self):
        queryset = FinancialReport.objects.filter(is_public=True)
        
        # 検索条件
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                models.Q(company__name__icontains=q) |
                models.Q(company__code__icontains=q) |
                models.Q(data__contains={"overallSummary": q})
            )
        
        # 評価フィルタ
        rating = self.request.GET.get('rating')
        if rating == 'high':
            queryset = queryset.filter(overall_rating__gte=7)
        elif rating == 'medium':
            queryset = queryset.filter(overall_rating__gte=4, overall_rating__lt=7)
        elif rating == 'low':
            queryset = queryset.filter(overall_rating__lt=4)
        
        # 投資判断フィルタ
        recommendation = self.request.GET.get('recommendation')
        if recommendation == 'buy':
            queryset = queryset.filter(data__contains={"recommendationText": "買い推奨"})
        elif recommendation == 'neutral':
            queryset = queryset.filter(data__contains={"recommendationText": "中立"})
        elif recommendation == 'sell':
            queryset = queryset.filter(data__contains={"recommendationText": "売り推奨"})
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recent_reports'] = FinancialReport.objects.filter(is_public=True).order_by('-updated_at')
        return context
        

class CompanyDetailView(DetailView):
    model = Company
    template_name = 'financial_reports/public/company_detail.html'
    
    def get_queryset(self):
        return Company.objects.filter(is_public=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reports'] = self.object.reports.filter(is_public=True)
        return context

class ReportDetailView(DetailView):
    model = FinancialReport
    template_name = 'financial_reports/public/report_detail.html'
    
    def get_queryset(self):
        return FinancialReport.objects.filter(is_public=True)
    
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        
        # 閲覧履歴を記録
        report = self.object
        ip_address = self.request.META.get('REMOTE_ADDR', '0.0.0.0')
        user_agent = self.request.META.get('HTTP_USER_AGENT', '')
        
        ReportView.objects.create(
            report=report,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return response

# 管理者ビュー
class AdminDashboardView(StaffRequiredMixin, TemplateView):
    template_name = 'financial_reports/admin/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['companies'] = Company.objects.all()
        context['reports'] = FinancialReport.objects.all()
        context['popular_reports'] = FinancialReport.objects.filter(is_public=True).order_by('-views__count')[:5]
        return context

class CompanyCreateView(StaffRequiredMixin, CreateView):
    model = Company
    form_class = CompanyForm
    template_name = 'financial_reports/admin/company_form.html'
    success_url = reverse_lazy('financial_reports:admin_dashboard')
    
    def form_valid(self, form):
        messages.success(self.request, '企業情報を作成しました。')
        return super().form_valid(form)

class CompanyUpdateView(StaffRequiredMixin, UpdateView):
    model = Company
    form_class = CompanyForm
    template_name = 'financial_reports/admin/company_form.html'
    success_url = reverse_lazy('financial_reports:admin_dashboard')
    
    def form_valid(self, form):
        messages.success(self.request, '企業情報を更新しました。')
        return super().form_valid(form)

class ReportCreateView(StaffRequiredMixin, CreateView):
    model = FinancialReport
    form_class = FinancialReportForm
    template_name = 'financial_reports/admin/report_form.html'
    success_url = reverse_lazy('financial_reports:admin_dashboard')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, '決算レポートを作成しました。')
        return super().form_valid(form)

class ReportUpdateView(StaffRequiredMixin, UpdateView):
    model = FinancialReport
    form_class = FinancialReportForm
    template_name = 'financial_reports/admin/report_form.html'
    success_url = reverse_lazy('financial_reports:admin_dashboard')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, '決算レポートを更新しました。')
        return super().form_valid(form)

class ReportTogglePublishView(StaffRequiredMixin, View):
    def post(self, request, pk):
        report = get_object_or_404(FinancialReport, pk=pk)
        report.is_public = not report.is_public
        report.save()
        
        status = '公開' if report.is_public else '非公開'
        messages.success(request, f'レポートを{status}に設定しました。')
        
        return HttpResponseRedirect(reverse_lazy('financial_reports:admin_dashboard'))

