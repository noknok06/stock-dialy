# checklist/forms.py
from django import forms
from .models import Checklist, ChecklistItem
from django.forms import inlineformset_factory

class ChecklistForm(forms.ModelForm):
    class Meta:
        model = Checklist
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'})
        }

class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ['item_text', 'order']
        widgets = {
            'item_text': forms.TextInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'})
        }

# インラインフォームセットを作成
ChecklistItemFormSet = inlineformset_factory(
    Checklist, 
    ChecklistItem,
    form=ChecklistItemForm,
    extra=1,  # 初期表示は1つだけに変更
    can_delete=True
)