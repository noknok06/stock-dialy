# users/forms.py
from allauth.socialaccount.forms import SignupForm as AllauthSocialSignupForm
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm, UserChangeForm, PasswordResetForm
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['class'] = 'form-control'
        self.fields['password'].widget.attrs['class'] = 'form-control'


class CustomSocialSignupForm(AllauthSocialSignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # フォームのスタイル設定
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'ユーザー名を入力してください'
        })
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'メールアドレス'
        })        


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # フォームフィールドのスタイル設定
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
            field.widget.attrs['placeholder'] = field.label

class CustomUserChangeForm(UserChangeForm):
    password = None  # パスワードフィールドを除外
    
    class Meta:
        model = User
        fields = ('username', 'email')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # フォームフィールドのスタイル設定
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class CustomPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # フォームフィールドのスタイル設定
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'メールアドレスを入力してください'
        })            