# analysis_template/models.py
from django.db import models
from django.conf import settings
from stockdiary.models import StockDiary

class AnalysisTemplate(models.Model):
    """分析テンプレート"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class AnalysisItem(models.Model):
    """分析項目"""
    ITEM_TYPE_CHOICES = [
        ('number', '数値'),
        ('text', 'テキスト'),
        ('select', '選択肢'),
    ]
    
    template = models.ForeignKey(AnalysisTemplate, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default='number')
    order = models.PositiveIntegerField(default=0)
    # 選択肢項目の場合のみ使用。カンマ区切りで選択肢を保存
    choices = models.TextField(blank=True, 
                              help_text='選択肢項目の場合、カンマ区切りで選択肢を入力してください。')
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.template.name} - {self.name}"
    
    def get_choices_list(self):
        """選択肢リストを取得"""
        if not self.choices:
            return []
        return [choice.strip() for choice in self.choices.split(',')]

class DiaryAnalysisValue(models.Model):
    """日記の分析項目の値"""
    diary = models.ForeignKey(StockDiary, on_delete=models.CASCADE, related_name='analysis_values')
    analysis_item = models.ForeignKey(AnalysisItem, on_delete=models.CASCADE)
    number_value = models.DecimalField(max_digits=15, decimal_places=5, null=True, blank=True)
    text_value = models.TextField(blank=True)
    
    class Meta:
        unique_together = ('diary', 'analysis_item')
    
    def __str__(self):
        return f"{self.diary} - {self.analysis_item}"
    
    def get_display_value(self):
        """表示用の値を取得"""
        if self.analysis_item.item_type == 'number':
            return self.number_value
        else:
            return self.text_value