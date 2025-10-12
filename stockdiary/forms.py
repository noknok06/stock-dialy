from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import StockDiary, StockTransaction, StockSplit, DiaryNote
from tags.models import Tag
from checklist.models import Checklist
from analysis_template.models import AnalysisTemplate


class StockDiaryForm(forms.ModelForm):
    """日記作成フォーム（トランザクション対応版）"""
    
    image = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/jpg,image/png,image/gif,image/webp',
            'title': '画像ファイル（JPEG, PNG, GIF, WebP）のみ'
        }),
        help_text="日記に関連する画像（チャート、スクリーンショット等）"
    )
    
    analysis_template = forms.ModelChoiceField(
        queryset=AnalysisTemplate.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="分析テンプレート",
        help_text="分析データを入力する場合は、テンプレートを選択してください"
    )
    
    # 初回取引フィールド（オプション）
    add_initial_transaction = forms.BooleanField(
        required=False,
        label="初回取引を追加",
        help_text="日記作成と同時に最初の購入記録を追加します"
    )
    purchase_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="購入日"
    )
    purchase_price = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '例: 1000'
        }),
        label="購入価格（円）"
    )
    purchase_quantity = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '例: 100'
        }),
        label="購入数量（株）"
    )
    purchase_note = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '取引メモ（任意）'
        }),
        label="メモ"
    )

    class Meta:
        model = StockDiary
        fields = [
            'stock_symbol', 'stock_name', 'sector', 'reason',
            'memo', 'checklist', 'tags'
        ]
        widgets = {
            'stock_symbol': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '日本株: 7203, 米国株: AAPL など',
                'maxlength': '50',
            }),
            'stock_name': forms.TextInput(attrs={
                'class': 'form-control', 
                'required': 'required',
                'maxlength': '100',
            }),
            'reason': forms.Textarea(attrs={
                'rows': 5, 
                'class': 'form-control',
                'maxlength': '1000',
            }),
            'memo': forms.Textarea(attrs={
                'rows': 5, 
                'class': 'form-control',
                'maxlength': '1000',
            }),
            'checklist': forms.SelectMultiple(attrs={
                'class': 'form-control', 
                'size': '5'
            }),
            'tags': forms.SelectMultiple(attrs={
                'class': 'form-control', 
                'size': '5'
            }),
            'sector': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '50',
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(StockDiaryForm, self).__init__(*args, **kwargs)
        
        if user:
            self.fields['checklist'].queryset = Checklist.objects.filter(user=user)
            self.fields['tags'].queryset = Tag.objects.filter(user=user)
            self.fields['analysis_template'].queryset = AnalysisTemplate.objects.filter(user=user)
        
        # ラベル設定
        self.fields['stock_symbol'].label = "銘柄コード（任意）"
        self.fields['stock_symbol'].help_text = "例: 7203（トヨタ）、AAPL（アップル）など"
        self.fields['stock_symbol'].required = False
        self.fields['reason'].label = "購入理由 / 投資記録"
        self.fields['memo'].label = "追加メモ / コメント"
    
    def clean_stock_name(self):
        stock_name = self.cleaned_data.get('stock_name')
        if stock_name and len(stock_name) > 100:
            raise ValidationError('銘柄名は100文字以内で入力してください。')
        return stock_name

    def clean_reason(self):
        reason = self.cleaned_data.get('reason')
        if reason and len(reason) > 1000:
            raise ValidationError('購入理由は1000文字以内で入力してください。')
        return reason

    def clean_memo(self):
        memo = self.cleaned_data.get('memo')
        if memo and len(memo) > 1000:
            raise ValidationError('メモは1000文字以内で入力してください。')
        return memo

    def clean_stock_symbol(self):
        stock_symbol = self.cleaned_data.get('stock_symbol')
        if stock_symbol and len(stock_symbol) > 50:
            raise ValidationError('銘柄コードは50文字以内で入力してください。')
        return stock_symbol

    def clean_sector(self):
        sector = self.cleaned_data.get('sector')
        if sector and len(sector) > 50:
            raise ValidationError('業種は50文字以内で入力してください。')
        return sector

    def clean(self):
        cleaned_data = super().clean()
        
        # 初回取引を追加する場合のバリデーション
        if cleaned_data.get('add_initial_transaction'):
            purchase_date = cleaned_data.get('purchase_date')
            purchase_price = cleaned_data.get('purchase_price')
            purchase_quantity = cleaned_data.get('purchase_quantity')
            
            if not purchase_date:
                self.add_error('purchase_date', '購入日を入力してください')
            if not purchase_price:
                self.add_error('purchase_price', '購入価格を入力してください')
            if not purchase_quantity:
                self.add_error('purchase_quantity', '購入数量を入力してください')
        
        return cleaned_data


class StockTransactionForm(forms.ModelForm):
    """取引追加フォーム"""
    
    class Meta:
        model = StockTransaction
        fields = ['transaction_type', 'date', 'price', 'quantity', 'note']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control',
                'required': 'required'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '例: 1200',
                'required': 'required'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '例: 50',
                'required': 'required'
            }),
            'note': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '任意',
                'maxlength': '200'
            }),
        }
        labels = {
            'transaction_type': '取引種別',
            'date': '取引日',
            'price': '単価（円）',
            'quantity': '数量（株）',
            'note': 'メモ',
        }

    def __init__(self, *args, **kwargs):
        self.diary = kwargs.pop('diary', None)
        super().__init__(*args, **kwargs)
        
        # 初期値設定
        from django.utils import timezone
        self.fields['date'].initial = timezone.now().date()

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity <= 0:
            raise ValidationError('数量は1以上を入力してください')
        return quantity

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price <= 0:
            raise ValidationError('単価は0より大きい値を入力してください')
        return price

    def clean(self):
        cleaned_data = super().clean()
        transaction_type = cleaned_data.get('transaction_type')
        quantity = cleaned_data.get('quantity')
        
        # 売却の場合、保有数をチェック
        if transaction_type == 'sell' and self.diary and quantity:
            current_quantity = self.diary.current_quantity
            if quantity > current_quantity:
                raise ValidationError(
                    f'売却数量が保有数（{current_quantity}株）を超えています'
                )
        
        return cleaned_data


class StockSplitForm(forms.ModelForm):
    """株式分割フォーム"""
    
    class Meta:
        model = StockSplit
        fields = ['split_date', 'split_ratio', 'note']
        widgets = {
            'split_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'split_ratio': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': '例: 2.0 (1→2株)',
            }),
            'note': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '任意',
                'maxlength': '200'
            }),
        }
        labels = {
            'split_date': '分割実行日',
            'split_ratio': '分割比率',
            'note': 'メモ',
        }
        help_texts = {
            'split_ratio': '例: 2.0 = 1株→2株、0.5 = 2株→1株（併合）',
        }

    def clean_split_ratio(self):
        ratio = self.cleaned_data.get('split_ratio')
        if ratio <= 0:
            raise ValidationError('分割比率は0より大きい値を入力してください')
        return ratio


class DiaryNoteForm(forms.ModelForm):
    """継続記録フォーム"""
    
    class Meta:
        model = DiaryNote
        fields = ['date', 'note_type', 'importance', 'content', 'current_price']
        widgets = {
            'date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control'
            }),
            'note_type': forms.Select(attrs={'class': 'form-select'}),
            'importance': forms.Select(attrs={'class': 'form-select'}),
            'content': forms.Textarea(attrs={
                'rows': 5, 
                'class': 'form-control',
                'maxlength': '1000',
            }),
            'current_price': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01'
            }),
        }

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if content and len(content) > 1000:
            raise ValidationError('記録内容は1000文字以内で入力してください。')
        return content