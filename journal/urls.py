# journal/urls.py
from django.urls import path
from . import views

app_name = 'journal'

urlpatterns = [
    # ダッシュボード
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # 銘柄管理
    path('stocks/', views.StockListView.as_view(), name='stock_list'),
    path('stocks/create/', views.StockCreateView.as_view(), name='stock_create'),
    path('stocks/<int:pk>/', views.StockDetailView.as_view(), name='stock_detail'),
    path('stocks/<int:pk>/update/', views.StockUpdateView.as_view(), name='stock_update'),
    
    # 投資判断記録管理
    path('entries/', views.JournalEntryListView.as_view(), name='journal_list'),
    path('entries/create/', views.JournalEntryCreateView.as_view(), name='create'),
    path('entries/<int:pk>/', views.JournalEntryDetailView.as_view(), name='journal_detail'),
    path('entries/<int:pk>/update/', views.JournalEntryUpdateView.as_view(), name='update'),
    path('entries/<int:pk>/delete/', views.JournalEntryDeleteView.as_view(), name='delete'),

]