# earnings_analysis/forms.py

from django import forms
from .models import TDNETDisclosure


class PDFUploadForm(forms.Form):
    """PDF URL入力フォーム"""
    
    DISCLOSURE_TYPE_CHOICES = [
        ('earnings', '決算短信'),
        ('forecast', '業績予想修正'),
        ('dividend', '配当予想修正'),
        ('buyback', '自己株式取得'),
        ('merger', '合併・買収'),
        ('offering', '募集・発行'),
        ('governance', 'ガバナンス'),
        ('other', 'その他'),
    ]
    
    pdf_url = forms.URLField(
        label='PDF URL',
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://example.com/disclosure.pdf',
            'size': 80
        }),
        help_text='適時開示PDFのURLを入力してください'
    )
    
    company_code = forms.CharField(
        label='証券コード',
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '7203'
        }),
        help_text='4桁の証券コード'
    )
    
    company_name = forms.CharField(
        label='企業名',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'トヨタ自動車株式会社'
        })
    )
    
    disclosure_type = forms.ChoiceField(
        label='開示種別',
        choices=DISCLOSURE_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    title = forms.CharField(
        label='タイトル',
        max_length=500,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '2024年3月期 第3四半期決算短信'
        })
    )
    
    max_pdf_pages = forms.IntegerField(
        label='PDF読み取りページ数',
        initial=50,
        min_value=1,
        max_value=200,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text='PDFから読み取る最大ページ数（多いほど時間がかかります）'
    )
    
    auto_generate_report = forms.BooleanField(
        label='自動的にレポート生成',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='チェックすると、PDF取り込み後すぐにAIレポートを生成します'
    )


class TDNETDisclosureAdminForm(forms.ModelForm):
    """開示情報の管理画面フォーム"""
    
    class Meta:
        model = TDNETDisclosure
        fields = '__all__'
        widgets = {
            'summary': forms.Textarea(attrs={'rows': 4}),
            'raw_data': forms.Textarea(attrs={'rows': 10}),
        }