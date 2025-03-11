# analysis_templates/forms.py
from django import forms
from .models import AnalysisTemplate, TemplateGroup, TemplateField, StockAnalysisData, FieldValue
from django.forms import inlineformset_factory
import re

class AnalysisTemplateForm(forms.ModelForm):
    class Meta:
        model = AnalysisTemplate
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
        }

class TemplateGroupForm(forms.ModelForm):
    class Meta:
        model = TemplateGroup
        fields = ['name', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'})
        }

class TemplateFieldForm(forms.ModelForm):
    class Meta:
        model = TemplateField
        fields = ['label', 'key', 'description', 'group', 'field_type', 'order', 
                 'unit', 'is_required', 'default_value', 'min_value', 'max_value', 'benchmark_value']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'form-control'}),
            'key': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'group': forms.Select(attrs={'class': 'form-control'}),
            'field_type': forms.Select(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_value': forms.TextInput(attrs={'class': 'form-control'}),
            'min_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'benchmark_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
        }
    
    def clean_key(self):
        """keyフィールドをスラグ形式に変換"""
        key = self.cleaned_data.get('key')
        if key:
            # スペースをアンダースコアに置換し、英数字とアンダースコアのみを許可
            key = re.sub(r'\s+', '_', key.lower())
            key = re.sub(r'[^\w]', '', key)
        return key

# インラインフォームセットを作成
TemplateGroupFormSet = inlineformset_factory(
    AnalysisTemplate, 
    TemplateGroup,
    form=TemplateGroupForm,
    extra=1,
    can_delete=True
)

TemplateFieldFormSet = inlineformset_factory(
    AnalysisTemplate, 
    TemplateField,
    form=TemplateFieldForm,
    extra=1,
    can_delete=True
)

class FieldValueForm(forms.ModelForm):
    """フィールド値の入力フォーム"""
    class Meta:
        model = FieldValue
        fields = ['field', 'text_value', 'number_value', 'date_value', 'boolean_value']
    
    # フィールド実装を動的に追加/削除するメソッド
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if hasattr(self, 'instance') and hasattr(self.instance, 'field') and self.instance.field:
            field_type = self.instance.field.field_type
            
            # 不要なフィールドを削除
            for field_name in list(self.fields.keys()):
                if field_name == 'field':
                    continue
                
                if field_type == 'number' and field_name == 'number_value':
                    continue
                elif field_type == 'percentage' and field_name == 'number_value':
                    continue
                elif field_type == 'text' and field_name == 'text_value':
                    continue
                elif field_type == 'date' and field_name == 'date_value':
                    continue
                elif field_type == 'boolean' and field_name == 'boolean_value':
                    continue
                elif field_type == 'rating' and field_name == 'number_value':
                    continue
                
                # 不要なフィールドを削除
                del self.fields[field_name]
            
            # フィールドタイプに応じたウィジェット属性を設定
            if field_type == 'number':
                self.fields['number_value'].widget.attrs.update({
                    'class': 'form-control',
                    'step': '0.01'
                })
                if self.instance.field.unit:
                    self.fields['number_value'].label = f"{self.instance.field.label} ({self.instance.field.unit})"
                
                # min/max値を設定
                if self.instance.field.min_value is not None:
                    self.fields['number_value'].widget.attrs['min'] = self.instance.field.min_value
                if self.instance.field.max_value is not None:
                    self.fields['number_value'].widget.attrs['max'] = self.instance.field.max_value
                
            elif field_type == 'percentage':
                self.fields['number_value'].widget.attrs.update({
                    'class': 'form-control',
                    'step': '0.1'
                })
                self.fields['number_value'].label = f"{self.instance.field.label} (%)"
                
            elif field_type == 'text':
                self.fields['text_value'].widget.attrs.update({'class': 'form-control'})
                
            elif field_type == 'date':
                self.fields['date_value'].widget = forms.DateInput(
                    attrs={'class': 'form-control', 'type': 'date'}
                )
                
            elif field_type == 'boolean':
                self.fields['boolean_value'].widget = forms.CheckboxInput(
                    attrs={'class': 'form-check-input'}
                )
                
            elif field_type == 'rating':
                self.fields['number_value'].widget = forms.Select(
                    choices=[(i, f"{'★' * i}") for i in range(1, 6)],
                    attrs={'class': 'form-control'}
                )
            
            # 必須フィールドの設定
            if self.instance.field.is_required:
                visible_fields = [f for f in self.fields if f != 'field']
                if visible_fields:
                    self.fields[visible_fields[0]].required = True
            
            # ラベルの設定
            for field_name in self.fields:
                if field_name != 'field':
                    self.fields[field_name].label = self.instance.field.label

# テンプレート内の各フィールドに対応する値フォームを生成するヘルパー関数
def create_field_value_forms(template, analysis_data=None):
    forms = []
    
    for field in template.fields.all():
        field_value = None
        if analysis_data:
            # 既存のデータがあれば取得
            field_value = FieldValue.objects.filter(
                analysis_data=analysis_data,
                field=field
            ).first()
        
        # 存在しなければ新規作成
        if not field_value:
            field_value = FieldValue(field=field)
            if analysis_data:
                field_value.analysis_data = analysis_data
        
        # フォームを作成
        form = FieldValueForm(instance=field_value, prefix=f"field_{field.id}")
        forms.append((field, form))
    
    return forms