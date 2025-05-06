# financial_reports/forms.py

from django import forms
from .models import Company, FinancialReport
import json
from decimal import Decimal

class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'code', 'abbr', 'color', 'is_public']
        widgets = {
            'color': forms.TextInput(attrs={'type': 'color'}),
        }

class FinancialReportForm(forms.ModelForm):
    # JSONデータをテキストエリアとして表示
    data_json = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 20, 
            'class': 'form-control', 
            'style': 'font-family: monospace; font-size: 0.9rem;'
        }),
        required=False,
        label='レポートデータ (JSON)',
        help_text='JSON形式でレポートデータを入力できます。空の場合は基本情報から自動生成します。'
    )
    
    # JSONファイルのアップロード
    json_file = forms.FileField(
        required=False,
        label='JSONファイル',
        help_text='JSONファイルをアップロードすることもできます。'
    )
    
    class Meta:
        model = FinancialReport
        fields = ['company', 'fiscal_period', 'achievement_badge', 'overall_rating', 'is_public', 'data']
        widgets = {
            'data': forms.HiddenInput(),
            'overall_rating': forms.NumberInput(attrs={'min': '1', 'max': '10', 'step': '0.1'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 既存のデータをJSONフィールドに設定
        if self.instance.pk and self.instance.data:
            self.fields['data_json'].initial = json.dumps(
                self.instance.data, 
                indent=2, 
                ensure_ascii=False
            )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # JSONファイルが提供された場合、そのデータを優先
        json_file = cleaned_data.get('json_file')
        if json_file:
            try:
                content = json_file.read().decode('utf-8')
                # JavaScriptオブジェクトの場合の対応
                if content.strip().endswith(';'):
                    content = content.strip()[:-1]
                data = json.loads(content)
                cleaned_data['data'] = data
            except Exception as e:
                self.add_error('json_file', f'JSONファイルの解析に失敗しました: {str(e)}')
        else:
            # テキストエリアからのJSONを取得
            data_json = cleaned_data.get('data_json')
            if data_json:
                try:
                    data = json.loads(data_json)
                    cleaned_data['data'] = data
                except json.JSONDecodeError as e:
                    self.add_error('data_json', f'JSONの形式が正しくありません: {str(e)}')
            else:
                # JSONが提供されなかった場合、基本情報から自動生成
                company = cleaned_data.get('company')
                fiscal_period = cleaned_data.get('fiscal_period')
                achievement_badge = cleaned_data.get('achievement_badge', '')
                overall_rating = cleaned_data.get('overall_rating', Decimal('0'))
                
                if company and fiscal_period:
                    data = {
                        'companyName': company.name,
                        'companyCode': company.code,
                        'companyAbbr': company.abbr,
                        'companyColor': company.color,
                        'fiscalPeriod': fiscal_period,
                        'achievementBadge': achievement_badge,
                        'overallRating': str(overall_rating),
                        'overallSummary': '',
                        'recommendationText': '',
                        'positivePoints': [],
                        'negativePoints': []
                    }
                    cleaned_data['data'] = data
        
        return cleaned_data