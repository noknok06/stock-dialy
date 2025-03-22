# ads/auth.py - 認証バックエンドと広告設定の統合
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from .models import UserAdPreference

User = get_user_model()

class AdsEnabledAuthBackend(ModelBackend):
    """
    広告設定に対応した認証バックエンド
    通常のModelBackendを継承して、認証成功時に広告設定を確認・更新する
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        ユーザー認証メソッド
        認証が成功した場合、広告設定を確認・更新する
        """
        # 通常の認証処理
        user = super().authenticate(request, username, password, **kwargs)
        
        # 認証成功の場合
        if user is not None:
            # 広告設定の確認
            self._check_ad_preferences(user)
        
        return user
    
    def _check_ad_preferences(self, user):
        """ユーザーの広告設定を確認・更新"""
        try:
            # 広告設定の取得または作成
            ad_preference, created = UserAdPreference.objects.get_or_create(
                user=user
            )
            
            # ここで必要に応じて広告設定を更新
            # 例: ユーザーの属性や最終ログイン日時に基づいて設定を調整
            
            if created:
                # 新規作成された場合は、サブスクリプションに基づいて設定を調整
                try:
                    subscription = user.subscription
                    if subscription and subscription.is_valid():
                        ad_preference.show_ads = subscription.plan.show_ads
                        ad_preference.is_premium = not subscription.plan.show_ads
                        ad_preference.save()
                except:
                    # サブスクリプションが存在しない場合は何もしない
                    pass
                
        except Exception:
            # エラーが発生した場合は処理をスキップ
            pass