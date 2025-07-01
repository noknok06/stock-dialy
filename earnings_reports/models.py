"""
earnings_reports/models.py
決算分析アプリのモデル定義
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator
import json

User = get_user_model()


class Company(models.Model):
    """企業マスタ"""
    
    stock_code = models.CharField('証券コード', max_length=10, unique=True, db_index=True)
    name = models.CharField('企業名', max_length=200)
    name_kana = models.CharField('企業名カナ', max_length=200, blank=True)
    market = models.CharField('市場', max_length=50, blank=True)
    sector = models.CharField('業種', max_length=100, blank=True)
    
    # EDINETから取得した情報
    edinet_code = models.CharField('EDINETコード', max_length=20, blank=True)
    last_sync = models.DateTimeField('最終同期', null=True, blank=True)
    
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    
    class Meta:
        verbose_name = '企業'
        verbose_name_plural = '企業一覧'
        ordering = ['stock_code']
    
    def __str__(self):
        return f"{self.stock_code} - {self.name}"
    
    def get_absolute_url(self):
        return reverse('earnings_reports:company_detail', kwargs={'stock_code': self.stock_code})


class Document(models.Model):
    """EDINET書類情報"""
    
    DOC_TYPES = [
        ('120', '有価証券報告書'),
        ('130', '四半期報告書'),
        ('140', '半期報告書'),
        ('350', '決算短信'),
        ('other', 'その他'),
    ]
    
    doc_id = models.CharField('書類ID', max_length=50, unique=True, db_index=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='documents')
    
    doc_type = models.CharField('書類種別', max_length=10, choices=DOC_TYPES)
    doc_description = models.TextField('書類名', max_length=500)
    submit_date = models.DateField('提出日')
    period_start = models.DateField('期間開始', null=True, blank=True)
    period_end = models.DateField('期間終了', null=True, blank=True)
    
    # ダウンロード・分析状況
    is_downloaded = models.BooleanField('ダウンロード済み', default=False)
    download_size = models.IntegerField('ファイルサイズ(MB)', null=True, blank=True)
    is_analyzed = models.BooleanField('分析済み', default=False)
    
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    
    class Meta:
        verbose_name = '書類'
        verbose_name_plural = '書類一覧'
        ordering = ['-submit_date', 'company__stock_code']
        unique_together = ['doc_id', 'company']
    
    def __str__(self):
        return f"{self.company.name} - {self.get_doc_type_display()} ({self.submit_date})"
    
    def get_absolute_url(self):
        return reverse('earnings_reports:document_detail', kwargs={'doc_id': self.doc_id})


class Analysis(models.Model):
    """分析結果メイン（修正版）"""
    
    ANALYSIS_STATUS = [
        ('pending', '分析待ち'),
        ('processing', '分析中'),
        ('completed', '分析完了'),
        ('failed', '分析失敗'),
    ]
    
    # ユニーク制約を削除し、同じ書類を複数回分析可能にする
    document = models.ForeignKey(
        'Document', 
        on_delete=models.CASCADE, 
        related_name='analyses'  # related_nameを複数形に変更
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analyses')
    
    status = models.CharField('分析状況', max_length=20, choices=ANALYSIS_STATUS, default='pending')
    
    # 分析結果サマリー
    overall_score = models.FloatField(
        '総合スコア', 
        validators=[MinValueValidator(-100), MaxValueValidator(100)], 
        null=True, 
        blank=True
    )
    confidence_level = models.CharField('信頼性', max_length=20, blank=True, help_text='high/medium/low')
    
    # メタデータ
    analysis_date = models.DateTimeField('分析実施日時', auto_now_add=True)
    processing_time = models.FloatField('処理時間(秒)', null=True, blank=True)
    error_message = models.TextField('エラーメッセージ', blank=True)
    
    # 分析設定
    settings_json = models.JSONField('分析設定', default=dict, blank=True)
    
    # タスクID（Celery用）
    task_id = models.CharField('タスクID', max_length=100, blank=True)
    
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    
    class Meta:
        verbose_name = '分析結果'
        verbose_name_plural = '分析結果一覧'
        ordering = ['-analysis_date']
        # ユニーク制約を削除し、同じ書類・ユーザーで複数の分析を許可
        # unique_together = ['document', 'user']  # この行を削除またはコメントアウト
    
    def __str__(self):
        return f"{self.document} - 分析結果 ({self.get_status_display()})"
    
    def get_absolute_url(self):
        return reverse('earnings_reports:analysis_detail', kwargs={'pk': self.pk})
    
    def is_latest_for_document(self):
        """この分析がその書類の最新分析かどうか"""
        latest = Analysis.objects.filter(
            document=self.document,
            user=self.user,
            status='completed'
        ).order_by('-analysis_date').first()
        
        return latest and latest.id == self.id


class SentimentAnalysis(models.Model):
    """感情・テキスト分析結果（修正版）"""
    
    # OneToOneField から ForeignKey に変更
    analysis = models.ForeignKey(
        Analysis, 
        on_delete=models.CASCADE, 
        related_name='sentiment_analyses'
    )
    
    # 感情分析スコア
    positive_score = models.FloatField('ポジティブ度', default=0.0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    negative_score = models.FloatField('ネガティブ度', default=0.0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    neutral_score = models.FloatField('ニュートラル度', default=0.0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # 経営陣の自信度指標
    confidence_keywords_count = models.IntegerField('自信表現回数', default=0)
    uncertainty_keywords_count = models.IntegerField('不確実性表現回数', default=0)
    growth_keywords_count = models.IntegerField('成長関連表現回数', default=0)
    
    # リスク分析
    risk_keywords_count = models.IntegerField('リスク言及回数', default=0)
    risk_severity = models.CharField('リスク深刻度', max_length=20, blank=True, help_text='low/medium/high/critical')
    
    # 前回からの変化
    sentiment_change = models.FloatField('感情変化', null=True, blank=True, help_text='前回比較（-100～100）')
    confidence_change = models.FloatField('自信度変化', null=True, blank=True)
    
    # 詳細データ
    key_phrases = models.JSONField('重要フレーズ', default=list, blank=True)
    risk_phrases = models.JSONField('リスクフレーズ', default=list, blank=True)
    
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    
    class Meta:
        verbose_name = '感情分析'
        verbose_name_plural = '感情分析一覧'
        ordering = ['-created_at']  # 最新順
    
    def __str__(self):
        return f"{self.analysis.document.company.name} - 感情分析 ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
    
    @property
    def dominant_sentiment(self):
        """主要な感情を返す"""
        scores = {
            'positive': self.positive_score,
            'negative': self.negative_score,
            'neutral': self.neutral_score
        }
        return max(scores, key=scores.get)
    
    @property
    def management_confidence_index(self):
        """経営陣自信度指数（0-100）"""
        confidence_ratio = self.confidence_keywords_count / max(1, self.uncertainty_keywords_count)
        return min(100, confidence_ratio * 20)  # 最大100に制限


class CashFlowAnalysis(models.Model):
    """キャッシュフロー分析結果（修正版）"""
    
    CASHFLOW_PATTERNS = [
        ('ideal', '理想型（+営業CF, -投資CF, -財務CF）'),
        ('growth', '成長型（+営業CF, -投資CF, +財務CF）'),
        ('restructuring', '再構築型（+営業CF, +投資CF, -財務CF）'),
        ('danger', '危険型（-営業CF, +投資CF, +財務CF）'),
        ('conservative', '保守型（+営業CF, 少額投資・財務）'),
        ('other', 'その他'),
    ]
    
    # OneToOneField から ForeignKey に変更
    analysis = models.ForeignKey(
        Analysis, 
        on_delete=models.CASCADE, 
        related_name='cashflow_analyses'
    )
    
    # キャッシュフロー金額（百万円）
    operating_cf = models.BigIntegerField('営業キャッシュフロー', null=True, blank=True)
    investing_cf = models.BigIntegerField('投資キャッシュフロー', null=True, blank=True)
    financing_cf = models.BigIntegerField('財務キャッシュフロー', null=True, blank=True)
    free_cf = models.BigIntegerField('フリーキャッシュフロー', null=True, blank=True)
    
    # パターン分類
    pattern = models.CharField('CFパターン', max_length=20, choices=CASHFLOW_PATTERNS, blank=True)
    pattern_score = models.FloatField('パターンスコア', validators=[MinValueValidator(-100), MaxValueValidator(100)], null=True, blank=True)
    
    # 前年同期比
    operating_cf_growth = models.FloatField('営業CF成長率(%)', null=True, blank=True)
    investing_cf_growth = models.FloatField('投資CF成長率(%)', null=True, blank=True)
    financing_cf_growth = models.FloatField('財務CF成長率(%)', null=True, blank=True)
    
    # 健全性指標
    cf_adequacy_ratio = models.FloatField('CF充足率', null=True, blank=True, help_text='営業CF/(設備投資+配当)')
    cf_quality_score = models.FloatField('CF品質スコア', validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    
    # 解釈とコメント
    interpretation = models.TextField('解釈', blank=True)
    risk_factors = models.JSONField('リスク要因', default=list, blank=True)
    
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    
    class Meta:
        verbose_name = 'キャッシュフロー分析'
        verbose_name_plural = 'キャッシュフロー分析一覧'
        ordering = ['-created_at']  # 最新順
    
    def __str__(self):
        return f"{self.analysis.document.company.name} - CF分析 ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
    
    @property
    def is_healthy_pattern(self):
        """健全なCFパターンかどうか"""
        return self.pattern in ['ideal', 'growth', 'conservative']
    
    def get_pattern_description(self):
        """パターンの詳細説明"""
        descriptions = {
            'ideal': 'トヨタ型: 稼いで→投資して→借金返済。最も安定したパターン。',
            'growth': 'テスラ型: 稼いで→投資して→更に資金調達。成長企業の典型パターン。',
            'restructuring': '再構築型: 事業売却等で資金調達し借金返済。一時的な構造改革パターン。',
            'danger': '破綻企業型: 赤字で→資産売却→借金増。要注意パターン。',
            'conservative': '保守型: 堅実経営で投資も借入も控えめ。安定志向のパターン。',
            'other': 'その他のパターン。個別に詳細確認が必要。'
        }
        return descriptions.get(self.pattern, '')


class AnalysisHistory(models.Model):
    """分析履歴・比較用"""
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='analysis_history')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # 履歴データ
    analysis_count = models.IntegerField('分析回数', default=0)
    last_analysis_date = models.DateTimeField('最終分析日', null=True, blank=True)
    
    # トレンドデータ
    sentiment_trend = models.JSONField('感情トレンド', default=list, blank=True)
    cf_trend = models.JSONField('CFトレンド', default=list, blank=True)
    
    # 通知設定
    notify_on_earnings = models.BooleanField('決算時通知', default=False)
    notify_threshold = models.FloatField('通知閾値', default=50.0, help_text='スコア変化がこの値を超えたら通知')
    
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    
    class Meta:
        verbose_name = '分析履歴'
        verbose_name_plural = '分析履歴一覧'
        unique_together = ['company', 'user']
    
    def __str__(self):
        return f"{self.company.name} - {self.user.username} 履歴"