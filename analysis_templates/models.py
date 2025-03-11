# analysis_templates/models.py
from django.db import models
from django.conf import settings

class AnalysisTemplate(models.Model):
    """銘柄データ分析のためのテンプレートを管理するモデル"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class TemplateGroup(models.Model):
    """分析テンプレート内のグループを管理するモデル"""
    template = models.ForeignKey(AnalysisTemplate, on_delete=models.CASCADE, related_name='groups')
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.template.name} - {self.name}"

class TemplateField(models.Model):
    """分析テンプレートのフィールドを管理するモデル"""
    template = models.ForeignKey(AnalysisTemplate, on_delete=models.CASCADE, related_name='fields')
    group = models.ForeignKey(TemplateGroup, on_delete=models.CASCADE, related_name='fields', null=True, blank=True)
    label = models.CharField(max_length=100)
    key = models.SlugField(max_length=100)  # データアクセス用の一意のキー
    description = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    
    # フィールドタイプ
    FIELD_TYPES = (
        ('number', '数値'),
        ('percentage', 'パーセント値'),
        ('text', 'テキスト'),
        ('date', '日付'),
        ('boolean', '真偽値（はい/いいえ）'),
        ('rating', '評価（1-5）'),
    )
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    
    # オプション設定
    unit = models.CharField(max_length=20, blank=True, help_text='数値の単位（円、倍など）')
    is_required = models.BooleanField(default=False)
    default_value = models.CharField(max_length=255, blank=True)
    
    # 数値フィールド用の設定
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    
    # 目標値・基準値（比較分析用）
    benchmark_value = models.FloatField(null=True, blank=True, help_text='業界平均値などの基準値')
    
    class Meta:
        ordering = ['order']
        unique_together = ['template', 'key']
    
    def __str__(self):
        return f"{self.template.name} - {self.label}"

class StockAnalysisData(models.Model):
    """各銘柄の分析データを保存するモデル"""
    diary = models.ForeignKey('stockdiary.StockDiary', on_delete=models.CASCADE, related_name='analysis_data')
    template = models.ForeignKey(AnalysisTemplate, on_delete=models.CASCADE, related_name='stock_data')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.diary.stock_name} - {self.template.name}"

class FieldValue(models.Model):
    """各フィールドの値を保存するモデル"""
    analysis_data = models.ForeignKey(StockAnalysisData, on_delete=models.CASCADE, related_name='field_values')
    field = models.ForeignKey(TemplateField, on_delete=models.CASCADE, related_name='values')
    
    # 様々なタイプの値を保存できるようにする
    text_value = models.TextField(blank=True, null=True)
    number_value = models.FloatField(blank=True, null=True)
    date_value = models.DateField(blank=True, null=True)
    boolean_value = models.BooleanField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.analysis_data.diary.stock_name} - {self.field.label}"
    
    def get_value(self):
        """フィールドタイプに応じた値を返す"""
        field_type = self.field.field_type
        if field_type in ['number', 'percentage', 'rating']:
            return self.number_value
        elif field_type == 'text':
            return self.text_value
        elif field_type == 'date':
            return self.date_value
        elif field_type == 'boolean':
            return self.boolean_value
        return None
    
    def get_formatted_value(self):
        """表示用にフォーマットされた値を返す"""
        value = self.get_value()
        if value is None:
            return "-"
        
        field_type = self.field.field_type
        if field_type == 'number':
            unit = self.field.unit
            return f"{value}{unit}"
        elif field_type == 'percentage':
            return f"{value}%"
        elif field_type == 'date':
            return value.strftime('%Y年%m月%d日')
        elif field_type == 'boolean':
            return "はい" if value else "いいえ"
        elif field_type == 'rating':
            return "★" * int(value)
        return str(value)