# financial_reports/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()

class Company(models.Model):
    """企業情報モデル"""
    name = models.CharField(_('企業名'), max_length=100)
    code = models.CharField(_('証券コード'), max_length=10)
    abbr = models.CharField(_('略称'), max_length=10)
    color = models.CharField(_('ブランドカラー'), max_length=20, default='#3B82F6')
    is_public = models.BooleanField(_('公開'), default=False)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        verbose_name = _('企業')
        verbose_name_plural = _('企業')
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('financial_reports:company_detail', kwargs={'pk': self.pk})

class FinancialReport(models.Model):
    """決算レポートモデル"""
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name=_('企業')
    )
    fiscal_period = models.CharField(_('決算期'), max_length=50)
    achievement_badge = models.CharField(_('業績バッジ'), max_length=50, blank=True)
    overall_rating = models.DecimalField(_('総合評価'), max_digits=3, decimal_places=1)
    is_public = models.BooleanField(_('公開'), default=False)
    data = models.JSONField(_('レポートデータ'))
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_reports',
        verbose_name=_('作成者')
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='updated_reports',
        verbose_name=_('更新者')
    )
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        verbose_name = _('決算レポート')
        verbose_name_plural = _('決算レポート')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company.name} - {self.fiscal_period}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('financial_reports:report_detail', kwargs={'pk': self.pk})

    @property
    def view_count(self):
        return self.views.count()

class ReportView(models.Model):
    """レポート閲覧履歴"""
    report = models.ForeignKey(
        FinancialReport, 
        on_delete=models.CASCADE,
        related_name='views',
        verbose_name=_('レポート')
    )
    ip_address = models.GenericIPAddressField(_('IPアドレス'), null=True, blank=True)  # ここをnull=Trueに変更
    user_agent = models.TextField(_('ユーザーエージェント'), blank=True)
    timestamp = models.DateTimeField(_('閲覧日時'), auto_now_add=True)