from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import DiaryTemplateForm
from .models import DiaryTemplate


class DiaryTemplateListView(LoginRequiredMixin, ListView):
    model = DiaryTemplate
    template_name = 'diary_templates/list.html'
    context_object_name = 'templates'

    def get_queryset(self):
        return DiaryTemplate.objects.filter(user=self.request.user)


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
