# stockdiary/urls.py（完全版）
from django.urls import path
from . import views
from . import api
from . import api_views  # 🔧 追加
from django.contrib.auth.decorators import login_required

app_name = 'stockdiary'

urlpatterns = [
    # ==========================================
    # 日記の基本CRUD
    # ==========================================
    path('', views.StockDiaryListView.as_view(), name='home'),
    path('create/', views.StockDiaryCreateView.as_view(), name='create'),
    path('<int:pk>/', views.StockDiaryDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.StockDiaryUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.StockDiaryDeleteView.as_view(), name='delete'),

    # ==========================================
    # 取引管理
    # ==========================================
    path('<int:diary_id>/transaction/add/', views.add_transaction, name='add_transaction'),
    path('transaction/<int:transaction_id>/', views.get_transaction, name='get_transaction'),
    path('transaction/<int:transaction_id>/update/', views.update_transaction, name='update_transaction'),
    path('transaction/<int:transaction_id>/delete/', views.delete_transaction, name='delete_transaction'),

    # ==========================================
    # 株式分割管理
    # ==========================================
    path('<int:diary_id>/stock-split/add/', views.add_stock_split, name='add_stock_split'),
    path('stock-split/<int:split_id>/apply/', views.apply_stock_split, name='apply_stock_split'),
    path('stock-split/<int:split_id>/delete/', views.delete_stock_split, name='delete_stock_split'),

    # ==========================================
    # 継続記録関連
    # ==========================================
    path('<int:pk>/note/', views.AddDiaryNoteView.as_view(), name='add_note'),
    path('<int:diary_pk>/note/<int:pk>/delete/', views.DeleteDiaryNoteView.as_view(), name='delete_note'),

    # ==========================================
    # 🆕 通知API（追加）
    # ==========================================
    path('api/diary/<int:diary_id>/notifications/create/', 
         api_views.create_diary_notification, 
         name='api_create_diary_notification'),
    
    path('api/diary/<int:diary_id>/notifications/', 
         api_views.list_diary_notifications, 
         name='api_list_diary_notifications'),
    path('api/notifications/<uuid:notification_id>/delete/', 
         api_views.delete_diary_notification, 
         name='api_delete_diary_notification'),

    path('notifications/', views.NotificationListView.as_view(), name='notification_list'),
    path('api/notifications/all/', api_views.list_all_notifications, name='api_list_all_notifications'),
    
    # ==========================================
    # 株式情報API
    # ==========================================
    path('api/stock/info/<str:stock_code>/', api.get_stock_info, name='api_stock_info'),
    path('api/stock/price/<str:stock_code>/', api.get_stock_price, name='api_stock_price'),
    path('api/create/', api.api_create_diary, name='api_create'),
    path('api/tab-content/<int:diary_id>/<str:tab_type>/', views.DiaryTabContentView.as_view(), name='api_tab_content'),

    # ==========================================
    # その他のエンドポイント
    # ==========================================
    path('diary-list/', login_required(views.diary_list), name='diary_list'),
    path('tab-content/<int:diary_id>/<str:tab_type>/', login_required(views.tab_content), name='tab_content'),

    # モバイル操作性向上
    path('search-suggestion/', login_required(views.search_suggestion), name='search_suggestion'),
    
    # 画像配信（セキュア）
    path('image/<int:diary_id>/<str:image_type>/', views.ServeImageView.as_view(), name='serve_image'),
    path('image/<int:diary_id>/<str:image_type>/<int:note_id>/', views.ServeImageView.as_view(), name='serve_image'),
    
    # 信用倍率関連API
    path('api/margin-chart-data/<int:diary_id>/', views.api_margin_chart_data, name='api_margin_chart'),
    path('api/margin-compare/<int:diary_id>/', views.api_margin_compare_data, name='api_margin_compare'),
    path('api/margin-sector/<int:diary_id>/', views.api_margin_sector_data, name='api_margin_sector'),
    path('api/margin-sector-suggestions/<int:diary_id>/', views.api_margin_sector_suggestions, name='api_margin_sector_suggestions'),

    # ハッシュタグAPI
    path('api/hashtags/', api_views.get_hashtags, name='api_hashtags'),

    # 銘柄一覧
    path('stocks/', views.StockListView.as_view(), name='stock_list'),
    path('api/stock-diaries/<str:symbol>/', views.api_stock_diaries, name='api_stock_diaries'),

    # 取引履歴アップロード
    path('trade-upload/', views.TradeUploadView.as_view(), name='trade_upload'),
    path('trade-upload/process/', views.process_trade_upload, name='process_trade_upload'),
    
    path('dashboard/', views.TradingDashboardView.as_view(), name='dashboard'),
]