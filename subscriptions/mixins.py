# subscriptions/mixins.py
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse

class SubscriptionLimitCheckMixin:
    """サブスクリプション制限をチェックするミックスイン"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        
        # サブスクリプションが取得できない場合はチェックをスキップ
        if not hasattr(request, 'subscription') or request.subscription is None:
            return super().dispatch(request, *args, **kwargs)
            
        # モデル名でチェック対象を判別
        model_name = self.model._meta.model_name
        
        if model_name == 'tag':
            return self.check_tag_limit(request, *args, **kwargs)
        elif model_name == 'analysistemplate':
            return self.check_template_limit(request, *args, **kwargs)
        elif model_name == 'portfoliosnapshot':
            return self.check_snapshot_limit(request, *args, **kwargs)
        elif model_name == 'stockdiary':
            return self.check_record_limit(request, *args, **kwargs)
            
        return super().dispatch(request, *args, **kwargs)
        
        
    def check_tag_limit(self, request, *args, **kwargs):
        """タグ数の制限チェック"""
        try:
            if request.method == 'POST':  # 新規作成時のみチェック
                plan = request.subscription.plan
                current_count = request.user.tag_set.count()
                
                if plan.max_tags != -1 and current_count >= plan.max_tags:
                    messages.error(request, f"タグ数が上限({plan.max_tags}個)に達しています。プランをアップグレードしてください。")
                    return redirect('subscriptions:upgrade')
        except Exception as e:
            # エラー発生時はログに記録
            print(f"Error in tag limit check: {str(e)}")
            # チェックをスキップ
            pass
                
        return super().dispatch(request, *args, **kwargs)
        
    def check_template_limit(self, request, *args, **kwargs):
        """分析テンプレート数の制限チェック"""
        try:
            if request.method == 'POST':  # 新規作成時のみチェック
                plan = request.subscription.plan
                current_count = request.user.analysistemplate_set.count()

                if plan.max_templates != -1 and current_count >= plan.max_tags:                
                    messages.error(request, f"分析テンプレート数が上限({plan.max_templates}個)に達しています。プランをアップグレードしてください。")
                    return redirect('subscriptions:upgrade')
        except Exception as e:
            # エラー発生時はログに記録
            print(f"Error in template limit check: {str(e)}")
            # チェックをスキップ
            pass
                
        return super().dispatch(request, *args, **kwargs)
    
    # subscriptions/mixins.py の check_snapshot_limit メソッドを改善
    # subscriptions/mixins.py の check_snapshot_limit メソッドを修正
    def check_snapshot_limit(self, request, *args, **kwargs):
        """スナップショット数の制限チェック"""
        try:
            if request.method == 'POST':  # 新規作成時のみチェック
                plan = request.subscription.plan
                current_count = request.user.portfoliosnapshot_set.count()
                
                # 同日のスナップショットがすでに存在するかチェック
                from django.utils import timezone
                import datetime
                from zoneinfo import ZoneInfo  # ZoneInfo を追加
                
                today = timezone.now().date()
                # timezone.utc の代わりに ZoneInfo("UTC") または datetime.timezone.utc を使用
                today_start = datetime.datetime.combine(today, datetime.time.min, tzinfo=ZoneInfo("UTC"))
                today_end = datetime.datetime.combine(today, datetime.time.max, tzinfo=ZoneInfo("UTC"))
                
                today_snapshot_exists = request.user.portfoliosnapshot_set.filter(
                    created_at__range=(today_start, today_end)
                ).exists()
                
                if today_snapshot_exists:
                    messages.error(request, "本日のスナップショットはすでに作成済みです。スナップショットは1日1回のみ作成できます。")
                    return redirect('portfolio:list')
                
                if plan.max_snapshots != -1 and current_count >= plan.max_tags:                
                    messages.error(
                        request, 
                        f"スナップショット数が上限({plan.max_snapshots}回)に達しています。"
                        f"プランをアップグレードするか、古いスナップショットを削除してください。"
                    )
                    return redirect('subscriptions:upgrade')
        except Exception as e:
            # エラー発生時はログに記録
            print(f"Error in snapshot limit check: {str(e)}")
            # チェックをスキップ
            pass
                
        return super().dispatch(request, *args, **kwargs)

    def check_record_limit(self, request, *args, **kwargs):
        """株式記録数の制限チェック"""
        try:
            if request.method == 'POST':  # 新規作成時のみチェック
                plan = request.subscription.plan
                current_count = request.user.stockdiary_set.count()
                
                if plan.max_records != -1 and current_count >= plan.max_tags:                
                    messages.error(request, f"株式記録数が上限({plan.max_records}件)に達しています。プランをアップグレードしてください。")
                    return redirect('subscriptions:upgrade')
        except Exception as e:
            # エラー発生時はログに記録
            print(f"Error in record limit check: {str(e)}")
            # チェックをスキップ
            pass
                
        return super().dispatch(request, *args, **kwargs)