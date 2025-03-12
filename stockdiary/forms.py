# stockdiary/forms.py
from django import forms
from .models import StockDiary
from tags.models import Tag
from checklist.models import Checklist
from analysis_template.models import AnalysisTemplate
from ckeditor_uploader.widgets import CKEditorUploadingWidget

class StockDiaryForm(forms.ModelForm):
    analysis_template = forms.ModelChoiceField(
        queryset=AnalysisTemplate.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="分析テンプレート",
        help_text="分析データを入力する場合は、テンプレートを選択してください"
    )

    class Meta:
        model = StockDiary
        fields = [
            'stock_symbol', 'stock_name', 'purchase_date', 
            'purchase_price', 'purchase_quantity', 'reason',
            'sell_date', 'sell_price', 'memo', 'checklist', 'tags'
        ]
        widgets = {
            'stock_symbol': forms.TextInput(attrs={'class': 'form-control'}),
            'stock_name': forms.TextInput(attrs={'class': 'form-control'}),
            'purchase_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'purchase_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            # 購入理由欄の拡張
            'reason': CKEditorUploadingWidget(config_name='default'), 
            'sell_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'sell_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'memo': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'checklist': forms.SelectMultiple(attrs={'class': 'form-control', 'size': '5'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-control', 'size': '5'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(StockDiaryForm, self).__init__(*args, **kwargs)
        
        if user:
            self.fields['checklist'].queryset = Checklist.objects.filter(user=user)
            self.fields['tags'].queryset = Tag.objects.filter(user=user)
            self.fields['analysis_template'].queryset = AnalysisTemplate.objects.filter(user=user)
            
        # ラベルを変更
        self.fields['reason'].label = "購入理由 / 投資記録"
        self.fields['memo'].label = "追加メモ / コメント"