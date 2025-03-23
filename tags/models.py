# tags/models.py
from django.db import models
from django.conf import settings

class Tag(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)  # タグ名

    class Meta:
        # ユーザーとタグ名の組み合わせで一意制約
        unique_together = ['user', 'name']
        ordering = ['name']  # 名前順に並べる

    def __str__(self):
        return str(self.name)