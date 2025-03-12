# company_master/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

def validate_date_format(value):
    """日付形式のバリデーション（YYYY-MM-DD形式または空白を許容）"""
    if value and value.strip():
        try:
            # 日付形式のチェック
            from datetime import datetime
            datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            raise ValidationError(
                _('%(value)sは無効な日付形式です。YYYY-MM-DD形式で入力してください。'),
                params={'value': value},
            )

class CompanyMaster(models.Model):
    """企業マスタ情報を保存するモデル"""
    date = models.CharField(
        max_length=10, 
        blank=True, 
        null=True, 
        verbose_name="日付", 
        validators=[validate_date_format]
    )
    code = models.CharField(max_length=10, unique=True, verbose_name="証券コード")
    name = models.CharField(max_length=100, verbose_name="銘柄名")
    market = models.CharField(max_length=50, blank=True, verbose_name="市場・商品区分")
    industry_code_33 = models.CharField(max_length=10, blank=True, verbose_name="33業種コード")
    industry_name_33 = models.CharField(max_length=100, blank=True, verbose_name="33業種区分")
    industry_code_17 = models.CharField(max_length=10, blank=True, verbose_name="17業種コード")
    industry_name_17 = models.CharField(max_length=100, blank=True, verbose_name="17業種区分")
    scale_code = models.CharField(max_length=10, blank=True, verbose_name="規模コード")
    scale_name = models.CharField(max_length=50, blank=True, verbose_name="規模区分")
    
    unit = models.IntegerField(default=100, verbose_name="売買単位")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "企業マスタ"
        verbose_name_plural = "企業マスタ"
        ordering = ['code']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['name']),
            models.Index(fields=['industry_code_33'])
        ]

    def __str__(self):
        return f"{self.code}: {self.name}"