# earnings_analysis/views/tdnet_ui.py

from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Avg
from ..models import TDNETReport, TDNETDisclosure
import logging

logger = logging.getLogger('earnings_analysis.tdnet')


class TDNETReportListView(ListView):
    """
    レポート一覧（ユーザー向け・スマホ最適化）
    公開されているレポートのみ表示、検索・フィルタ機能付き
    """
    model = TDNETReport
    template_name = 'earnings_analysis/tdnet/user/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = TDNETReport.objects.filter(
            status='published'
        ).select_related('disclosure').order_by('-published_at')
        
        # キーワード検索（企業名 or 証券コード or タイトル）
        keyword = self.request.GET.get('q', '').strip()
        if keyword:
            queryset = queryset.filter(
                Q(disclosure__company_name__icontains=keyword) |
                Q(disclosure__company_code__icontains=keyword) |
                Q(title__icontains=keyword) |
                Q(one_line_summary__icontains=keyword)
            )
        
        # レポートタイプでフィルタ
        report_type = self.request.GET.get('type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        # シグナルでフィルタ
        signal = self.request.GET.get('signal')
        if signal:
            if signal == 'positive':
                queryset = queryset.filter(signal__in=['strong_positive', 'positive'])
            elif signal == 'negative':
                queryset = queryset.filter(signal__in=['strong_negative', 'negative'])
            elif signal == 'neutral':
                queryset = queryset.filter(signal='neutral')
        
        # スコア範囲でフィルタ
        min_score = self.request.GET.get('min_score')
        if min_score:
            try:
                queryset = queryset.filter(overall_score__gte=int(min_score))
            except ValueError:
                pass
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = '開示レポート'
        context['report_types'] = TDNETReport.REPORT_TYPE_CHOICES
        
        # 現在の検索条件を保持
        context['current_keyword'] = self.request.GET.get('q', '')
        context['current_type'] = self.request.GET.get('type', '')
        context['current_signal'] = self.request.GET.get('signal', '')
        context['current_min_score'] = self.request.GET.get('min_score', '')
        
        # シグナル別の統計
        base_qs = TDNETReport.objects.filter(status='published')
        context['total_count'] = base_qs.count()
        context['positive_count'] = base_qs.filter(
            signal__in=['strong_positive', 'positive']
        ).count()
        context['neutral_count'] = base_qs.filter(signal='neutral').count()
        context['negative_count'] = base_qs.filter(
            signal__in=['strong_negative', 'negative']
        ).count()
        
        # 平均スコア
        avg = base_qs.aggregate(avg=Avg('overall_score'))['avg']
        context['avg_score'] = round(avg, 1) if avg else 0
        
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
        
        # 同じ企業の他のレポート（最新3件）
        context['related_reports'] = TDNETReport.objects.filter(
            status='published',
            disclosure__company_code=self.object.disclosure.company_code
        ).exclude(pk=self.object.pk).order_by('-published_at')[:3]
        
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
        
        queryset = TDNETReport.objects.filter(
            status='published',
            disclosure__company_code=self.company_code
        ).select_related('disclosure').order_by('-published_at')
        
        # レポートタイプでフィルタ
        report_type = self.request.GET.get('type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        return queryset
    
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
        context['report_types'] = TDNETReport.REPORT_TYPE_CHOICES
        context['current_type'] = self.request.GET.get('type', '')
        
        # 平均スコアを計算
        reports = self.get_queryset()
        if reports.exists():
            context['avg_score'] = reports.aggregate(
                avg=Avg('overall_score')
            )['avg']
        
        return context