"""
earnings_reports/forms.py
決算分析アプリのフォーム定義
"""

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Company, Document, Analysis, AnalysisHistory
import re

User = get_user_model()


class StockCodeSearchForm(forms.Form):
    """銘柄コード検索フォーム"""
    
    stock_code = forms.CharField(
        label='証券コード',
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '例: 7203, 6758',
            'autocomplete': 'off',
            'id': 'stock-code-input'
        })
    )
    
    def clean_stock_code(self):
        """証券コードのバリデーション"""
        stock_code = self.cleaned_data['stock_code'].strip()
        
        # 4桁の数字のみ許可
        if not re.match(r'^\d{4}$', stock_code):
            raise ValidationError('証券コードは4桁の数字で入力してください。')
        
        return stock_code


class DocumentSelectionForm(forms.Form):
    """書類選択フォーム"""
    
    selected_documents = forms.ModelMultipleChoiceField(
        queryset=Document.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        label='分析対象書類',
        required=True,
        help_text='分析したい書類を選択してください（複数選択可）'
    )
    
    def __init__(self, company=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if company:
            # 該当企業の未分析書類を優先表示
            self.fields['selected_documents'].queryset = Document.objects.filter(
                company=company,
                doc_type__in=['120', '130', '140', '350']  # 決算関連書類のみ
            ).order_by('-submit_date')


class AnalysisSettingsForm(forms.Form):
    """分析設定フォーム"""
    
    ANALYSIS_DEPTH = [
        ('basic', '基本分析（感情・CF分析）'),
        ('detailed', '詳細分析（+リスク・トレンド分析）'),
        ('comprehensive', '包括分析（+過去比較・予測）'),
    ]
    
    analysis_depth = forms.ChoiceField(
        choices=ANALYSIS_DEPTH,
        initial='detailed',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='分析レベル'
    )
    
    include_sentiment = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='感情分析を含む'
    )
    
    include_cashflow = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='キャッシュフロー分析を含む'
    )
    
    compare_previous = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='前回結果との比較',
        help_text='過去の分析結果がある場合、比較を行います'
    )
    
    notify_on_completion = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='分析完了時に通知',
        help_text='分析が完了したらメール通知を送信します'
    )
    
    custom_keywords = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': '追加で検索したいキーワードをカンマ区切りで入力\n例: 新製品, DX, 海外展開'
        }),
        label='カスタムキーワード',
        help_text='分析で特に注目したいキーワードがあれば入力してください'
    )
    
    def clean_custom_keywords(self):
        """カスタムキーワードをリストに変換"""
        keywords = self.cleaned_data.get('custom_keywords', '')
        if keywords:
            # カンマ区切りでリストに変換し、空文字を除去
            return [k.strip() for k in keywords.split(',') if k.strip()]
        return []


class CompanyRegistrationForm(forms.ModelForm):
    """企業登録フォーム（EDINET未登録企業用）"""
    
    class Meta:
        model = Company
        fields = ['stock_code', 'name', 'name_kana', 'market', 'sector']
        widgets = {
            'stock_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '4桁の証券コード'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '企業名'
            }),
            'name_kana': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'カナ企業名（任意）'
            }),
            'market': forms.Select(attrs={'class': 'form-select'}, choices=[
                ('', '選択してください'),
                ('東証プライム', '東証プライム'),
                ('東証スタンダード', '東証スタンダード'),
                ('東証グロース', '東証グロース'),
                ('その他', 'その他'),
            ]),
            'sector': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '業種（任意）'
            }),
        }
    
    def clean_stock_code(self):
        """証券コードの重複チェック"""
        stock_code = self.cleaned_data['stock_code']
        
        if Company.objects.filter(stock_code=stock_code).exists():
            raise ValidationError('この証券コードは既に登録されています。')
        
        return stock_code


class AnalysisFilterForm(forms.Form):
    """分析結果フィルタフォーム"""
    
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(),
        required=False,
        empty_label='全ての企業',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='企業'
    )
    
    doc_type = forms.ChoiceField(
        choices=[('', '全ての書類')] + Document.DOC_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='書類種別'
    )
    
    status = forms.ChoiceField(
        choices=[('', '全ての状況')] + Analysis.ANALYSIS_STATUS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='分析状況'
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='開始日'
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='終了日'
    )
    
    score_min = forms.FloatField(
        required=False,
        min_value=-100,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1',
            'placeholder': '-100 ～ 100'
        }),
        label='最小スコア'
    )
    
    score_max = forms.FloatField(
        required=False,
        min_value=-100,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1',
            'placeholder': '-100 ～ 100'
        }),
        label='最大スコア'
    )


class NotificationSettingsForm(forms.ModelForm):
    """通知設定フォーム"""
    
    class Meta:
        model = AnalysisHistory
        fields = ['notify_on_earnings', 'notify_threshold']
        widgets = {
            'notify_on_earnings': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'max': '100',
                'placeholder': '50.0'
            }),
        }
        help_texts = {
            'notify_on_earnings': '企業の決算発表時期に通知を受け取ります',
            'notify_threshold': 'スコア変化がこの値を超えた場合に通知します',
        }


class BulkAnalysisForm(forms.Form):
    """一括分析フォーム"""
    
    companies = forms.ModelMultipleChoiceField(
        queryset=Company.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label='対象企業',
        help_text='複数企業を一括で分析します'
    )
    
    doc_types = forms.MultipleChoiceField(
        choices=Document.DOC_TYPES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label='書類種別',
        initial=['120', '130', '350']  # デフォルトで主要書類を選択
    )
    
    days_back = forms.IntegerField(
        initial=90,
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '90'
        }),
        label='検索期間（日）',
        help_text='何日前までの書類を対象にするか'
    )
    
    max_documents_per_company = forms.IntegerField(
        initial=5,
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '5'
        }),
        label='企業あたり最大書類数',
        help_text='各企業につき最大何件の書類を分析するか'
    )
    
    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if user:
            # ユーザーが過去に分析した企業を優先表示
            analyzed_companies = Company.objects.filter(
                analysis_history__user=user
            ).distinct()
            
            if analyzed_companies.exists():
                self.fields['companies'].queryset = analyzed_companies