# subscriptions/mixins.py - 修正版
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse

class SubscriptionLimitCheckMixin:
    """サブスクリプション制限をチェックするミックスイン（全制限を無効化）"""
    
    def dispatch(self, request, *args, **kwargs):
        # 制限チェックをバイパスして常に許可
        return super().dispatch(request, *args, **kwargs)
        
    # 以下のメソッドは呼び出されなくなるが、構造を維持するために残す
    def check_tag_limit(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
        
    def check_template_limit(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def check_snapshot_limit(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def check_record_limit(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)