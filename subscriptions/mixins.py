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
                
                if current_count >= plan.max_tags:
                    messages.error(request, f"タグ数が上限({plan.max_tags}個)に達しています。プランをアップグレードしてください。")
                    return redirect('subscriptions:upgrade')
        except Exception:
            # エラーが発生した場合はチェックをスキップ
            pass
                
        return super().dispatch(request, *args, **kwargs)
    # 他の制限チェックメソッドも同様に実装
    def check_template_limit(self, request, *args, **kwargs):
        try:
            if request.method == 'POST':
                plan = request.subscription.plan
                current_count = request.user.analysistemplate_set.count()
                
                if current_count >= plan.max_templates:
                    messages.error(request, f"分析テンプレート数が上限({plan.max_templates}個)に達しています。プランをアップグレードしてください。")
                    return redirect('subscriptions:upgrade')
                
        except Exception:
            # エラーが発生した場合はチェックをスキップ
            pass

        return super().dispatch(request, *args, **kwargs)
    
    def check_snapshot_limit(self, request, *args, **kwargs):
        try:
            if request.method == 'POST':
                plan = request.subscription.plan
                current_count = request.user.portfoliosnapshot_set.count()
                
                if current_count >= plan.max_snapshots:
                    messages.error(request, f"スナップショット数が上限({plan.max_snapshots}回)に達しています。プランをアップグレードしてください。")
                    return redirect('subscriptions:upgrade')
                
        except Exception:
            # エラーが発生した場合はチェックをスキップ
            pass    
        return super().dispatch(request, *args, **kwargs)
    
    def check_record_limit(self, request, *args, **kwargs):
        try:
            if request.method == 'POST':
                plan = request.subscription.plan
                current_count = request.user.stockdiary_set.count()
                
                if current_count >= plan.max_records:
                    messages.error(request, f"株式記録数が上限({plan.max_records}件)に達しています。プランをアップグレードしてください。")
                    return redirect('subscriptions:upgrade')
                
        except Exception:
            # エラーが発生した場合はチェックをスキップ
            pass
        
        return super().dispatch(request, *args, **kwargs)