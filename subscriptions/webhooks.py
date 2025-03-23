# subscriptions/webhooks.py の完全なバージョン
import stripe
import json
import time
import logging
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone

from subscriptions.models import SubscriptionPlan, UserSubscription, StripeCustomer, SubscriptionEvent
from ads.models import UserAdPreference

User = get_user_model()
logger = logging.getLogger(__name__)

# 冪等性のためのイベント処理記録
PROCESSED_EVENTS = set()

@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Stripeからのwebhookイベントを処理するビュー"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        # Stripeのシークレットキーを設定
        stripe.api_key = settings.STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid payload received from Stripe: {str(e)}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid signature received from Stripe: {str(e)}")
        return HttpResponse(status=400)
    
    # 冪等性チェック - 同じイベントIDを重複処理しない
    event_id = event['id']
    if event_id in PROCESSED_EVENTS:
        logger.info(f"Event {event_id} already processed, skipping")
        return HttpResponse(status=200)
    
    # イベントタイプに応じた処理
    try:
        # 処理時間が5秒を超える場合は非同期処理を検討
        handler = EVENT_HANDLERS.get(event['type'])
        if handler:
            handler(event)
            
        # 処理済みイベントを記録（メモリ上限を考慮）
        PROCESSED_EVENTS.add(event_id)
        if len(PROCESSED_EVENTS) > 1000:  # 最大1000件を記憶
            PROCESSED_EVENTS.clear()
            PROCESSED_EVENTS.add(event_id)
    except Exception as e:
        logger.error(f"Error processing webhook event {event_id}: {str(e)}", exc_info=True)
        # 500エラーを返すとStripeが再試行するため、成功レスポンスを返す
        # 実際のエラーはログに記録し、アラート設定で検知する
        return HttpResponse(status=200)
    
    return HttpResponse(status=200)

@transaction.atomic
def handle_checkout_session_completed(event):
    """チェックアウトセッション完了時の処理"""
    session = event['data']['object']
    
    # メタデータからプランIDとユーザーIDを取得
    metadata = session.get('metadata', {})
    plan_id = metadata.get('plan_id')
    user_id = metadata.get('user_id')
    
    if not plan_id or not user_id:
        logger.error("Missing plan_id or user_id in checkout session metadata")
        return
    
    try:
        # ユーザーとプランを取得
        user = User.objects.get(id=user_id)
        plan = SubscriptionPlan.objects.get(id=plan_id)
        
        # サブスクリプションIDを取得
        stripe_subscription_id = session.get('subscription')
        if stripe_subscription_id:
            # Stripeサブスクリプション情報を取得
            stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
            
            # 請求期間情報の保存
            current_period_start = timezone.datetime.fromtimestamp(stripe_subscription.current_period_start, tz=timezone.utc)
            current_period_end = timezone.datetime.fromtimestamp(stripe_subscription.current_period_end, tz=timezone.utc)
            
            # 顧客IDの保存
            customer_id = session.get('customer')
            
            # サブスクリプション情報の取得または作成
            old_plan = None
            if hasattr(user, 'subscription'):
                subscription = user.subscription
                old_plan = subscription.plan
                subscription.plan = plan
                subscription.is_active = True
                subscription.stripe_subscription_id = stripe_subscription_id
                subscription.stripe_customer_id = customer_id
                subscription.current_period_start = current_period_start
                subscription.current_period_end = current_period_end
                subscription.scheduled_downgrade_to = None  # ダウングレード予定をクリア
                subscription.save()
            else:
                subscription = UserSubscription.objects.create(
                    user=user,
                    plan=plan,
                    is_active=True,
                    stripe_subscription_id=stripe_subscription_id,
                    stripe_customer_id=customer_id,
                    current_period_start=current_period_start,
                    current_period_end=current_period_end
                )
            
            # イベント記録
            event_type = 'created' if not old_plan else ('upgraded' if plan.price_monthly > old_plan.price_monthly else 'downgraded' if plan.price_monthly < old_plan.price_monthly else 'updated')
            SubscriptionEvent.objects.create(
                user=user,
                subscription=subscription,
                event_type=event_type,
                from_plan=old_plan,
                to_plan=plan,
                stripe_event_id=event['id'],
                details={
                    'session_id': session.get('id'),
                    'subscription_id': stripe_subscription_id,
                    'amount_total': session.get('amount_total'),
                    'currency': session.get('currency')
                }
            )
            
            # 広告設定も更新
            update_ad_preferences(user, plan)
            
            logger.info(f"User {user.username} subscription updated to {plan.name}")
        
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
    except SubscriptionPlan.DoesNotExist:
        logger.error(f"Plan with ID {plan_id} not found")
    except Exception as e:
        logger.error(f"Error updating subscription: {str(e)}", exc_info=True)
        raise

@transaction.atomic
def handle_subscription_created(event):
    """サブスクリプション作成時の処理"""
    subscription = event['data']['object']
    customer_id = subscription.get('customer')
    
    if not customer_id:
        logger.error("Missing customer ID in subscription data")
        return
    
    try:
        # 顧客IDからユーザーを特定
        stripe_customer = StripeCustomer.objects.filter(stripe_id=customer_id).first()
        if not stripe_customer:
            logger.error(f"No StripeCustomer found with ID {customer_id}")
            return
        
        user = stripe_customer.user
        
        # Stripeサブスクリプション情報を取得
        items = subscription.get('items', {}).get('data', [])
        if not items:
            logger.error("No items found in subscription data")
            return
        
        # プランIDを見つける
        price_id = items[0].get('price', {}).get('id')
        
        # プランを取得
        plan = find_plan_by_stripe_price(price_id)
        if not plan:
            logger.error(f"No matching plan found for Stripe price {price_id}")
            return
        
        # 請求期間情報の保存
        current_period_start = timezone.datetime.fromtimestamp(subscription.get('current_period_start'), tz=timezone.utc)
        current_period_end = timezone.datetime.fromtimestamp(subscription.get('current_period_end'), tz=timezone.utc)
        
        # サブスクリプション情報の取得または作成
        old_plan = None
        if hasattr(user, 'subscription'):
            user_subscription = user.subscription
            old_plan = user_subscription.plan
            user_subscription.plan = plan
            user_subscription.is_active = True
            user_subscription.stripe_subscription_id = subscription.get('id')
            user_subscription.stripe_customer_id = customer_id
            user_subscription.current_period_start = current_period_start
            user_subscription.current_period_end = current_period_end
            user_subscription.scheduled_downgrade_to = None  # ダウングレード予定をクリア
            user_subscription.save()
        else:
            user_subscription = UserSubscription.objects.create(
                user=user,
                plan=plan,
                is_active=True,
                stripe_subscription_id=subscription.get('id'),
                stripe_customer_id=customer_id,
                current_period_start=current_period_start,
                current_period_end=current_period_end
            )
        
        # イベント記録
        event_type = 'created' if not old_plan else ('upgraded' if plan.price_monthly > old_plan.price_monthly else 'downgraded' if plan.price_monthly < old_plan.price_monthly else 'updated')
        SubscriptionEvent.objects.create(
            user=user,
            subscription=user_subscription,
            event_type=event_type,
            from_plan=old_plan,
            to_plan=plan,
            stripe_event_id=event['id'],
            details={
                'subscription_id': subscription.get('id'),
                'status': subscription.get('status'),
                'price_id': price_id
            }
        )
        
        # 広告設定も更新
        update_ad_preferences(user, plan)
        
        logger.info(f"Created subscription for user {user.username} with plan {plan.name}")
    except Exception as e:
        logger.error(f"Error handling subscription creation: {str(e)}", exc_info=True)
        raise

@transaction.atomic
def handle_subscription_updated(event):
    """サブスクリプション更新時の処理"""
    subscription = event['data']['object']
    customer_id = subscription.get('customer')
    
    if not customer_id:
        logger.error("Missing customer ID in subscription data")
        return
    
    try:
        # 顧客IDからユーザーを特定
        stripe_customer = StripeCustomer.objects.filter(stripe_id=customer_id).first()
        if not stripe_customer:
            logger.error(f"No StripeCustomer found with ID {customer_id}")
            return
        
        user = stripe_customer.user
        
        # サブスクリプションのステータスを確認
        status = subscription.get('status')
        subscription_id = subscription.get('id')
        
        # サブスクリプション情報の取得
        try:
            user_subscription = UserSubscription.objects.get(user=user)
        except UserSubscription.DoesNotExist:
            logger.error(f"No UserSubscription found for user {user.username}")
            return
        
        # 請求期間情報の更新
        if 'current_period_start' in subscription:
            user_subscription.current_period_start = timezone.datetime.fromtimestamp(subscription.get('current_period_start'), tz=timezone.utc)
        
        if 'current_period_end' in subscription:
            user_subscription.current_period_end = timezone.datetime.fromtimestamp(subscription.get('current_period_end'), tz=timezone.utc)
        
        if status == 'active':
            # アイテムから価格情報を取得
            items = subscription.get('items', {}).get('data', [])
            if not items:
                logger.error("No items found in subscription data")
                return
            
            price_id = items[0].get('price', {}).get('id')
            
            # プランを取得
            plan = find_plan_by_stripe_price(price_id)
            if not plan:
                logger.error(f"No matching plan found for Stripe price {price_id}")
                return
            
            old_plan = user_subscription.plan
            
            # プランが変更された場合のみ更新
            if plan.id != old_plan.id:
                user_subscription.plan = plan
                user_subscription.scheduled_downgrade_to = None  # ダウングレード予定をクリア
            
            user_subscription.is_active = True
            user_subscription.stripe_subscription_id = subscription_id
            user_subscription.stripe_customer_id = customer_id
            user_subscription.save()
            
            # プランが変更された場合のみイベント記録
            if plan.id != old_plan.id:
                event_type = 'upgraded' if plan.price_monthly > old_plan.price_monthly else 'downgraded' if plan.price_monthly < old_plan.price_monthly else 'updated'
                SubscriptionEvent.objects.create(
                    user=user,
                    subscription=user_subscription,
                    event_type=event_type,
                    from_plan=old_plan,
                    to_plan=plan,
                    stripe_event_id=event['id'],
                    details={
                        'subscription_id': subscription_id,
                        'status': status,
                        'price_id': price_id
                    }
                )
                
                # 広告設定も更新
                update_ad_preferences(user, plan)
                
                logger.info(f"Updated subscription for user {user.username} to plan {plan.name}")
                
        elif status in ['canceled', 'unpaid', 'past_due']:
            # サブスクリプションが終了する場合の処理
            
            # キャンセル日時を更新
            if status == 'canceled' and not user_subscription.canceled_at:
                user_subscription.canceled_at = timezone.now()
            
            # サブスクリプションが終了したときだけステータスを更新
            if status == 'canceled':
                user_subscription.is_active = False
                
                # フリープランに戻す
                try:
                    free_plan = SubscriptionPlan.objects.get(slug='free')
                    old_plan = user_subscription.plan
                    user_subscription.plan = free_plan
                    
                    # イベント記録
                    SubscriptionEvent.objects.create(
                        user=user,
                        subscription=user_subscription,
                        event_type='canceled',
                        from_plan=old_plan,
                        to_plan=free_plan,
                        stripe_event_id=event['id'],
                        details={
                            'subscription_id': subscription_id,
                            'status': status
                        }
                    )
                    
                    # 広告設定も更新
                    update_ad_preferences(user, free_plan)
                except SubscriptionPlan.DoesNotExist:
                    logger.error("Free plan not found")
            
            user_subscription.save()
            logger.info(f"Subscription {status} for user {user.username}")
    except Exception as e:
        logger.error(f"Error handling subscription update: {str(e)}", exc_info=True)
        raise

@transaction.atomic
def handle_subscription_deleted(event):
    """サブスクリプション削除時の処理"""
    subscription = event['data']['object']
    customer_id = subscription.get('customer')
    subscription_id = subscription.get('id')
    
    if not customer_id:
        logger.error("Missing customer ID in subscription data")
        return
    
    try:
        # 顧客IDからユーザーを特定
        stripe_customer = StripeCustomer.objects.filter(stripe_id=customer_id).first()
        if not stripe_customer:
            logger.error(f"No StripeCustomer found with ID {customer_id}")
            return
        
        user = stripe_customer.user
        
        # サブスクリプション情報の取得
        try:
            user_subscription = UserSubscription.objects.get(user=user)
        except UserSubscription.DoesNotExist:
            logger.error(f"No UserSubscription found for user {user.username}")
            return
        
        # このSubscriptionIDが一致するか確認
        if user_subscription.stripe_subscription_id != subscription_id:
            logger.warning(f"Subscription ID mismatch: {user_subscription.stripe_subscription_id} vs {subscription_id}")
            return
        
        # フリープランに戻す
        try:
            free_plan = SubscriptionPlan.objects.get(slug='free')
            old_plan = user_subscription.plan
            user_subscription.plan = free_plan
            user_subscription.is_active = True
            user_subscription.stripe_subscription_id = None
            user_subscription.canceled_at = timezone.now()
            user_subscription.scheduled_downgrade_to = None
            user_subscription.save()
            
            # イベント記録
            SubscriptionEvent.objects.create(
                user=user,
                subscription=user_subscription,
                event_type='canceled',
                from_plan=old_plan,
                to_plan=free_plan,
                stripe_event_id=event['id'],
                details={
                    'subscription_id': subscription_id,
                    'status': 'deleted'
                }
            )
            
            # 広告設定も更新
            update_ad_preferences(user, free_plan)
            
            logger.info(f"Subscription deleted for user {user.username}, reverted to free plan")
        except SubscriptionPlan.DoesNotExist:
            logger.error("Free plan not found")
    except Exception as e:
        logger.error(f"Error handling subscription deletion: {str(e)}", exc_info=True)
        raise

@transaction.atomic
def handle_payment_succeeded(event):
    """請求書支払い成功時の処理"""
    invoice = event['data']['object']
    customer_id = invoice.get('customer')
    subscription_id = invoice.get('subscription')
    
    if not customer_id or not subscription_id:
        logger.error("Missing customer ID or subscription ID in invoice data")
        return
    
    try:
        # 顧客IDからユーザーを特定
        stripe_customer = StripeCustomer.objects.filter(stripe_id=customer_id).first()
        if not stripe_customer:
            logger.error(f"No StripeCustomer found with ID {customer_id}")
            return
        
        user = stripe_customer.user
        
        # サブスクリプション情報の取得
        try:
            user_subscription = UserSubscription.objects.get(user=user)
        except UserSubscription.DoesNotExist:
            logger.error(f"No UserSubscription found for user {user.username}")
            return
        
        # イベント記録
        SubscriptionEvent.objects.create(
            user=user,
            subscription=user_subscription,
            event_type='payment_succeeded',
            from_plan=user_subscription.plan,
            to_plan=user_subscription.plan,
            stripe_event_id=event['id'],
            details={
                'invoice_id': invoice.get('id'),
                'amount_paid': invoice.get('amount_paid'),
                'currency': invoice.get('currency'),
                'subscription_id': subscription_id
            }
        )
        
        logger.info(f"Payment succeeded for user {user.username}, subscription {subscription_id}")
        
        # 次の期間への更新時にダウングレード予定があれば適用する
        if user_subscription.scheduled_downgrade_to and invoice.get('billing_reason') == 'subscription_cycle':
            # ダウングレードの適用
            old_plan = user_subscription.plan
            new_plan = user_subscription.scheduled_downgrade_to
            
            user_subscription.plan = new_plan
            user_subscription.scheduled_downgrade_to = None
            user_subscription.save()
            
            # イベント記録
            SubscriptionEvent.objects.create(
                user=user,
                subscription=user_subscription,
                event_type='downgraded',
                from_plan=old_plan,
                to_plan=new_plan,
                stripe_event_id=event['id'],
                details={
                    'invoice_id': invoice.get('id'),
                    'billing_reason': invoice.get('billing_reason'),
                    'subscription_id': subscription_id
                }
            )
            
            # 広告設定も更新
            update_ad_preferences(user, new_plan)
            
            logger.info(f"Applied scheduled downgrade for user {user.username} from {old_plan.name} to {new_plan.name}")
            
    except Exception as e:
        logger.error(f"Error handling payment success: {str(e)}", exc_info=True)
        raise

@transaction.atomic
def handle_payment_failed(event):
    """請求書支払い失敗時の処理"""
    invoice = event['data']['object']
    customer_id = invoice.get('customer')
    subscription_id = invoice.get('subscription')
    
    if not customer_id or not subscription_id:
        logger.error("Missing customer ID or subscription ID in invoice data")
        return
    
    try:
        # 顧客IDからユーザーを特定
        stripe_customer = StripeCustomer.objects.filter(stripe_id=customer_id).first()
        if not stripe_customer:
            logger.error(f"No StripeCustomer found with ID {customer_id}")
            return
        
        user = stripe_customer.user
        
        # サブスクリプション情報の取得
        try:
            user_subscription = UserSubscription.objects.get(user=user)
        except UserSubscription.DoesNotExist:
            logger.error(f"No UserSubscription found for user {user.username}")
            return
        
        # イベント記録
        SubscriptionEvent.objects.create(
            user=user,
            subscription=user_subscription,
            event_type='payment_failed',
            from_plan=user_subscription.plan,
            to_plan=user_subscription.plan,
            stripe_event_id=event['id'],
            details={
                'invoice_id': invoice.get('id'),
                'amount_due': invoice.get('amount_due'),
                'currency': invoice.get('currency'),
                'subscription_id': subscription_id,
                'attempt_count': invoice.get('attempt_count')
            }
        )
        
        logger.warning(f"Payment failed for user {user.username}, subscription {subscription_id}, attempt {invoice.get('attempt_count')}")
        
    except Exception as e:
        logger.error(f"Error handling payment failure: {str(e)}", exc_info=True)
        raise


def find_plan_by_stripe_price(price_id):
    """Stripeの価格IDからプランを検索する"""
    # まずstripe_price_idで直接検索
    try:
        return SubscriptionPlan.objects.get(stripe_price_id=price_id)
    except SubscriptionPlan.DoesNotExist:
        pass
    
    # 見つからない場合はStripe APIで価格情報を取得
    try:
        price = stripe.Price.retrieve(price_id)
        product = stripe.Product.retrieve(price.product)
        
        # 製品名や金額からプランを特定
        product_name = product.get('name', '').lower()
        amount = price.get('unit_amount', 0)
        
        # プラン名でマッチを試みる
        for keyword, slug in [('pro', 'pro'), ('basic', 'basic'), ('free', 'free')]:
            if keyword in product_name:
                try:
                    return SubscriptionPlan.objects.get(slug=slug)
                except SubscriptionPlan.DoesNotExist:
                    continue
        
        # 金額でマッチを試みる
        try:
            return SubscriptionPlan.objects.get(price_monthly=amount/100)
        except SubscriptionPlan.DoesNotExist:
            pass
        
        # デフォルトはベーシックプラン
        try:
            return SubscriptionPlan.objects.get(slug='basic')
        except SubscriptionPlan.DoesNotExist:
            # 最後の手段としてフリープラン
            return SubscriptionPlan.objects.get(slug='free')
    except Exception as e:
        logger.error(f"Error finding plan from Stripe price {price_id}: {str(e)}")
        return None


def update_ad_preferences(user, plan):
    """ユーザーの広告設定をプランに合わせて更新する"""
    try:
        ad_preference, created = UserAdPreference.objects.get_or_create(
            user=user,
            defaults={
                'show_ads': plan.show_ads,
                'is_premium': not plan.show_ads,
                'allow_personalized_ads': plan.show_ads
            }
        )
        
        if not created:
            ad_preference.show_ads = plan.show_ads
            ad_preference.is_premium = not plan.show_ads
            ad_preference.allow_personalized_ads = plan.show_ads
            ad_preference.save()
        
        logger.info(f"Updated ad preferences for user {user.username}: show_ads={plan.show_ads}")
    except Exception as e:
        logger.error(f"Error updating ad preferences: {str(e)}", exc_info=True)


# イベントタイプとハンドラーの対応表
EVENT_HANDLERS = {
    'checkout.session.completed': handle_checkout_session_completed,
    'customer.subscription.created': handle_subscription_created,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
    'invoice.payment_succeeded': handle_payment_succeeded,
    'invoice.payment_failed': handle_payment_failed,
}