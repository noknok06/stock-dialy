# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    diary_note_tag_limit = models.IntegerField(
        default=3,
        help_text='グラフの@タグ計算に使う継続記録の件数（直近N件）',
    )

    def __str__(self):
        return self.username