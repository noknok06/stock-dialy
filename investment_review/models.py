# investment_review/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import json


class InvestmentReview(models.Model):
    """投資振り返りレポート"""
    
    REVIEW_TYPE_CHOICES = [
        ('monthly', '月次レビュー'),
        ('weekly', '週次レビュー'),
        ('custom', 'カスタム期間'),
    ]
    
    ANALYSIS_STATUS_CHOICES = [
        ('pending', '分析待ち'),
        ('processing', '分析中'),
        ('completed', '完了'),
        ('failed', 'エラー'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200, verbose_name='レポートタイトル')
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPE_CHOICES, default='monthly')
    
    # 分析期間
    start_date = models.DateField(verbose_name='分析開始日')
    end_date = models.DateField(verbose_name='分析終了日')
    
    # 分析ステータス
    status = models.CharField(max_length=20, choices=ANALYSIS_STATUS_CHOICES, default='pending')
    
    # 分析結果（JSON形式で保存）
    analysis_data = models.JSONField(default=dict, verbose_name='分析データ')
    
    # Geminiからの振り返りコメント
    professional_insights = models.TextField(blank=True, verbose_name='プロ目線の振り返り')
    
    # 統計情報
    total_entries = models.IntegerField(default=0, verbose_name='総記録数')
    active_holdings = models.IntegerField(default=0, verbose_name='保有中銘柄数')
    completed_trades = models.IntegerField(default=0, verbose_name='売却完了数')
    memo_entries = models.IntegerField(default=0, verbose_name='メモ記録数')
    
    # メタデータ
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    analysis_completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'review_type']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
    
    def get_analysis_period_display(self):
        """分析期間の表示用テキスト"""
        return f"{self.start_date.strftime('%Y年%m月%d日')} - {self.end_date.strftime('%Y年%m月%d日')}"
    
    def is_analysis_completed(self):
        """分析が完了しているか"""
        return self.status == 'completed'
    
    def get_success_rate(self):
        """成功率を計算"""
        if self.completed_trades == 0:
            return None
        
        profitable_trades = self.analysis_data.get('profitable_trades', 0)
        return round((profitable_trades / self.completed_trades) * 100, 1)
    
    def get_total_profit_loss(self):
        """総損益を取得"""
        return self.analysis_data.get('total_profit_loss', 0)
    
    def get_avg_holding_period(self):
        """平均保有期間を取得"""
        return self.analysis_data.get('avg_holding_period', 0)
    
    @classmethod
    def create_monthly_review(cls, user, year=None, month=None):
        """月次レビューを作成"""
        if year is None or month is None:
            now = timezone.now().date()
            year, month = now.year, now.month
        
        # 前月の日付範囲を計算
        from calendar import monthrange
        
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1
        
        start_date = timezone.datetime(prev_year, prev_month, 1).date()
        _, last_day = monthrange(prev_year, prev_month)
        end_date = timezone.datetime(prev_year, prev_month, last_day).date()
        
        title = f"{prev_year}年{prev_month}月の投資振り返り"
        
        # 既存レビューがある場合は更新
        existing_review = cls.objects.filter(
            user=user,
            start_date=start_date,
            end_date=end_date,
            review_type='monthly'
        ).first()
        
        if existing_review:
            return existing_review
        
        return cls.objects.create(
            user=user,
            title=title,
            review_type='monthly',
            start_date=start_date,
            end_date=end_date
        )


class ReviewInsight(models.Model):
    """振り返りの個別インサイト"""
    
    INSIGHT_TYPE_CHOICES = [
        ('strength', '強み・良い点'),
        ('weakness', '改善点'),
        ('opportunity', '機会・チャンス'),
        ('risk', 'リスク・注意点'),
        ('recommendation', '推奨アクション'),
    ]
    
    review = models.ForeignKey(InvestmentReview, on_delete=models.CASCADE, related_name='insights')
    insight_type = models.CharField(max_length=20, choices=INSIGHT_TYPE_CHOICES)
    title = models.CharField(max_length=200, verbose_name='インサイトタイトル')
    content = models.TextField(verbose_name='内容')
    priority = models.IntegerField(default=1, verbose_name='優先度（1-5）')
    
    # 関連データ（具体的な数値や根拠）
    supporting_data = models.JSONField(default=dict, verbose_name='根拠データ')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['insight_type', '-priority', 'created_at']
    
    def __str__(self):
        return f"{self.review.title} - {self.get_insight_type_display()}: {self.title}"