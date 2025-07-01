"""
earnings_reports/signals.py
決算分析システムのシグナルハンドラー
"""

import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .models import Analysis, AnalysisHistory, Company, SentimentAnalysis, CashFlowAnalysis

logger = logging.getLogger('earnings_analysis')
User = get_user_model()


@receiver(post_save, sender=Analysis)
def analysis_post_save_handler(sender, instance, created, **kwargs):
    """分析完了時の処理"""
    
    if not created and instance.status == 'completed':
        # 分析履歴の更新
        update_analysis_history(instance)
        
        # 分析完了通知
        if should_send_notification(instance):
            send_analysis_completion_notification(instance)
        
        # スコア変化の通知
        check_score_change_notification(instance)


@receiver(post_save, sender=SentimentAnalysis)
def sentiment_analysis_post_save_handler(sender, instance, created, **kwargs):
    """感情分析完了時の処理"""
    
    if created:
        logger.info(f"感情分析完了: {instance.analysis.document.company.name}")
        
        # 異常値検出
        detect_sentiment_anomalies(instance)


@receiver(post_save, sender=CashFlowAnalysis)
def cashflow_analysis_post_save_handler(sender, instance, created, **kwargs):
    """キャッシュフロー分析完了時の処理"""
    
    if created:
        logger.info(f"CF分析完了: {instance.analysis.document.company.name}")
        
        # リスクパターン検出
        detect_cashflow_risks(instance)


@receiver(pre_delete, sender=Company)
def company_pre_delete_handler(sender, instance, **kwargs):
    """企業削除前の処理"""
    
    # 関連データのクリーンアップ
    logger.info(f"企業削除: {instance.name} - 関連データをクリーンアップ")


def update_analysis_history(analysis):
    """分析履歴の更新"""
    
    try:
        history, created = AnalysisHistory.objects.get_or_create(
            company=analysis.document.company,
            user=analysis.user,
            defaults={
                'analysis_count': 0,
                'sentiment_trend': [],
                'cf_trend': []
            }
        )
        
        # 分析回数の更新
        history.analysis_count += 1
        history.last_analysis_date = analysis.analysis_date
        
        # トレンドデータの更新
        update_trend_data(history, analysis)
        
        history.save()
        
        logger.info(f"分析履歴更新: {analysis.document.company.name} (計{history.analysis_count}回)")
        
    except Exception as e:
        logger.error(f"分析履歴更新エラー: {str(e)}")


def update_trend_data(history, analysis):
    """トレンドデータの更新"""
    
    try:
        # 感情トレンドの更新
        if hasattr(analysis, 'sentiment'):
            sentiment = analysis.sentiment
            sentiment_point = {
                'date': analysis.analysis_date.isoformat(),
                'positive_score': sentiment.positive_score,
                'negative_score': sentiment.negative_score,
                'confidence_index': sentiment.management_confidence_index
            }
            
            sentiment_trend = history.sentiment_trend or []
            sentiment_trend.append(sentiment_point)
            
            # 最新12ポイントのみ保持
            history.sentiment_trend = sentiment_trend[-12:]
        
        # CFトレンドの更新
        if hasattr(analysis, 'cashflow'):
            cashflow = analysis.cashflow
            cf_point = {
                'date': analysis.analysis_date.isoformat(),
                'pattern': cashflow.pattern,
                'pattern_score': cashflow.pattern_score,
                'quality_score': cashflow.cf_quality_score
            }
            
            cf_trend = history.cf_trend or []
            cf_trend.append(cf_point)
            
            # 最新12ポイントのみ保持
            history.cf_trend = cf_trend[-12:]
        
    except Exception as e:
        logger.error(f"トレンドデータ更新エラー: {str(e)}")


def should_send_notification(analysis):
    """通知送信の判定"""
    
    try:
        # ユーザーの分析設定を確認
        settings_json = analysis.settings_json or {}
        
        # 分析完了通知が有効かチェック
        if settings_json.get('notify_on_completion', False):
            return True
        
        # 分析履歴の通知設定をチェック
        history = AnalysisHistory.objects.filter(
            company=analysis.document.company,
            user=analysis.user
        ).first()
        
        if history and history.notify_on_earnings:
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"通知判定エラー: {str(e)}")
        return False


def send_analysis_completion_notification(analysis):
    """分析完了通知の送信"""
    
    try:
        user = analysis.user
        company = analysis.document.company
        
        subject = f'【カブログ】{company.name}の分析が完了しました'
        
        message = f"""
{user.username}様

{company.name}（{company.stock_code}）の決算分析が完了しました。

■ 分析結果サマリー
・総合スコア: {analysis.overall_score or 'N/A'}
・信頼性: {analysis.get_confidence_level_display() or 'N/A'}
・処理時間: {analysis.processing_time or 'N/A'}秒

■ 分析対象書類
・{analysis.document.get_doc_type_display()}
・提出日: {analysis.document.submit_date}

詳細な分析結果は以下のリンクからご確認ください。
{settings.SITE_URL}/earnings/analysis/{analysis.pk}/

---
カブログ決算分析システム
        """.strip()
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True
        )
        
        logger.info(f"分析完了通知送信: {user.email}")
        
    except Exception as e:
        logger.error(f"通知送信エラー: {str(e)}")


def check_score_change_notification(analysis):
    """スコア変化通知のチェック"""
    
    try:
        if analysis.overall_score is None:
            return
        
        # 前回の分析結果を取得
        previous_analysis = Analysis.objects.filter(
            document__company=analysis.document.company,
            user=analysis.user,
            status='completed',
            analysis_date__lt=analysis.analysis_date
        ).order_by('-analysis_date').first()
        
        if not previous_analysis or previous_analysis.overall_score is None:
            return
        
        # スコア変化を計算
        score_change = analysis.overall_score - previous_analysis.overall_score
        
        # 通知設定を確認
        history = AnalysisHistory.objects.filter(
            company=analysis.document.company,
            user=analysis.user
        ).first()
        
        if not history:
            return
        
        threshold = history.notify_threshold or 50.0
        
        # 閾値を超えた変化があれば通知
        if abs(score_change) >= threshold:
            send_score_change_notification(analysis, previous_analysis, score_change)
            
    except Exception as e:
        logger.error(f"スコア変化通知チェックエラー: {str(e)}")


def send_score_change_notification(analysis, previous_analysis, score_change):
    """スコア変化通知の送信"""
    
    try:
        user = analysis.user
        company = analysis.document.company
        
        change_direction = "上昇" if score_change > 0 else "下降"
        change_icon = "📈" if score_change > 0 else "📉"
        
        subject = f'【カブログ】{company.name}のスコアが大きく変化しました {change_icon}'
        
        message = f"""
{user.username}様

{company.name}（{company.stock_code}）の分析スコアに大きな変化がありました。

■ スコア変化
・前回: {previous_analysis.overall_score:.1f}
・今回: {analysis.overall_score:.1f}
・変化: {score_change:+.1f} ({change_direction})

■ 分析日時
・前回: {previous_analysis.analysis_date.strftime('%Y年%m月%d日')}
・今回: {analysis.analysis_date.strftime('%Y年%m月%d日')}

詳細な分析結果をご確認いただき、投資判断の参考にしてください。

{settings.SITE_URL}/earnings/analysis/{analysis.pk}/

---
カブログ決算分析システム
        """.strip()
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True
        )
        
        logger.info(f"スコア変化通知送信: {user.email} ({score_change:+.1f})")
        
    except Exception as e:
        logger.error(f"スコア変化通知エラー: {str(e)}")


def detect_sentiment_anomalies(sentiment_analysis):
    """感情分析の異常値検出"""
    
    try:
        # 極端な感情スコアの検出
        if sentiment_analysis.risk_keywords_count >= 20:
            logger.warning(
                f"高リスク企業検出: {sentiment_analysis.analysis.document.company.name} "
                f"(リスク言及: {sentiment_analysis.risk_keywords_count}回)"
            )
        
        # 急激な感情変化の検出
        if sentiment_analysis.sentiment_change and abs(sentiment_analysis.sentiment_change) >= 50:
            logger.warning(
                f"急激な感情変化検出: {sentiment_analysis.analysis.document.company.name} "
                f"(変化: {sentiment_analysis.sentiment_change:+.1f})"
            )
            
    except Exception as e:
        logger.error(f"感情分析異常値検出エラー: {str(e)}")


def detect_cashflow_risks(cashflow_analysis):
    """キャッシュフローリスク検出"""
    
    try:
        company_name = cashflow_analysis.analysis.document.company.name
        
        # 危険パターンの検出
        if cashflow_analysis.pattern == 'danger':
            logger.warning(f"危険CFパターン検出: {company_name}")
        
        # 営業CFマイナスの検出
        if cashflow_analysis.operating_cf and cashflow_analysis.operating_cf < 0:
            logger.warning(f"営業CFマイナス検出: {company_name}")
        
        # フリーCF大幅マイナスの検出
        if cashflow_analysis.free_cf and cashflow_analysis.free_cf < -100000:  # -1000億円以下
            logger.warning(f"大幅フリーCFマイナス検出: {company_name}")
            
    except Exception as e:
        logger.error(f"CFリスク検出エラー: {str(e)}")


# 定期的な通知処理（Celeryタスクから呼び出される想定）
def send_earnings_calendar_notifications():
    """決算カレンダー通知の送信"""
    
    try:
        from datetime import timedelta
        from .utils.company_utils import get_earnings_schedule
        
        # 通知設定が有効なユーザーを取得
        notification_users = AnalysisHistory.objects.filter(
            notify_on_earnings=True
        ).select_related('user', 'company')
        
        for history in notification_users:
            # 企業の決算予定を確認
            schedule = get_earnings_schedule(history.company, days_ahead=7)
            
            if schedule:
                send_earnings_schedule_notification(history.user, history.company, schedule)
                
    except Exception as e:
        logger.error(f"決算カレンダー通知エラー: {str(e)}")


def send_earnings_schedule_notification(user, company, schedule):
    """決算予定通知の送信"""
    
    try:
        subject = f'【カブログ】{company.name}の決算発表予定'
        
        schedule_text = '\n'.join([
            f"・{item['date'].strftime('%m月%d日')}: {item['description']}"
            for item in schedule
        ])
        
        message = f"""
{user.username}様

{company.name}（{company.stock_code}）の決算発表が近づいています。

■ 予定
{schedule_text}

分析の準備をお忘れなく。

---
カブログ決算分析システム
        """.strip()
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True
        )
        
        logger.info(f"決算予定通知送信: {user.email} - {company.name}")
        
    except Exception as e:
        logger.error(f"決算予定通知エラー: {str(e)}")