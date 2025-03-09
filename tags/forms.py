# stockdiary/forms.py
class StockDiaryForm(forms.ModelForm):
    class Meta:
        model = StockDiary
        fields = [
            'stock_symbol', 'stock_name', 'purchase_date', 
            'purchase_price', 'purchase_quantity', 'reason',
            'sell_date', 'sell_price', 'memo', 'checklist', 'tags'
        ]
        widgets = {
            # 他のフィールド...
            'tags': forms.CheckboxSelectMultiple(attrs={'class': 'tag-checkbox-list'}),
        }