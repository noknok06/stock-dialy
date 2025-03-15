# analysis_template/forms.py
from django import forms
from .models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from django.forms import inlineformset_factory

class AnalysisTemplateForm(forms.ModelForm):
    class Meta:
        model = AnalysisTemplate
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class AnalysisItemForm(forms.ModelForm):
    class Meta:
        model = AnalysisItem
        fields = ['name', 'description', 'item_type', 'choices', 'value_label', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'item_type': forms.Select(attrs={'class': 'form-select', 'id': 'item_type_select'}),
            'choices': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'value_label': forms.TextInput(attrs={'class': 'form-control'}),  # 追加
            'order': forms.NumberInput(attrs={'class': 'form-control'})
        }

# 既存のフォームセットファクトリを更新して、新しいフィールドを含める
AnalysisItemFormSet = inlineformset_factory(
    AnalysisTemplate, 
    AnalysisItem, 
    form=AnalysisItemForm,
    extra=1,  # 新規作成時に表示する空のフォームの数
    min_num=1,  # 最低限必要なフォームの数
    validate_min=True,  # 最低数の検証を行うか
    can_delete=True  # 削除ボタンを表示するか
)


class DiaryAnalysisValueForm(forms.ModelForm):
    class Meta:
        model = DiaryAnalysisValue
        fields = ['analysis_item', 'number_value', 'text_value']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # analysis_itemのインスタンスが設定されている場合
        if self.instance and self.instance.analysis_item:
            item = self.instance.analysis_item
            
            # 項目タイプに基づいてフィールドを設定
            if item.item_type == 'number':
                self.fields['number_value'] = forms.DecimalField(
                    label=item.name,
                    required=False,
                    widget=forms.NumberInput(attrs={'class': 'form-control'})
                )
                self.fields['text_value'].widget = forms.HiddenInput()
            elif item.item_type == 'select' and item.choices:
                choices = [(choice, choice) for choice in item.get_choices_list()]
                choices.insert(0, ('', '選択してください'))
                self.fields['text_value'] = forms.ChoiceField(
                    label=item.name,
                    choices=choices,
                    required=False,
                    widget=forms.Select(attrs={'class': 'form-select'})
                )
                self.fields['number_value'].widget = forms.HiddenInput()
            else:  # text
                self.fields['text_value'] = forms.CharField(
                    label=item.name,
                    required=False,
                    widget=forms.TextInput(attrs={'class': 'form-control'})
                )
                self.fields['number_value'].widget = forms.HiddenInput()
            
            # 説明があれば表示
            if item.description:
                help_text = item.description
                if item.item_type == 'number':
                    self.fields['number_value'].help_text = help_text
                else:
                    self.fields['text_value'].help_text = help_text

# 分析項目値のセットを作成するための工場関数
def create_analysis_value_formset(template, diary=None, data=None):
    """
    指定されたテンプレートの分析項目に基づいてフォームセットを作成
    
    Args:
        template: AnalysisTemplateインスタンス
        diary: 既存のStockDiaryインスタンス（編集時など）
        data: POSTデータ（保存時）
    
    Returns:
        分析項目値のフォームのリスト
    """
    forms = []
    
    # テンプレートの各分析項目についてフォームを作成
    for item in template.items.all():
        initial = {}
        instance = None
        
        # 既存の日記がある場合、その分析項目の値を取得
        if diary:
            try:
                instance = DiaryAnalysisValue.objects.get(diary=diary, analysis_item=item)
            except DiaryAnalysisValue.DoesNotExist:
                instance = DiaryAnalysisValue(diary=diary, analysis_item=item)
        else:
            instance = DiaryAnalysisValue(analysis_item=item)
            
        # フォームを作成して追加
        prefix = f"analysis_item_{item.id}"
        if data:
            form = DiaryAnalysisValueForm(data=data, instance=instance, prefix=prefix)
        else:
            form = DiaryAnalysisValueForm(instance=instance, prefix=prefix)
            
        forms.append((item, form))
    
    return forms