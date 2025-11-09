# analysis_template/forms.py
from django import forms
from django.core.exceptions import ValidationError
from company_master.models import CompanyMaster
from .models import AnalysisTemplate, TemplateMetrics, MetricDefinition


class AnalysisTemplateForm(forms.ModelForm):
    """分析テンプレートフォーム"""
    
    class Meta:
        model = AnalysisTemplate
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'テンプレート名を入力',
                'maxlength': '200'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'テンプレートの説明を入力（任意）'
            }),
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name or not name.strip():
            raise ValidationError('テンプレート名は必須です')
        return name.strip()


class CompanySelectionForm(forms.Form):
    """企業選択フォーム"""
    company_code = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '株式コードを入力',
            'id': 'company-code-input',
            'autocomplete': 'off'
        }),
        label='株式コード'
    )
    
    companies = forms.ModelMultipleChoiceField(
        queryset=CompanyMaster.objects.all().order_by('code'),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label='企業を選択'
    )
    
    def clean_company_code(self):
        code = self.cleaned_data.get('company_code')
        if code:
            try:
                CompanyMaster.objects.get(code=code)
            except CompanyMaster.DoesNotExist:
                raise ValidationError(f'株式コード {code} は存在しません')
        return code


class TemplateMetricsForm(forms.ModelForm):
    """テンプレート指標入力フォーム"""
    
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
                'placeholder': '指標値を入力'
            }),
            'fiscal_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例: 2024',
                'maxlength': '10'
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
        ).order_by('display_order', 'name')


class BulkMetricsForm(forms.Form):
    """一括指標入力フォーム"""
    
    def __init__(self, *args, template=None, companies=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if not template or not companies:
            return
        
        # 各企業×指標の組み合わせでフィールドを動的生成
        metrics = MetricDefinition.objects.filter(is_active=True).order_by('display_order')
        
        for company in companies:
            for metric in metrics:
                field_name = f'metric_{company.code}_{metric.id}'
                
                # 既存値を取得
                existing_value = None
                try:
                    existing_metric = TemplateMetrics.objects.get(
                        template=template,
                        company=company,
                        metric_definition=metric
                    )
                    existing_value = existing_metric.value
                except TemplateMetrics.DoesNotExist:
                    pass
                
                self.fields[field_name] = forms.DecimalField(
                    required=False,
                    max_digits=15,
                    decimal_places=2,
                    initial=existing_value,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control form-control-sm',
                        'placeholder': metric.get_formatted_unit(),
                        'step': '0.01'
                    }),
                    label=f'{company.name} - {metric.display_name}'
                )


class CompanySearchForm(forms.Form):
    """企業検索フォーム"""
    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '企業名または株式コードで検索',
            'id': 'company-search-input'
        }),
        label='検索'
    )
    
    industry = forms.ChoiceField(
        choices=[('', '全業種')] + [
            (industry, industry) for industry in 
            CompanyMaster.objects.values_list('industry_name_33', flat=True)
            .distinct().order_by('industry_name_33') if industry
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='業種'
    )
    
    market = forms.ChoiceField(
        choices=[('', '全市場')] + [
            (market, market) for market in 
            CompanyMaster.objects.values_list('market', flat=True)
            .distinct().order_by('market') if market
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='市場'
    )


class MetricDefinitionForm(forms.ModelForm):
    """指標定義フォーム（管理者用）"""
    
    class Meta:
        model = MetricDefinition
        fields = [
            'name', 'display_name', 'metric_type', 'description',
            'unit', 'min_value', 'max_value', 'is_active', 'display_order'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'metric_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'min_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }