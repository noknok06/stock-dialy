# subscriptions/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import UserSubscription, SubscriptionPlan

class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # サブスクリプションがなければフリープランを割り当て
            try:
                subscription = request.user.subscription
                if not subscription.is_valid():
                    # 期限切れの場合はフリープランに戻す
                    try:
                        free_plan = SubscriptionPlan.objects.get(slug='free')
                        subscription.plan = free_plan
                        subscription.is_active = True
                        subscription.end_date = None
                        subscription.save()
                        
                        # 広告設定も更新
                        self.update_ad_preferences(request.user, show_ads=True)
                        
                        messages.info(request, "サブスクリプションの期限が切れたため、フリープランに戻りました。")
                    except SubscriptionPlan.DoesNotExist:
                        # フリープランが存在しない場合は何もしない（エラー防止）
                        pass
            except (UserSubscription.DoesNotExist, AttributeError):
                # サブスクリプションがなければ作成を試みる
                try:
                    free_plan = SubscriptionPlan.objects.get(slug='free')
                    UserSubscription.objects.create(user=request.user, plan=free_plan)
                    
                    # 広告設定も初期化
                    self.update_ad_preferences(request.user, show_ads=True)
                except SubscriptionPlan.DoesNotExist:
                    # フリープランが存在しない場合は何もしない（エラー防止）
                    pass
                
            # サブスクリプション情報をリクエストに追加（エラー処理を追加）
            try:
                request.subscription = request.user.subscription
            except (UserSubscription.DoesNotExist, AttributeError):
                # サブスクリプションがない場合はNoneを設定
                request.subscription = None
            
            # プラン制限に関する警告表示（リソース使用量が上限に近づいている場合）
            self.check_resource_warnings(request)
        
        response = self.get_response(request)
        return response
    
    def update_ad_preferences(self, user, show_ads=True):
        """ユーザーの広告設定を更新"""
        try:
            from ads.models import UserAdPreference
            ad_preference, _ = UserAdPreference.objects.get_or_create(
                user=user,
                defaults={
                    'show_ads': show_ads,
                    'is_premium': not show_ads,
                    'allow_personalized_ads': show_ads
                }
            )
            
            ad_preference.show_ads = show_ads
            ad_preference.is_premium = not show_ads
            
            # 有料プランならパーソナライズ広告を無効化、フリープランなら有効化
            if not show_ads:
                ad_preference.allow_personalized_ads = False
            else:
                ad_preference.allow_personalized_ads = True
                
            ad_preference.save()
            return True
        except Exception as e:
            print(f"Error updating ad preferences: {str(e)}")
            return False

    def check_resource_warnings(self, request):
        """リソース使用量の警告チェック（上限の80%以上使用している場合に警告）"""
        if not hasattr(request, 'subscription') or request.subscription is None:
            return
        
        try:
            subscription = request.subscription
            plan = subscription.plan
            
            # タグ数チェック
            tag_count = request.user.tag_set.count()
            tag_limit = plan.max_tags
            if tag_limit > 0 and tag_count >= tag_limit * 0.8 and tag_count < tag_limit:
                messages.warning(request, f"タグ数が上限({tag_limit}個)の{int(tag_count/tag_limit*100)}%に達しています。")
            
            # テンプレート数チェック
            template_count = request.user.analysistemplate_set.count()
            template_limit = plan.max_templates
            if template_limit > 0 and template_count >= template_limit * 0.8 and template_count < template_limit:
                messages.warning(request, f"分析テンプレート数が上限({template_limit}個)の{int(template_count/template_limit*100)}%に達しています。")
            
            # スナップショット数チェック
            snapshot_count = request.user.portfoliosnapshot_set.count()
            snapshot_limit = plan.max_snapshots
            if snapshot_limit > 0 and snapshot_count >= snapshot_limit * 0.8 and snapshot_count < snapshot_limit:
                messages.warning(request, f"スナップショット数が上限({snapshot_limit}回)の{int(snapshot_count/snapshot_limit*100)}%に達しています。")
            
            # 株式記録数チェック
            record_count = request.user.stockdiary_set.count()
            record_limit = plan.max_records
            if record_limit > 0 and record_count >= record_limit * 0.8 and record_count < record_limit:
                messages.warning(request, f"株式記録数が上限({record_limit}件)の{int(record_count/record_limit*100)}%に達しています。")
        
        except Exception as e:
            print(f"Error checking resource warnings: {str(e)}")