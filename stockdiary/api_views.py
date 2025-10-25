# stockdiary/api_views.py
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_GET
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import (
    PushSubscription, DiaryNotification, 
    NotificationLog, StockDiary
)
import json
from pywebpush import webpush, WebPushException


@require_GET
def get_vapid_public_key(request):
    """VAPID公開鍵を返す（認証不要）"""
    return JsonResponse({
        'public_key': settings.WEBPUSH_SETTINGS.get('VAPID_PUBLIC_KEY', '')
    })


@require_http_methods(["POST"])
@login_required
def subscribe_push(request):
    """プッシュ通知サブスクリプションを登録"""
    try:
        data = json.loads(request.body)
        subscription_info = data.get('subscription')
        
        if not subscription_info:
            return JsonResponse({'error': '無効なサブスクリプション'}, status=400)
        
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
            'created': created
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
@login_required
def unsubscribe_push(request):
    """プッシュ通知サブスクリプションを解除"""
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        
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


@require_http_methods(["POST"])
@login_required
def create_diary_notification(request, diary_id):
    """日記の通知設定を作成"""
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        data = json.loads(request.body)
        
        notification = DiaryNotification.objects.create(
            diary=diary,
            notification_type=data.get('notification_type', 'reminder'),
            target_price=data.get('target_price'),
            alert_above=data.get('alert_above', True),
            remind_at=data.get('remind_at'),
            frequency=data.get('frequency'),
            notify_time=data.get('notify_time'),
            message=data.get('message', ''),
            is_active=True
        )
        
        return JsonResponse({
            'success': True,
            'notification_id': str(notification.id),
            'message': '通知を設定しました'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["DELETE", "POST"])
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
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
@login_required
def list_diary_notifications(request, diary_id):
    """日記の通知設定一覧を取得"""
    try:
        diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
        notifications = diary.notifications.filter(is_active=True)
        
        data = [{
            'id': str(n.id),
            'type': n.notification_type,
            'type_display': n.get_notification_type_display(),
            'target_price': str(n.target_price) if n.target_price else None,
            'alert_above': n.alert_above,
            'remind_at': n.remind_at.isoformat() if n.remind_at else None,
            'frequency': n.frequency,
            'notify_time': n.notify_time.isoformat() if n.notify_time else None,
            'message': n.message,
            'last_sent': n.last_sent.isoformat() if n.last_sent else None,
        } for n in notifications]
        
        return JsonResponse({'notifications': data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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