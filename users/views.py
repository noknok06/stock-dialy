# users/views.py
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView, DeleteView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth import get_user_model
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    PasswordResetView, PasswordResetDoneView,
    PasswordResetConfirmView, PasswordResetCompleteView
)
from .forms import CustomPasswordResetForm
from django.views.generic import FormView
from django.contrib.auth.forms import AuthenticationForm
from allauth.socialaccount.models import SocialAccount

User = get_user_model()

class CustomLoginView(LoginView):
    template_name = 'users/login.html'
    redirect_authenticated_user = True
    authentication_form = CustomAuthenticationForm
    
    def get_success_url(self):
        return reverse_lazy('stockdiary:home')

class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('users:login')

class SignUpView(CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = 'users/signup.html'
    success_url = reverse_lazy('users:login')

class GoogleLoginView(TemplateView):
    template_name = 'users/google_login.html'


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'users/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # ユーザーの統計情報を取得
        context['diary_count'] = user.stockdiary_set.count()
        context['template_count'] = user.analysistemplate_set.count()
        context['tag_count'] = user.tag_set.count()
        
        # 最近の投資日記を取得（最新5件）
        context['recent_diaries'] = user.stockdiary_set.all().order_by('-created_at')[:5]
        
        # サブスクリプション情報を追加
        try:
            subscription = user.subscription
            context['subscription'] = subscription
            context['subscription_plan'] = subscription.plan
        except:
            # サブスクリプションがない場合はフリープラン情報を取得
            try:
                from subscriptions.models import SubscriptionPlan
                context['subscription_plan'] = SubscriptionPlan.objects.get(slug='free')
            except:
                context['subscription_plan'] = None
        
        return context

class AccountDeleteConfirmView(LoginRequiredMixin, TemplateView):
    """アカウント削除の確認画面を表示するビュー"""
    template_name = 'users/account_delete_confirm.html'

class AccountDeleteView(LoginRequiredMixin, DeleteView):
    """アカウントを削除するビュー"""
    model = get_user_model()
    success_url = reverse_lazy('users:login')
    template_name = 'users/account_deleted.html'
    
    def get_object(self, queryset=None):
        # 現在ログインしているユーザーを対象にする
        return self.request.user
    
    def delete(self, request, *args, **kwargs):
        # ユーザーの投稿・コメント等を削除するカスタム処理を行う場合はここに記述
        user = self.get_object()
        messages.success(request, 'アカウントを削除しました。ご利用ありがとうございました。')
        
        # ログアウト処理を先に行う
        logout(request)
        
        # ユーザーを削除
        user.delete()
        
        return redirect(self.success_url)

# users/views.py に以下を追加（冒頭のインポート部分）
from django.contrib.auth.views import PasswordChangeView
from django.views.generic.edit import UpdateView
from django.contrib import messages
from django.contrib.auth import logout  # 既存のImportがなければ追加
from .forms import CustomPasswordChangeForm, CustomUserChangeForm

# 既存のビュークラスと一緒に以下を追加

class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """パスワード変更ビュー"""
    form_class = CustomPasswordChangeForm
    template_name = 'users/password_change.html'
    success_url = reverse_lazy('users:profile')
    
    def form_valid(self, form):
        # フォームが有効な場合の処理
        response = super().form_valid(form)
        messages.success(self.request, 'パスワードが正常に変更されました。')
        return response

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """プロフィール更新ビュー"""
    model = User
    form_class = CustomUserChangeForm
    template_name = 'users/profile_update.html'
    success_url = reverse_lazy('users:profile')
    
    def get_object(self, queryset=None):
        return self.request.user
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'プロフィール情報が更新されました。')
        return response        


class CustomPasswordResetView(PasswordResetView):
    template_name = 'users/password_reset.html'
    email_template_name = 'users/password_reset_email_text.txt'  # プレーンテキスト版
    html_email_template_name = 'users/password_reset_email.html'  # HTML版
    subject_template_name = 'users/password_reset_subject.txt'
    form_class = CustomPasswordResetForm
    success_url = reverse_lazy('users:password_reset_done')

    def dispatch(self, request, *args, **kwargs):
        # ユーザーのメールアドレスを取得（フォーム送信時）
        if request.method == 'POST':
            email = request.POST.get('email')
            if email:
                # ユーザーを検索
                try:
                    user = User.objects.get(email=email)
                    # Google認証ユーザーかどうかを確認
                    if user.socialaccount_set.filter(provider='google').exists():
                        messages.info(request, 'このアカウントはGoogle認証で登録されています。Googleアカウントのパスワードリセットを行ってください。')
                        return redirect('users:password_reset')
                except User.DoesNotExist:
                    pass
        return super().dispatch(request, *args, **kwargs)
        
class CustomPasswordResetDoneView(PasswordResetDoneView):
    """パスワードリセットメール送信完了ビュー"""
    template_name = 'users/password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """パスワードリセット確認ビュー"""
    template_name = 'users/password_reset_confirm.html'
    success_url = reverse_lazy('users:password_reset_complete')

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    """パスワードリセット完了ビュー"""
    template_name = 'users/password_reset_complete.html'        


class SocialAccountConnectedView(LoginRequiredMixin, TemplateView):
    """ソーシャルアカウント接続完了ビュー"""
    template_name = 'socialaccount/signup_success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # ユーザーのソーシャルアカウント情報を取得
        try:
            social_account = SocialAccount.objects.get(user=user, provider='google')
            context['social_account'] = social_account
            context['social_data'] = social_account.extra_data
        except SocialAccount.DoesNotExist:
            context['social_account'] = None
            
        return context


class ConnectExistingAccountView(FormView):
    """既存アカウントとGoogleアカウントを連携するビュー"""
    template_name = 'users/connect_existing_account.html'
    form_class = AuthenticationForm
    success_url = reverse_lazy('stockdiary:home')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['email'] = self.request.session.get('connect_email', '')
        return context
    
    def form_valid(self, form):
        # ユーザーをログイン
        login(self.request, form.get_user())
        user = form.get_user()
        
        # セッションからGoogleアカウントのデータを取得
        email = self.request.session.get('connect_email')
        
        if email:
            # 既存アカウントとGoogleアカウントを関連付ける
            try:
                social_account = SocialAccount.objects.get(email=email, provider='google')
                social_account.user = user
                social_account.save()
                messages.success(self.request, 'Googleアカウントと既存アカウントが連携されました')
            except SocialAccount.DoesNotExist:
                messages.error(self.request, 'Google認証情報が見つかりませんでした')
            
            # セッションをクリア
            if 'connect_email' in self.request.session:
                del self.request.session['connect_email']
        
        return super().form_valid(form)            

class EmailDuplicateNotificationView(TemplateView):
    """メールアドレスが重複している場合の通知ビュー"""
    template_name = 'users/email_duplicate.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['email'] = self.request.GET.get('email', '')
        return context