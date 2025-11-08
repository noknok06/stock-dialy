# stockdiary/api_views.py
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_GET
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import (
    PushSubscription, DiaryNotification, 
    NotificationLog, StockDiary
)
import json
from pywebpush import webpush, WebPushException
from decimal import Decimal, InvalidOperation
import logging
import traceback


@require_GET
def get_vapid_public_key(request):
    """VAPID公開鍵を返す（認証不要）"""
    return JsonResponse({
        'public_key': settings.WEBPUSH_SETTINGS.get('VAPID_PUBLIC_KEY', '')
    })


@csrf_exempt  # 🆕 CSRF保護を無効化
@require_http_methods(["POST"])
def subscribe_push(request):
    """プッシュ通知サブスクリプションを登録"""
    
    # 認証チェック
    if not request.user.is_authenticated:
        return JsonResponse({'error': '認証が必要です'}, status=401)
    
    try:
        data = json.loads(request.body)
        subscription_info = data.get('subscription')
        
        if not subscription_info:
            return JsonResponse({'error': '無効なサブスクリプション'}, status=400)
        
        from stockdiary.models import PushSubscription
        
        # サブスクリプションを作成または更新
        subscription, created = PushSubscription.objects.update_or_create(
            endpoint=subscription_info['endpoint'],
            defaults={
                'user': request.user,
                'p256dh': subscription_info['keys']['p256dh'],
                'auth': subscription_info['keys']['auth'],
                'device_name': data.get('device_name', ''),
                'user_agent': data.get('user_agent', ''),
                'is_active': True,
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': 'プッシュ通知を有効にしました',
            'created': created,
            'subscription_id': str(subscription.id)
        })
        
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Push subscription error: {e}")
        logger.error(traceback.format_exc())
        
        return JsonResponse({
            'error': str(e),
            'detail': 'サブスクリプションの登録に失敗しました'
        }, status=500)
        

@csrf_exempt  # 🆕
@require_http_methods(["POST"])
def unsubscribe_push(request):
    """プッシュ通知サブスクリプションを解除"""
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': '認証が必要です'}, status=401)
    
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        
        if not endpoint:
            return JsonResponse({'error': 'エンドポイントが必要です'}, status=400)
        
        from stockdiary.models import PushSubscription
        
        PushSubscription.objects.filter(
            user=request.user,
            endpoint=endpoint
        ).update(is_active=False)
        
        return JsonResponse({
            'success': True,
            'message': 'プッシュ通知を無効にしました'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    

@login_required
@require_http_methods(["POST"])
def create_diary_notification(request, diary_id):
    """日記の通知設定を作成（リマインダーのみ）"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # 日記を取得
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        
        # リクエストボディをパース
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON format'
            }, status=400)
        
        # 必須フィールドのバリデーション
        remind_at = data.get('remind_at')
        if not remind_at:
            return JsonResponse({
                'success': False,
                'error': '通知日時を入力してください'
            }, status=400)
        
        # 日時をパース
        try:
            from datetime import datetime
            remind_at_dt = datetime.fromisoformat(remind_at.replace('Z', '+00:00'))
            
            # タイムゾーンを適用
            from django.utils import timezone
            if timezone.is_naive(remind_at_dt):
                remind_at_dt = timezone.make_aware(remind_at_dt)
        except ValueError as e:
            logger.error(f"Date parsing error: {e}")
            return JsonResponse({
                'success': False,
                'error': '日時の形式が正しくありません'
            }, status=400)
        
        # 過去の日時をチェック
        now = timezone.now()
        if remind_at_dt < now:
            return JsonResponse({
                'success': False,
                'error': '過去の日時は指定できません'
            }, status=400)
        
        # メッセージを取得（オプション）
        message = data.get('message', '').strip()
        
        # 通知を作成
        notification_data = {
            'diary': diary,
            'remind_at': remind_at_dt,
            'message': message,
            'is_active': True
        }
        
        logger.info(f"Creating notification with data: {notification_data}")
        
        notification = DiaryNotification.objects.create(**notification_data)
        
        logger.info(f"✅ Notification created: {notification.id}")
        
        return JsonResponse({
            'success': True,
            'message': 'リマインダーを設定しました',
            'notification_id': str(notification.id),
            'notification': {
                'id': str(notification.id),
                'remind_at': notification.remind_at.isoformat(),
                'message': notification.message,
                'is_active': notification.is_active,
                'created_at': notification.created_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Unexpected error: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': f'通知設定中にエラーが発生しました: {str(e)}'
        }, status=500)
    

@require_http_methods(["POST"])  # ← DELETEを削除、POSTのみ
@login_required
def delete_diary_notification(request, notification_id):
    """日記の通知設定を削除"""
    try:
        notification = get_object_or_404(
            DiaryNotification,
            id=notification_id,
            diary__user=request.user
        )
        notification.delete()
        
        return JsonResponse({
            'success': True,
            'message': '通知設定を削除しました'
        })
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"通知削除エラー: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def list_diary_notifications(request, diary_id):
    """日記の通知設定一覧を取得"""
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        
        notifications = DiaryNotification.objects.filter(
            diary=diary
        ).order_by('-created_at')
        
        notification_list = []
        for notification in notifications:
            notification_list.append({
                'id': str(notification.id),
                'remind_at': notification.remind_at.isoformat(),
                'message': notification.message,
                'is_active': notification.is_active,
                'last_sent': notification.last_sent.isoformat() if notification.last_sent else None,
                'created_at': notification.created_at.isoformat(),
            })
        
        return JsonResponse({
            'success': True,
            'notifications': notification_list,
            'count': len(notification_list)
        })
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"List notifications error: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_GET
@login_required
def get_notification_logs(request):
    """通知履歴を取得"""
    limit = int(request.GET.get('limit', 20))
    offset = int(request.GET.get('offset', 0))
    unread_only = request.GET.get('unread', 'false').lower() == 'true'
    
    logs = NotificationLog.objects.filter(user=request.user)
    
    if unread_only:
        logs = logs.filter(is_read=False)
    
    logs = logs[offset:offset + limit]
    
    data = [{
        'id': log.id,
        'title': log.title,
        'message': log.message,
        'url': log.url,
        'is_read': log.is_read,
        'sent_at': log.sent_at.isoformat(),
    } for log in logs]
    
    unread_count = NotificationLog.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    return JsonResponse({
        'logs': data,
        'unread_count': unread_count,
        'has_more': logs.count() == limit
    })


@require_http_methods(["POST"])
@login_required
def mark_notification_read(request, log_id):
    """通知を既読にする"""
    try:
        log = get_object_or_404(NotificationLog, id=log_id, user=request.user)
        log.is_read = True
        log.read_at = timezone.now()
        log.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
@login_required
def mark_all_read(request):
    """すべての通知を既読にする"""
    try:
        NotificationLog.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# プッシュ通知送信ヘルパー
def send_push_notification(user, title, message, url='/', tag='notification'):
    """ユーザーにプッシュ通知を送信"""
    subscriptions = PushSubscription.objects.filter(
        user=user,
        is_active=True
    )
    
    payload = json.dumps({
        'title': title,
        'message': message,
        'url': url,
        'tag': tag,
        'icon': '/static/images/icon-192.png',
        'badge': '/static/images/badge-72.png',
    })
    
    success_count = 0
    failed_subscriptions = []
    
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': subscription.endpoint,
                    'keys': {
                        'p256dh': subscription.p256dh,
                        'auth': subscription.auth
                    }
                },
                data=payload,
                vapid_private_key=settings.WEBPUSH_SETTINGS.get('VAPID_PRIVATE_KEY'),
                vapid_claims={
                    'sub': f'mailto:{settings.WEBPUSH_SETTINGS.get("VAPID_ADMIN_EMAIL")}'
                }
            )
            success_count += 1
            subscription.last_used = timezone.now()
            subscription.save()
            
        except WebPushException as e:
            if e.response and e.response.status_code in [404, 410]:
                failed_subscriptions.append(subscription)
    
    # 無効なサブスクリプションを削除
    for sub in failed_subscriptions:
        sub.is_active = False
        sub.save()
    
    return success_count

@login_required
@require_http_methods(["GET"])
def list_all_notifications(request):
    """すべての日記の通知設定一覧を取得"""
    try:
        notifications = DiaryNotification.objects.filter(
            diary__user=request.user
        ).select_related('diary').order_by('-created_at')
        
        notification_list = []
        for notification in notifications:
            notification_list.append({
                'id': str(notification.id),
                'diary_id': notification.diary.id,
                'diary_name': notification.diary.stock_name,
                'remind_at': notification.remind_at.isoformat(),
                'message': notification.message,
                'is_active': notification.is_active,
                'last_sent': notification.last_sent.isoformat() if notification.last_sent else None,
                'created_at': notification.created_at.isoformat(),
            })
        
        return JsonResponse({
            'success': True,
            'notifications': notification_list,
            'count': len(notification_list)
        })
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"List all notifications error: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)