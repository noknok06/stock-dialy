# tags/views.py
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Tag
from django import forms

class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'})
        }

class TagListView(LoginRequiredMixin, ListView):
    model = Tag
    template_name = 'tags/tag_list.html'
    context_object_name = 'tags'
    
    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # スピードダイアルのアクションを定義
        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'add',
                'url': reverse_lazy('tags:create'),
                'icon': 'bi-plus-lg',
                'label': '新規作成'
            }
        ]
        context['page_actions'] = analytics_actions
        return context

class TagCreateView(LoginRequiredMixin, CreateView):
    model = Tag
    form_class = TagForm
    template_name = 'tags/tag_form.html'
    success_url = reverse_lazy('tags:list')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # スピードダイアルのアクションを定義
        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        context['page_actions'] = analytics_actions
        return context


class TagUpdateView(LoginRequiredMixin, UpdateView):
    model = Tag
    form_class = TagForm
    template_name = 'tags/tag_form.html'
    success_url = reverse_lazy('tags:list')
    
    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # スピードダイアルのアクションを定義
        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        context['page_actions'] = analytics_actions
        return context


class TagDeleteView(LoginRequiredMixin, DeleteView):
    model = Tag
    template_name = 'tags/tag_confirm_delete.html'
    success_url = reverse_lazy('tags:list')
    
    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # スピードダイアルのアクションを定義
        analytics_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('tags:list'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        context['page_actions'] = analytics_actions
        return context
