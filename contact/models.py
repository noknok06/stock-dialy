from django.db import models
from django.utils import timezone

class ContactMessage(models.Model):
    """お問い合わせメッセージを保存するモデル"""
    name = models.CharField('お名前', max_length=100)
    email = models.EmailField('メールアドレス')
    subject = models.CharField('件名', max_length=200)
    message = models.TextField('メッセージ')
    created_at = models.DateTimeField('送信日時', default=timezone.now)
    is_read = models.BooleanField('既読', default=False)
    
    class Meta:
        verbose_name = 'お問い合わせ'
        verbose_name_plural = 'お問い合わせ'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name}: {self.subject}"
