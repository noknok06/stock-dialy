# checklist/models.py
from django.db import models
from django.conf import settings

class Checklist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class ChecklistItem(models.Model):
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name='items')
    item_text = models.CharField(max_length=200)
    status = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.item_text

class DiaryChecklistItem(models.Model):
    diary = models.ForeignKey('stockdiary.StockDiary', on_delete=models.CASCADE)
    checklist_item = models.ForeignKey(ChecklistItem, on_delete=models.CASCADE)
    status = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('diary', 'checklist_item')
    
    def __str__(self):
        return f"{self.diary} - {self.checklist_item} ({self.status})"        