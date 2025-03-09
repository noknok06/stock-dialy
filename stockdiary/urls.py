# stockdiary/urls.py
from django.urls import path
from . import views
from . import api

app_name = 'stockdiary'

urlpatterns = [
    path('', views.StockDiaryListView.as_view(), name='home'),
    path('create/', views.StockDiaryCreateView.as_view(), name='create'),
    path('<int:pk>/', views.StockDiaryDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.StockDiaryUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.StockDiaryDeleteView.as_view(), name='delete'),

    path('api/stock/info/<str:stock_code>/', api.get_stock_info, name='api_stock_info'),
    path('api/stock/price/<str:stock_code>/', api.get_stock_price, name='api_stock_price'),

    # 新しく追加する分析ダッシュボードのURL
    path('analytics/', views.DiaryAnalyticsView.as_view(), name='analytics'),
]