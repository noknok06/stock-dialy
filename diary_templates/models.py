from django.conf import settings
from django.db import models


class DiaryTemplate(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='diary_templates',
    )
    title = models.CharField(max_length=100)
    body = models.TextField(max_length=10000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'title']
        ordering = ['title']
        verbose_name = '日記テンプレート'
        verbose_name_plural = '日記テンプレート'

    def __str__(self):
        return self.title
