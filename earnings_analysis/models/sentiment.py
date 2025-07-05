# earnings_analysis/models/sentiment.py
from django.db import models
from django.utils import timezone
from django.db.models import JSONField  # ✅ こちらに変更

import uuid

class SentimentAnalysisSession(models.Model):
    """感情分析セッション（一時保存）"""
    
    STATUS_CHOICES = [
        ('PENDING', '待機中'),
        ('PROCESSING', '処理中'),
        ('COMPLETED', '完了'),
        ('FAILED', '失敗'),
    ]
    
    SENTIMENT_CHOICES = [
        ('positive', 'ポジティブ'),
        ('negative', 'ネガティブ'),
        ('neutral', '中立'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    session_id = models.CharField('セッションID', max_length=64, unique=True, default=uuid.uuid4)
    document = models.ForeignKey('DocumentMetadata', on_delete=models.CASCADE, verbose_name='対象書類')
    
    # 分析結果
    overall_score = models.FloatField('全体感情スコア', null=True, blank=True, help_text='-1.0〜+1.0')
    sentiment_label = models.CharField('感情ラベル', max_length=20, choices=SENTIMENT_CHOICES, null=True, blank=True)
    
    # ステータス
    processing_status = models.CharField('処理ステータス', max_length=20, choices=STATUS_CHOICES, default='PENDING')
    error_message = models.TextField('エラーメッセージ', blank=True)
    
    # 分析結果詳細（JSON）
    analysis_result = JSONField('分析結果詳細', null=True, blank=True)
    
    # タイムスタンプ
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    expires_at = models.DateTimeField('有効期限')
    
    class Meta:
        db_table = 'earnings_analysis_sentiment_session'
        verbose_name = '感情分析セッション'
        verbose_name_plural = '感情分析セッション一覧'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['processing_status']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"感情分析 {self.session_id[:8]}... - {self.document.company_name}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def progress_percentage(self):
        """進行率計算"""
        if self.processing_status == 'PENDING':
            return 0
        elif self.processing_status == 'PROCESSING':
            return 50  # 実際の進行率はanalysis_resultから取得
        elif self.processing_status in ['COMPLETED', 'FAILED']:
            return 100
        return 0


class SentimentAnalysisHistory(models.Model):
    """感情分析履歴（統計用）"""
    
    SENTIMENT_CHOICES = [
        ('positive', 'ポジティブ'),
        ('negative', 'ネガティブ'),
        ('neutral', '中立'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    document = models.ForeignKey('DocumentMetadata', on_delete=models.CASCADE, verbose_name='対象書類')
    
    # 分析結果
    overall_score = models.FloatField('全体感情スコア', help_text='-1.0〜+1.0')
    sentiment_label = models.CharField('感情ラベル', max_length=20, choices=SENTIMENT_CHOICES)
    
    # メタデータ
    analysis_date = models.DateTimeField('分析実行日時', auto_now_add=True)
    user_ip = models.GenericIPAddressField('実行ユーザーIP', null=True, blank=True)
    analysis_duration = models.FloatField('分析処理時間（秒）', null=True, blank=True)
    
    class Meta:
        db_table = 'earnings_analysis_sentiment_history'
        verbose_name = '感情分析履歴'
        verbose_name_plural = '感情分析履歴一覧'
        ordering = ['-analysis_date']
        indexes = [
            models.Index(fields=['document', 'analysis_date']),
            models.Index(fields=['sentiment_label']),
            models.Index(fields=['analysis_date']),
        ]
    
    def __str__(self):
        return f"{self.document.company_name} - {self.get_sentiment_label_display()} ({self.overall_score:.2f})"