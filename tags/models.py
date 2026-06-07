# tags/models.py
import math
from django.db import models
from django.conf import settings


class Tag(models.Model):
    AXIS_THEME          = 'theme'
    AXIS_BUSINESS_MODEL = 'business_model'
    AXIS_RISK           = 'risk'
    AXIS_CAPITAL_POLICY = 'capital_policy'
    AXIS_MACRO          = 'macro'
    AXIS_EVENT          = 'event'
    AXIS_CUSTOM         = 'custom'

    AXIS_CHOICES = [
        (AXIS_THEME,          'テーマ'),
        (AXIS_BUSINESS_MODEL, 'ビジネスモデル'),
        (AXIS_RISK,           'リスク'),
        (AXIS_CAPITAL_POLICY, '資本政策'),
        (AXIS_MACRO,          'マクロ感応'),
        (AXIS_EVENT,          'イベント'),
        (AXIS_CUSTOM,         'ラベル'),
    ]

    user   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name   = models.CharField(max_length=50)
    axis   = models.CharField(
        max_length=20,
        choices=AXIS_CHOICES,
        default=AXIS_THEME,
        verbose_name='軸',
    )
    parent = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
        verbose_name='親タグ',
    )
    # 出現銘柄数（document frequency）。タグ追加/削除のたびに再計算する。
    df = models.PositiveIntegerField(default=0, verbose_name='出現銘柄数')

    class Meta:
        unique_together = ['user', 'name']
        ordering = ['axis', 'name']

    def __str__(self):
        return str(self.name)

    def idf(self, total_diaries: int) -> float:
        """IDF: log(N / df)。df=0 の場合は 1 として扱う。"""
        return math.log(max(total_diaries, 1) / max(self.df, 1))
