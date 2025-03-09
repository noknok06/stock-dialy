# checklist/urls.py
from django.urls import path
from . import views

app_name = 'checklist'

urlpatterns = [
    path('', views.ChecklistListView.as_view(), name='list'),
    path('create/', views.ChecklistCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ChecklistDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.ChecklistUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.ChecklistDeleteView.as_view(), name='delete'),
    # checklist/urls.py に追加
    path('item/<int:item_id>/toggle/', views.toggle_checklist_item, name='toggle_item'),
]