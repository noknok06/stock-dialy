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

    # 新規追加：売却登録ページ
    path('sell/', views.StockDiarySellView.as_view(), name='sell'),
    path('sell/<int:pk>/', views.StockDiarySellView.as_view(), name='sell_specific'),
    path('<int:pk>/cancel_sell/', views.CancelSellView.as_view(), name='cancel_sell'),
    
    path('api/stock/info/<str:stock_code>/', api.get_stock_info, name='api_stock_info'),
    path('api/stock/price/<str:stock_code>/', api.get_stock_price, name='api_stock_price'),
    path('api/create/', api.api_create_diary, name='api_create'),
    path('api/tab-content/<int:diary_id>/<str:tab_type>/', views.DiaryTabContentView.as_view(), name='api_tab_content'),

    path('<int:pk>/note/', views.AddDiaryNoteView.as_view(), name='add_note'),
    path('<int:diary_pk>/note/<int:pk>/delete/', views.DeleteDiaryNoteView.as_view(), name='delete_note'),

    path('analytics/', views.DiaryAnalyticsView.as_view(), name='analytics'),
]