# journal/forms.py
from django import forms
from .models import JournalEntry, Stock, ThesisChangeTracker, DiaryJournalChecklistItem
from tags.models import Tag
from checklist.models import Checklist, ChecklistItem
from analysis_template.models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django.utils import timezone

class StockForm(forms.ModelForm):
    """銘柄情報フォーム"""
    class Meta:
        model = Stock
        fields = ['symbol', 'name', 'industry', 'sector']
        widgets = {
            'symbol': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'industry': forms.TextInput(attrs={'class': 'form-control'}),
            'sector': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.user = self.user
        if commit:
            instance.save()
        return instance

class JournalEntryForm(forms.ModelForm):
    """投資判断記録フォーム"""
    
    # 共通フィールド
    content = forms.CharField(
        widget=CKEditorUploadingWidget(config_name='default'),
        required=True,
        label="記録内容"
    )
    
    # 分析テンプレート
    analysis_template = forms.ModelChoiceField(
        queryset=AnalysisTemplate.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="分析テンプレート",
        help_text="分析データを入力する場合は、テンプレートを選択してください"
    )
    
    class Meta:
        model = JournalEntry
        fields = [
            'stock', 'entry_type', 'entry_date', 'title', 'content',
            'thesis_change', 'price_at_entry', 'watch_reason',
            'target_price', 'stop_loss', 'expected_return',
            'trade_type', 'trade_price', 'trade_quantity', 'trade_costs',
            'checklist', 'tags', 'analysis_template'
        ]
        widgets = {
            'stock': forms.Select(attrs={'class': 'form-select'}),
            'entry_type': forms.HiddenInput(),
            'entry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'thesis_change': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price_at_entry': forms.NumberInput(attrs={'class': 'form-control'}),
            'watch_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'target_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'stop_loss': forms.NumberInput(attrs={'class': 'form-control'}),
            'expected_return': forms.NumberInput(attrs={'class': 'form-control'}),
            'trade_type': forms.Select(attrs={'class': 'form-select'}),
            'trade_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'trade_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'trade_costs': forms.NumberInput(attrs={'class': 'form-control'}),
            'checklist': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.previous_entry = kwargs.pop('previous_entry', None)
        
        super().__init__(*args, **kwargs)
        
        # 初期値の設定
        if not self.instance.pk and not self.initial.get('entry_date'):
            self.initial['entry_date'] = timezone.now().date()
        
        if self.user:
            # ユーザーに関連するリストのフィルタリング
            self.fields['stock'].queryset = Stock.objects.filter(user=self.user)
            self.fields['checklist'].queryset = Checklist.objects.filter(user=self.user)
            self.fields['tags'].queryset = Tag.objects.filter(user=self.user)
            self.fields['analysis_template'].queryset = AnalysisTemplate.objects.filter(user=self.user)
        
        # 前回の記録が指定されている場合
        if self.previous_entry:
            self.fields['previous_entry'].initial = self.previous_entry.id
            self.fields['stock'].initial = self.previous_entry.stock
            # 編集不可に設定（同一銘柄の連続記録のため）
            self.fields['stock'].widget.attrs['readonly'] = True
            
            # 前回の値をヒントとして表示
            if self.previous_entry.target_price:
                self.fields['target_price'].help_text = f"前回: {self.previous_entry.target_price}"
            if self.previous_entry.stop_loss:
                self.fields['stop_loss'].help_text = f"前回: {self.previous_entry.stop_loss}"
            if self.previous_entry.expected_return:
                self.fields['expected_return'].help_text = f"前回: {self.previous_entry.expected_return}%"
    
    def clean(self):
        cleaned_data = super().clean()
        entry_type = cleaned_data.get('entry_type')
        
        # タイプ別の必須フィールドの検証
        if entry_type == 'watch':
            if not cleaned_data.get('price_at_entry'):
                self.add_error('price_at_entry', '現在株価は必須です')
        elif entry_type == 'research':
            if not cleaned_data.get('target_price'):
                self.add_error('target_price', '目標株価は必須です')
        elif entry_type == 'trade':
            trade_type = cleaned_data.get('trade_type')
            if not trade_type:
                self.add_error('trade_type', '取引タイプは必須です')
            if not cleaned_data.get('trade_price'):
                self.add_error('trade_price', '取引価格は必須です')
            if not cleaned_data.get('trade_quantity'):
                self.add_error('trade_quantity', '数量は必須です')
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if self.user:
            instance.user = self.user
        
        if self.previous_entry:
            instance.previous_entry = self.previous_entry
        
        if commit:
            instance.save()
            
            # M2Mフィールドの保存
            self.save_m2m()
            
            # チェックリスト項目のステータスを処理
            self.process_checklist_items(instance)
            
            # 分析テンプレートが選択されていれば、分析値を処理
            analysis_template = cleaned_data.get('analysis_template')
            if analysis_template:
                self.process_analysis_values(instance, analysis_template)
            
            # 前回からの変化がある場合、変化追跡レコードを作成
            if self.previous_entry and instance.thesis_change:
                self.create_thesis_change_tracker(instance)
            
        return instance
    
    def process_checklist_items(self, instance):
        """チェックリスト項目のステータスを処理"""
        # チェックリスト項目のステータスを処理する処理を追加
        pass
    
    def process_analysis_values(self, instance, template):
        """分析テンプレート値を処理"""
        # 分析テンプレート値を処理する処理を追加
        pass
    
    def create_thesis_change_tracker(self, instance):
        """投資判断の変化を追跡記録する"""
        # 変化のタイプを推測
        change_type = 'other'
        
        # 目標株価の変化を検出
        if self.previous_entry.target_price and instance.target_price:
            if instance.target_price > self.previous_entry.target_price:
                change_type = 'price_target_increase'
            elif instance.target_price < self.previous_entry.target_price:
                change_type = 'price_target_decrease'
        
        # リターン予想の変化を検出
        if self.previous_entry.expected_return and instance.expected_return:
            if self.previous_entry.expected_return > 0 and instance.expected_return < 0:
                change_type = 'bullish_to_bearish'
            elif self.previous_entry.expected_return < 0 and instance.expected_return > 0:
                change_type = 'bearish_to_bullish'
        
        # 変化の影響レベルを推定
        impact_level = 1  # デフォルトは小
        
        # 変化の要約を生成
        change_summary = instance.thesis_change[:200] if len(instance.thesis_change) > 200 else instance.thesis_change
        
        # 変化追跡レコードを作成
        ThesisChangeTracker.objects.create(
            stock=instance.stock,
            from_entry=self.previous_entry,
            to_entry=instance,
            change_type=change_type,
            change_summary=change_summary,
            change_detail=instance.thesis_change,
            impact_level=impact_level
        )

# 銘柄検索フォーム
class StockSearchForm(forms.Form):
    """銘柄検索フォーム"""
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '証券コードまたは銘柄名で検索'
        })
    )
    status = forms.ChoiceField(
        choices=[
            ('all', 'すべて'),
            ('watching', 'ウォッチ中'),
            ('holding', '保有中'),
            ('sold', '売却済み')
        ],
        required=False,
        initial='all',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    industry = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '業種で絞り込み'
        })
    )