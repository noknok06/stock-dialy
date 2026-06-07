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


class MasterTag(models.Model):
    """管理者がキュレーションする標準分析タグ（全ユーザー共有の補完候補）。

    旧来はコード内の HASHTAG_AXIS_MAP（ハードコード辞書）で管理していたが、
    デプロイなしで追加・編集・無効化できるよう DB 管理へ移行した。

    - ユーザー独自タグ（Tag, 既定 custom 軸）とは別物。
    - `/api/hashtags/` の補完候補と、@タグ保存時の軸（axis）決定に使われる。
    - is_active=False にすると補完候補・軸決定から除外される（削除せず無効化できる）。
    - 軸（axis）を 'custom' 以外にすることで分析スコアリングの対象になる。
    """
    name = models.CharField(max_length=50, unique=True, verbose_name='タグ名')
    axis = models.CharField(
        max_length=20,
        choices=Tag.AXIS_CHOICES,
        default=Tag.AXIS_THEME,
        verbose_name='軸',
    )
    is_active = models.BooleanField(default=True, verbose_name='有効')
    sort_order = models.IntegerField(default=0, verbose_name='表示順')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # tag_axis_config.get_master_axis_map() のキャッシュキーと同一にすること
    CACHE_KEY = 'master_tag_axis_map'

    class Meta:
        ordering = ['sort_order', 'axis', 'name']
        verbose_name = '標準タグ'
        verbose_name_plural = '標準タグ'

    def __str__(self):
        return str(self.name)

    def _clear_axis_cache(self):
        from django.core.cache import cache
        cache.delete(self.CACHE_KEY)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._clear_axis_cache()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        self._clear_axis_cache()
        return result
