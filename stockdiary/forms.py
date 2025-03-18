# stockdiary/forms.py
from django import forms
from .models import StockDiary
from tags.models import Tag
from checklist.models import Checklist
from analysis_template.models import AnalysisTemplate
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from .models import DiaryNote

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
            'sell_date', 'sell_price', 'memo', 'checklist', 'tags', 'sector'
        ]
        widgets = {
            'stock_symbol': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '日本株: 7203, 米国株: AAPL など',
                'sector': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            }),
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
        self.fields['stock_symbol'].label = "銘柄コード（任意）"
        self.fields['stock_symbol'].help_text = "例: 7203（トヨタ）、AAPL（アップル）など。入力すると自動検索します。"
        self.fields['stock_symbol'].required = False  # 必須項目から外す
        self.fields['reason'].label = "購入理由 / 投資記録"
        self.fields['memo'].label = "追加メモ / コメント"
    
        # 売却時の入力値検証のためにsell_dateが入力されたときのみチェック
        if self.data.get('sell_date'):
            self.fields['purchase_price'].required = True
            self.fields['purchase_quantity'].required = True

        self.fields['purchase_price'].help_text = "記録のみの場合は空欄でもOK"
        self.fields['purchase_quantity'].help_text = "記録のみの場合は空欄でもOK"

    def clean(self):
        cleaned_data = super().clean()
        sell_date = cleaned_data.get('sell_date')
        purchase_price = cleaned_data.get('purchase_price')
        purchase_quantity = cleaned_data.get('purchase_quantity')
        
        # 売却日が入力されている場合は、購入価格と株数が必須
        if sell_date:
            if purchase_price is None:
                self.add_error('purchase_price', '売却する場合は購入価格を入力してください')
            if purchase_quantity is None:
                self.add_error('purchase_quantity', '売却する場合は購入数量を入力してください')
        
        # 売却日が入力されている場合のみ価格と数量を必須にする
        if sell_date:
            if purchase_price is None:
                self.add_error('purchase_price', '売却する場合は購入価格を入力してください')
            if purchase_quantity is None:
                self.add_error('purchase_quantity', '売却する場合は購入数量を入力してください')
        
        return cleaned_data
        
class DiaryNoteForm(forms.ModelForm):
    """日記エントリーへの継続的なメモ追加フォーム"""
    class Meta:
        model = DiaryNote
        fields = ['date', 'note_type', 'importance', 'content', 'current_price']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'note_type': forms.Select(attrs={'class': 'form-select'}),
            'importance': forms.Select(attrs={'class': 'form-select'}),
            'content': CKEditorUploadingWidget(config_name='basic'),  
            'current_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }        