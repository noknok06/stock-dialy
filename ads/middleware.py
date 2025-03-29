# ads/middleware.py - サブスクリプション関連の参照を削除
from django.conf import settings
from django.urls import resolve
from .models import UserAdPreference

class AdsMiddleware:
    """広告表示を制御するミドルウェア"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        # 広告を表示しないパスパターン
        self.no_ads_paths = [
            '/admin/',
            '/accounts/login/',
            '/accounts/signup/',
            '/accounts/password_reset/',
        ]
        
        # 広告を表示しないネームスペースのリスト
        self.no_ads_namespaces = [
            'admin',
            'ads:ad_preferences',
            'ads:privacy_policy',
        ]
    
    def __call__(self, request):
        # リクエストオブジェクトに広告表示フラグを追加
        request.show_ads = self._should_show_ads(request)
        
        # パーソナライズ広告の設定も追加
        request.personalized_ads = self._should_show_personalized_ads(request)
        
        response = self.get_response(request)
        return response
    
    def _should_show_ads(self, request):
        """広告を表示すべきかどうかを判定"""
        # デフォルト設定
        show_ads_default = getattr(settings, 'ADS_SETTINGS', {}).get('SHOW_ADS_DEFAULT', True)
        
        # 広告非表示パスかどうかをチェック
        path = request.path

        auth_paths = [
            '/users/login/',
            '/users/logout/',
            '/users/signup/',
            '/users/password-reset/',
            '/users/profile/password/',
            '/users/google-login/',
            '/ads/terms/',
            '/ads/privacy-policy/',
            '/ads/faq/',
            '/ads/guide/',
            '/contact/',
        ]
        
        if path in auth_paths:
            print(f"Path {path} matches auth_paths - should hide ads")
            return False
        else:
            print(f"Path {path} does not match any auth paths")
        
        # URLの名前空間をチェック
        try:
            resolved = resolve(request.path_info)
            url_namespace = resolved.namespace
            if url_namespace in self.no_ads_namespaces:
                return False
        except:
            pass
        
        # ユーザーがログインしている場合
        if request.user.is_authenticated:
            # 広告設定をチェック
            try:
                ad_preference = UserAdPreference.objects.get(user=request.user)
                return ad_preference.should_show_ads()
            except UserAdPreference.DoesNotExist:
                # 設定がない場合は作成
                try:
                    ad_preference = UserAdPreference.objects.create(user=request.user)
                    return ad_preference.should_show_ads()
                except:
                    pass
        
        # 上記のチェックでいずれも該当しない場合、デフォルト設定を使用
        return show_ads_default
        
    def _should_show_personalized_ads(self, request):
        """パーソナライズ広告を表示すべきかどうかを判定"""
        # デフォルト設定
        personalized_ads_default = getattr(settings, 'ADS_SETTINGS', {}).get('PERSONALIZED_ADS_DEFAULT', True)
        
        # ユーザーがログインしている場合
        if request.user.is_authenticated:
            try:
                # 広告設定を確認
                ad_preference = UserAdPreference.objects.get(user=request.user)
                return ad_preference.allow_personalized_ads
            except UserAdPreference.DoesNotExist:
                # 設定がない場合は作成
                try:
                    ad_preference = UserAdPreference.objects.create(user=request.user)
                    return ad_preference.allow_personalized_ads
                except:
                    pass
        
        # デフォルト設定を使用
        return personalized_ads_default