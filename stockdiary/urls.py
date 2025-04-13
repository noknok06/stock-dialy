# stockdiary/urls.py
from django.urls import path
from . import views
from . import api

from django.contrib.auth.decorators import login_required

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

    path('calendar-partial/', login_required(views.calendar_partial), name='calendar_partial'),
    path('day-events/', login_required(views.day_events), name='day_events'),
    path('diary-list/', login_required(views.diary_list), name='diary_list'),
    path('tab-content/<int:diary_id>/<str:tab_type>/', login_required(views.tab_content), name='tab_content'),

    path('calendar-partial/', login_required(views.calendar_partial), name='calendar_partial'),
    path('day-events/', login_required(views.day_events), name='day_events'),
    path('diary-list/', login_required(views.diary_list), name='diary_list'),
    path('tab-content/<int:diary_id>/<str:tab_type>/', login_required(views.tab_content), name='tab_content'),

    # 新規：モバイル操作性向上のための追加エンドポイント
    path('search-suggestion/', login_required(views.search_suggestion), name='search_suggestion'),
    path('<int:pk>/context-actions/', login_required(views.context_actions), name='context_actions'),
]