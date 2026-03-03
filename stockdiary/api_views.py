# stockdiary/api_views.py
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_GET
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import (
    PushSubscription, DiaryNotification,
    NotificationLog, StockDiary
)
from .utils import (
    extract_hashtags, get_all_hashtags_from_queryset, search_diaries_by_hashtag,
    get_tag_graph_data, get_sector_graph_data, get_hashtag_graph_data,
    get_mention_graph_data,
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


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def subscribe_push(request):
    """プッシュ通知サブスクリプションを登録"""
    
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
        

@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def unsubscribe_push(request):
    """プッシュ通知サブスクリプションを解除"""
    
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


@login_required
@require_http_methods(["GET"])
def get_hashtags(request):
    """
    ユーザーの日記から全てのハッシュタグを取得

    Query Parameters:
        - q: 検索クエリ（ハッシュタグのフィルタリング用）
        - limit: 返却する最大件数（デフォルト: 50）
    """
    try:
        query = request.GET.get('q', '').strip().lstrip('#')
        limit = int(request.GET.get('limit', 50))

        # ユーザーの日記を取得
        diaries = StockDiary.objects.filter(user=request.user)

        # 全てのハッシュタグを抽出
        hashtags = get_all_hashtags_from_queryset(diaries)

        # クエリでフィルタリング
        if query:
            hashtags = [
                tag_data for tag_data in hashtags
                if query.lower() in tag_data['tag'].lower()
            ]

        # 上限を適用
        hashtags = hashtags[:limit]

        return JsonResponse({
            'success': True,
            'hashtags': hashtags,
            'count': len(hashtags)
        })

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Get hashtags error: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==========================================
# 関連日記API
# ==========================================

def _diary_excerpt(diary, length=60):
    """日記の本文（reason or memo）から簡易抜粋を生成"""
    import re
    text = (diary.reason or diary.memo or '').strip()
    text = re.sub(r'#{1,6}\s*', '', text)       # Markdown見出し除去
    text = re.sub(r'[*_`>\-]+', '', text)        # Markdown記号除去
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return ''
    return text[:length] + ('…' if len(text) > length else '')


@login_required
@require_http_methods(["GET"])
def search_related_diaries(request, diary_id):
    """関連付けする日記を検索する"""
    diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse({'diaries': []})

    # 自身・既に関連付け済み・逆方向も除外
    already_linked_ids = set(diary.linked_diaries.values_list('id', flat=True))
    already_linked_ids |= set(diary.linked_from.values_list('id', flat=True))
    already_linked_ids.add(diary_id)

    from django.db.models import Q
    results = StockDiary.objects.filter(
        user=request.user
    ).filter(
        Q(stock_name__icontains=query) | Q(stock_symbol__icontains=query) | Q(reason__icontains=query)
    ).exclude(
        id__in=already_linked_ids
    ).order_by('-updated_at')[:10]

    diaries = [
        {
            'id': d.id,
            'stock_name': d.stock_name,
            'stock_symbol': d.stock_symbol,
            'first_purchase_date': d.first_purchase_date.strftime('%Y/%m/%d') if d.first_purchase_date else None,
            'excerpt': _diary_excerpt(d),
        }
        for d in results
    ]
    return JsonResponse({'diaries': diaries})


@login_required
@require_http_methods(["POST"])
def add_related_diary(request, diary_id):
    """関連日記を追加する（双方向）"""
    import json
    diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)

    try:
        data = json.loads(request.body)
        related_id = int(data.get('related_id'))
    except (ValueError, TypeError, KeyError):
        return JsonResponse({'error': '無効なパラメータ'}, status=400)

    if related_id == diary_id:
        return JsonResponse({'error': '自分自身は関連付けできません'}, status=400)

    related = get_object_or_404(StockDiary, id=related_id, user=request.user)

    # 双方向で追加
    diary.linked_diaries.add(related)
    related.linked_diaries.add(diary)

    return JsonResponse({
        'success': True,
        'diary': {
            'id': related.id,
            'stock_name': related.stock_name,
            'stock_symbol': related.stock_symbol,
        }
    })


@login_required
@require_http_methods(["POST"])
def remove_related_diary(request, diary_id, related_id):
    """関連日記を解除する（双方向）"""
    diary = get_object_or_404(StockDiary, id=diary_id, user=request.user)
    related = get_object_or_404(StockDiary, id=related_id, user=request.user)

    # 双方向で削除
    diary.linked_diaries.remove(related)
    related.linked_diaries.remove(diary)

    return JsonResponse({'success': True})


@login_required
@require_http_methods(["GET"])
def diary_graph_data(request):
    """日記関連グラフのノード・エッジデータを返す。

    Query Parameters:
        status:     all / holding / sold / memo（デフォルト: all）
        tag:        タグID（空文字 or 未指定で全て）
        edge_modes: カンマ区切りのモード列（manual,tag,sector,hashtag）
                    後方互換のため edge_mode（単数）も受け付ける

    edge_modes:
        manual   - 手動 linked_diaries リンク
        tag      - Tagをハブノードとして diary→tag エッジを生成
        sector   - 業種をハブノードとして diary→sector エッジを生成
        hashtag  - @ハッシュタグをハブノードとして diary→hashtag エッジを生成

    複数モードを同時に指定すると各モードのノード・エッジを統合して返す。
    """
    try:
        user = request.user
        status_filter = request.GET.get('status', 'all')
        tag_id = request.GET.get('tag', '').strip()

        # edge_modes（複数可）を解析。後方互換として edge_mode（単数）も受け付ける
        VALID_MODES = {'manual', 'tag', 'sector', 'hashtag', 'mention'}
        raw = request.GET.get('edge_modes', request.GET.get('edge_mode', 'tag')).strip()
        edge_modes = [m.strip() for m in raw.split(',') if m.strip() in VALID_MODES]
        if not edge_modes:
            edge_modes = ['tag']

        all_user_qs = StockDiary.objects.filter(user=user)

        # --- primary: フィルター条件に合う日記 ---
        primary_qs = all_user_qs
        if status_filter == 'holding':
            primary_qs = primary_qs.filter(current_quantity__gt=0)
        elif status_filter == 'sold':
            primary_qs = primary_qs.filter(transaction_count__gt=0, current_quantity=0)
        elif status_filter == 'memo':
            primary_qs = primary_qs.filter(transaction_count=0)
        if tag_id:
            try:
                primary_qs = primary_qs.filter(tags__id=int(tag_id))
            except (ValueError, TypeError):
                pass

        primary_ids = set(primary_qs.values_list('id', flat=True))

        # 全モードで共通利用する primary 日記を一括取得
        # mention モードで memo も参照するため常に含める
        primary_diaries = list(
            primary_qs.prefetch_related('tags').only(
                'id', 'stock_name', 'stock_symbol', 'sector',
                'realized_profit', 'current_quantity', 'transaction_count', 'reason', 'memo',
            )
        )

        # 結果コンテナ（日記ノードは id で重複排除）
        diary_nodes_map = {}   # diary_id -> node dict
        hub_nodes_map = {}     # hub_id   -> node dict
        all_edges = []

        # ====================================================
        # manual モード: 手動リンク（diary-diary エッジ）
        # ====================================================
        if 'manual' in edge_modes:
            Through = StockDiary.linked_diaries.through
            is_filtered = (status_filter != 'all' or bool(tag_id))
            secondary_ids = set()
            if is_filtered:
                linked_from = set(
                    Through.objects.filter(from_stockdiary_id__in=primary_ids)
                    .values_list('to_stockdiary_id', flat=True)
                )
                linked_to = set(
                    Through.objects.filter(to_stockdiary_id__in=primary_ids)
                    .values_list('from_stockdiary_id', flat=True)
                )
                secondary_ids = (linked_from | linked_to) - primary_ids

            manual_all_ids = primary_ids | secondary_ids

            # secondary 日記（フィルター外だが手動リンクで繋がっている日記）
            if secondary_ids:
                for d in all_user_qs.filter(id__in=secondary_ids).only(
                    'id', 'stock_name', 'stock_symbol', 'sector',
                    'realized_profit', 'current_quantity', 'transaction_count'
                ):
                    if d.id not in diary_nodes_map:
                        diary_nodes_map[d.id] = {
                            'id': d.id,
                            'node_type': 'diary',
                            'stock_name': d.stock_name,
                            'stock_symbol': d.stock_symbol,
                            'status': _diary_status(d),
                            'sector': d.sector or '未分類',
                            'realized_profit': float(d.realized_profit),
                            'link_count': 0,
                            'url': f'/stockdiary/{d.id}/',
                            'is_primary': False,
                        }

            raw_links = Through.objects.filter(
                from_stockdiary_id__in=manual_all_ids,
                to_stockdiary_id__in=manual_all_ids,
            ).values_list('from_stockdiary_id', 'to_stockdiary_id')

            manual_edge_set = set()
            for src, tgt in raw_links:
                manual_edge_set.add((min(src, tgt), max(src, tgt)))

            for s, t in manual_edge_set:
                all_edges.append({'source': s, 'target': t, 'edge_type': 'manual'})

        # ====================================================
        # tag モード: タグハブノード
        # ====================================================
        if 'tag' in edge_modes:
            hub_data = get_tag_graph_data(primary_diaries)
            for hub in hub_data['tag_nodes']:
                hub['link_count'] = hub.get('diary_count', 0)
                hub_nodes_map[hub['id']] = hub
            all_edges.extend(hub_data['edges'])

        # ====================================================
        # sector モード: 業種ハブノード（CompanyMaster で補完）
        # ====================================================
        if 'sector' in edge_modes:
            # sector が空の日記について CompanyMaster から業種を補完
            symbols_without_sector = [
                d.stock_symbol for d in primary_diaries
                if not (d.sector or '').strip() and d.stock_symbol
            ]
            company_sector_map = {}
            if symbols_without_sector:
                from company_master.models import CompanyMaster
                for c in CompanyMaster.objects.filter(
                    code__in=symbols_without_sector
                ).values('code', 'industry_name_33', 'industry_name_17'):
                    company_sector_map[c['code']] = (
                        c['industry_name_33'] or c['industry_name_17'] or ''
                    )

            hub_data = get_sector_graph_data(primary_diaries, company_sector_map)
            for hub in hub_data['sector_nodes']:
                hub['link_count'] = hub.get('diary_count', 0)
                hub_nodes_map[hub['id']] = hub
            all_edges.extend(hub_data['edges'])

        # ====================================================
        # hashtag モード: @ハッシュタグハブノード
        # ====================================================
        if 'hashtag' in edge_modes:
            hub_data = get_hashtag_graph_data(primary_diaries)
            for hub in hub_data['hashtag_nodes']:
                hub['link_count'] = hub.get('diary_count', 0)
                hub_nodes_map[hub['id']] = hub
            all_edges.extend(hub_data['edges'])

        # ====================================================
        # mention モード: テキスト内銘柄コード → diary-diary エッジ
        # ====================================================
        if 'mention' in edge_modes:
            # 全ユーザー日記の stock_symbol → diary_id マップを構築
            symbol_to_diary_id = {}
            for row in all_user_qs.filter(stock_symbol__gt='').values('id', 'stock_symbol'):
                if row['stock_symbol']:
                    symbol_to_diary_id[row['stock_symbol']] = row['id']

            mention_data = get_mention_graph_data(primary_diaries, symbol_to_diary_id)
            all_edges.extend(mention_data['edges'])

            # primary に含まれないメンション先日記をセカンダリノードとして追加
            mention_secondary_ids = mention_data['mentioned_diary_ids'] - set(diary_nodes_map.keys())
            if mention_secondary_ids:
                for d in all_user_qs.filter(id__in=mention_secondary_ids).only(
                    'id', 'stock_name', 'stock_symbol', 'sector',
                    'realized_profit', 'current_quantity', 'transaction_count'
                ):
                    if d.id not in diary_nodes_map:
                        diary_nodes_map[d.id] = {
                            'id': d.id,
                            'node_type': 'diary',
                            'stock_name': d.stock_name,
                            'stock_symbol': d.stock_symbol,
                            'status': _diary_status(d),
                            'sector': d.sector or '未分類',
                            'realized_profit': float(d.realized_profit),
                            'link_count': 0,
                            'url': f'/stockdiary/{d.id}/',
                            'is_primary': False,
                        }

        # ====================================================
        # primary 日記ノードを diary_nodes_map に追加（重複排除）
        # ====================================================
        for d in primary_diaries:
            if d.id not in diary_nodes_map:
                diary_nodes_map[d.id] = {
                    'id': d.id,
                    'node_type': 'diary',
                    'stock_name': d.stock_name,
                    'stock_symbol': d.stock_symbol,
                    'status': _diary_status(d),
                    'sector': d.sector or '未分類',
                    'realized_profit': float(d.realized_profit),
                    'link_count': 0,
                    'url': f'/stockdiary/{d.id}/',
                    'is_primary': True,
                }

        # link_count を全エッジから集計（diary ノードのみ）
        link_count_map = {}
        for e in all_edges:
            for key in ('source', 'target'):
                v = e[key]
                if isinstance(v, int):
                    link_count_map[v] = link_count_map.get(v, 0) + 1

        for diary_id, node in diary_nodes_map.items():
            node['link_count'] = link_count_map.get(diary_id, 0)

        all_nodes = list(diary_nodes_map.values()) + list(hub_nodes_map.values())

        return JsonResponse({
            'nodes': all_nodes,
            'edges': all_edges,
            'meta': {
                'total_nodes': len(all_nodes),
                'total_edges': len(all_edges),
                'modes': edge_modes,
            },
        })

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"diary_graph_data error: {traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _diary_status(diary) -> str:
    """日記オブジェクトから保有ステータス文字列を返す"""
    if diary.current_quantity > 0:
        return 'holding'
    elif diary.transaction_count > 0:
        return 'sold'
    return 'memo'