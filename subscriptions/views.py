# subscriptions/views.py
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from .models import SubscriptionPlan, UserSubscription
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import stripe
from django.conf import settings
from django.utils import timezone

class UpgradeView(LoginRequiredMixin, ListView):
    """プランアップグレード画面"""
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


class CheckoutView(LoginRequiredMixin, TemplateView):
    """決済処理画面（テスト用に簡素化+Stripe準備）"""
    template_name = 'subscriptions/checkout.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan_id = self.kwargs.get('plan_id')
        billing_type = self.kwargs.get('type', 'monthly')
        
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
            context['plan'] = plan
            context['billing_type'] = billing_type
            
            # テスト用設定
            context['is_test_mode'] = True
            
            # Stripe準備（コメントアウトしておく）
            """
            # Stripe決済セッションを作成
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # 価格を選択（月額/年額）
            price = plan.price_yearly if billing_type == 'yearly' else plan.price_monthly
            
            # プラン名
            plan_display_name = f"{plan.name} ({billing_type})"
            
            # Stripeの顧客IDを取得または作成
            customer_id = None
            try:
                # ユーザーに関連するStripe顧客IDを取得（存在する場合）
                if hasattr(self.request.user, 'stripe_customer'):
                    customer_id = self.request.user.stripe_customer.stripe_id
            except:
                pass
                
            # 顧客IDがない場合は新規作成
            if not customer_id:
                customer = stripe.Customer.create(
                    email=self.request.user.email,
                    name=self.request.user.username,
                    metadata={
                        'user_id': self.request.user.id
                    }
                )
                customer_id = customer.id
                
                # 顧客IDを保存（StripeCustomerモデルがある場合）
                # StripeCustomer.objects.create(user=self.request.user, stripe_id=customer_id)
            
            # 決済セッションを作成
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'jpy',
                        'product_data': {
                            'name': plan_display_name,
                        },
                        'unit_amount': int(price),
                        'recurring': {
                            'interval': 'year' if billing_type == 'yearly' else 'month',
                        }
                    },
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=self.request.build_absolute_uri(reverse('subscriptions:success')) + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=self.request.build_absolute_uri(reverse('subscriptions:upgrade')),
                metadata={
                    'user_id': self.request.user.id,
                    'plan_id': plan.id,
                    'billing_type': billing_type
                }
            )
            
            context['stripe_public_key'] = settings.STRIPE_PUBLIC_KEY
            context['checkout_session_id'] = checkout_session.id
            """
            
        except SubscriptionPlan.DoesNotExist:
            context['error'] = "指定されたプランが見つかりません"
        except Exception as e:
            context['error'] = f"エラーが発生しました: {str(e)}"
        
        return context
    
    def post(self, request, *args, **kwargs):
        """テスト用の簡易プラン切り替え処理"""
        plan_id = self.kwargs.get('plan_id')
        
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
            
            # ユーザーのサブスクリプションを更新または作成
            subscription, created = UserSubscription.objects.get_or_create(
                user=request.user,
                defaults={'plan': plan, 'is_active': True}
            )
            
            if not created:
                subscription.plan = plan
                subscription.is_active = True
                subscription.save()
            
            messages.success(request, f"{plan.name}プランに切り替えました")
            return redirect('subscriptions:success')
            
        except SubscriptionPlan.DoesNotExist:
            messages.error(request, "指定されたプランが見つかりません")
            return redirect('subscriptions:upgrade')
        except Exception as e:
            messages.error(request, f"エラーが発生しました: {str(e)}")
            return redirect('subscriptions:upgrade')


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
    
class DowngradeView(LoginRequiredMixin, TemplateView):
    """ダウングレード処理"""
    template_name = 'subscriptions/downgrade.html'
    
    def get(self, request, *args, **kwargs):
        try:
            # フリープランを取得
            free_plan = SubscriptionPlan.objects.get(slug='free')
            
            # ユーザーのサブスクリプションを更新
            subscription, created = UserSubscription.objects.get_or_create(
                user=request.user,
                defaults={'plan': free_plan}
            )
            
            if not created:
                subscription.plan = free_plan
                subscription.save()
                
            messages.success(request, "プランをフリープランに変更しました")
            return redirect('subscriptions:upgrade')
            
        except Exception as e:
            messages.error(request, f"エラーが発生しました: {str(e)}")
            return super().get(request, *args, **kwargs)



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