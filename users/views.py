# users/views.py
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView, DeleteView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth import get_user_model
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin

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
        context['checklist_count'] = user.checklist_set.count()
        context['tag_count'] = user.tag_set.count()
        
        # 最近の投資日記を取得（最新5件）
        context['recent_diaries'] = user.stockdiary_set.all().order_by('-created_at')[:5]
        
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