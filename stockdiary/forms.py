# stockdiary/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import StockDiary, Transaction, StockSplit, DiaryNote
from tags.models import Tag
from decimal import Decimal


class StockDiaryForm(forms.ModelForm):
    """日記作成・編集フォーム（基本情報のみ）"""
    
    # 画像アップロード用フィールド
    image = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/jpg,image/png,image/gif,image/webp',
            'title': '画像ファイル（JPEG, PNG, GIF, WebP）のみ'
        }),
        help_text="日記に関連する画像（チャート、スクリーンショット等）"
    )
        
    # 初回購入情報（オプション）
    add_initial_purchase = forms.BooleanField(
        required=False,
        initial=False,
        label="初回購入情報を入力する",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    initial_purchase_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label="購入日"
    )
    
    initial_purchase_price = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01',
            'placeholder': '例: 1000.00'
        }),
        label="購入単価（円）"
    )
    
    initial_purchase_quantity = forms.DecimalField(
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '1',
            'min': '1',
            'placeholder': '例: 100'
        }),
        label="購入数量（株）"
    )

    class Meta:
        model = StockDiary
        fields = [
            'stock_symbol', 'stock_name', 'reason',
            'memo', 'tags', 'sector'
        ]
        widgets = {
            'stock_symbol': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '日本株: 7203 など',
                'maxlength': '50',
            }),
            'stock_name': forms.TextInput(attrs={
                'class': 'form-control', 
                'required': 'required',
                'maxlength': '100',
            }),
            'reason': forms.Textarea(attrs={
                'rows': 10,
                'class': 'form-control',
                'maxlength': '5000',
                'id': 'id_reason',
                'placeholder': '投資理由や分析内容を記録（Markdown対応）\n\n📝 見出し: # 見出し\n🏷️ タグ: @成長株 @配当 @長期保有\n\n例:\n## 投資判断\n成長性が高く、配当も安定している。\nタグ: @成長株 @配当'
            }),
            'memo': forms.Textarea(attrs={
                'rows': 5, 
                'class': 'form-control',
                'maxlength': '1000',
                'placeholder': 'その他のメモ'
            }),
            'tags': forms.SelectMultiple(attrs={'class': 'form-control', 'size': '5'}),
            'sector': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '50',
                'placeholder': '例: 電気機器'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(StockDiaryForm, self).__init__(*args, **kwargs)
        
        if user:
            self.fields['tags'].queryset = Tag.objects.filter(user=user)
        
        # ラベル設定
        self.fields['stock_symbol'].label = "銘柄コード（任意）"
        self.fields['stock_symbol'].help_text = "米国株も検索可能ですが、為替対応はありません。"
        self.fields['stock_symbol'].required = False
        self.fields['reason'].label = "投資理由 / 分析内容"
        self.fields['reason'].help_text = "Markdown対応。タグは @タグ名 の形式で記述すると検索可能になります（例: @成長株 @配当）"
        self.fields['memo'].label = "追加メモ"
        
        # 初期値設定（新規作成時）
        if not self.instance.pk:
            from django.utils import timezone
            self.fields['initial_purchase_date'].initial = timezone.now().date()

    def clean_stock_name(self):
        """銘柄名のバリデーション"""
        stock_name = self.cleaned_data.get('stock_name')
        if stock_name and len(stock_name) > 100:
            raise ValidationError('銘柄名は100文字以内で入力してください。')
        return stock_name

    def clean_reason(self):
        """投資理由のバリデーション"""
        reason = self.cleaned_data.get('reason')
        if reason and len(reason) > 5000:
            raise ValidationError('投資理由は5000文字以内で入力してください。')
        return reason

    def clean_memo(self):
        """メモのバリデーション"""
        memo = self.cleaned_data.get('memo')
        if memo and len(memo) > 1000:
            raise ValidationError('メモは1000文字以内で入力してください。')
        return memo

    def clean_stock_symbol(self):
        """銘柄コードのバリデーション"""
        stock_symbol = self.cleaned_data.get('stock_symbol')
        if stock_symbol and len(stock_symbol) > 50:
            raise ValidationError('銘柄コードは50文字以内で入力してください。')
        return stock_symbol

    def clean_sector(self):
        """業種のバリデーション"""
        sector = self.cleaned_data.get('sector')
        if sector and len(sector) > 50:
            raise ValidationError('業種は50文字以内で入力してください。')
        return sector

    def clean(self):
        """初回購入情報の整合性チェック"""
        cleaned_data = super().clean()
        add_initial_purchase = cleaned_data.get('add_initial_purchase')
        
        if add_initial_purchase:
            # 初回購入を追加する場合、必須項目をチェック
            initial_date = cleaned_data.get('initial_purchase_date')
            initial_price = cleaned_data.get('initial_purchase_price')
            initial_quantity = cleaned_data.get('initial_purchase_quantity')
            
            if not initial_date:
                self.add_error('initial_purchase_date', '購入日を入力してください')
            
            if not initial_price:
                self.add_error('initial_purchase_price', '購入単価を入力してください')
            elif initial_price <= 0:
                self.add_error('initial_purchase_price', '購入単価は正の数を入力してください')
            
            if not initial_quantity:
                self.add_error('initial_purchase_quantity', '購入数量を入力してください')
            elif initial_quantity <= 0:
                self.add_error('initial_purchase_quantity', '購入数量は正の数を入力してください')
        
        return cleaned_data


class TransactionForm(forms.ModelForm):
    """取引追加・編集フォーム"""
    
    class Meta:
        model = Transaction
        fields = ['transaction_type', 'transaction_date', 'price', 'quantity', 'memo']
        widgets = {
            'transaction_type': forms.Select(attrs={
                'class': 'form-select',
                'required': 'required'
            }),
            'transaction_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'required': 'required'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'max': '9999999.99',  # 最大999万円
                'placeholder': '例: 1000.00',
                'required': 'required'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1',
                'min': '1',
                'max': '99999999',  # 最大9999万株
                'placeholder': '例: 100',
                'required': 'required'
            }),
            'memo': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': '取引に関するメモ（任意）',
                'maxlength': '500'
            }),
        }
        labels = {
            'transaction_type': '取引種別',
            'transaction_date': '取引日',
            'price': '単価（円）',
            'quantity': '数量（株）',
            'memo': 'メモ'
        }
        help_texts = {
            'price': '1株あたりの単価を入力',
            'quantity': '取引する株数を入力',
            'memo': '取引に関する補足情報（500文字以内）'
        }

    def __init__(self, *args, **kwargs):
        self.diary = kwargs.pop('diary', None)
        super(TransactionForm, self).__init__(*args, **kwargs)
        
        # 初期値設定（新規作成時）
        if not self.instance.pk:
            from django.utils import timezone
            self.fields['transaction_date'].initial = timezone.now().date()
            self.fields['transaction_type'].initial = 'buy'

    def clean_price(self):
        """単価のバリデーション"""
        price = self.cleaned_data.get('price')
        if price is not None:
            if price <= 0:
                raise ValidationError('単価は正の数を入力してください')
            if price > Decimal('9999999.99'):
                raise ValidationError('単価は999万9999円以下で入力してください')
        return price

    def clean_quantity(self):
        """数量のバリデーション"""
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None:
            if quantity <= 0:
                raise ValidationError('数量は正の数を入力してください')
            if quantity > Decimal('99999999'):
                raise ValidationError('数量は9999万株以下で入力してください')
        return quantity

    def clean_memo(self):
        """メモのバリデーション"""
        memo = self.cleaned_data.get('memo')
        if memo and len(memo) > 500:
            raise ValidationError('メモは500文字以内で入力してください')
        return memo

    def clean(self):
        """売却時の保有数チェック"""
        cleaned_data = super().clean()
        transaction_type = cleaned_data.get('transaction_type')
        quantity = cleaned_data.get('quantity')
        
        if transaction_type == 'sell' and quantity and self.diary:
            # 現在の保有数を取得
            current_holdings = self.diary.current_quantity
            
            # 編集時は元の取引を除外して計算
            if self.instance.pk:
                old_transaction = Transaction.objects.get(pk=self.instance.pk)
                if old_transaction.transaction_type == 'sell':
                    current_holdings += old_transaction.quantity
            
            if quantity > current_holdings:
                raise ValidationError({
                    'quantity': f'保有数（{current_holdings}株）を超える売却はできません'
                })
        
        return cleaned_data


class StockSplitForm(forms.ModelForm):
    """株式分割フォーム"""
    
    class Meta:
        model = StockSplit
        fields = ['split_date', 'split_ratio', 'memo']
        widgets = {
            'split_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'required': 'required'
            }),
            'split_ratio': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'min': '0.0001',
                'placeholder': '例: 2.0（1→2株の分割）',
                'required': 'required'
            }),
            'memo': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': '分割に関するメモ（任意）',
                'maxlength': '500'
            }),
        }
        labels = {
            'split_date': '分割実行日',
            'split_ratio': '分割比率',
            'memo': 'メモ'
        }
        help_texts = {
            'split_date': '株式分割が実行される日付',
            'split_ratio': '1株が何株になるか（例: 1→2株なら「2.0」）',
            'memo': '分割に関する補足情報（500文字以内）'
        }

    def __init__(self, *args, **kwargs):
        super(StockSplitForm, self).__init__(*args, **kwargs)
        
        # 初期値設定
        if not self.instance.pk:
            from django.utils import timezone
            self.fields['split_date'].initial = timezone.now().date()

    def clean_split_ratio(self):
        """分割比率のバリデーション"""
        split_ratio = self.cleaned_data.get('split_ratio')
        if split_ratio is not None and split_ratio <= 0:
            raise ValidationError('分割比率は正の数を入力してください')
        return split_ratio

    def clean_memo(self):
        """メモのバリデーション"""
        memo = self.cleaned_data.get('memo')
        if memo and len(memo) > 500:
            raise ValidationError('メモは500文字以内で入力してください')
        return memo


class DiaryNoteForm(forms.ModelForm):
    """継続記録フォーム"""
    
    class Meta:
        model = DiaryNote
        fields = ['date', 'note_type', 'importance', 'content', 'current_price']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'note_type': forms.Select(attrs={'class': 'form-select'}),
            'importance': forms.Select(attrs={'class': 'form-select'}),
            'content': forms.Textarea(attrs={
                'rows': 5, 
                'class': 'form-control',
                'maxlength': '1000',
            }),
            'current_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def clean_content(self):
        """記録内容のバリデーション"""
        content = self.cleaned_data.get('content')
        if content and len(content) > 1000:
            raise ValidationError('記録内容は1000文字以内で入力してください。')
        return content

class TradeUploadForm(forms.Form):
    """取引履歴アップロードフォーム"""
    BROKER_CHOICES = [
        ('rakuten', '楽天証券'),
        ('sbi', 'SBI証券'),  # 将来的に対応
    ]
    
    broker = forms.ChoiceField(
        label='証券会社',
        choices=BROKER_CHOICES,
        initial='rakuten',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    csv_file = forms.FileField(
        label='取引履歴CSVファイル',
        help_text='楽天証券からダウンロードした取引履歴CSVファイルを選択してください',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        })
    )
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data.get('csv_file')
        
        if csv_file:
            # ファイルサイズチェック（10MB以下）
            if csv_file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('ファイルサイズは10MB以下にしてください')
            
            # ファイル拡張子チェック
            if not csv_file.name.endswith('.csv'):
                raise forms.ValidationError('CSVファイルを選択してください')
        
        return csv_file        