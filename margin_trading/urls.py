# margin_trading/urls.py
from django.urls import path
from . import views

app_name = 'margin_trading'

urlpatterns = [
    # 管理画面
    path('', views.MarginDataListView.as_view(), name='list'),
    path('import/', views.ImportDataView.as_view(), name='import_data'),
    path('logs/', views.ImportLogListView.as_view(), name='logs'),
    
    # API
    path('api/stock/<str:stock_code>/', views.get_stock_margin_data, name='stock_data_api'),
    path('api/latest/', views.get_latest_data, name='latest_data_api'),
]

#