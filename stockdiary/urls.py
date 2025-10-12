# stockdiary/urls.py
from django.urls import path
from . import views
from . import api
from django.contrib.auth.decorators import login_required

app_name = 'stockdiary'

urlpatterns = [
    # 日記CRUD
    path('', views.StockDiaryListView.as_view(), name='home'),
    path('create/', views.StockDiaryCreateView.as_view(), name='create'),
    path('<int:pk>/', views.StockDiaryDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.StockDiaryUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.StockDiaryDeleteView.as_view(), name='delete'),
    
    # 取引管理（新規）
    path('<int:diary_id>/transaction/add/', 
         views.AddTransactionView.as_view(), 
         name='add_transaction'),
    path('transaction/<int:pk>/edit/', 
         views.EditTransactionView.as_view(), 
         name='edit_transaction'),
    path('transaction/<int:pk>/delete/', 
         views.DeleteTransactionView.as_view(), 
         name='delete_transaction'),
    
    # 株式分割（新規）
    path('<int:diary_id>/split/add/',
         views.AddStockSplitView.as_view(),
         name='add_split'),
    path('split/<int:pk>/apply/',
         views.ApplyStockSplitView.as_view(),
         name='apply_split'),
    path('split/<int:pk>/delete/',
         views.DeleteStockSplitView.as_view(),
         name='delete_split'),
    
    # API関連
    path('api/stock/info/<str:stock_code>/', api.get_stock_info, name='api_stock_info'),
    path('api/stock/price/<str:stock_code>/', api.get_stock_price, name='api_stock_price'),
    path('api/create/', api.api_create_diary, name='api_create'),
    path('api/tab-content/<int:diary_id>/<str:tab_type>/', 
         views.DiaryTabContentView.as_view(), 
         name='api_tab_content'),

    # 継続記録関連
    path('<int:pk>/note/', views.AddDiaryNoteView.as_view(), name='add_note'),
    path('<int:diary_pk>/note/<int:pk>/delete/', 
         views.DeleteDiaryNoteView.as_view(), 
         name='delete_note'),

    # その他のエンドポイント
    path('diary-list/', login_required(views.diary_list), name='diary_list'),
    path('tab-content/<int:diary_id>/<str:tab_type>/', 
         login_required(views.tab_content), 
         name='tab_content'),

    # モバイル操作性向上
    path('search-suggestion/', login_required(views.search_suggestion), name='search_suggestion'),
    path('<int:pk>/context-actions/', login_required(views.context_actions), name='context_actions'),
    
    # 画像配信（セキュア）
    path('image/<int:diary_id>/<str:image_type>/', 
         views.ServeImageView.as_view(), 
         name='serve_image'),
    path('image/<int:diary_id>/<str:image_type>/<int:note_id>/', 
         views.ServeImageView.as_view(), 
         name='serve_image'),
    
    # 信用倍率関連API
    path('api/margin-chart-data/<int:diary_id>/', 
         views.api_margin_chart_data, 
         name='api_margin_chart'),
    path('api/margin-compare/<int:diary_id>/', 
         views.api_margin_compare_data, 
         name='api_margin_compare'),
    path('api/margin-sector/<int:diary_id>/', 
         views.api_margin_sector_data, 
         name='api_margin_sector'),
    path('api/margin-sector-suggestions/<int:diary_id>/', 
         views.api_margin_sector_suggestions, 
         name='api_margin_sector_suggestions'),

    # 株式一覧
    path('stocks/', views.StockListView.as_view(), name='stock_list'),
    path('api/stock-diaries/<str:symbol>/', 
         views.api_stock_diaries, 
         name='api_stock_diaries'),
]