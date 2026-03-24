from django.urls import path
from . import views

app_name = 'margin_tracking'

urlpatterns = [
    path('api/<str:stock_code>/', views.margin_data_api, name='margin_data_api'),
    path('widget/<str:stock_code>/', views.margin_widget, name='margin_widget'),
]
