# analysis_template/forms.py
from django import forms
from django.forms import inlineformset_factory
from .models import (
    AnalysisTemplate, TemplateCompany, TemplateMetrics,
    MetricDefinition, CompanyMaster
)


class AnalysisTemplateForm(forms.ModelForm):
    """分析テンプレートフォーム"""
    
    class Meta:
        model = AnalysisTemplate
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'テンプレート名を入力'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'テンプレートの説明（任意）'
            }),
        }


class TemplateCompanyForm(forms.ModelForm):
    """テンプレート企業フォーム"""
    company_code = forms.CharField(
        label='銘柄コード',
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '銘柄コードで検索'
        })
    )
    
    class Meta:
        model = TemplateCompany
        fields = ['company', 'display_order']
        widgets = {
            'company': forms.Select(attrs={
                'class': 'form-select'
            }),
            'display_order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 初期値として全企業を表示
        self.fields['company'].queryset = CompanyMaster.objects.all().order_by('code')


# テンプレート企業のフォームセット
TemplateCompanyFormSet = inlineformset_factory(
    AnalysisTemplate,
    TemplateCompany,
    form=TemplateCompanyForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class TemplateMetricsForm(forms.ModelForm):
    """テンプレート指標フォーム"""
    
    class Meta:
        model = TemplateMetrics
        fields = ['metric_definition', 'value', 'fiscal_year', 'notes']
        widgets = {
            'metric_definition': forms.Select(attrs={
                'class': 'form-select'
            }),
            'value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '値を入力'
            }),
            'fiscal_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例: 2024'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': '備考（任意）'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # アクティブな指標定義のみ表示
        self.fields['metric_definition'].queryset = MetricDefinition.objects.filter(
            is_active=True
        ).order_by('display_order')


class BulkMetricsForm(forms.Form):
    """一括指標入力フォーム"""
    company = forms.ModelChoiceField(
        label='企業',
        queryset=CompanyMaster.objects.all().order_by('code'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    fiscal_year = forms.CharField(
        label='会計年度',
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '例: 2024'
        })
    )
    
    def __init__(self, *args, template=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if template:
            # テンプレートに登録されている企業のみ選択可能
            self.fields['company'].queryset = template.companies.all().order_by('code')
            
            # 各指標定義に対してフィールドを動的に追加
            for metric_def in MetricDefinition.objects.filter(is_active=True).order_by('display_order'):
                field_name = f'metric_{metric_def.id}'
                self.fields[field_name] = forms.DecimalField(
                    label=metric_def.display_name,
                    max_digits=15,
                    decimal_places=2,
                    required=False,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'step': '0.01',
                        'placeholder': f'{metric_def.get_formatted_unit()}'
                    })
                )


class CompanySearchForm(forms.Form):
    """企業検索フォーム"""
    query = forms.CharField(
        label='検索',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '銘柄コードまたは企業名で検索'
        })
    )
    industry = forms.CharField(
        label='業種',
        max_length=10,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 業種の選択肢を動的に設定
        industries = CompanyMaster.objects.values_list(
            'industry_code_33', 'industry_name_33'
        ).distinct().order_by('industry_code_33')
        
        self.fields['industry'].widget.choices = [('', '全業種')] + list(industries)