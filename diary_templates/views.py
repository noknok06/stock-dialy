from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .defaults import SAMPLE_TEMPLATE_TITLE, ensure_sample_template
from .forms import DiaryTemplateForm
from .models import DiaryTemplate


class DiaryTemplateListView(LoginRequiredMixin, ListView):
    model = DiaryTemplate
    template_name = 'diary_templates/list.html'
    context_object_name = 'templates'

    def get_queryset(self):
        return DiaryTemplate.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['has_sample_template'] = DiaryTemplate.objects.filter(
            user=self.request.user, title=SAMPLE_TEMPLATE_TITLE
        ).exists()
        return context


@login_required
@require_POST
def add_sample_template(request):
    """重厚版「サンプルテンプレート」を任意で追加する。既存があれば何もしない。"""
    ensure_sample_template(request.user)
    return redirect('diary_templates:list')


class DiaryTemplateCreateView(LoginRequiredMixin, CreateView):
    model = DiaryTemplate
    form_class = DiaryTemplateForm
    template_name = 'diary_templates/form.html'
    success_url = reverse_lazy('diary_templates:list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class DiaryTemplateUpdateView(LoginRequiredMixin, UpdateView):
    model = DiaryTemplate
    form_class = DiaryTemplateForm
    template_name = 'diary_templates/form.html'
    success_url = reverse_lazy('diary_templates:list')

    def get_queryset(self):
        return DiaryTemplate.objects.filter(user=self.request.user)


class DiaryTemplateDeleteView(LoginRequiredMixin, DeleteView):
    model = DiaryTemplate
    template_name = 'diary_templates/confirm_delete.html'
    success_url = reverse_lazy('diary_templates:list')

    def get_queryset(self):
        return DiaryTemplate.objects.filter(user=self.request.user)
