from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse
from django.contrib.auth import get_user_model
import random
import string
from django.contrib import messages

User = get_user_model()

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
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
                    # sociallogin.state['next']は使用せず、例外を投げる
                    from django.shortcuts import redirect
                    from allauth.exceptions import ImmediateHttpResponse
                    raise ImmediateHttpResponse(redirect('users:login'))
                    
            except User.DoesNotExist:
                # 既存ユーザーが見つからない場合は新規登録フローへ
                pass