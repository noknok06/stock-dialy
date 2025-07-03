from django.db import models

class Company(models.Model):
    """企業マスタ"""
    edinet_code = models.CharField('EDINETコード', max_length=6, unique=True, db_index=True)
    securities_code = models.CharField('証券コード', max_length=5, blank=True, null=True, db_index=True)
    company_name = models.CharField('企業名', max_length=255, db_index=True)
    company_name_kana = models.CharField('企業名カナ', max_length=255, blank=True)
    jcn = models.CharField('法人番号', max_length=13, blank=True, null=True)
    is_active = models.BooleanField('有効フラグ', default=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'earnings_analysis_company'
        verbose_name = '企業'
        verbose_name_plural = '企業一覧'
        ordering = ['company_name']

    def __str__(self):
        return f"{self.securities_code or 'N/A'} {self.company_name}"