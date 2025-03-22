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

# subscriptions/views.py のCheckoutViewを修正

class CheckoutView(LoginRequiredMixin, TemplateView):
    """決済処理画面（確認画面付き）"""
    
    def get_template_names(self):
        """確認済みかどうかでテンプレートを切り替え"""
        confirmed = self.request.GET.get('confirmed', 'false') == 'true'
        return 'subscriptions/checkout.html' if confirmed else 'subscriptions/checkout_confirm.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan_id = self.kwargs.get('plan_id')
        billing_type = self.kwargs.get('type', 'monthly')
        
        # デバッグ情報
        print(f"CheckoutView: plan_id={plan_id}, type={billing_type}")
        
        # プランIDが存在しない場合のエラーハンドリング
        if plan_id is None:
            context['error'] = "プランIDが指定されていません。"
            print("Error: Plan ID is None")
            return context
        
        try:
            # プランIDでの取得を試みる
            plan = SubscriptionPlan.objects.get(id=plan_id)
            context['plan'] = plan
            context['billing_type'] = billing_type
            
            # テスト用設定
            context['is_test_mode'] = True
            
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
            except Exception as e:
                print(f"Error checking downgrade status: {str(e)}")
                pass
            
            context['is_downgrade'] = is_downgrade
            context['confirmed'] = self.request.GET.get('confirmed', 'false') == 'true'
            
        except SubscriptionPlan.DoesNotExist:
            # プランが見つからない場合のエラーメッセージ
            context['error'] = f"指定されたプラン(ID: {plan_id})が見つかりません。"
            print(f"Error: Plan with ID {plan_id} not found.")
        except Exception as e:
            # その他のエラー
            context['error'] = f"エラーが発生しました: {str(e)}"
            print(f"Error in CheckoutView: {str(e)}")
        
        return context
    
    def post(self, request, *args, **kwargs):
        """プラン変更処理"""
        plan_id = self.kwargs.get('plan_id')
        
        # プランIDが存在しない場合のエラーハンドリング
        if plan_id is None:
            messages.error(request, "プランIDが指定されていません。")
            return redirect('subscriptions:upgrade')
            
        confirmed = request.POST.get('confirmed', 'false') == 'true'
        
        # 確認していない場合は確認画面にリダイレクト
        if not confirmed:
            return redirect(reverse('subscriptions:checkout', kwargs=self.kwargs) + '?confirmed=true')
        
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
            
            # 広告設定も直接更新して確実に反映
            try:
                from ads.models import UserAdPreference
                ad_preference, _ = UserAdPreference.objects.get_or_create(
                    user=request.user
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
            except Exception as e:
                print(f"Error updating ad preferences during plan change: {str(e)}")
            
            messages.success(request, f"{plan.name}に切り替えました")
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
# subscriptions/views.py のDowngradeViewを修正

class DowngradeView(LoginRequiredMixin, TemplateView):
    """ダウングレード処理（確認付き）"""
    template_name = 'subscriptions/downgrade.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            # フリープランを取得
            free_plan = SubscriptionPlan.objects.get(slug='free')
            context['plan'] = free_plan
            
            # 処理中かどうか
            context['processing'] = self.request.GET.get('processing', 'false') == 'true'
            
        except Exception as e:
            context['error'] = f"エラーが発生しました: {str(e)}"
        
        return context
    
    def post(self, request, *args, **kwargs):
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
            
            # 広告設定を直接更新（シグナルに加えて確実に更新）
            try:
                from ads.models import UserAdPreference
                ad_preference, _ = UserAdPreference.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'show_ads': True,
                        'is_premium': False,
                        'allow_personalized_ads': True
                    }
                )
                ad_preference.show_ads = True
                ad_preference.is_premium = False
                ad_preference.allow_personalized_ads = True
                ad_preference.save()
            except Exception as e:
                print(f"Error updating ad preferences during downgrade: {str(e)}")
                
            messages.success(request, "プランをフリープランに変更しました")
            
            # 処理中画面を表示してからリダイレクト
            return redirect(reverse('subscriptions:downgrade') + '?processing=true')
            
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