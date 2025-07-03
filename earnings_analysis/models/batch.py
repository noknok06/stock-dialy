from django.db import models

class BatchExecution(models.Model):
    """バッチ実行履歴"""
    
    STATUS_CHOICES = [
        ('RUNNING', '実行中'),
        ('SUCCESS', '成功'),
        ('FAILED', '失敗'),
    ]
    
    batch_date = models.DateField('対象日付', unique=True, db_index=True)
    status = models.CharField('ステータス', max_length=20, choices=STATUS_CHOICES)
    processed_count = models.PositiveIntegerField('処理件数', default=0)
    error_message = models.TextField('エラーメッセージ', blank=True)
    started_at = models.DateTimeField('開始時刻', null=True, blank=True)
    completed_at = models.DateTimeField('完了時刻', null=True, blank=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)

    class Meta:
        db_table = 'earnings_analysis_batch_execution'
        verbose_name = 'バッチ実行履歴'
        verbose_name_plural = 'バッチ実行履歴一覧'
        ordering = ['-batch_date']

    def __str__(self):
        return f"{self.batch_date} - {self.get_status_display()}"