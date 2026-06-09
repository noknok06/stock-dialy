from django.urls import path

from . import api, views

app_name = 'diary_templates'

urlpatterns = [
    path('', views.DiaryTemplateListView.as_view(), name='list'),
    path('add-sample/', views.add_sample_template, name='add_sample'),
    path('create/', views.DiaryTemplateCreateView.as_view(), name='create'),
    path('<int:pk>/update/', views.DiaryTemplateUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.DiaryTemplateDeleteView.as_view(), name='delete'),

    path('api/list/', api.list_templates, name='api_list'),
    path('api/<int:pk>/', api.get_template, name='api_detail'),
]
