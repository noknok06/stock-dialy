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

# 既存のコードはそのまま保持して、最後に以下を追加

class PortfolioEvaluation(models.Model):
    """ポートフォリオ評価結果"""
    
    EVALUATION_STATUS_CHOICES = [
        ('pending', '分析待ち'),
        ('processing', '分析中'),
        ('completed', '完了'),
        ('failed', 'エラー'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200, verbose_name='評価タイトル', default='ポートフォリオ評価')
    
    # 評価実行時のポートフォリオ状況
    evaluation_date = models.DateTimeField(auto_now_add=True, verbose_name='評価実行日時')
    total_holdings = models.IntegerField(default=0, verbose_name='保有銘柄数')
    total_portfolio_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, 
                                               verbose_name='ポートフォリオ総額')
    total_investment = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
                                          verbose_name='総投資額')
    total_return_pct = models.FloatField(null=True, blank=True, verbose_name='総合リターン率')
    
    # 分析ステータス
    status = models.CharField(max_length=20, choices=EVALUATION_STATUS_CHOICES, default='pending')
    
    # 評価データ（JSON形式で保存）
    portfolio_data = models.JSONField(default=dict, verbose_name='ポートフォリオデータ')
    market_context = models.JSONField(default=dict, verbose_name='市場環境データ')
    
    # AI評価結果
    professional_evaluation = models.TextField(blank=True, verbose_name='プロ評価コメント')
    api_used = models.BooleanField(default=False, verbose_name='Gemini API使用')
    
    # メタデータ
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-evaluation_date']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'evaluation_date']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.title} ({self.evaluation_date.strftime('%Y-%m-%d %H:%M')})"
    
    def get_evaluation_period_display(self):
        """評価日時の表示用テキスト"""
        return self.evaluation_date.strftime('%Y年%m月%d日 %H:%M')
    
    def is_evaluation_completed(self):
        """評価が完了しているか"""
        return self.status == 'completed'
    
    def get_win_rate(self):
        """勝率を取得"""
        portfolio_analysis = self.portfolio_data.get('portfolio_analysis', {})
        return portfolio_analysis.get('win_rate', 0)
    
    def get_diversification_score(self):
        """分散投資スコアを取得"""
        portfolio_analysis = self.portfolio_data.get('portfolio_analysis', {})
        return portfolio_analysis.get('diversification_score', 'unknown')
    
    def get_risk_level(self):
        """リスクレベルを取得"""
        risk_analysis = self.portfolio_data.get('risk_analysis', {})
        return risk_analysis.get('risk_level', 'unknown')


class PortfolioEvaluationInsight(models.Model):
    """ポートフォリオ評価の個別インサイト"""
    
    INSIGHT_TYPE_CHOICES = [
        ('strength', '強み・ポジティブ要素'),
        ('weakness', '弱み・リスク要素'),
        ('neutral', '中立的現状判断'),
        ('recommendation', '改善提案'),
        ('risk_assessment', 'リスク評価'),
        ('market_positioning', '市場ポジショニング'),
    ]
    
    evaluation = models.ForeignKey(PortfolioEvaluation, on_delete=models.CASCADE, related_name='insights')
    insight_type = models.CharField(max_length=20, choices=INSIGHT_TYPE_CHOICES)
    title = models.CharField(max_length=200, verbose_name='インサイトタイトル')
    content = models.TextField(verbose_name='内容')
    priority = models.IntegerField(default=1, verbose_name='優先度（1-5）')
    
    # 関連する銘柄（オプション）
    related_stocks = models.JSONField(default=list, verbose_name='関連銘柄')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['insight_type', '-priority', 'created_at']
    
    def __str__(self):
        return f"{self.evaluation.title} - {self.get_insight_type_display()}: {self.title}"