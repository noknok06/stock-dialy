from django import forms

from .models import DiaryTemplate


class DiaryTemplateForm(forms.ModelForm):
    class Meta:
        model = DiaryTemplate
        fields = ['title', 'body']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例: 企業分析（標準）',
                'maxlength': 100,
            }),
            'body': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 20,
                'placeholder': '## ひとこと要約\n\n## ビジネスモデル\n- ...',
            }),
        }
        labels = {
            'title': 'テンプレートタイトル',
            'body': 'テンプレート本文',
        }
