# watchlist/forms.py
from django import forms
from .models import WatchlistEntry, WatchlistNote
from tags.models import Tag
from ckeditor_uploader.widgets import CKEditorUploadingWidget

class WatchlistEntryForm(forms.ModelForm):
    """ウォッチリストエントリー作成・編集フォーム"""
    class Meta:
        model = WatchlistEntry
        fields = [
            'stock_symbol', 'stock_name', 'discovery_date',
            'analysis', 'interest_reason', 'potential_entry_price',
            'status', 'priority', 'tags'
        ]
        widgets = {
            'stock_symbol': forms.TextInput(attrs={'class': 'form-control'}),
            'stock_name': forms.TextInput(attrs={'class': 'form-control'}),
            'discovery_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'analysis': CKEditorUploadingWidget(config_name='default'),
            'interest_reason': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'potential_entry_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-control', 'size': '5'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(WatchlistEntryForm, self).__init__(*args, **kwargs)
        
        if user:
            self.fields['tags'].queryset = Tag.objects.filter(user=user)

class WatchlistNoteForm(forms.ModelForm):
    """ウォッチリストエントリーへの追加メモ/更新フォーム"""
    class Meta:
        model = WatchlistNote
        fields = ['date', 'content', 'current_price', 'action']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'content': CKEditorUploadingWidget(config_name='default'),
            'current_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'action': forms.Select(attrs={'class': 'form-select'}),
        }