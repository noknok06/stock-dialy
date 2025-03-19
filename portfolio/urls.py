# portfolio/urls.py
from django.urls import path
from . import views

app_name = 'portfolio'

urlpatterns = [
    path('snapshots/', views.SnapshotListView.as_view(), name='list'),
    path('snapshots/<int:pk>/', views.SnapshotDetailView.as_view(), name='detail'),
    path('snapshots/create/', views.CreateSnapshotView.as_view(), name='create_snapshot'),
    path('snapshots/compare/', views.CompareSnapshotsView.as_view(), name='compare'),
    path('snapshots/<int:pk>/delete/', views.SnapshotDeleteView.as_view(), name='delete'),
]