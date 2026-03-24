from django.db import models
from decimal import Decimal


class MarginData(models.Model):
    """
    信用取引残高データ（JPX週次データ）

    JPX「信用取引残高等」PDFから取得した週次の信用取引残高。
    合計欄の売り残高・買い残高を保存し、信用倍率を管理する。
    """
    record_date = models.DateField(verbose_name='申込日', db_index=True)
    stock_code = models.CharField(max_length=4, verbose_name='銘柄コード', db_index=True)
    stock_name = models.CharField(max_length=100, blank=True, verbose_name='銘柄名')

    # 合計欄の残高（単位：千株）
    short_balance = models.BigIntegerField(verbose_name='売り残高（合計）')
    long_balance = models.BigIntegerField(verbose_name='買い残高（合計）')

    # 信用倍率 = 買い残高 / 売り残高（売り残高が0の場合はNULL）
    margin_ratio = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='信用倍率'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('record_date', 'stock_code')]
        indexes = [
            models.Index(fields=['stock_code', '-record_date']),
            models.Index(fields=['-record_date']),
        ]
        verbose_name = '信用取引残高'
        verbose_name_plural = '信用取引残高'
        ordering = ['-record_date', 'stock_code']

    def __str__(self):
        return f"{self.stock_code} ({self.record_date}) 倍率:{self.margin_ratio}"

    def save(self, *args, **kwargs):
        # 信用倍率を自動計算
        if self.short_balance and self.short_balance > 0:
            self.margin_ratio = Decimal(str(self.long_balance)) / Decimal(str(self.short_balance))
            # 小数点2桁に丸める
            self.margin_ratio = self.margin_ratio.quantize(Decimal('0.01'))
        else:
            self.margin_ratio = None
        super().save(*args, **kwargs)


class MarginFetchLog(models.Model):
    """信用倍率データ取得ログ"""
    STATUS_CHOICES = [
        ('running', '実行中'),
        ('success', '成功'),
        ('failed', '失敗'),
        ('partial', '一部成功'),
    ]

    record_date = models.DateField(verbose_name='対象申込日', unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='running', verbose_name='ステータス')
    records_created = models.IntegerField(default=0, verbose_name='新規作成件数')
    records_updated = models.IntegerField(default=0, verbose_name='更新件数')
    total_records = models.IntegerField(default=0, verbose_name='処理件数合計')
    pdf_url = models.URLField(blank=True, verbose_name='取得元PDF URL')
    error_message = models.TextField(blank=True, verbose_name='エラーメッセージ')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = '取得ログ'
        verbose_name_plural = '取得ログ'
        ordering = ['-record_date']

    def __str__(self):
        return f"{self.record_date} [{self.status}] {self.total_records}件"
