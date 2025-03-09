# users/views.py
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth import get_user_model
from .forms import CustomUserCreationForm, CustomAuthenticationForm

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