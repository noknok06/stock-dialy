from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse
from django.contrib.auth import get_user_model
import random
import string
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def list_apps(self, request, provider=None, client_id=None):
        """
        settings.pyのAPPキーとDBのSocialAppが重複した場合、
        settings.py側（APP設定）を優先して1つだけ返す。
        """
        try:
            apps = super().list_apps(request, provider=provider, client_id=client_id)
        except Exception as e:
            logger.error(f"Error in list_apps: {e}")
            return []

        if len(apps) > 1 and provider:
            # settings.py由来のアプリを優先（pkがNone = DB未保存）
            settings_apps = [app for app in apps if app.pk is None]
            if settings_apps:
                logger.warning(
                    f"Multiple SocialApps found for provider '{provider}'. "
                    f"Using settings-based configuration. "
                    f"Please remove duplicate SocialApp from the database via admin."
                )
                return settings_apps[:1]
            # すべてDB由来の場合は最初の1つを返す
            logger.warning(
                f"Multiple SocialApps found in DB for provider '{provider}'. "
                f"Using first one. Please clean up duplicates."
            )
            return apps[:1]
        return apps

    def pre_social_login(self, request, sociallogin):
        """ソーシャルログイン前の処理"""
        # すでに認証済みのユーザーの場合は何もしない
        if request.user.is_authenticated:
            return

        # メールアドレスで既存ユーザーを検索
        email = sociallogin.account.extra_data.get('email')
        if email:
            try:
                # メールアドレスが一致する既存ユーザーを検索
                existing_user = User.objects.get(email=email)

                # 既存ユーザーにソーシャルアカウントが接続されているか確認
                if existing_user.socialaccount_set.filter(provider='google').exists():
                    # 既に連携済みの場合は通常のログインフローを続ける
                    pass
                else:
                    # 既存ユーザーだが、ソーシャル連携がまだの場合
                    # ここでは自動連携せず、メッセージを表示してリダイレクト
                    messages.info(
                        request,
                        f"メールアドレス {email} は既に通常アカウントとして登録されています。"
                        f"そのアカウントでログインしてください。"
                    )
                    # ログインページにリダイレクト
                    from django.shortcuts import redirect
                    from allauth.exceptions import ImmediateHttpResponse
                    raise ImmediateHttpResponse(redirect('users:login'))

            except User.DoesNotExist:
                # 既存ユーザーが見つからない場合は新規登録フローへ
                pass
