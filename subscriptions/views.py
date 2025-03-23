# subscriptions/views.py
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from .models import UserSubscription, SubscriptionPlan, SubscriptionEvent
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import stripe
from django.conf import settings
from django.utils import timezone

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse

# subscriptions/views.py のUpgradeViewを修正

class UpgradeView(LoginRequiredMixin, ListView):
    """プランアップグレード画面"""
    template_name = 'subscriptions/upgrade.html'
    model = SubscriptionPlan
    context_object_name = 'plans'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # 各プランのIDをデバッグ出力
            all_plans = list(context['plans'])
            for plan in all_plans:
                print(f"Plan: {plan.slug}, ID: {plan.id}, Name: {plan.name}")
            
            # フリープラン、ベーシックプラン、プロプランのIDを設定
            free_plan = None
            basic_plan = None
            pro_plan = None
            
            for plan in all_plans:
                if plan.slug == 'free':
                    free_plan = plan
                elif plan.slug == 'basic':
                    basic_plan = plan
                elif plan.slug == 'pro':
                    pro_plan = plan
            
            context['free_plan'] = free_plan
            context['basic_plan'] = basic_plan
            context['pro_plan'] = pro_plan
            
            # 現在のプラン
            context['current_plan'] = self.request.user.subscription.plan
        except Exception as e:
            print(f"Error in UpgradeView: {str(e)}")
            # サブスクリプションが存在しない場合はフリープランを探す
            try:
                context['current_plan'] = SubscriptionPlan.objects.get(slug='free')
            except SubscriptionPlan.DoesNotExist:
                context['current_plan'] = None
        
        return context


class CheckoutView(LoginRequiredMixin, TemplateView):
    """決済処理画面（セキュリティ強化版）"""
    
    def get_template_names(self):
        """確認済みかどうかでテンプレートを切り替え"""
        confirmed = self.request.GET.get('confirmed', 'false') == 'true'
        return 'subscriptions/checkout.html' if confirmed else 'subscriptions/checkout_confirm.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan_id = self.kwargs.get('plan_id')
        billing_type = self.kwargs.get('type', 'monthly')
        
        # プランIDが存在しない場合のエラーハンドリング
        if plan_id is None:
            context['error'] = "プランIDが指定されていません。"
            return context
        
        try:
            # プランIDでの取得を試みる
            plan = SubscriptionPlan.objects.get(id=plan_id)
            context['plan'] = plan
            context['billing_type'] = billing_type
            
            # Stripe公開キーを設定
            context['stripe_public_key'] = settings.STRIPE_PUBLISHABLE_KEY
            
            # 現在のプランと比較してダウングレードかどうかを判定
            is_downgrade = False
            try:
                current_plan = self.request.user.subscription.plan
                if current_plan.id != plan.id:
                    if (
                        (current_plan.slug == 'pro' and plan.slug in ['basic', 'free']) or
                        (current_plan.slug == 'basic' and plan.slug == 'free')
                    ):
                        is_downgrade = True
            except Exception:
                pass
            
            context['is_downgrade'] = is_downgrade
            context['confirmed'] = self.request.GET.get('confirmed', 'false') == 'true'
            
        except SubscriptionPlan.DoesNotExist:
            # プランが見つからない場合のエラーメッセージ
            context['error'] = "指定されたプランが見つかりません。"
        except Exception as e:
            # その他のエラー
            context['error'] = "エラーが発生しました。しばらく経ってからもう一度お試しください。"
            # ログにはエラー詳細を記録（本番環境ではユーザーには表示しない）
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in CheckoutView: {str(e)}")
        
        return context
    
    def post(self, request, *args, **kwargs):
        """プラン変更処理（Stripe連携版）"""
        plan_id = self.kwargs.get('plan_id')
        
        # プランIDが存在しない場合のエラーハンドリング
        if plan_id is None:
            messages.error(request, "プランIDが指定されていません。")
            return redirect('subscriptions:upgrade')
            
        confirmed = request.POST.get('confirmed', 'false') == 'true'
        payment_method_id = request.POST.get('payment_method_id')
        
        # 確認していない場合は確認画面にリダイレクト
        if not confirmed:
            return redirect(reverse('subscriptions:checkout', kwargs=self.kwargs) + '?confirmed=true')
        
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
            
            # フリープランの場合はStripeを使わず直接更新
            if plan.slug == 'free':
                return self._handle_free_plan_change(request, plan)
            
            # 有料プランの場合のStripe処理
            # Stripe APIキーを設定
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # テストモードの場合、実際のStripe処理をスキップ
            if getattr(settings, 'STRIPE_TEST_MODE', True):
                # テストモードでは直接ユーザーのサブスクリプションを更新
                return self._handle_test_mode_change(request, plan)
            
            # 本番モードの場合のStripe処理
            if not payment_method_id:
                messages.error(request, "支払い情報が不足しています。もう一度お試しください。")
                return redirect('subscriptions:checkout', plan_id=plan_id, type=self.kwargs.get('type', 'monthly'))
            
            # 既存のStripeカスタマーかどうかを確認
            customer = None
            try:
                # この部分は実際のデータモデルに合わせて調整する必要があります
                from .models import StripeCustomer
                stripe_customer = StripeCustomer.objects.get(user=request.user)
                customer = stripe_customer.stripe_id
            except:
                # 新規カスタマーの場合は作成
                stripe_customer = stripe.Customer.create(
                    email=request.user.email,
                    payment_method=payment_method_id,
                    invoice_settings={
                        'default_payment_method': payment_method_id,
                    }
                )
                customer = stripe_customer.id
                
                # カスタマーIDをデータベースに保存
                from .models import StripeCustomer
                StripeCustomer.objects.create(
                    user=request.user,
                    stripe_id=customer
                )
            
            # サブスクリプションを作成または更新
            # 既存のサブスクリプションIDがあれば更新、なければ新規作成
            stripe_subscription_id = None
            try:
                # ユーザーの現在のサブスクリプション情報を取得
                user_subscription = UserSubscription.objects.get(user=request.user)
                stripe_subscription_id = getattr(user_subscription, 'stripe_subscription_id', None)
            except UserSubscription.DoesNotExist:
                pass
                
            if stripe_subscription_id:
                # 既存のサブスクリプションを更新
                subscription = stripe.Subscription.modify(
                    stripe_subscription_id,
                    # プランに基づいて価格を指定
                    items=[{
                        'price': self._get_stripe_price_id(plan, self.kwargs.get('type', 'monthly')),
                    }],
                    expand=['latest_invoice.payment_intent']
                )
            else:
                # 新規サブスクリプションを作成
                subscription = stripe.Subscription.create(
                    customer=customer,
                    items=[{
                        'price': self._get_stripe_price_id(plan, self.kwargs.get('type', 'monthly')),
                    }],
                    expand=['latest_invoice.payment_intent'],
                )
            
            # サブスクリプションステータスを確認
            status = subscription.status
            if status == 'active' or status == 'trialing':
                # 成功: ユーザーのサブスクリプションを更新
                user_subscription, created = UserSubscription.objects.get_or_create(
                    user=request.user,
                    defaults={'plan': plan, 'is_active': True}
                )
                
                if not created:
                    user_subscription.plan = plan
                    user_subscription.is_active = True
                    
                # Stripe情報を保存
                user_subscription.stripe_subscription_id = subscription.id
                user_subscription.save()
                
                # 広告設定も更新
                self._update_ad_preferences(request.user, plan)
                
                messages.success(request, f"{plan.name}に切り替えました")
                return redirect('subscriptions:success')
            else:
                # 支払いが必要な場合は、クライアントシークレットを取得して確認ページに戻す
                client_secret = subscription.latest_invoice.payment_intent.client_secret
                return redirect(f"{reverse('subscriptions:checkout', kwargs=self.kwargs)}?confirmed=true&client_secret={client_secret}")
                
        except SubscriptionPlan.DoesNotExist:
            messages.error(request, "指定されたプランが見つかりません")
            return redirect('subscriptions:upgrade')
        except stripe.error.CardError as e:
            # カードエラーの場合
            error_message = e.user_message or "カード情報に問題があります。別のカードをお試しください。"
            messages.error(request, error_message)
            return redirect('subscriptions:checkout', plan_id=plan_id, type=self.kwargs.get('type', 'monthly'))
        except stripe.error.StripeError as e:
            # その他のStripeエラー
            messages.error(request, "決済処理中にエラーが発生しました。しばらく経ってからもう一度お試しください。")
            # ログにはエラー詳細を記録
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Stripe error: {str(e)}")
            return redirect('subscriptions:checkout', plan_id=plan_id, type=self.kwargs.get('type', 'monthly'))
        except Exception as e:
            # その他の予期しないエラー
            messages.error(request, "エラーが発生しました。しばらく経ってからもう一度お試しください。")
            # ログにはエラー詳細を記録
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error in checkout: {str(e)}")
            return redirect('subscriptions:upgrade')
    
    def _handle_free_plan_change(self, request, plan):
        """フリープランへの変更処理"""
        # ユーザーのサブスクリプションを更新
        subscription, created = UserSubscription.objects.get_or_create(
            user=request.user,
            defaults={'plan': plan}
        )
        
        if not created:
            subscription.plan = plan
            subscription.save()
            
            # Stripeサブスクリプションがある場合はキャンセル
            stripe_subscription_id = getattr(subscription, 'stripe_subscription_id', None)
            if stripe_subscription_id:
                try:
                    stripe.api_key = settings.STRIPE_SECRET_KEY
                    stripe.Subscription.delete(stripe_subscription_id)
                    subscription.stripe_subscription_id = None
                    subscription.save()
                except Exception as e:
                    # エラーはログに記録するが、ユーザーフローは中断しない
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error canceling Stripe subscription: {str(e)}")
        
        # 広告設定を更新
        self._update_ad_preferences(request.user, plan)
        
        messages.success(request, f"{plan.name}に切り替えました")
        return redirect('subscriptions:success')
    
    def _handle_test_mode_change(self, request, plan):
        """テストモードでのプラン変更処理"""
        # ユーザーのサブスクリプションを更新
        subscription, created = UserSubscription.objects.get_or_create(
            user=request.user,
            defaults={'plan': plan, 'is_active': True}
        )
        
        if not created:
            subscription.plan = plan
            subscription.is_active = True
            subscription.save()
        
        # 広告設定も更新
        self._update_ad_preferences(request.user, plan)
        
        messages.success(request, f"{plan.name}に切り替えました（テストモード）")
        return redirect('subscriptions:success')
    
    def _update_ad_preferences(self, user, plan):
        """プラン変更に伴う広告設定の更新"""
        try:
            from ads.models import UserAdPreference
            ad_preference, _ = UserAdPreference.objects.get_or_create(
                user=user
            )
            
            # 広告表示設定をプランに応じて更新
            ad_preference.show_ads = plan.show_ads
            ad_preference.is_premium = not plan.show_ads
            
            # 有料プランならパーソナライズ広告を無効化
            if not plan.show_ads:
                ad_preference.allow_personalized_ads = False
            else:
                # フリープランの場合、パーソナライズ広告を有効化
                ad_preference.allow_personalized_ads = True
                
            ad_preference.save()
            return True
        except Exception as e:
            # エラーはログに記録するが、ユーザーフローは中断しない
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating ad preferences: {str(e)}")
            return False
    
    def _get_stripe_price_id(self, plan, billing_type):
        """プランと課金タイプに基づいてStripeの価格IDを取得"""
        # 実際の実装ではデータベースから価格IDを取得するか、
        # プラン設定から取得する必要があります
        # ここでは簡略化のため、ダミーの価格IDマッピングを使用
        price_mapping = {
            'basic': {
                'monthly': 'price_basic_monthly',
                'yearly': 'price_basic_yearly',
            },
            'pro': {
                'monthly': 'price_pro_monthly',
                'yearly': 'price_pro_yearly',
            },
        }
        
        # プランスラグに基づいて価格IDを取得
        return price_mapping.get(plan.slug, {}).get(billing_type, 'price_default')
        
class SubscriptionSuccessView(LoginRequiredMixin, TemplateView):
    """サブスクリプション成功画面（テスト用簡素化+Stripe準備）"""
    template_name = 'subscriptions/success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            subscription = self.request.user.subscription
            context['subscription'] = subscription
            context['plan'] = subscription.plan
        except:
            pass
            
        return context
    
    # Stripe準備（コメントアウトしておく）
    """
    def get(self, request, *args, **kwargs):
        session_id = request.GET.get('session_id')
        
        if session_id:
            try:
                # セッション情報を取得
                stripe.api_key = settings.STRIPE_SECRET_KEY
                checkout_session = stripe.checkout.Session.retrieve(session_id)
                
                # サブスクリプション情報を取得
                subscription = stripe.Subscription.retrieve(checkout_session.subscription)
                
                # メタデータから情報を取得
                plan_id = checkout_session.metadata.get('plan_id')
                
                if plan_id:
                    plan = SubscriptionPlan.objects.get(id=plan_id)
                    
                    # ユーザーのサブスクリプションを更新
                    user_subscription, created = UserSubscription.objects.get_or_create(
                        user=request.user,
                        defaults={
                            'plan': plan,
                            'is_active': True
                        }
                    )
                    
                    if not created:
                        user_subscription.plan = plan
                        user_subscription.is_active = True
                        # 有効期限を設定（オプション）
                        # user_subscription.end_date = ...
                        user_subscription.save()
                    
                    # Stripe情報を保存（オプション）
                    # user.stripe_subscription_id = subscription.id
                    # user.save()
                    
                    messages.success(request, f"{plan.name}プランへのアップグレードが完了しました")
                
            except Exception as e:
                messages.error(request, f"処理中にエラーが発生しました: {str(e)}")
        
        return super().get(request, *args, **kwargs)
    """
# subscriptions/views.py のDowngradeViewを修正



class DowngradeView(LoginRequiredMixin, TemplateView):
    """ダウングレード処理（確認付き）- 次の請求日まで現在のプランを維持"""
    template_name = 'subscriptions/downgrade.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 現在のサブスクリプション情報を取得
        user = self.request.user
        try:
            subscription = user.subscription
            context['subscription'] = subscription
            context['current_plan'] = subscription.plan
            
            # 現在のプランがフリープランの場合はダウングレードできない
            if subscription.plan.slug == 'free':
                context['error'] = 'すでにフリープランのため、ダウングレードできません。'
            
            # 予定されたダウングレードがある場合
            if subscription.scheduled_downgrade_to:
                free_plan = SubscriptionPlan.objects.get(slug='free')
                context['scheduled_downgrade'] = True
                context['target_plan'] = free_plan
                context['downgrade_date'] = subscription.current_period_end
                
            # 処理中かどうか
            context['processing'] = self.request.GET.get('processing', 'false') == 'true'
            
            # ダウングレード後のプラン（フリープラン）
            try:
                context['free_plan'] = SubscriptionPlan.objects.get(slug='free')
            except SubscriptionPlan.DoesNotExist:
                context['error'] = 'フリープランが見つかりません。'
                
        except Exception as e:
            context['error'] = f'エラーが発生しました: {str(e)}'
        
        return context
    
    def post(self, request, *args, **kwargs):
        """ダウングレード処理 - 次の請求日に適用"""
        try:
            user = request.user
            subscription = user.subscription
            
            # 現在のプランがフリープランの場合はダウングレードできない
            if subscription.plan.slug == 'free':
                messages.error(request, 'すでにフリープランのため、ダウングレードできません。')
                return redirect('subscriptions:upgrade')
            
            # フリープランを取得
            try:
                free_plan = SubscriptionPlan.objects.get(slug='free')
            except SubscriptionPlan.DoesNotExist:
                messages.error(request, 'フリープランが見つかりません。')
                return redirect('subscriptions:upgrade')
            
            # Stripeサブスクリプションがある場合
            if subscription.stripe_subscription_id:
                try:
                    stripe.api_key = settings.STRIPE_SECRET_KEY
                    
                    # Stripeサブスクリプションを次の請求日にキャンセルするよう設定
                    stripe_sub = stripe.Subscription.modify(
                        subscription.stripe_subscription_id,
                        cancel_at_period_end=True
                    )
                    
                    # 次の請求日のタイムスタンプを取得
                    current_period_end = stripe_sub.current_period_end
                    end_date = timezone.datetime.fromtimestamp(current_period_end, tz=timezone.utc)
                    
                    # 次の請求日にダウングレードするようスケジュール
                    subscription.scheduled_downgrade_to = free_plan
                    subscription.current_period_end = end_date
                    subscription.save()
                    
                    # イベント記録
                    SubscriptionEvent.objects.create(
                        user=user,
                        subscription=subscription,
                        event_type='downgraded',
                        from_plan=subscription.plan,
                        to_plan=free_plan,
                        details={
                            'scheduled': True,
                            'effective_date': end_date.isoformat()
                        }
                    )
                    
                    messages.success(request, f'{end_date.strftime("%Y年%m月%d日")}の請求日以降にフリープランに変更されます。それまでは現在のプランをご利用いただけます。')
                    
                except Exception as e:
                    messages.error(request, f'Stripeの処理中にエラーが発生しました: {str(e)}')
                    return redirect('subscriptions:upgrade')
            else:
                # Stripeサブスクリプションがない場合は即時ダウングレード
                old_plan = subscription.plan
                subscription.plan = free_plan
                subscription.scheduled_downgrade_to = None
                subscription.save()
                
                # 広告設定も更新
                from ads.models import UserAdPreference
                ad_preference, _ = UserAdPreference.objects.get_or_create(
                    user=user,
                    defaults={
                        'show_ads': free_plan.show_ads,
                        'is_premium': not free_plan.show_ads,
                        'allow_personalized_ads': free_plan.show_ads
                    }
                )
                ad_preference.show_ads = free_plan.show_ads
                ad_preference.is_premium = not free_plan.show_ads
                ad_preference.allow_personalized_ads = free_plan.show_ads
                ad_preference.save()
                
                # イベント記録
                SubscriptionEvent.objects.create(
                    user=user,
                    subscription=subscription,
                    event_type='downgraded',
                    from_plan=old_plan,
                    to_plan=free_plan,
                    details={
                        'scheduled': False,
                        'immediate': True
                    }
                )
                
                messages.success(request, 'プランをフリープランに変更しました')
            
            # 処理中画面を表示してからリダイレクト
            return redirect(reverse('subscriptions:downgrade') + '?processing=true')
            
        except Exception as e:
            messages.error(request, f'エラーが発生しました: {str(e)}')
            return redirect('subscriptions:upgrade')

class CancelScheduledDowngradeView(LoginRequiredMixin, View):
    """予定されたダウングレードをキャンセルする"""
    
    def post(self, request, *args, **kwargs):
        try:
            user = request.user
            subscription = user.subscription
            
            # 予定されたダウングレードがない場合
            if not subscription.scheduled_downgrade_to:
                messages.error(request, '予定されたダウングレードはありません。')
                return redirect('subscriptions:upgrade')
            
            # Stripeサブスクリプションがある場合
            if subscription.stripe_subscription_id:
                try:
                    stripe.api_key = settings.STRIPE_SECRET_KEY
                    
                    # 自動更新を再開
                    stripe_sub = stripe.Subscription.modify(
                        subscription.stripe_subscription_id,
                        cancel_at_period_end=False
                    )
                    
                    # ダウングレード予定をクリア
                    subscription.scheduled_downgrade_to = None
                    subscription.save()
                    
                    messages.success(request, 'ダウングレードがキャンセルされました。現在のプランが継続されます。')
                    
                except Exception as e:
                    messages.error(request, f'Stripeの処理中にエラーが発生しました: {str(e)}')
            else:
                # ダウングレード予定をクリア
                subscription.scheduled_downgrade_to = None
                subscription.save()
                
                messages.success(request, 'ダウングレードがキャンセルされました。現在のプランが継続されます。')
            
            return redirect('subscriptions:upgrade')
            
        except Exception as e:
            messages.error(request, f'エラーが発生しました: {str(e)}')
            return redirect('subscriptions:upgrade')

# Stripeの準備ができたらコメントを外す
"""
@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    # "Stripeからのwebhookを処理するビュー"
    
    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            # Invalid payload
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            # Invalid signature
            return HttpResponse(status=400)
        
        # イベントタイプに応じた処理
        if event['type'] == 'customer.subscription.updated':
            self.handle_subscription_updated(event)
        elif event['type'] == 'customer.subscription.deleted':
            self.handle_subscription_deleted(event)
        elif event['type'] == 'invoice.payment_succeeded':
            self.handle_payment_succeeded(event)
        elif event['type'] == 'invoice.payment_failed':
            self.handle_payment_failed(event)
        
        return HttpResponse(status=200)
    
    def handle_subscription_updated(self, event):
        # サブスクリプション更新イベントの処理"
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        # 顧客IDに紐づくユーザーを特定
        try:
            # 実装例
            # user = StripeCustomer.objects.get(stripe_id=customer_id).user
            pass
        except Exception as e:
            print(f"Error handling subscription update: {str(e)}")
    
    def handle_subscription_deleted(self, event):
        # "サブスクリプション削除イベントの処理"
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        try:
            # 実装例
            # user = StripeCustomer.objects.get(stripe_id=customer_id).user
            pass
        except Exception as e:
            print(f"Error handling subscription deletion: {str(e)}")
    
    def handle_payment_succeeded(self, event):
        # "支払い成功イベントの処理"
        invoice = event['data']['object']
        customer_id = invoice['customer']
        
        try:
            # 実装例
            pass
        except Exception as e:
            print(f"Error handling payment success: {str(e)}")
    
    def handle_payment_failed(self, event):
        # 支払い失敗イベントの処理"
        invoice = event['data']['object']
        customer_id = invoice['customer']
        
        try:
            # 実装例
            pass
        except Exception as e:
            print(f"Error handling payment failure: {str(e)}")
"""
class SubscriptionUsageView(LoginRequiredMixin, TemplateView):
    """サブスクリプション使用状況の詳細ビュー"""
    template_name = 'subscriptions/usage.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            subscription = self.request.user.subscription
            plan = subscription.plan
            
            context['subscription'] = subscription
            context['plan'] = plan
            
            # リソース使用状況を取得
            user = self.request.user
            
            # タグデータ
            tags = user.tag_set.all()
            tag_count = tags.count()
            tag_limit = plan.max_tags
            tag_percent = int(tag_count / tag_limit * 100) if tag_limit > 0 else 0
            
            # テンプレートデータ
            templates = user.analysistemplate_set.all()
            template_count = templates.count()
            template_limit = plan.max_templates
            template_percent = int(template_count / template_limit * 100) if template_limit > 0 else 0
            
            # スナップショットデータ
            snapshots = user.portfoliosnapshot_set.all()
            snapshot_count = snapshots.count()
            snapshot_limit = plan.max_snapshots
            snapshot_percent = int(snapshot_count / snapshot_limit * 100) if snapshot_limit > 0 else 0
            
            # 株式記録データ
            records = user.stockdiary_set.all()
            record_count = records.count()
            record_limit = plan.max_records
            record_percent = int(record_count / record_limit * 100) if record_limit > 0 else 0
            
            # コンテキストに追加
            context.update({
                'resources': {
                    'tags': {
                        'items': tags,
                        'count': tag_count,
                        'limit': tag_limit,
                        'percent': tag_percent,
                        'name': 'タグ',
                        'status': 'danger' if tag_percent > 90 else 'warning' if tag_percent > 70 else 'success',
                    },
                    'templates': {
                        'items': templates,
                        'count': template_count,
                        'limit': template_limit,
                        'percent': template_percent,
                        'name': '分析テンプレート',
                        'status': 'danger' if template_percent > 90 else 'warning' if template_percent > 70 else 'success',
                    },
                    'snapshots': {
                        'items': snapshots,
                        'count': snapshot_count,
                        'limit': snapshot_limit,
                        'percent': snapshot_percent,
                        'name': 'スナップショット',
                        'status': 'danger' if snapshot_percent > 90 else 'warning' if snapshot_percent > 70 else 'success',
                    },
                    'records': {
                        'items': records,
                        'count': record_count,
                        'limit': record_limit,
                        'percent': record_percent,
                        'name': '株式記録',
                        'status': 'danger' if record_percent > 90 else 'warning' if record_percent > 70 else 'success',
                    }
                }
            })
            
        except Exception as e:
            # エラーが発生した場合はエラーメッセージをコンテキストに追加
            context['error'] = f"使用状況データの取得中にエラーが発生しました: {str(e)}"
            
        return context

class PlanView(LoginRequiredMixin, ListView):
    """プラン一覧表示画面 - UpgradeViewと同じテンプレートを使用"""
    template_name = 'subscriptions/upgrade.html'
    model = SubscriptionPlan
    context_object_name = 'plans'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['current_plan'] = self.request.user.subscription.plan
        except:
            # サブスクリプションが存在しない場合はフリープランを探す
            try:
                context['current_plan'] = SubscriptionPlan.objects.get(slug='free')
            except:
                context['current_plan'] = None
        return context        



# Stripeテスト用のビューを追加
class StripeTestView(LoginRequiredMixin, TemplateView):
    """Stripe決済テスト用のビュー"""
    template_name = 'subscriptions/stripe_test.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Stripe公開キーを設定（settingsから取得）
        context['stripe_public_key'] = settings.STRIPE_PUBLIC_KEY
        # 現在のサブスクリプション情報を取得
        try:
            subscription = self.request.user.subscription
            context['current_subscription'] = subscription
            context['current_plan'] = subscription.plan
        except Exception as e:
            context['error'] = str(e)
        
        # 利用可能なプランを取得
        context['plans'] = SubscriptionPlan.objects.all().order_by('price_monthly')
        
        return context

# 決済セッション作成用のビュー
class CreateCheckoutSessionView(LoginRequiredMixin, View):
    """Stripe Checkout Session作成ビュー"""
    
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        plan_id = data.get('plan_id')
        
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
            
            # Stripeシークレットキーを設定
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Stripe顧客IDを取得または作成
            customer_id = None
            try:
                # ユーザーにStripe顧客IDがあるか確認
                from .models import StripeCustomer
                stripe_customer = StripeCustomer.objects.get(user=request.user)
                customer_id = stripe_customer.stripe_id
            except:
                # Stripe顧客を新規作成
                customer = stripe.Customer.create(
                    email=request.user.email,
                    name=request.user.username,
                    metadata={
                        'user_id': request.user.id
                    }
                )
                customer_id = customer.id
                
                # DBに保存
                from .models import StripeCustomer
                StripeCustomer.objects.create(
                    user=request.user,
                    stripe_id=customer_id
                )
            
            # 決済セッションを作成
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'jpy',
                            'product_data': {
                                'name': plan.name,
                                'description': f'カブログの{plan.name}サブスクリプション',
                            },
                            'unit_amount': int(plan.price_monthly),
                            'recurring': {
                                'interval': 'month',
                            }
                        },
                        'quantity': 1,
                    },
                ],
                mode='subscription',
                success_url=request.build_absolute_uri(reverse('subscriptions:success')) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.build_absolute_uri(reverse('subscriptions:upgrade')),
                metadata={
                    'plan_id': plan.id,
                    'user_id': request.user.id,
                }
            )
            
            return JsonResponse({
                'id': checkout_session.id
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)


def plan_redirect_view(request, slug):
    """指定されたスラグのプランにリダイレクトするビュー"""
    plan = get_object_or_404(SubscriptionPlan, slug=slug)
    return redirect('subscriptions:checkout', plan_id=plan.id, type='monthly')            


@staff_member_required
def admin_cancel_subscription(request, id):
    """管理者がサブスクリプションをキャンセルする"""
    subscription = get_object_or_404(UserSubscription, id=id)
    
    if request.method == 'POST':
        # Stripe連携がある場合はStripeでもキャンセル
        if subscription.stripe_subscription_id:
            try:
                import stripe
                from django.conf import settings
                stripe.api_key = settings.STRIPE_SECRET_KEY
                
                # 次の請求日にキャンセルするよう設定
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                
                # フリープランをスケジュール
                try:
                    free_plan = SubscriptionPlan.objects.get(slug='free')
                    
                    # 現在のプランを保存
                    old_plan = subscription.plan
                    
                    # ダウングレードをスケジュール
                    subscription.scheduled_downgrade_to = free_plan
                    subscription.canceled_at = timezone.now()
                    subscription.save()
                    
                    # イベント記録
                    SubscriptionEvent.objects.create(
                        user=subscription.user,
                        subscription=subscription,
                        event_type='canceled',
                        from_plan=old_plan,
                        to_plan=free_plan,
                        details={
                            'canceled_by': 'admin',
                            'admin_username': request.user.username,
                            'scheduled': True
                        }
                    )
                    
                    messages.success(request, f'サブスクリプションを次の請求日({subscription.current_period_end.strftime("%Y-%m-%d")})にキャンセルするよう設定しました。')
                    
                except SubscriptionPlan.DoesNotExist:
                    messages.error(request, 'フリープランが見つかりません。')
                
            except Exception as e:
                messages.error(request, f'Stripeの処理中にエラーが発生しました: {str(e)}')
        else:
            # Stripe連携がない場合は即時キャンセル
            try:
                free_plan = SubscriptionPlan.objects.get(slug='free')
                
                # 現在のプランを保存
                old_plan = subscription.plan
                
                # フリープランに変更
                subscription.plan = free_plan
                subscription.scheduled_downgrade_to = None
                subscription.canceled_at = timezone.now()
                subscription.save()
                
                # イベント記録
                SubscriptionEvent.objects.create(
                    user=subscription.user,
                    subscription=subscription,
                    event_type='canceled',
                    from_plan=old_plan,
                    to_plan=free_plan,
                    details={
                        'canceled_by': 'admin',
                        'admin_username': request.user.username,
                        'immediate': True
                    }
                )
                
                # 広告設定も更新
                from ads.models import UserAdPreference
                try:
                    ad_pref = UserAdPreference.objects.get(user=subscription.user)
                    ad_pref.show_ads = free_plan.show_ads
                    ad_pref.is_premium = not free_plan.show_ads
                    ad_pref.allow_personalized_ads = free_plan.show_ads
                    ad_pref.save()
                except UserAdPreference.DoesNotExist:
                    pass
                
                messages.success(request, 'サブスクリプションを即時キャンセルしました。フリープランに変更されました。')
                
            except SubscriptionPlan.DoesNotExist:
                messages.error(request, 'フリープランが見つかりません。')
    else:
        # GETリクエストの場合は確認画面を表示
        context = {
            'subscription': subscription,
            'title': 'サブスクリプションのキャンセル',
            'action': 'キャンセル',
            'message': f'ユーザー "{subscription.user.username}" のサブスクリプション（プラン: {subscription.plan.name}）をキャンセルしますか？',
            'warning': 'この操作はユーザーへの通知なしに行われます。',
            'action_url': reverse('admin:cancel_subscription', args=[subscription.id]),
        }
        return render(request, 'admin/subscriptions/confirm_action.html', context)
    
    return redirect('admin:subscriptions_usersubscription_changelist')

@staff_member_required
def admin_activate_subscription(request, id):
    """管理者がサブスクリプションを有効化する"""
    subscription = get_object_or_404(UserSubscription, id=id)
    
    if request.method == 'POST':
        subscription.is_active = True
        subscription.save()
        
        # イベント記録
        SubscriptionEvent.objects.create(
            user=subscription.user,
            subscription=subscription,
            event_type='updated',
            from_plan=subscription.plan,
            to_plan=subscription.plan,
            details={
                'activated_by': 'admin',
                'admin_username': request.user.username
            }
        )
        
        messages.success(request, f'サブスクリプションを有効化しました。')
    else:
        # GETリクエストの場合は確認画面を表示
        context = {
            'subscription': subscription,
            'title': 'サブスクリプションの有効化',
            'action': '有効化',
            'message': f'ユーザー "{subscription.user.username}" のサブスクリプションを有効化しますか？',
            'action_url': reverse('admin:activate_subscription', args=[subscription.id]),
        }
        return render(request, 'admin/subscriptions/confirm_action.html', context)
    
    return redirect('admin:subscriptions_usersubscription_changelist')

@staff_member_required
def admin_change_plan(request, id):
    """管理者がサブスクリプションのプランを変更する"""
    subscription = get_object_or_404(UserSubscription, id=id)
    
    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        if not plan_id:
            messages.error(request, 'プランが選択されていません。')
            return redirect('admin:change_plan', id=id)
        
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
            
            # 現在のプランを保存
            old_plan = subscription.plan
            
            # プランを変更
            subscription.plan = plan
            subscription.scheduled_downgrade_to = None
            subscription.is_active = True
            subscription.save()
            
            # イベント記録
            event_type = 'upgraded' if plan.price_monthly > old_plan.price_monthly else 'downgraded' if plan.price_monthly < old_plan.price_monthly else 'updated'
            SubscriptionEvent.objects.create(
                user=subscription.user,
                subscription=subscription,
                event_type=event_type,
                from_plan=old_plan,
                to_plan=plan,
                details={
                    'changed_by': 'admin',
                    'admin_username': request.user.username
                }
            )
            
            # 広告設定も更新
            from ads.models import UserAdPreference
            try:
                ad_pref = UserAdPreference.objects.get(user=subscription.user)
                ad_pref.show_ads = plan.show_ads
                ad_pref.is_premium = not plan.show_ads
                ad_pref.allow_personalized_ads = plan.show_ads
                ad_pref.save()
            except UserAdPreference.DoesNotExist:
                pass
            
            messages.success(request, f'サブスクリプションのプランを {old_plan.name} から {plan.name} に変更しました。')
            
        except SubscriptionPlan.DoesNotExist:
            messages.error(request, '指定されたプランが見つかりません。')
    else:
        # GETリクエストの場合はプラン選択画面を表示
        context = {
            'subscription': subscription,
            'plans': SubscriptionPlan.objects.all().order_by('display_order', 'price_monthly'),
            'title': 'サブスクリプションのプラン変更',
            'message': f'ユーザー "{subscription.user.username}" のサブスクリプションのプランを変更します。',
            'action_url': reverse('admin:change_plan', args=[subscription.id]),
        }
        return render(request, 'admin/subscriptions/change_plan.html', context)
    
    return redirect('admin:subscriptions_usersubscription_changelist')

@staff_member_required
def admin_cancel_downgrade(request, id):
    """管理者が予定されたダウングレードをキャンセルする"""
    subscription = get_object_or_404(UserSubscription, id=id)
    
    if not subscription.scheduled_downgrade_to:
        messages.error(request, 'このサブスクリプションには予定されたダウングレードはありません。')
        return redirect('admin:subscriptions_usersubscription_changelist')
    
    if request.method == 'POST':
        # Stripe連携がある場合はStripeでも変更
        if subscription.stripe_subscription_id:
            try:
                import stripe
                from django.conf import settings
                stripe.api_key = settings.STRIPE_SECRET_KEY
                
                # 自動更新を再開
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=False
                )
                
                messages.success(request, 'Stripeサブスクリプションの自動更新を再開しました。')
                
            except Exception as e:
                messages.error(request, f'Stripeの処理中にエラーが発生しました: {str(e)}')
        
        # ダウングレード予定をクリア
        target_plan = subscription.scheduled_downgrade_to
        subscription.scheduled_downgrade_to = None
        subscription.canceled_at = None
        subscription.save()
        
        # イベント記録
        SubscriptionEvent.objects.create(
            user=subscription.user,
            subscription=subscription,
            event_type='updated',
            from_plan=subscription.plan,
            to_plan=subscription.plan,
            details={
                'canceled_downgrade': True,
                'canceled_by': 'admin',
                'admin_username': request.user.username,
                'target_plan_name': target_plan.name if target_plan else 'Unknown'
            }
        )
        
        messages.success(request, 'ダウングレード予定をキャンセルしました。現在のプランが継続されます。')
    else:
        # GETリクエストの場合は確認画面を表示
        context = {
            'subscription': subscription,
            'title': 'ダウングレード予定のキャンセル',
            'action': 'キャンセル',
            'message': f'ユーザー "{subscription.user.username}" の {subscription.scheduled_downgrade_to.name} へのダウングレード予定をキャンセルしますか？',
            'action_url': reverse('admin:cancel_downgrade', args=[subscription.id]),
        }
        return render(request, 'admin/subscriptions/confirm_action.html', context)
    
    return redirect('admin:subscriptions_usersubscription_changelist')

@staff_member_required
def admin_sync_subscription(request, id):
    """管理者がStripeと同期する"""
    subscription = get_object_or_404(UserSubscription, id=id)
    
    if not subscription.stripe_subscription_id:
        messages.error(request, 'このサブスクリプションにはStripe IDがないため同期できません。')
        return redirect('admin:subscriptions_usersubscription_changelist')
    
    try:
        import stripe
        from django.conf import settings
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Stripeからサブスクリプション情報を取得
        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
        
        # ステータスが active の場合のみ更新
        if stripe_sub.status == 'active':
            # 請求期間情報の更新
            subscription.current_period_start = timezone.datetime.fromtimestamp(stripe_sub.current_period_start, tz=timezone.utc)
            subscription.current_period_end = timezone.datetime.fromtimestamp(stripe_sub.current_period_end, tz=timezone.utc)
            
            # キャンセル予定の確認
            if stripe_sub.cancel_at_period_end and not subscription.scheduled_downgrade_to:
                # フリープランをスケジュール
                try:
                    free_plan = SubscriptionPlan.objects.get(slug='free')
                    subscription.scheduled_downgrade_to = free_plan
                except SubscriptionPlan.DoesNotExist:
                    messages.warning(request, 'フリープランが見つからないため、ダウングレード予定を設定できませんでした。')
            elif not stripe_sub.cancel_at_period_end and subscription.scheduled_downgrade_to:
                # ダウングレード予定をクリア
                subscription.scheduled_downgrade_to = None
                subscription.canceled_at = None
            
            # 価格情報からプランを更新
            items = stripe_sub.get('items', {}).get('data', [])
            if items:
                price_id = items[0].get('price', {}).get('id')
                if price_id:
                    from .webhooks import find_plan_by_stripe_price
                    plan = find_plan_by_stripe_price(price_id)
                    if plan and plan.id != subscription.plan.id:
                        old_plan = subscription.plan
                        subscription.plan = plan
                        
                        # イベント記録
                        event_type = 'upgraded' if plan.price_monthly > old_plan.price_monthly else 'downgraded' if plan.price_monthly < old_plan.price_monthly else 'updated'
                        SubscriptionEvent.objects.create(
                            user=subscription.user,
                            subscription=subscription,
                            event_type=event_type,
                            from_plan=old_plan,
                            to_plan=plan,
                            details={
                                'synced_by': 'admin',
                                'admin_username': request.user.username,
                                'stripe_price_id': price_id
                            }
                        )
                        
                        messages.success(request, f'プランを {old_plan.name} から {plan.name} に更新しました。')
            
            subscription.save()
            messages.success(request, 'Stripeとの同期が完了しました。')
        else:
            # サブスクリプションが無効の場合
            subscription.is_active = False
            subscription.save()
            
            messages.warning(request, f'Stripeでのサブスクリプションステータスは "{stripe_sub.status}" です。サブスクリプションを無効に設定しました。')
    except Exception as e:
        messages.error(request, f'Stripeとの同期中にエラーが発生しました: {str(e)}')
    
    return redirect('admin:subscriptions_usersubscription_changelist')    